import json

import pytest

from famjet_poc.pipeline import (StageLedger, admit_resources, stress_inventory,
                                 diagnostic_policy, secondary_ledger, timing_accuracy_admission,
                                 k16_probe_allocation, remaining_probe_allocation,
                                 execute_study_probe)


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


def test_interrupted_public_stage_retains_first_clock_and_attempt_bytes(tmp_path):
    root = tmp_path / 'run'
    ledger = StageLedger(root)
    original = {'schema_version': 1, 'phase': 'probe', 'manifest_sha256': 'a' * 64,
                'allocation_id': 'probe', 'max_wall_seconds': 120,
                'max_disk_bytes': 1024, 'max_rss_bytes': 2**30}
    started = []
    def interrupted(out):
        started.append(ledger.first_start_epoch('probe'))
        attempt = out / 'attempt-000'
        attempt.mkdir()
        (attempt / 'partial.txt').write_text('original failed attempt')
        raise KeyboardInterrupt()
    with pytest.raises(KeyboardInterrupt):
        ledger.stage('probe', {'allocation': original}, interrupted, retryable=True)
    def resumed(out):
        assert (out / 'attempt-000' / 'partial.txt').read_text() == 'original failed attempt'
        assert ledger.first_start_epoch('probe') == started[0]
        allocation = remaining_probe_allocation(original, started[0], started[0] + 30)
        assert allocation['max_wall_seconds'] == 90
        attempt = out / 'attempt-001'
        attempt.mkdir()
        (attempt / 'done.txt').write_text('new attempt')
        return {'status': 'measured', 'allocation': allocation}
    result = ledger.stage('probe', {'allocation': original}, resumed,
                          resume=True, retryable=True)
    assert result['allocation']['max_wall_seconds'] == 90
    with pytest.raises(RuntimeError, match='deadline'):
        remaining_probe_allocation(original, started[0], started[0] + 120)


def test_resume_reconciles_process_terminated_running_public_stage(tmp_path):
    from famjet.provenance import canonical_hash
    root = tmp_path / 'run'
    ledger = StageLedger(root)
    stage_dir = root / 'public-probe'
    stage_dir.mkdir()
    (stage_dir / 'attempt-000.txt').write_text('interrupted bytes')
    ledger._append({'stage': 'public-probe', 'status': 'running',
                    'input_sha256': canonical_hash({'allocation': 1}),
                    'start_monotonic': 1., 'start_epoch_seconds': 10.,
                    'deadline_epoch_seconds': 130.})
    def resumed(directory):
        assert (directory / 'attempt-000.txt').read_text() == 'interrupted bytes'
        (directory / 'attempt-001.txt').write_text('new attempt')
        return {'status': 'measured'}
    assert ledger.stage('public-probe', {'allocation': 1}, resumed,
                        resume=True, retryable=True)['status'] == 'measured'
    statuses = [item['status'] for item in json.loads(ledger.path.read_text())['generations']]
    assert statuses == ['running', 'failed', 'running', 'completed']


def test_monitored_stage_cancels_live_owned_worker_and_never_seals(tmp_path):
    import os
    import signal
    import subprocess
    import time
    ledger = StageLedger(tmp_path / 'run')
    started = []
    cancelled = []
    unrelated = subprocess.Popen(['sleep', '5'])
    def observer(_root):
        child = started[0] if started else None
        live = child is not None and child.poll() is None
        return {'tree_rss_bytes': 2**30 if live else 1,
                'run_output_bytes': 0, 'now_epoch_seconds': time.time(),
                'descendant_pids': [child.pid] if live else []}
    def cancel(pid):
        cancelled.append(pid)
        os.kill(pid, signal.SIGTERM)
    def action(_directory):
        child = subprocess.Popen(['sleep', '5'])
        started.append(child)
        child.wait(timeout=3)
        return {'status': 'complete'}
    try:
        with pytest.raises(RuntimeError, match='RSS|resource'):
            ledger.stage('live-worker', {'allocation': {
                'max_wall_seconds': 3, 'max_disk_bytes': 1024,
                'max_rss_bytes': 1024, 'allocation_id': 'unit-worker'}},
                action, monitor=True, monitor_observer=observer,
                monitor_cancel=cancel)
        statuses = [item['status'] for item in json.loads(ledger.path.read_text())['generations']]
        assert statuses == ['running', 'failed']
        assert started[0].pid in cancelled and unrelated.pid not in cancelled
        assert unrelated.poll() is None
    finally:
        for child in [*started, unrelated]:
            if child.poll() is None:
                child.terminate()
            child.wait(timeout=2)


def test_real_e3_probe_callee_uses_original_stage_clock_and_attempt_dir(tmp_path):
    from famjet_poc.contracts import ShapeSpec
    from famjet_poc.study import study_manifest
    manifest = study_manifest({'profile': 'unit_test', 'shape': ShapeSpec(12, 1).to_json(),
                               'training_seed': 412, 'development_seed': 318,
                               'max_query_attempts': 512,
                               'cache_limits': {'disk_bytes': 8_000_000,
                                                'lru_bytes': 8_000_000},
                               'worker_limits': {'max_frame_bytes': 8_000_000,
                                                 'max_array_bytes': 4_000_000,
                                                 'max_histories': 64}})
    allocation = {'schema_version': 1, 'phase': 'probe',
                  'manifest_sha256': manifest['manifest_sha256'],
                  'allocation_id': 'unit-real-callee', 'max_wall_seconds': 60.,
                  'max_disk_bytes': 8_000_000, 'max_rss_bytes': 2_000_000_000}
    ledger = StageLedger(tmp_path / 'run')
    result = ledger.stage('unit-probe', {'allocation': allocation},
                          lambda directory: execute_study_probe(
                              ledger, 'unit-probe', manifest, allocation, directory),
                          retryable=True)
    recorded = json.loads(open(result['probe_path']).read())
    assert result['attempt'] == 0 and recorded['status'] == 'measured'
    assert recorded['allocation']['max_wall_seconds'] <= 60.
    assert result['original_start_epoch_seconds'] == ledger.first_start_epoch('unit-probe')
    assert 'attempt-000' in result['probe_path']


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
    with pytest.raises(RuntimeError, match='RSS'):
        admit_resources({**receipt['observed'], 'tree_rss_bytes': 2 * 2**30},
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
