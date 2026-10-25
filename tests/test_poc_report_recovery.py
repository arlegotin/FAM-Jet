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


def test_historical_policy_rejects_consistently_rewritten_clock(tmp_path):
    from famjet_poc.report_inputs import _verify_historical_run_policy
    repository = Path(__file__).resolve().parents[1]
    archive = repository / 'docs/research/e2e-run06-execution-record'
    original = Path('artifacts/e2e-core-run-06')
    run = tmp_path / 'copy'
    run.mkdir()
    for name in ('run-policy.json', 'run-policy-anchor.json'):
        (run / name).write_bytes((repository / original / name).read_bytes())
    freeze = json.loads((archive / 'study-freeze-v1.json').read_bytes())
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


def test_old_execution_apis_remain_strict():
    from famjet_poc.protected import FrozenStudyRef
    from famjet_poc.execution_policy import bind_run_policy
    repository = Path(__file__).resolve().parents[1]
    run = repository / 'artifacts/e2e-core-run-06'
    freeze = json.loads((run / 'freeze/study-freeze-v1.json').read_bytes())
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
    run = repository / 'artifacts/e2e-run06-original-archive/run'
    admitted = _admit_report_migration(run, 'run06-report-order-v1', copied)
    assert admitted['original_exit_code'] == 1
    assert admitted['execution_sha256'] == 'b994b3ef7b770fb50db7adba3a9125f75c7c5dc1a4cd3dc3d85843d3177e1260'
    protected = copied / 'famjet_poc/protected.py'
    protected.write_bytes(protected.read_bytes() + b'\n# altered\n')
    with pytest.raises(ValueError, match='inventory|transition|identity'):
        _admit_report_migration(run, 'run06-report-order-v1', copied)


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
