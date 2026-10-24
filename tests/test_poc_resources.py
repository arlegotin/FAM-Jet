import json
import os
from pathlib import Path
import signal
import subprocess
import time

import pytest

from famjet_poc.resources import LiveStageGuard


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
