"""Live host resource enforcement for E4 stage boundaries.

The sampler cancels only descendant PIDs present in two current host tree
observations. The external run witness owns the hard process-group stop; this
guard records every sample and refuses stage completion after any violation.
"""
import hashlib
import json
import math
import os
from pathlib import Path
import signal
import threading
import time

from famjet.provenance import canonical_json


class LiveStageGuard:
    def __init__(self, root, allocation, receipt_path, *, observer=None,
                 cancel=None, sample_interval=.1):
        if (type(allocation) is not dict or
                any(type(allocation.get(key)) not in (int, float) or
                    not math.isfinite(allocation[key]) or allocation[key] <= 0
                    for key in ('max_wall_seconds', 'max_disk_bytes', 'max_rss_bytes')) or
                type(allocation.get('allocation_id')) is not str or
                not allocation['allocation_id'] or
                type(sample_interval) not in (int, float) or sample_interval <= 0):
            raise ValueError('finite live stage allocation required')
        if observer is None:
            from .pipeline import observe_resources
            observer = observe_resources
        self.root = Path(root)
        self.allocation = allocation
        self.receipt_path = Path(receipt_path)
        self.observer = observer
        self.cancel = cancel or (lambda pid: os.kill(pid, signal.SIGTERM))
        self.sample_interval = sample_interval
        self.started = None
        self.samples = []
        self.violation = None
        self.cancelled = set()
        self.cancellation_seconds = 0.0
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread = None
        self.receipt_ref = None

    def _record(self):
        observed_started = time.perf_counter()
        try:
            observed = self.observer(self.root)
            if (type(observed) is not dict or
                    any(type(observed.get(k)) not in (int, float) or
                        not math.isfinite(observed[k]) or observed[k] < 0
                        for k in ('tree_rss_bytes', 'run_output_bytes', 'now_epoch_seconds')) or
                    type(observed.get('descendant_pids')) is not list or
                    any(type(pid) is not int or pid <= 0 or pid == os.getpid()
                        for pid in observed['descendant_pids'])):
                raise ValueError('incomplete host process-tree observation')
            sample = {'elapsed_seconds': time.monotonic() - self.started,
                      'observer_seconds': time.perf_counter() - observed_started,
                      'now_epoch_seconds': observed['now_epoch_seconds'],
                      'tree_rss_bytes': observed['tree_rss_bytes'],
                      'output_bytes': observed['run_output_bytes'],
                      'descendant_pids': sorted(set(observed['descendant_pids']))}
            if sample['elapsed_seconds'] >= self.allocation['max_wall_seconds']:
                reason = 'wall deadline exceeded'
            elif sample['tree_rss_bytes'] > self.allocation['max_rss_bytes']:
                reason = 'live tree RSS exceeded'
            elif sample['output_bytes'] > self.allocation['max_disk_bytes']:
                reason = 'stage output exceeded'
            else:
                reason = None
        except Exception as exc:
            sample = {'elapsed_seconds': time.monotonic() - self.started,
                      'observer_seconds': time.perf_counter() - observed_started,
                      'observer_error': f'{type(exc).__name__}: {exc}'}
            reason = 'host resource observer failed'
        with self._lock:
            self.samples.append(sample)
            if reason and self.violation is None:
                self.violation = reason
        if reason:
            suspects = sample.get('descendant_pids')
            if suspects is None:
                suspects = next((prior['descendant_pids'] for prior in
                                 reversed(self.samples[:-1]) if 'descendant_pids' in prior), [])
            self._cancel_verified(suspects)

    def _cancel_verified(self, suspects):
        started = time.perf_counter()
        try:
            current = self.observer(self.root)
            verified = set(current['descendant_pids']) & set(suspects)
        except Exception:
            verified = set()
        for pid in sorted(verified):
            if pid == os.getpid() or pid in self.cancelled:
                continue
            try:
                self.cancel(pid)
            except ProcessLookupError:
                pass
            except Exception as exc:
                with self._lock:
                    self.violation = self.violation or f'owned child cancellation failed: {exc}'
            else:
                with self._lock:
                    self.cancelled.add(pid)
        self.cancellation_seconds += time.perf_counter() - started

    def _watch(self):
        while not self._stop.wait(self.sample_interval):
            self._record()
            if self.violation:
                return

    def _write_receipt(self, exception=None):
        body = {'schema_version': 1, 'kind': 'famjet_e4_live_stage_guard',
                'allocation': self.allocation,
                'process_identity': {'pid': os.getpid(), 'ppid': os.getppid(),
                                     'process_group_id': os.getpgrp()},
                'status': 'failed' if self.violation or exception else 'completed',
                'violation': self.violation, 'exception': exception,
                'samples': self.samples,
                'sample_count': len(self.samples),
                'observer_seconds': sum(sample['observer_seconds']
                                        for sample in self.samples),
                'cancellation_seconds': self.cancellation_seconds,
                'cancelled_owned_descendants': sorted(self.cancelled),
                'sample_interval_seconds': self.sample_interval,
                'scope': 'current_parent_plus_verified_live_descendants'}
        raw = canonical_json(body)
        measured_output = next((sample['output_bytes'] for sample in reversed(self.samples)
                                if 'output_bytes' in sample), None)
        if (measured_output is not None and
                measured_output + len(raw) > self.allocation['max_disk_bytes'] and
                self.violation is None):
            self.violation = 'stage output including guard receipt exceeded'
            body['status'] = 'failed'
            body['violation'] = self.violation
            raw = canonical_json(body)
        self.receipt_path.parent.mkdir(parents=True, exist_ok=True)
        with self.receipt_path.open('xb') as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        self.receipt_ref = {'path': str(self.receipt_path),
                            'sha256': hashlib.sha256(raw).hexdigest(),
                            'bytes': len(raw)}

    def __enter__(self):
        self.started = time.monotonic()
        self._record()
        if self.violation:
            self._write_receipt()
            raise RuntimeError(self.violation)
        self._thread = threading.Thread(target=self._watch, daemon=True)
        self._thread.start()
        return self

    def check(self):
        if self.violation:
            raise RuntimeError(self.violation)
        self._record()
        if self.violation:
            raise RuntimeError(self.violation)

    def __exit__(self, exc_type, exc, tb):
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2)
            if self._thread.is_alive():
                self.violation = self.violation or 'host resource observer did not stop'
        if not self.violation:
            self._record()
        self._write_receipt(None if exc is None else f'{type(exc).__name__}: {exc}')
        if exc is None and self.violation:
            raise RuntimeError(self.violation)
        return False
