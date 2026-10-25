"""The run06 transition is an exact historical report admission."""

import pytest
from famjet.provenance import canonical_hash
import subprocess
import sys
from pathlib import Path
import json
import hashlib
from types import SimpleNamespace
import shutil
import os
from famjet.provenance import canonical_json


_REPOSITORY = Path(__file__).resolve().parents[1]
_FROZEN = _REPOSITORY / 'docs/research/e2e-run06-execution-record/study-freeze-v1.json'


def _sealed_policy_fixture(root):
    frozen = json.loads(_FROZEN.read_bytes())
    policy = frozen['inputs']['resource_policy']
    policy_raw = canonical_json(policy)
    (root / 'run-policy.json').write_bytes(policy_raw)
    anchor = {'schema_version': 1, 'kind': 'famjet_run_policy_anchor_v2',
              'run_policy_sha256': hashlib.sha256(policy_raw).hexdigest(),
              'execution_source_sha256': policy['execution_source_sha256'],
              'original_start_epoch_seconds': policy['start_epoch_seconds'],
              'global_deadline_epoch_seconds': policy['global_deadline_epoch_seconds'],
              'work_deadline_epoch_seconds': policy['work_deadline_epoch_seconds']}
    (root / 'run-policy-anchor.json').write_bytes(canonical_json(anchor))
    return frozen


def _run06_integration_root():
    if os.environ.get('FAMJET_RUN06_INTEGRATION') != '1':
        pytest.skip('set FAMJET_RUN06_INTEGRATION=1 with the verified local run06 archive')
    root = _REPOSITORY / 'artifacts/e2e-run06-original-archive/run'
    prep = root.parent / 'prep'
    if not (root / 'run-ledger.json').is_file() or not (prep / 'exit-witness.json').is_file():
        pytest.skip('verified complete run06 run/prep archive unavailable')
    return root


def _admitted_fixture(*_args):
    return {'compatibility_id': 'run06-report-safety-v2',
            'execution_sha256': 'b994b3ef7b770fb50db7adba3a9125f75c7c5dc1a4cd3dc3d85843d3177e1260',
            'reporter_sha256': 'fixture-reporter', 'manifest_sha256': 'fixture-manifest',
            'launcher_sha256': 'fixture-launcher', 'archive_index_sha256': 'fixture-index',
            'original_exit_code': 1, 'original_report_status': 'failed'}


def test_report_migration_rejects_scientific_source_or_clock_change():
    from famjet_poc.report_inputs import _validate_report_transition
    old = {'famjet_poc/report_inputs.py': 'a' * 64,
           'famjet_poc/protected.py': 'b' * 64, 'requirements.lock': 'c' * 64}
    new = {**old, 'famjet_poc/report_inputs.py': 'd' * 64}
    manifest = {'old_files': old, 'new_files': new,
                'old_sha256': canonical_hash(old), 'new_sha256': canonical_hash(new),
                'pinned': {'run-policy.json': 'policy', 'run-policy-anchor.json': 'anchor'}}
    _validate_report_transition(manifest, old, new,
                                {'run-policy.json': 'policy', 'run-policy-anchor.json': 'anchor'})
    with pytest.raises(ValueError, match='transition'):
        _validate_report_transition(manifest, old, {**new, 'famjet_poc/protected.py': 'e' * 64},
                                    {'run-policy.json': 'policy', 'run-policy-anchor.json': 'anchor'})
    with pytest.raises(ValueError, match='pinned|clock'):
        _validate_report_transition(manifest, old, new,
                                    {'run-policy.json': 'policy', 'run-policy-anchor.json': 'changed'})


def test_recovery_launcher_exposes_only_fixed_migration(tmp_path):
    launcher = Path(__file__).resolve().parents[1] / 'scripts/report_run06_recovery.py'
    help_result = subprocess.run([sys.executable, str(launcher), '--help'],
                                 capture_output=True, text=True)
    assert help_result.returncode == 0
    assert '--compatibility-id' in help_result.stdout
    run = tmp_path / 'run'
    run.mkdir()
    rejected = subprocess.run([sys.executable, str(launcher), '--run', str(run),
                               '--out', str(tmp_path / 'out' / 'report.md'),
                               '--archived-source', str(tmp_path),
                               '--compatibility-id', 'unregistered'],
                              capture_output=True, text=True)
    assert rejected.returncode != 0
    assert 'unregistered' in rejected.stderr
    assert not (tmp_path / 'out').exists()


