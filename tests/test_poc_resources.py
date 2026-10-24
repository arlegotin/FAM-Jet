import ast
import json
import os
from pathlib import Path
import signal
import stat
import subprocess
import time
from types import SimpleNamespace

import pytest

from famjet_poc.resources import LiveStageGuard
from famjet_poc import pipeline


def _stub_host_processes(monkeypatch):
    def observe_command(argv, **_kwargs):
        if argv[0] == 'ps':
            return SimpleNamespace(stdout=f'{os.getpid()} {os.getppid()} 1024\n')
        if argv[0] == 'vm_stat':
            return SimpleNamespace(stdout='Mach Virtual Memory Statistics: (page size of 4096 bytes)\nPages free: 1000000.\nPages speculative: 0.\n')
        raise AssertionError(f'unexpected host command: {argv}')
    monkeypatch.setattr(pipeline.subprocess, 'run', observe_command)


def test_live_guard_production_observer_keeps_atomic_rename_healthy(tmp_path, monkeypatch):
    _stub_host_processes(monkeypatch)
    temporary = tmp_path / '.e4-in-progress'
    final = tmp_path / 'output.bin'
    temporary.write_bytes(b'payload')
    original_stat = os.stat
    renamed = []

    def rename_after_stat(path, *args, **kwargs):
        if os.fspath(path) == str(temporary) and not renamed:
            info = original_stat(path, *args, **kwargs)
            os.replace(temporary, final)
            renamed.append(True)
            return info
        return original_stat(path, *args, **kwargs)

    monkeypatch.setattr(pipeline.os, 'stat', rename_after_stat)
    allocation = {'max_wall_seconds': 5, 'max_disk_bytes': 1_000_000,
                  'max_rss_bytes': 10**12, 'allocation_id': 'unit-rename'}
    with LiveStageGuard(tmp_path, allocation, tmp_path / 'guard.json',
                        sample_interval=10) as guard:
        guard.check()
    receipt = json.loads((tmp_path / 'guard.json').read_bytes())
    assert renamed == [True]
    assert receipt['status'] == 'completed' and receipt['violation'] is None
    assert receipt['samples'][-1]['output_bytes'] >= len(b'payload')
    assert final.read_bytes() == b'payload'


def test_live_guard_production_observer_permission_error_blocks_completion(
        tmp_path, monkeypatch):
    _stub_host_processes(monkeypatch)
    output = tmp_path / 'output.bin'
    output.write_bytes(b'payload')
    original_stat = os.stat

    def denied_stat(path, *args, **kwargs):
        if os.fspath(path) == str(output):
            raise PermissionError('output stat denied')
        return original_stat(path, *args, **kwargs)

    monkeypatch.setattr(pipeline.os, 'stat', denied_stat)
    allocation = {'max_wall_seconds': 5, 'max_disk_bytes': 1_000_000,
                  'max_rss_bytes': 10**12, 'allocation_id': 'unit-output-denied'}
    with pytest.raises(RuntimeError, match='host resource observer failed'):
        with LiveStageGuard(tmp_path, allocation, tmp_path / 'guard.json',
                            sample_interval=10):
            raise AssertionError('stage entered after unreadable output')
    receipt = json.loads((tmp_path / 'guard.json').read_bytes())
    assert receipt['status'] == 'failed'
    assert receipt['violation'] == 'host resource observer failed'
    assert 'PermissionError' in receipt['samples'][0]['observer_error']


def test_witness_output_counter_survives_rename_and_rejects_permission_error(
        tmp_path, monkeypatch):
    source = Path(__file__).resolve().parents[1] / 'docs/research/e2e-process-witness.py'
    mirror = (Path(__file__).resolve().parents[1] /
              '.superpowers/sdd/2026-10-16-famjet/e2e-process-witness.py')
    assert source.read_bytes() == mirror.read_bytes()
    function = next(node for node in ast.parse(source.read_text()).body
                    if isinstance(node, ast.FunctionDef) and node.name == '_count_output_bytes')
    namespace = {'os': os, 'stat': stat, 'Path': Path}
    exec(compile(ast.Module(body=[function], type_ignores=[]), str(source), 'exec'), namespace)
    count = namespace['_count_output_bytes']
    temporary = tmp_path / '.e3-in-progress'
    final = tmp_path / 'result.bin'
    temporary.write_bytes(b'payload')
    original_stat = os.stat
    renamed = []

    def racing_stat(path, *args, **kwargs):
        if os.fspath(path) == str(temporary) and not renamed:
            info = original_stat(path, *args, **kwargs)
            os.replace(temporary, final)
            renamed.append(True)
            return info
        if os.fspath(path) == str(final) and len(renamed) == 2:
            raise PermissionError('witness output denied')
        return original_stat(path, *args, **kwargs)

    monkeypatch.setattr(os, 'stat', racing_stat)
    assert count((tmp_path,)) == len(b'payload')
    assert renamed == [True]
    assert count((tmp_path,)) == len(b'payload')
    renamed.append(True)
    with pytest.raises(PermissionError, match='witness output denied'):
        count((tmp_path,))


def test_live_guard_cancels_only_verified_active_worker_and_blocks_completion(tmp_path):
    worker = subprocess.Popen(['sleep', '5'])
    unrelated = subprocess.Popen(['sleep', '5'])
    cancelled = []
    observations = []
    def observe(_root):
        observations.append(1)
        return {'tree_rss_bytes': 1 if len(observations) == 1 else 2**30,
                'run_output_bytes': 0,
                'now_epoch_seconds': time.time(),
                'descendant_pids': [worker.pid] if worker.poll() is None else []}
    def cancel(pid):
        cancelled.append(pid)
        os.kill(pid, signal.SIGTERM)
    allocation = {'max_wall_seconds': 5, 'max_disk_bytes': 1024,
                  'max_rss_bytes': 1024, 'allocation_id': 'unit-live'}
    try:
        with pytest.raises(RuntimeError, match='RSS|resource'):
            with LiveStageGuard(tmp_path, allocation, tmp_path / 'guard.json',
                                observer=observe, cancel=cancel,
                                sample_interval=.01) as guard:
                time.sleep(.05)
                guard.check()
        assert worker.pid in cancelled
        assert unrelated.pid not in cancelled and unrelated.poll() is None
        receipt = json.loads((tmp_path / 'guard.json').read_bytes())
        assert receipt['status'] == 'failed' and receipt['samples']
        assert receipt['sample_count'] == len(receipt['samples'])
        assert receipt['observer_seconds'] >= 0
        assert worker.pid in receipt['cancelled_owned_descendants']
    finally:
        for process in (worker, unrelated):
            if process.poll() is None:
                process.terminate()
            process.wait(timeout=2)


def test_live_guard_initial_observer_failure_is_fail_closed(tmp_path):
    def unavailable(_root):
        raise PermissionError('host ps denied')
    allocation = {'max_wall_seconds': 5, 'max_disk_bytes': 1024,
                  'max_rss_bytes': 1024, 'allocation_id': 'unit-observer'}
    with pytest.raises(RuntimeError, match='observer'):
        with LiveStageGuard(tmp_path, allocation, tmp_path / 'guard.json',
                            observer=unavailable):
            raise AssertionError('work began after failed observation')
    receipt = json.loads((tmp_path / 'guard.json').read_bytes())
    assert receipt['status'] == 'failed'
