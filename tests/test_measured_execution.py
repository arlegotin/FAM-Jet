import json
import os
import signal
import subprocess
import threading
import time

import pytest

from famjet_poc.resources import LiveStageGuard
from famjet_poc.execution_policy import (load_execution_policy, new_run_policy,
                                         verify_run_policy, admit_scientific_work,
                                         verify_public_selection, verify_public_gate_ref,
                                         bind_run_policy)
from famjet_poc.pipeline import StageLedger, stage_public_selection_gate


def _allocation(wall=2):
    return {'allocation_id': 'measured-test', 'max_wall_seconds': wall,
            'max_disk_bytes': 1000000, 'max_rss_bytes': 1000}


def _observation(rss=10, disk=0):
    return {'tree_rss_bytes': rss, 'run_output_bytes': disk,
            'now_epoch_seconds': time.time(), 'descendant_pids': []}


def test_cached_checks_still_expire_original_deadline(tmp_path):
    with pytest.raises(RuntimeError, match='wall deadline'):
        with LiveStageGuard(tmp_path, _allocation(.04), tmp_path / 'guard.json',
                            observer=lambda _: _observation(), sample_interval=10) as guard:
            guard.check()
            time.sleep(.05)
            guard.check()
    receipt = json.loads((tmp_path / 'guard.json').read_bytes())
    assert receipt['status'] == 'failed'
    assert receipt['reuse_count'] >= 1


def test_entry_and_exit_force_fresh_observations_while_checks_reuse(tmp_path):
    seen = []
    def observe(_):
        seen.append(1)
        return _observation()
    with LiveStageGuard(tmp_path, _allocation(), tmp_path / 'guard.json',
                        observer=observe, sample_interval=10) as guard:
        for _ in range(15):
            guard.check()
    receipt = json.loads((tmp_path / 'guard.json').read_bytes())
    assert len(seen) == 2
    assert receipt['forced_count'] == 2
    assert receipt['reuse_count'] == 15


def test_blocked_observer_fails_closed_with_bounded_teardown(tmp_path):
    hold = threading.Event()
    def blocked(_):
        hold.wait(10)
        return _observation()
    started = time.monotonic()
    try:
        guard = LiveStageGuard(tmp_path, _allocation(), tmp_path / 'guard.json',
                               observer=blocked)
        guard.observer_timeout_seconds = .05
        with pytest.raises(RuntimeError, match='observer'):
            with guard:
                pass
        assert time.monotonic() - started < 2
        assert json.loads((tmp_path / 'guard.json').read_bytes())['status'] == 'failed'
    finally:
        hold.set()


def test_concurrent_foreground_and_background_observations_are_serial(tmp_path):
    active = 0
    maximum = 0
    lock = threading.Lock()
    def observe(_):
        nonlocal active, maximum
        with lock:
            active += 1
            maximum = max(maximum, active)
        time.sleep(.015)
        with lock:
            active -= 1
        return _observation()
    with LiveStageGuard(tmp_path, _allocation(), tmp_path / 'guard.json',
                        observer=observe, sample_interval=.01) as guard:
        workers = [threading.Thread(target=guard.check) for _ in range(8)]
        for worker in workers:
            worker.start()
        for worker in workers:
            worker.join()
        time.sleep(.04)
    assert maximum == 1