def test_report_safety_v2_launcher_has_its_own_fixed_id():
    launcher = _REPOSITORY / 'scripts/report_run06_recovery_v2.py'
    result = subprocess.run([sys.executable, str(launcher), '--help'],
                            capture_output=True, text=True)
    assert result.returncode == 0
    assert 'run06-report-safety-v2' in result.stdout
    assert 'run06-report-order-v1' not in result.stdout


def test_historical_policy_rejects_consistently_rewritten_clock(tmp_path):
    from famjet_poc.report_inputs import _verify_historical_run_policy
    repository = Path(__file__).resolve().parents[1]
    original = Path('artifacts/e2e-core-run-06')
    run = tmp_path / 'copy'
    run.mkdir()
    freeze = _sealed_policy_fixture(run)
    paths = SimpleNamespace(root=run, original_root=original)
    assert _verify_historical_run_policy(paths, freeze['inputs']) == freeze['inputs']['resource_policy']
    policy = json.loads((run / 'run-policy.json').read_bytes())
    policy['start_epoch_seconds'] += 1
    policy['global_deadline_epoch_seconds'] += 1
    policy['work_deadline_epoch_seconds'] += 1
    (run / 'run-policy.json').write_text(json.dumps(policy))
    anchor = json.loads((run / 'run-policy-anchor.json').read_bytes())
    anchor['original_start_epoch_seconds'] += 1
    anchor['global_deadline_epoch_seconds'] += 1
    anchor['work_deadline_epoch_seconds'] += 1
    anchor['run_policy_sha256'] = hashlib.sha256((run / 'run-policy.json').read_bytes()).hexdigest()
    (run / 'run-policy-anchor.json').write_text(json.dumps(anchor))
    with pytest.raises(ValueError, match='hash|policy|clock'):
        _verify_historical_run_policy(paths, freeze['inputs'])


def test_old_execution_apis_remain_strict(tmp_path):
    from famjet_poc.protected import FrozenStudyRef
    from famjet_poc.execution_policy import bind_run_policy
    repository = Path(__file__).resolve().parents[1]
    run = tmp_path / 'run'
    (run / 'freeze').mkdir(parents=True)
    raw = _FROZEN.read_bytes()
    (run / 'freeze/study-freeze-v1.json').write_bytes(raw)
    freeze = _sealed_policy_fixture(run)
    reference = FrozenStudyRef(run / 'freeze/study-freeze-v1.json',
                               hashlib.sha256((run / 'freeze/study-freeze-v1.json').read_bytes()).hexdigest(),
                               freeze['source_sha256'], freeze['executable']['sha256'])
    with pytest.raises(ValueError, match='executable'):
        reference.read()
    with pytest.raises(ValueError, match='policy|source|deadline'):
        bind_run_policy(run / 'run-policy.json')


def test_repeated_recovery_destination_preserves_first_publication(tmp_path):
    from scripts.report_run06_recovery import _destination
    requested = tmp_path / 'published' / 'final.md'
    assert _destination(requested) == requested
    requested.parent.mkdir()
    (requested.parent / 'recovery-receipt.json').write_text('{}')
    second = _destination(requested)
    assert second == tmp_path / 'published-replay-002' / 'final.md'
    assert requested.parent.exists()


def test_registered_admission_binds_copied_run_and_all_source_bytes(tmp_path):
    from famjet_poc.report_inputs import _admit_report_migration
    repository = Path(__file__).resolve().parents[1]
    archive = repository / 'docs/research/e2e-run06-execution-source'
    copied = tmp_path / 'source'
    shutil.copytree(archive, copied)
    run = _run06_integration_root()
    admitted = _admit_report_migration(run, 'run06-report-safety-v2', copied)
    assert admitted['original_exit_code'] == 1
    assert admitted['execution_sha256'] == 'b994b3ef7b770fb50db7adba3a9125f75c7c5dc1a4cd3dc3d85843d3177e1260'
    protected = copied / 'famjet_poc/protected.py'
    protected.write_bytes(protected.read_bytes() + b'\n# altered\n')
    with pytest.raises(ValueError, match='inventory|transition|identity'):
        _admit_report_migration(run, 'run06-report-safety-v2', copied)


