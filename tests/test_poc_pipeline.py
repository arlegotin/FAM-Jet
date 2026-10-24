import json

import pytest

from famjet_poc.pipeline import (StageLedger, admit_resources, stress_inventory,
                                 diagnostic_policy, secondary_ledger, timing_accuracy_admission,
                                 k16_probe_allocation)


def test_resume_skips_only_verified_completed_stage(tmp_path):
    ledger = StageLedger(tmp_path / 'run')
    calls = []
    def action(out):
        calls.append(1)
        (out / 'result.json').write_text(json.dumps({'answer': 7}))
        return {'answer': 7}
    first = ledger.stage('public', {'seed': 1}, action)
    second = StageLedger(tmp_path / 'run').stage('public', {'seed': 1}, action, resume=True)
    assert first == second == {'answer': 7}
    assert calls == [1]
    (tmp_path / 'run' / 'public' / 'result.json').write_text('changed')
    with pytest.raises(ValueError, match='hash'):
        StageLedger(tmp_path / 'run').stage('public', {'seed': 1}, action, resume=True)


def test_failed_stage_retains_failed_attempt_and_never_restarts_same_allocation(tmp_path):
    ledger = StageLedger(tmp_path / 'run')
    def fail(out):
        (out / 'partial.txt').write_text('partial')
        raise RuntimeError('boom')
    with pytest.raises(RuntimeError, match='boom'):
        ledger.stage('protected', {'seed': 1}, fail)
    with pytest.raises(ValueError, match='failed'):
        StageLedger(tmp_path / 'run').stage('protected', {'seed': 1}, fail, resume=True)
    assert (tmp_path / 'run' / 'protected' / 'partial.txt').read_text() == 'partial'


def test_public_stage_resume_keeps_failed_bytes_and_original_input(tmp_path):
    ledger = StageLedger(tmp_path / 'run')
    calls = []
    def action(out):
        calls.append(1)
        if len(calls) == 1:
            (out / 'partial.txt').write_text('kept')
            raise RuntimeError('public interruption')
        assert (out / 'partial.txt').read_text() == 'kept'
        (out / 'done.txt').write_text('done')
        return {'status': 'done'}
    with pytest.raises(RuntimeError):
        ledger.stage('public', {'seed': 1}, action, retryable=True)
    assert StageLedger(tmp_path / 'run').stage('public', {'seed': 1}, action,
                                               resume=True, retryable=True) == {'status': 'done'}
    assert calls == [1, 1]


def test_stage_ledger_rejects_edited_generation(tmp_path):
    ledger = StageLedger(tmp_path / 'run')
    def action(out):
        (out / 'done.txt').write_text('done')
        return {'status': 'done'}
    ledger.stage('public', {'seed': 1}, action)
    path = tmp_path / 'run' / 'run-ledger.json'
    payload = json.loads(path.read_text())
    payload['generations'][0]['input_sha256'] = '0' * 64
    path.write_text(json.dumps(payload))
    with pytest.raises(ValueError, match='ledger'):
        StageLedger(tmp_path / 'run').stage('public', {'seed': 1}, action, resume=True)


def test_admission_requires_ram_disk_and_continuous_deadline():
    receipt = admit_resources({'free_ram_bytes': 8 * 2**30, 'free_disk_bytes': 9 * 2**30,
                               'tree_rss_bytes': 100, 'now_epoch_seconds': 10.},
                              {'max_incremental_rss_bytes': 1 * 2**30,
                               'max_output_bytes': 1 * 2**30, 'deadline_epoch_seconds': 20.})
    assert receipt['status'] == 'admitted'
    with pytest.raises(RuntimeError, match='deadline'):
        admit_resources({**receipt['observed'], 'now_epoch_seconds': 21.},
                        {'max_incremental_rss_bytes': 1 * 2**30,
                         'max_output_bytes': 1 * 2**30, 'deadline_epoch_seconds': 20.})


def test_stress_inventory_is_predeclared_and_disjoint():
    items = stress_inventory()
    assert len(items) == 144
    assert len({item['history_id'] for item in items}) == 144
    assert sum(item['population'] == 'boundary' for item in items) == 16
    assert sum(item['robustness'] == 'heavy_noise' for item in items) == 16
    assert all(item['seed'] == 2026102401910 and item['length'] == 512 for item in items)


def test_diagnostic_keeps_missing_task_failure_without_redraw():
    from famjet_poc.contracts import PopulationSpec, ShapeSpec
    from famjet_poc.data import generate_episode
    spec = PopulationSpec('poc_numeric_v1', ShapeSpec(16, 8), 'unit_test', 11,
                          (128,), ('piecewise_stationary',), 8, 128)
    episode = generate_episode(spec, 'unfit-diagnostic')
    episode.metadata['target_valid'] = [[False] * 8]
    policy = diagnostic_policy([episode], ('mean', 'contrast'), 'a' * 64)
    assert policy['status'] == 'failed_missing_primary_task'
    assert policy['history_ids'] == ['unfit-diagnostic']


def test_secondary_ledger_names_unavailable_tasks_with_null_metrics():
    rows = secondary_ledger([])
    by_name = {row['name']: row for row in rows}
    assert {'latest', 'presence', 'interval_support', 'change_sign',
            'corrected_categorical_v32', 'random_binding_v32',
            'sharp_windows', 'heavy_noise'} <= set(by_name)
    assert by_name['random_binding_v32']['status'] == 'unsupported'
    assert by_name['random_binding_v32']['metrics'] is None
    assert by_name['heavy_noise']['status'] == 'unentered'


def test_timing_disables_break_even_without_application_tolerance():
    admission = timing_accuracy_admission(('jet', 'bank', 'exact'))
    assert admission['accuracy_satisfied'] == {'jet': False, 'bank': False, 'exact': False}
    assert admission['reason'] == 'no application tolerance specified'


def test_k16_probe_uses_current_manifest_not_historical_receipt():
    manifest = {'manifest_sha256': 'b' * 64, 'e3_source_sha256': 'c' * 64}
    policy = {'probe_ref': {'path': 'old-probe.json', 'sha256': 'a' * 64},
              'expected_e3_source_sha256': 'c' * 64,
              'probe_ref_status': 'historical_pre_worker_fix; requires fresh matching actual CLI probe'}
    allocation = k16_probe_allocation(manifest, policy)
    assert allocation['phase'] == 'probe'
    assert allocation['manifest_sha256'] == 'b' * 64
    assert allocation['allocation_id'] == 'e4-k16-current-source-probe-v1'
    assert 'probe_ref' not in allocation