def test_nested_guards_serialize_two_roots_and_keep_independent_disk_caps(tmp_path):
    outer_root = tmp_path / 'outer'
    inner_root = outer_root / 'runs'
    inner_root.mkdir(parents=True)
    active = 0
    maximum = 0
    calls = {'outer': 0, 'runs': 0}
    lock = threading.Lock()
    def observe(root):
        nonlocal active, maximum
        with lock:
            active += 1
            maximum = max(maximum, active)
            calls[root.name] += 1
        time.sleep(.015)
        with lock:
            active -= 1
        return _observation(disk=5 if root.name == 'outer' else 2)
    with LiveStageGuard(outer_root, _allocation(), outer_root / 'outer-guard.json',
                        observer=observe, sample_interval=.01) as outer:
        with LiveStageGuard(inner_root, _allocation(), inner_root / 'inner-guard.json',
                            observer=observe, sample_interval=.01) as inner:
            threads = [threading.Thread(target=guard.check)
                       for guard in (outer, inner) for _ in range(4)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()
            time.sleep(.04)
    assert maximum == 1
    assert calls['outer'] >= 2 and calls['runs'] >= 2
    assert json.loads((inner_root / 'inner-guard.json').read_bytes())['samples'][0]['output_bytes'] == 2
    assert json.loads((outer_root / 'outer-guard.json').read_bytes())['samples'][0]['output_bytes'] == 5


def test_blocked_nested_observer_fails_both_guards_without_parallel_call(tmp_path):
    hold = threading.Event()
    active = 0
    maximum = 0
    lock = threading.Lock()
    def observe(root):
        nonlocal active, maximum
        with lock:
            active += 1
            maximum = max(maximum, active)
        if root.name == 'runs':
            hold.wait(10)
        with lock:
            active -= 1
        return _observation()
    outer_root = tmp_path / 'outer'; inner_root = outer_root / 'runs'
    inner_root.mkdir(parents=True)
    started = time.monotonic()
    try:
        outer = LiveStageGuard(outer_root, _allocation(), outer_root / 'outer.json',
                               observer=observe, sample_interval=.01)
        inner = LiveStageGuard(inner_root, _allocation(), inner_root / 'inner.json',
                               observer=observe, sample_interval=.01)
        outer.observer_timeout_seconds = inner.observer_timeout_seconds = .05
        with pytest.raises(RuntimeError, match='observer'):
            with outer:
                with inner:
                    outer.check()
        assert time.monotonic() - started < 2
        assert maximum == 1
    finally:
        hold.set()


def test_stale_background_observer_cannot_serve_cached_success(tmp_path):
    hold = threading.Event()
    calls = []
    def observe(_):
        calls.append(1)
        if len(calls) > 1:
            hold.wait(10)
        return _observation()
    try:
        guard = LiveStageGuard(tmp_path, _allocation(), tmp_path / 'guard.json',
                               observer=observe, sample_interval=.01)
        guard.observer_timeout_seconds = .05
        with pytest.raises(RuntimeError, match='observer'):
            with guard:
                time.sleep(.3)
                guard.check()
        receipt = json.loads((tmp_path / 'guard.json').read_bytes())
        assert receipt['status'] == 'failed'
        assert len(calls) >= 2
        assert receipt['maximum_reused_sample_age_seconds'] == 0
        assert receipt['maximum_sample_age_seconds'] >= .05
    finally:
        hold.set()


def test_slow_fresh_observation_uses_five_second_operation_bound_but_reuse_stays_quarter_second(tmp_path):
    calls = []
    def observe(_):
        calls.append(time.monotonic())
        if len(calls) == 2:
            time.sleep(.31)
        return _observation()
    with LiveStageGuard(tmp_path, _allocation(2), tmp_path / 'guard.json',
                        observer=observe, sample_interval=10) as guard:
        assert guard.observer_timeout_seconds == 5.0
        time.sleep(.26)
        guard.check()
        guard.check()
    receipt = json.loads((tmp_path / 'guard.json').read_bytes())
    assert receipt['status'] == 'completed'
    assert len(calls) == 3
    assert receipt['reuse_count'] == 1
    assert 0 <= receipt['maximum_reused_sample_age_seconds'] <= .25
    assert .30 <= receipt['maximum_observer_operation_seconds'] < 5
    assert receipt['maximum_sample_age_seconds'] > .25


def test_wall_deadline_still_fails_during_accepted_slow_observation(tmp_path):
    calls = []
    def observe(_):
        calls.append(1)
        if len(calls) == 2:
            time.sleep(.31)
        return _observation()
    with pytest.raises(RuntimeError, match='wall deadline'):
        with LiveStageGuard(tmp_path, _allocation(.4), tmp_path / 'guard.json',
                            observer=observe, sample_interval=10) as guard:
            guard.check()
            time.sleep(.26)
            guard.check()
    receipt = json.loads((tmp_path / 'guard.json').read_bytes())
    assert receipt['status'] == 'failed'


def test_background_interval_observes_even_with_fresh_foreground_cache(tmp_path):
    observations = []
    def observe(_):
        observations.append(time.monotonic())
        return _observation()
    with LiveStageGuard(tmp_path, _allocation(), tmp_path / 'guard.json',
                        observer=observe, sample_interval=.025):
        time.sleep(.09)
    receipt = json.loads((tmp_path / 'guard.json').read_bytes())
    assert receipt['background_count'] >= 2
    assert len(observations) >= 4  # entry, at least two background samples, exit


def test_background_deadline_cancels_only_currently_verified_owned_child(tmp_path):
    worker = subprocess.Popen(['sleep', '5'])
    unrelated = subprocess.Popen(['sleep', '5'])
    cancelled = []
    def observe(_):
        return {**_observation(),
                'descendant_pids': [worker.pid] if worker.poll() is None else []}
    def cancel(pid):
        cancelled.append(pid)
        os.kill(pid, signal.SIGTERM)
    try:
        with pytest.raises(RuntimeError, match='wall deadline'):
            with LiveStageGuard(tmp_path, _allocation(.05), tmp_path / 'guard.json',
                                observer=observe, cancel=cancel,
                                sample_interval=.01):
                time.sleep(.08)
        assert cancelled == [worker.pid]
        assert unrelated.poll() is None
    finally:
        for process in (worker, unrelated):
            if process.poll() is None:
                process.terminate()
            process.wait(timeout=2)


def test_fresh_exit_observation_detects_disk_violation(tmp_path):
    observed = []
    def observe(_):
        observed.append(1)
        return _observation(disk=0 if len(observed) == 1 else 1000001)
    with pytest.raises(RuntimeError, match='output'):
        with LiveStageGuard(tmp_path, _allocation(), tmp_path / 'guard.json',
                            observer=observe, sample_interval=10) as guard:
            guard.check()
    receipt = json.loads((tmp_path / 'guard.json').read_bytes())
    assert receipt['status'] == 'failed'
    assert len(observed) == 3  # exit sample and verified-descendant observation


def test_dated_policy_is_strict_and_reserve_blocks_scientific_admission(tmp_path):
    policy = load_execution_policy()
    assert (policy['policy_id'], policy['global_wall_seconds'],
            policy['synthetic_cell_wall_seconds'], policy['completion_reserve_seconds']) == (
                'e2e-measured-execution-v2-20261025', 28800, 1800, 1800)
    run = new_run_policy('a' * 64, start_epoch_seconds=1000)
    verify_run_policy(run, 'a' * 64)
    with pytest.raises(ValueError, match='policy'):
        verify_run_policy({**run, 'global_wall_seconds': 21600}, 'a' * 64)
    with pytest.raises(ValueError, match='policy'):
        verify_run_policy({**run, 'global_wall_seconds': 28800.0}, 'a' * 64)
    with pytest.raises(RuntimeError, match='reserve'):
        admit_scientific_work(run, 1800, now_epoch_seconds=26300)
    admit_scientific_work(run, 1800, now_epoch_seconds=26000)


def test_policy_rejects_bool_and_float_coercion_of_declared_integer_fields(tmp_path, monkeypatch):
    from famjet_poc import execution_policy
    path = tmp_path / 'policy.json'
    monkeypatch.setattr(execution_policy, 'POLICY_PATH', path)
    values = dict(execution_policy.EXPECTED_POLICY)
    values['schema_version'] = True
    path.write_text(json.dumps(values))
    with pytest.raises(ValueError, match='policy'):
        execution_policy.load_execution_policy()
    values['schema_version'] = 1
    values['global_wall_seconds'] = 28800.0
    path.write_text(json.dumps(values))
    with pytest.raises(ValueError, match='policy'):
        execution_policy.load_execution_policy()


def test_run_policy_anchor_rejects_consistent_original_clock_rewrite(tmp_path):
    from famjet.provenance import canonical_json
    master = new_run_policy('a' * 64, start_epoch_seconds=1000)
    path = tmp_path / 'run-policy.json'
    path.write_bytes(canonical_json(master))
    bind_run_policy(path, create=True)
    assert bind_run_policy(path) == master
    rewritten = new_run_policy('a' * 64, start_epoch_seconds=2000)
    path.write_bytes(canonical_json(rewritten))
    with pytest.raises(ValueError, match='anchor'):
        bind_run_policy(path)


def test_prefreeze_pipeline_resume_checks_complete_source_before_stage_reuse(tmp_path, monkeypatch):
    from famjet.provenance import canonical_json
    from famjet_poc import execution_policy, pipeline, protected
    out = tmp_path / 'run'
    out.mkdir()
    path = out / 'run-policy.json'
    path.write_bytes(canonical_json(new_run_policy('a' * 64,
                                                   start_epoch_seconds=time.time() - 10)))
    bind_run_policy(path, create=True)
    monkeypatch.setattr(pipeline, '_study_inputs',
                        lambda _: ({'manifest_sha256': 'a' * 64}, {}))
    class StageReached(Exception):
        pass
    monkeypatch.setattr(pipeline, 'StageLedger', lambda _: (_ for _ in ()).throw(StageReached()))
    with pytest.raises(StageReached):
        pipeline.run(out, resume=True)
    original_identity = protected.executable_identity
    monkeypatch.setattr(protected, 'executable_identity',
                        lambda: {**original_identity(), 'sha256': 'f' * 64})
    with pytest.raises(ValueError, match='source'):
        pipeline.run(out, resume=True)


def test_public_gate_rejects_wrong_baseline_before_any_freeze(tmp_path):
    with pytest.raises(ValueError, match='baseline'):
        verify_public_selection({}, {}, {'normalization': {}},
                                baseline_sha256='0' * 64)


def test_stage_refuses_new_scientific_work_that_consumes_reserve(tmp_path):
    policy = new_run_policy('a' * 64, start_epoch_seconds=time.time() - 26200)
    ledger = StageLedger(tmp_path / 'run')
    called = []
    with pytest.raises(RuntimeError, match='reserve'):
        ledger.stage('private', {'allocation': _allocation(1800)},
                     lambda _: called.append(True), scientific_policy=policy)
    assert called == []
    assert not (tmp_path / 'run' / 'private').exists()


def test_archived_public_models_and_normalization_match_six_role_baseline():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    baseline = json.loads((root / 'docs/research/e2e-evaluation-v2-selection-baseline.json').read_bytes())
    refs = {role: {'path': str(root / item['archived_model_ref']['path']),
                   'sha256': item['archived_model_ref']['sha256']}
            for role, item in baseline['roles'].items()}
    old_public_modes = json.loads((root / 'artifacts/e2e-core-run-04/transfer_fit/modes/transfer-modes.json').read_bytes())
    modes = {'normalization': old_public_modes['normalization'],
             'task_adapted': {'jet': refs['real_jet'], 'bank': refs['real_bank']}}
    result = verify_public_selection({'jet': refs['k16_jet'], 'bank': refs['k16_bank']},
                                     {'jet': refs['k12_jet'], 'bank': refs['k12_bank']}, modes)
    assert set(result['roles']) == set(baseline['roles'])
    with pytest.raises(ValueError, match='normalization'):
        verify_public_selection({'jet': refs['k16_jet'], 'bank': refs['k16_bank']},
                                {'jet': refs['k12_jet'], 'bank': refs['k12_bank']},
                                {**modes, 'normalization': {}})
    with pytest.raises(ValueError, match='shape/spec'):
        verify_public_selection({'jet': refs['k16_bank'], 'bank': refs['k16_jet']},
                                {'jet': refs['k12_jet'], 'bank': refs['k12_bank']}, modes)


def test_public_gate_receipt_rejects_forged_match_and_changed_bytes(tmp_path):
    from pathlib import Path
    from famjet.provenance import canonical_json
    import hashlib
    root = Path(__file__).resolve().parents[1]
    baseline = json.loads((root / 'docs/research/e2e-evaluation-v2-selection-baseline.json').read_bytes())
    refs = {role: {'path': str(root / item['archived_model_ref']['path']),
                   'sha256': item['archived_model_ref']['sha256']}
            for role, item in baseline['roles'].items()}
    old_modes = json.loads((root / 'artifacts/e2e-core-run-04/transfer_fit/modes/transfer-modes.json').read_bytes())
    selected16 = {'jet': refs['k16_jet'], 'bank': refs['k16_bank']}
    selected12 = {'jet': refs['k12_jet'], 'bank': refs['k12_bank']}
    modes = {'normalization': old_modes['normalization'],
             'task_adapted': {'jet': refs['real_jet'], 'bank': refs['real_bank']}}
    correct = verify_public_selection(selected16, selected12, modes)
    path = tmp_path / 'gate.json'
    path.write_bytes(canonical_json({**correct, 'verification_seconds': .01}))
    ref = {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
    assert verify_public_gate_ref(ref, selected16, selected12, modes)['status'] == 'matched'
    forged = {**correct, 'roles': {**correct['roles'],
              'k16_jet': {**correct['roles']['k16_jet'], 'numeric_sha256': '0' * 64}},
              'verification_seconds': .01}
    path.write_bytes(canonical_json(forged))
    with pytest.raises(ValueError, match='bytes'):
        verify_public_gate_ref(ref, selected16, selected12, modes)
    forged_ref = {**ref, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
    with pytest.raises(ValueError, match='result'):
        verify_public_gate_ref(forged_ref, selected16, selected12, modes)


def test_pipeline_gate_mismatch_fails_before_freeze_or_protected_stage(tmp_path):
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    baseline = json.loads((root / 'docs/research/e2e-evaluation-v2-selection-baseline.json').read_bytes())
    refs = {role: {'path': str(root / item['archived_model_ref']['path']),
                   'sha256': item['archived_model_ref']['sha256']}
            for role, item in baseline['roles'].items()}
    ledger = StageLedger(tmp_path / 'run')
    modes = {'normalization': {},
             'task_adapted': {'jet': refs['real_jet'], 'bank': refs['real_bank']}}
    with pytest.raises(ValueError, match='normalization'):
        stage_public_selection_gate(ledger,
            {'jet': refs['k16_jet'], 'bank': refs['k16_bank']},
            {'jet': refs['k12_jet'], 'bank': refs['k12_bank']},
            modes, 'a' * 64, monitor_observer=lambda _: _observation())
    generations = json.loads(ledger.path.read_bytes())['generations']
    assert [entry['stage'] for entry in generations] == ['public_selection_gate'] * 2
    assert [entry['status'] for entry in generations] == ['running', 'failed']
    assert not (ledger.root / 'freeze').exists()
    assert not any(path.name.startswith('cell-') for path in ledger.root.iterdir())


def test_pipeline_run_stops_at_public_mismatch_before_freeze_factory(tmp_path, monkeypatch):
    import hashlib
    from pathlib import Path
    from famjet_poc import pipeline, transfer
    root = Path(__file__).resolve().parents[1]
    old = root / 'artifacts/e2e-core-run-04'
    out = tmp_path / 'new-run'
    manifest, _ = pipeline._study_inputs(out)
    def ref(path):
        return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
    probe16 = old / 'probe_k16/attempt-000/probe/probe.json'
    probe12 = old / 'probe_k12/attempt-000/probe/probe.json'
    journal16 = old / 'development_k16/study/development.json'
    journal12 = old / 'development_k12/study/development.json'
    modes_path = old / 'transfer_fit/modes/transfer-modes.json'
    public_modes = json.loads(modes_path.read_bytes())
    monkeypatch.setattr(transfer, 'verify_transfer_probe',
        lambda *_args: {'recommended_wall_seconds': 300,
                        'recommended_disk_bytes': 256 * 2**20,
                        'recommended_rss_bytes': 1610612736})
    monkeypatch.setattr(transfer.ModeRefs, 'read',
        lambda _self: {**public_modes, 'normalization': {}})
    entered = []
    class PublicFixtureLedger:
        def __init__(self, path):
            self.root = Path(path)
        def stage(self, name, _inputs, action, **_kwargs):
            entered.append(name)
            if name in {'freeze', 'stress'} or name.startswith(('cell-', 'beijing-')):
                raise AssertionError('protected/freeze stage entered after public mismatch')
            if name == 'probe_k16':
                return {'probe_path': str(probe16), 'probe_sha256': ref(probe16)['sha256'],
                        'e3_source_sha256': manifest['e3_source_sha256']}
            if name == 'development_k16':
                return {'journal_path': str(journal16), 'journal_sha256': ref(journal16)['sha256']}
            if name == 'probe_k12':
                return {'probe_path': str(probe12), 'probe_sha256': ref(probe12)['sha256']}
            if name == 'development_k12':
                return {'journal_path': str(journal12), 'journal_sha256': ref(journal12)['sha256']}
            if name == 'probe_beijing_fit':
                return {'probe_ref': {'path': 'unused-public-probe', 'sha256': 'a' * 64}}
            if name == 'transfer_fit':
                return {'modes_ref': ref(modes_path), 'live_guard_ref': {}}
            if name == 'public_selection_gate':
                directory = self.root / name
                directory.mkdir()
                return action(directory)
            return {'status': 'public_fixture_skipped'}
    monkeypatch.setattr(pipeline, 'StageLedger', PublicFixtureLedger)
    with pytest.raises(ValueError, match='normalization'):
        pipeline.run(out)
    assert entered[-1] == 'public_selection_gate'
    assert 'freeze' not in entered
    assert not any(path.name.startswith('cell-') for path in out.iterdir())