@pytest.mark.parametrize('damage', ['requirements.lock', 'extra', 'missing'])
def test_archived_execution_inventory_mutations_rejected(tmp_path, damage):
    from famjet_poc.report_inputs import _admit_report_migration
    repository = Path(__file__).resolve().parents[1]
    copied = tmp_path / 'source'
    shutil.copytree(repository / 'docs/research/e2e-run06-execution-source', copied)
    if damage == 'requirements.lock':
        target = copied / 'requirements.lock'
        target.write_bytes(target.read_bytes() + b'\n# altered\n')
    elif damage == 'extra':
        (copied / 'extra.py').write_text('pass')
    else:
        (copied / 'famjet_poc/protected.py').unlink()
    run = tmp_path / 'run'
    run.mkdir()
    with pytest.raises((ValueError, FileNotFoundError)):
        _admit_report_migration(run, 'run06-report-safety-v2', copied)


@pytest.mark.parametrize('damage', ['freeze', 'release', 'run', 'extra', 'missing'])
def test_sealed_input_inventory_mutations_rejected_before_scoring(tmp_path, damage):
    from famjet_poc.report_inputs import _inventory
    root = tmp_path / 'run'
    root.mkdir()
    names = {'freeze/study-freeze-v1.json': b'frozen',
             'release/release.json': b'synthetic',
             'run-ledger.json': b'ledger'}
    for name, raw in names.items():
        path = root / name
        path.parent.mkdir(exist_ok=True)
        path.write_bytes(raw)
    expected = {name: {'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw)}
                for name, raw in names.items()}
    assert _inventory(root, expected) == expected
    if damage == 'freeze':
        (root / 'freeze/study-freeze-v1.json').write_bytes(b'changed')
    elif damage == 'release':
        (root / 'release/release.json').write_bytes(b'changed')
    elif damage == 'run':
        (root / 'run-ledger.json').write_bytes(b'changed')
    elif damage == 'extra':
        (root / 'release/extra.json').write_bytes(b'added')
    else:
        (root / 'release/release.json').unlink()
    with pytest.raises(ValueError, match='inventory|extra'):
        _inventory(root, expected)


def test_copied_admission_avoids_original_run_and_protected_work(monkeypatch):
    from famjet_poc.report_inputs import _admit_report_migration
    from famjet_poc import protected, pipeline
    repository = Path(__file__).resolve().parents[1]
    original = (repository / 'artifacts/e2e-core-run-06').resolve()
    copied = _run06_integration_root()
    source = repository / 'docs/research/e2e-run06-execution-source'
    real_open = Path.open
    def guarded_open(path, *args, **kwargs):
        if path.resolve().is_relative_to(original):
            raise AssertionError('original run location was opened')
        return real_open(path, *args, **kwargs)
    def forbidden(*args, **kwargs):
        raise AssertionError('protected scientific work was invoked')
    monkeypatch.setattr(Path, 'open', guarded_open)
    monkeypatch.setattr(protected, 'freeze_study', forbidden)
    monkeypatch.setattr(protected, 'seal_release', forbidden)
    monkeypatch.setattr(pipeline, 'run', forbidden)
    accepted = _admit_report_migration(copied, 'run06-report-safety-v2', source)
    assert accepted['original_exit_code'] == 1


def test_failed_recovery_keeps_attempt_and_does_not_publish(tmp_path):
    launcher = Path(__file__).resolve().parents[1] / 'scripts/report_run06_recovery.py'
    run = tmp_path / 'empty-run'
    run.mkdir()
    out = tmp_path / 'publication' / 'final.md'
    archive = Path(__file__).resolve().parents[1] / 'docs/research/e2e-run06-execution-source'
    result = subprocess.run([sys.executable, str(launcher), '--run', str(run),
                             '--out', str(out), '--archived-source', str(archive),
                             '--compatibility-id', 'run06-report-order-v1'],
                            capture_output=True, text=True)
    assert result.returncode != 0
    assert not out.parent.exists()
    attempts = list(tmp_path.glob('publication-attempt-*'))
    assert len(attempts) == 1
    receipt = json.loads((attempts[0] / 'recovery-receipt.json').read_bytes())
    assert receipt['status'] == 'failed'
    assert receipt['reporter_git_revision']
    assert receipt['elapsed_seconds'] >= 0


@pytest.mark.parametrize('layout', [('run', 'prep'), ('e2e-core-run-06', 'e2e-core-run-06-prep')])
@pytest.mark.parametrize('input_name', ['run', 'prep', 'source'])
def test_output_guard_protects_every_input_before_writing(tmp_path, layout, input_name):
    from scripts.report_run06_recovery import main
    run = tmp_path / layout[0]
    prep = tmp_path / layout[1]
    source = tmp_path / 'source'
    for directory in (run, prep, source):
        directory.mkdir()
        (directory / 'sentinel').write_bytes(directory.name.encode())
    selected = {'run': run, 'prep': prep, 'source': source}[input_name]
    before = {str(p): p.read_bytes() for directory in (run, prep, source)
              for p in directory.rglob('*') if p.is_file()}
    with pytest.raises(ValueError, match='outside sealed inputs'):
        main(['--run', str(run), '--out', str(selected / 'recovery' / 'final.md'),
              '--archived-source', str(source), '--compatibility-id', 'run06-report-order-v1'])
    after = {str(p): p.read_bytes() for directory in (run, prep, source)
             for p in directory.rglob('*') if p.is_file()}
    assert after == before
    assert not (selected / 'recovery').exists()


def test_coordinated_launcher_and_manifest_rewrite_rejected(tmp_path):
    from famjet_poc.report_inputs import _verify_launcher_authorization
    repository = Path(__file__).resolve().parents[1]
    launcher = repository / 'scripts/report_run06_recovery.py'
    manifest = json.loads((repository / 'docs/research/e2e-run06-report-migration.json').read_bytes())
    copied = tmp_path / 'launcher.py'
    copied.write_bytes(launcher.read_bytes())
    _verify_launcher_authorization(manifest, copied)
    copied.write_bytes(copied.read_bytes() + b'\n# changed launcher\n')
    manifest['launcher_sha256'] = hashlib.sha256(copied.read_bytes()).hexdigest()
    with pytest.raises(ValueError, match='launcher|authorization'):
        _verify_launcher_authorization(manifest, copied)


def test_coordinated_reporting_lock_and_manifest_rewrite_rejected(tmp_path):
    from famjet_poc.report_inputs import _verify_reporting_lock
    repository = Path(__file__).resolve().parents[1]
    manifest = json.loads((repository / 'docs/research/e2e-run06-report-migration.json').read_bytes())
    copied = tmp_path / 'reporting.lock'
    copied.write_bytes((repository / 'docs/reporting-requirements.lock').read_bytes())
    _verify_reporting_lock(manifest, copied)
    copied.write_bytes(copied.read_bytes() + b'\n# altered reporting lock\n')
    manifest['report_lock_sha256'] = hashlib.sha256(copied.read_bytes()).hexdigest()
    with pytest.raises(ValueError, match='reporting lock|authorization'):
        _verify_reporting_lock(manifest, copied)


def test_report_transition_rejects_full_source_mutation_matrix():
    from famjet_poc.report_inputs import _validate_report_transition
    old = {'famjet_poc/report_inputs.py': 'a' * 64,
           'famjet_poc/protected.py': 'b' * 64,
           'requirements.lock': 'c' * 64}
    new = {**old, 'famjet_poc/report_inputs.py': 'd' * 64}
    manifest = {'old_files': old, 'new_files': new,
                'old_sha256': canonical_hash(old), 'new_sha256': canonical_hash(new),
                'pinned': {'freeze': 'f', 'release': 'r', 'run': 'i'}}
    altered = [
        {**new, 'famjet_poc/protected.py': 'x' * 64},
        {**new, 'requirements.lock': 'x' * 64},
        {**new, 'famjet_poc/report_inputs.py': 'x' * 64},
        {**new, 'extra.py': 'x' * 64},
        {k: v for k, v in new.items() if k != 'requirements.lock'},
    ]
    for source in altered:
        with pytest.raises(ValueError, match='transition'):
            _validate_report_transition(manifest, old, source, manifest['pinned'])
    for key in ('freeze', 'release', 'run'):
        with pytest.raises(ValueError, match='pinned'):
            _validate_report_transition(manifest, old, new,
                                        {**manifest['pinned'], key: 'altered'})
    changed_target = {**manifest, 'new_files': {**new, 'famjet_poc/protected.py': 'x' * 64}}
    with pytest.raises(ValueError, match='transition'):
        _validate_report_transition(changed_target, old, new, manifest['pinned'])


def test_report_safety_v2_requires_exact_prior_and_two_report_paths():
    from famjet_poc.report_inputs import _validate_report_safety_transition
    old = {'famjet_poc/report_inputs.py': 'a' * 64,
           'famjet_poc/report.py': 'b' * 64,
           'famjet_poc/protected.py': 'c' * 64,
           'requirements.lock': 'd' * 64}
    prior = {**old, 'famjet_poc/report_inputs.py': 'e' * 64}
    current = {**prior, 'famjet_poc/report_inputs.py': 'f' * 64,
               'famjet_poc/report.py': 'g' * 64}
    manifest = {'old_files': old, 'prior_files': prior, 'new_files': current,
                'old_sha256': canonical_hash(old), 'prior_sha256': canonical_hash(prior),
                'new_sha256': canonical_hash(current)}
    _validate_report_safety_transition(manifest, old, prior, current)
    for altered in ({**current, 'famjet_poc/protected.py': 'x' * 64},
                    {**current, 'requirements.lock': 'x' * 64},
                    {**current, 'famjet_poc/report.py': 'x' * 64},
                    {**current, 'extra.py': 'x' * 64}):
        with pytest.raises(ValueError, match='transition'):
            _validate_report_safety_transition(manifest, old, prior, altered)
    with pytest.raises(ValueError, match='transition'):
        _validate_report_safety_transition(manifest, old,
            {**prior, 'famjet_poc/protected.py': 'x' * 64}, current)


def test_report_safety_v2_committed_chain_matches_current_source():
    from famjet_poc.protected import executable_identity
    from famjet_poc.report_inputs import _validate_report_safety_transition
    v1 = json.loads((_REPOSITORY / 'docs/research/e2e-run06-report-migration.json').read_bytes())
    v2 = json.loads((_REPOSITORY / 'docs/research/e2e-run06-report-safety-migration.json').read_bytes())
    current = executable_identity()
    assert hashlib.sha256((_REPOSITORY / 'docs/research/e2e-run06-report-migration.json').read_bytes()).hexdigest() == '881cf66a7a5b099e5620ab4e4d17699b1c1c005052e67dabb649ec1642b00e27'
    assert hashlib.sha256((_REPOSITORY / 'scripts/report_run06_recovery.py').read_bytes()).hexdigest() == '9bcb1724fd16793314f5fcd5f8faef87d78fccfc70343705540ff92f206eb83e'
    assert hashlib.sha256((_REPOSITORY / 'scripts/report_run06_recovery_v2.py').read_bytes()).hexdigest() == v2['launcher_sha256']
    assert v2['prior_manifest_sha256'] == hashlib.sha256((_REPOSITORY / 'docs/research/e2e-run06-report-migration.json').read_bytes()).hexdigest()
    assert v2['prior_files'] == v1['new_files']
    assert v2['new_files'] == current['files']
    assert v2['new_sha256'] == current['sha256']
    _validate_report_safety_transition(v2, v1['old_files'], v1['new_files'], current['files'])


@pytest.mark.parametrize('change', [
    {'schema_version': 2}, {'schema_version': 1.0},
    {'start_epoch_seconds': True}, {'global_deadline_epoch_seconds': 0},
    {'work_deadline_epoch_seconds': 0}, {'execution_source_sha256': '0' * 64},
    {'execution_policy_sha256': '0' * 64},
])
def test_historical_policy_field_mutations_rejected(tmp_path, change):
    from famjet_poc.report_inputs import _verify_historical_run_policy
    repository = Path(__file__).resolve().parents[1]
    original = Path('artifacts/e2e-core-run-06')
    root = tmp_path / 'run'
    root.mkdir()
    inputs = _sealed_policy_fixture(root)['inputs']
    policy_path = root / 'run-policy.json'
    body = json.loads(policy_path.read_bytes())
    body.update(change)
    policy_path.write_text(json.dumps(body))
    with pytest.raises(ValueError, match='hash|policy|clock'):
        _verify_historical_run_policy(SimpleNamespace(root=root, original_root=original), inputs)


def test_failed_post_admission_receipt_keeps_provenance_and_partial_hashes(tmp_path, monkeypatch):
    from scripts import report_run06_recovery as launcher
    repository = Path(__file__).resolve().parents[1]
    run = tmp_path / 'run'
    run.mkdir()
    source = repository / 'docs/research/e2e-run06-execution-source'
    monkeypatch.setattr(launcher, '_admit_report_migration', _admitted_fixture)
    def fail_after_admission(run, out, archive):
        out.with_name('partial-chart-data.json').write_bytes(b'partial-scientific-output')
        raise RuntimeError('controlled downstream failure')
    monkeypatch.setattr(launcher, '_render', fail_after_admission)
    out = tmp_path / 'publication/final.md'
    with pytest.raises(RuntimeError, match='controlled downstream'):
        launcher.main(['--run', str(run), '--out', str(out), '--archived-source', str(source),
                       '--compatibility-id', 'run06-report-order-v1'])
    receipt = json.loads((tmp_path / 'publication-attempt-001/recovery-receipt.json').read_bytes())
    assert receipt['status'] == 'failed'
    assert receipt['admission_state'] == 'verified'
    assert receipt['execution_sha256'] == 'b994b3ef7b770fb50db7adba3a9125f75c7c5dc1a4cd3dc3d85843d3177e1260'
    assert receipt['reporter_sha256']
    assert receipt['manifest_sha256']
    assert receipt['launcher_sha256']
    assert receipt['original_exit_code'] == 1
    assert receipt['output_files']['partial-chart-data.json']['sha256'] == hashlib.sha256(b'partial-scientific-output').hexdigest()


def test_publication_failure_does_not_claim_completion(tmp_path, monkeypatch):
    from scripts import report_run06_recovery as launcher
    repository = Path(__file__).resolve().parents[1]
    run = tmp_path / 'run'
    run.mkdir()
    source = repository / 'docs/research/e2e-run06-execution-source'
    monkeypatch.setattr(launcher, '_admit_report_migration', _admitted_fixture)
    def render_fixture(run, out, archive):
        out.write_bytes(b'report')
        return {'execution_sha256': 'old', 'reporter_sha256': 'new'}
    monkeypatch.setattr(launcher, '_render', render_fixture)
    monkeypatch.setattr(launcher, '_publish', lambda *_: (_ for _ in ()).throw(OSError('publication failed')))
    out = tmp_path / 'publication/final.md'
    with pytest.raises(OSError, match='publication failed'):
        launcher.main(['--run', str(run), '--out', str(out), '--archived-source', str(source),
                       '--compatibility-id', 'run06-report-order-v1'])
    receipt = json.loads((tmp_path / 'publication-attempt-001/recovery-receipt.json').read_bytes())
    assert receipt['status'] == 'failed'
    assert receipt['admission_state'] == 'verified'
    assert receipt['output_files']['final.md']['sha256'] == hashlib.sha256(b'report').hexdigest()
    assert not out.parent.exists()


def test_volatile_plot_invocation_is_only_in_receipt_and_outputs_replay(tmp_path, monkeypatch):
    from scripts import report_run06_recovery as launcher
    repository = Path(__file__).resolve().parents[1]
    run = tmp_path / 'run'
    run.mkdir()
    source = repository / 'docs/research/e2e-run06-execution-source'
    monkeypatch.setattr(launcher, '_admit_report_migration', _admitted_fixture)
    counter = [0]
    def render_fixture(run, out, archive):
        counter[0] += 1
        out.write_bytes(b'fixed report')
        out.with_suffix('.json').write_bytes(b'{"scientific":"fixed"}')
        out.with_name(out.stem + '-chart-data.json').write_bytes(b'{"chart":"fixed"}')
        plots = out.with_name(out.stem + '-charts')
        plots.mkdir()
        (plots / 'figure.svg').write_bytes(b'<svg>fixed</svg>')
        (plots / 'plot-invocation.json').write_text(json.dumps({'argv': [str(out)], 'elapsed_seconds': counter[0]}))
        (plots / 'plot-invocation.log').write_bytes(f'volatile-{counter[0]}'.encode())
        return {'execution_sha256': 'old', 'reporter_sha256': 'new'}
    monkeypatch.setattr(launcher, '_render', render_fixture)
    out = tmp_path / 'publication/final.md'
    for _ in range(2):
        launcher.main(['--run', str(run), '--out', str(out), '--archived-source', str(source),
                       '--compatibility-id', 'run06-report-order-v1'])
    first, second = out.parent, tmp_path / 'publication-replay-002'
    first_receipt = json.loads((first / 'recovery-receipt.json').read_bytes())
    second_receipt = json.loads((second / 'recovery-receipt.json').read_bytes())
    assert first_receipt['output_files'] == second_receipt['output_files']
    assert first_receipt['plot_invocations'] != second_receipt['plot_invocations']
    assert not list(first.rglob('plot-invocation.*'))
    assert not list(second.rglob('plot-invocation.*'))
    assert set(first_receipt['output_files']) == {
        'final.md', 'final.json', 'final-chart-data.json', 'final-charts/figure.svg'}


def test_partial_plot_log_is_captured_in_receipt(tmp_path):
    from scripts.report_run06_recovery import _capture_plot_invocations
    plots = tmp_path / 'final-charts'
    plots.mkdir()
    (plots / 'plot-invocation.log').write_bytes(b'partial renderer output')
    captured = _capture_plot_invocations(tmp_path)
    assert captured[0]['stdout_stderr_sha256'] == hashlib.sha256(b'partial renderer output').hexdigest()
    assert not (plots / 'plot-invocation.log').exists()


def test_report_composition_preserves_static_recovery_provenance(tmp_path, monkeypatch):
    from scripts import report_run06_recovery as launcher
    provenance = {'execution_sha256': 'old-sha', 'reporter_sha256': 'new-sha',
                  'manifest_sha256': 'manifest-sha', 'launcher_sha256': 'launcher-sha',
                  'original_exit_code': 1, 'original_report_status': 'failed',
                  'original_report_error': 'protected run ID inventory differs from freeze'}
    inputs = {'status': 'scientific_artifacts_validated', 'report_recovery': provenance}
    monkeypatch.setattr(launcher, 'load_report_inputs', lambda *args, **kwargs: inputs)
    monkeypatch.setattr(launcher.report, '_science_chart_data', lambda *_: {'science': 'fixed'})
    monkeypatch.setattr(launcher.report, '_render_plots', lambda *_: {'chart_data_sha256': 'fixed'})
    monkeypatch.setattr(launcher.report, '_science_machine', lambda *_: {'decision': 'inconclusive'})
    monkeypatch.setattr(launcher.report, '_science_markdown', lambda *_: '# Prescribed science')
    out = tmp_path / 'final.md'
    returned = launcher._render(tmp_path, out, tmp_path)
    machine = json.loads(out.with_suffix('.json').read_bytes())
    markdown = out.read_text()
    assert returned is provenance
    assert machine['report_recovery']['execution_sha256'] == 'old-sha'
    assert machine['report_recovery']['reporter_sha256'] == 'new-sha'
    assert machine['report_recovery']['original_exit_code'] == 1
    for value in ('old-sha', 'new-sha', 'manifest-sha', 'launcher-sha',
                  'initial report failed', 'protected run ID inventory differs from freeze'):
        assert value in markdown
