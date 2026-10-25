"""Artifact closure, portable references, and fail-closed report admission."""

import hashlib
import json
from pathlib import Path
import shutil

import pytest

from famjet_poc.contracts import PopulationSpec, ShapeSpec
from famjet_poc.pipeline import StageLedger
from famjet_poc.protected import freeze_study, seal_release


def _tiny_run(root):
    root.mkdir()
    ledger = StageLedger(root)
    spec = PopulationSpec('poc_numeric_v1', ShapeSpec(16, 8), 'unit_test', 17,
                          (128,), ('piecewise_stationary',), 8, 64)
    inputs = {'profile': 'unit_test', 'model_pair_sha256': 'a' * 64,
              'populations': [{'phase': 'unit_test', 'split': 'pilot',
                               'spec': spec.to_json(), 'episode_ids': ['tiny-0', 'tiny-1']}],
              'unit_test_admission': {'schema_version': 1,
                       'kind': 'famjet_e4_unit_test_admission', 'status': 'accepted'},
              'calibration': None}
    frozen = None
    def freeze_action(directory):
        nonlocal frozen
        frozen = freeze_study(inputs, directory)
        return {'path': str(frozen.path), 'sha256': frozen.sha256}
    ledger.stage('freeze', {'test_only': True}, freeze_action)
    def release_action(directory):
        receipts = []
        for method, loss in (('jet', 1.), ('bank', 2.)):
            rows = [{'history_id': hid, 'query_id': qid, 'method': method,
                     'task': 'mean' if qid % 2 == 0 else 'contrast',
                     'loss': loss, 'score_scope': 'primary'}
                    for hid in ('tiny-0', 'tiny-1') for qid in range(8)]
            path = directory / (method + '.json')
            path.write_text(json.dumps(rows))
            receipts.append({'run_id': method, 'phase': 'unit_test',
                   'method': method, 'history_ids': ['tiny-0', 'tiny-1'],
                   'rows_path': str(path),
                   'rows_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                   'status': 'completed', 'freeze_sha256': frozen.sha256})
        ref = seal_release(frozen, receipts, directory, expected_methods=('jet', 'bank'))
        return {'release_path': str(ref.path), 'release_sha256': ref.sha256}
    ledger.stage('release', {'freeze_sha256': frozen.sha256}, release_action)
    return root


def test_tiny_release_admits_only_non_scientific_smoke(tmp_path):
    from famjet_poc.report_inputs import load_report_inputs
    run = _tiny_run(tmp_path / 'run')
    inputs = load_report_inputs(run)
    assert inputs['status'] == 'non_scientific_smoke'
    assert inputs['synthetic']['methods'] == ['jet', 'bank']
    assert inputs['synthetic']['query_rows'] == 32


def test_missing_pair_and_row_tamper_refuse_report(tmp_path):
    from famjet_poc.report_inputs import load_report_inputs
    run = _tiny_run(tmp_path / 'run')
    body = json.loads((run / 'release' / 'release.json').read_text())
    body['receipts'].pop()
    (run / 'release' / 'release.json').write_text(json.dumps(body))
    with pytest.raises(ValueError, match='hash|pair|method|release'):
        load_report_inputs(run)
    run2 = _tiny_run(tmp_path / 'run2')
    (run2 / 'release' / 'bank.json').write_text('[]')
    with pytest.raises(ValueError, match='hash|row'):
        load_report_inputs(run2)


def test_copied_run_replays_with_original_removed_and_rejects_escape(tmp_path):
    from famjet_poc.report_inputs import load_report_inputs
    run = _tiny_run(tmp_path / 'run')
    copy = tmp_path / 'archive' / 'run'
    shutil.copytree(run, copy)
    shutil.rmtree(run)
    assert load_report_inputs(copy)['synthetic']['query_rows'] == 32
    body = json.loads((copy / 'release' / 'release.json').read_text())
    # Retain the original release bytes, but replace a referenced local file with a symlink.
    (copy / 'release' / 'jet.json').unlink()
    (copy / 'release' / 'jet.json').symlink_to(tmp_path / 'outside.json')
    (tmp_path / 'outside.json').write_text('[]')
    with pytest.raises(ValueError, match='outside|symlink|escape'):
        load_report_inputs(copy)


def test_report_stage_may_finish_after_render_without_changing_inputs(tmp_path):
    from famjet_poc.report_inputs import load_report_inputs
    run = _tiny_run(tmp_path / 'run')
    before = load_report_inputs(run)
    ledger = StageLedger(run)
    def report_action(directory):
        (directory / 'final.md').write_text('test output')
        return {'status': 'complete'}
    ledger.stage('report', {'release': before['release_sha256']}, report_action)
    after = load_report_inputs(run)
    assert before == after


def test_scientific_profile_requires_all_entered_stages_and_real_pairs():
    from famjet_poc.report_inputs import require_scientific_stages
    with pytest.raises(ValueError, match='missing.*real|stage'):
        require_scientific_stages({'freeze': {}, 'release': {}},
                                  {'populations': [], 'expected_methods': ['jet', 'bank']})


def test_relative_runroot_artifacts_replay_after_copy(tmp_path, monkeypatch):
    from famjet_poc.report_inputs import load_report_inputs
    monkeypatch.chdir(tmp_path)
    _tiny_run(Path('relative-run'))
    copy = tmp_path / 'archive' / 'run'
    shutil.copytree(tmp_path / 'relative-run', copy)
    shutil.rmtree(tmp_path / 'relative-run')
    assert load_report_inputs(copy)['synthetic']['query_rows'] == 32


def test_external_beijing_arrays_are_inventory_verified_not_rehashed():
    from famjet_poc.report_inputs import verify_beijing_inventory
    splits = ('training', 'development_fit', 'development_calibration', 'test')
    frozen = {name: [{'history_id': name + ':0', 'sha256': 'a' * 64}] for name in splits}
    manifest = {'splits': {name: {'blocks': frozen[name]} for name in splits}}
    assert verify_beijing_inventory(frozen, manifest) == 'verified_inventory_not_rehashed'
    manifest['splits']['test']['blocks'] = [{'history_id': 'test:0', 'sha256': 'b' * 64}]
    with pytest.raises(ValueError, match='inventory'):
        verify_beijing_inventory(frozen, manifest)


def test_copied_scientific_policy_and_gate_refs_resolve_after_original_removed(tmp_path):
    from famjet.provenance import canonical_json
    from famjet_poc.execution_policy import (new_run_policy, bind_run_policy,
                                              verify_public_selection,
                                              verify_public_gate_ref)
    from famjet_poc.report_inputs import ArtifactPaths
    repository = Path(__file__).resolve().parents[1]
    baseline = json.loads((repository / 'docs/research/e2e-evaluation-v2-selection-baseline.json').read_bytes())
    modes_public = json.loads((repository / 'artifacts/e2e-core-run-04/transfer_fit/modes/transfer-modes.json').read_bytes())
    original = tmp_path / 'original'
    (original / 'freeze').mkdir(parents=True)
    (original / 'freeze/study-freeze-v1.json').write_text('{}')
    refs = {}
    for role, item in baseline['roles'].items():
        source = repository / item['archived_model_ref']['path']
        directory = original / 'public-models' / role
        directory.mkdir(parents=True)
        for suffix in ('.json', '.npz'):
            shutil.copy2(source.with_suffix(suffix), directory / source.with_suffix(suffix).name)
        refs[role] = {'path': str(directory / source.name),
                      'sha256': item['archived_model_ref']['sha256']}
    selected16 = {'jet': refs['k16_jet'], 'bank': refs['k16_bank']}
    selected12 = {'jet': refs['k12_jet'], 'bank': refs['k12_bank']}
    modes = {'task_adapted': {'jet': refs['real_jet'], 'bank': refs['real_bank']},
             'normalization': modes_public['normalization']}
    gate = verify_public_selection(selected16, selected12, modes)
    gate_path = original / 'public_selection_gate/gate.json'
    gate_path.parent.mkdir()
    gate_path.write_bytes(canonical_json({**gate, 'verification_seconds': .01}))
    gate_ref = {'path': str(gate_path),
                'sha256': hashlib.sha256(gate_path.read_bytes()).hexdigest()}
    policy_path = original / 'run-policy.json'
    policy = new_run_policy('a' * 64, start_epoch_seconds=1000)
    policy_path.write_bytes(canonical_json(policy))
    bind_run_policy(policy_path, create=True)
    copy = tmp_path / 'copy'
    shutil.copytree(original, copy)
    shutil.rmtree(original)
    paths = ArtifactPaths(copy, original / 'freeze/study-freeze-v1.json')
    assert verify_public_gate_ref(gate_ref, selected16, selected12, modes,
                                  resolve=paths.resolve)['status'] == 'matched'
    assert bind_run_policy(copy / 'run-policy.json') == policy
