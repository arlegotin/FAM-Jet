"""Closed Task18 numerical/fixture runner; see README for launch environment.

The Python -m loader imports the frozen package before this module. Thread
environment variables must therefore be set by the parent shell before Python.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import resource
import shutil
import subprocess
import sys
import time


THREAD_ENV = ('OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'OPENBLAS_NUM_THREADS',
              'VECLIB_MAXIMUM_THREADS')


def _launch_threads():
    if any(os.environ.get(name) != '1' for name in THREAD_ENV):
        raise RuntimeError('launcher must set all CPU thread environment variables to 1 before Python import')


def _rss_sample():
    """Current process RSS and separate lifetime highwater, in bytes."""
    if sys.platform == 'darwin':
        row = subprocess.run(('ps', '-o', 'rss=', '-p', str(os.getpid())),
                             capture_output=True, text=True, timeout=5, check=True)
        current = int(row.stdout.strip())*1024
        highwater = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    elif sys.platform.startswith('linux'):
        status = Path('/proc/self/status').read_text()
        current = int(re.search(r'^VmRSS:\s+(\d+) kB$', status, re.M).group(1))*1024
        highwater = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)*1024
    else:
        raise RuntimeError('RSS telemetry unavailable on this platform')
    return current, highwater


def _free_plus_speculative():
    """macOS printed free+speculative pages; file-backed pages are excluded."""
    if sys.platform != 'darwin':
        raise RuntimeError('free+speculative admission requires macOS vm_stat')
    result = subprocess.run(('vm_stat',), capture_output=True, text=True, timeout=5, check=True)
    pages = re.search(r'page size of (\d+) bytes', result.stdout)
    free = re.search(r'^Pages free:\s+([\d.]+)', result.stdout, re.M)
    speculative = re.search(r'^Pages speculative:\s+([\d.]+)', result.stdout, re.M)
    if not all((pages, free, speculative)):
        raise RuntimeError('vm_stat admission fields unavailable')
    return int(pages.group(1))*(int(free.group(1).rstrip('.'))+int(speculative.group(1).rstrip('.')))


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _publish_start(out, status, progress):
    """Persist admission status and the closed work inventory before work."""
    from famjet.artifacts import atomic_json
    atomic_json(Path(out)/'status.json', status)
    atomic_json(Path(out)/'progress.json', progress)


def main(argv=None):
    parser = argparse.ArgumentParser(description='Bounded Task18 reader diagnostics (fresh output only)')
    parser.add_argument('--mode', required=True, choices=('numerical', 'numerical_then_tiny_fit'))
    parser.add_argument('--out', required=True, type=Path, help='new unique output directory')
    args = parser.parse_args(argv)
    start = time.monotonic()
    deadline = start+1200.
    out = args.out.resolve()
    if out.exists():
        parser.error('--out must name a fresh, nonexistent directory')
    out.mkdir(parents=True, exist_ok=False)
    status = {'status': 'RUNNING', 'phase': 'admission', 'mode': args.mode,
              'utc_start': datetime.now(timezone.utc).isoformat(),
              'monotonic_start': start, 'monotonic_deadline': deadline,
              'argv': sys.argv if argv is None else [sys.argv[0], *argv],
              'environment': {name: os.environ.get(name) for name in THREAD_ENV},
              'platform': platform.platform()}
    from famjet.artifacts import atomic_json
    atomic_json(out/'status.json', status)
    try:
        _launch_threads()
        # Import only after verifying the launch contract. -m package import
        # has already happened, so the parent shell is the true pre-import gate.
        import torch
        from .checks import ResourceGuard, admission, numerical_checks, tiny_fit, new_campaign_progress
        progress = new_campaign_progress(args.mode)
        _publish_start(out, status, progress)
        if torch.get_num_threads() != 1:
            raise RuntimeError('actual torch CPU thread count differs from 1')
        baseline, highwater = _rss_sample()
        free = _free_plus_speculative()
        disk = shutil.disk_usage(out).free
        status.update(torch_num_threads=torch.get_num_threads(), baseline_rss=baseline,
                      baseline_lifetime_highwater=highwater,
                      admission_free_plus_speculative_bytes=free, admission_disk_free_bytes=disk,
                      admission_reserve_fraction=.25,
                      incremental_rss_cap_bytes=2**30, output_cap_bytes=2*2**30,
                      source_sha256={name: _sha(Path(__file__).with_name(name)) for name in
                                     ('__init__.py', 'contract.py', 'reader.py', 'fixtures.py', 'checks.py', 'check_run.py')},
                      lock_sha256=_sha(Path(__file__).resolve().parents[2]/'requirements.lock'))
        environment_identity = {'python': sys.version, 'executable': sys.executable,
                                'torch': torch.__version__, 'platform': status['platform'],
                                'thread_env': status['environment'],
                                'torch_num_threads': status['torch_num_threads']}
        status['environment_sha256'] = hashlib.sha256(json.dumps(
            environment_identity, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
        if status['lock_sha256'] != '2b1931e022c8e2555c45a9f9fb5feead7077b9043bfc088fc2db3e811bbe21d1':
            raise RuntimeError('requirements.lock identity mismatch')
        if not admission(free, disk):
            raise RuntimeError('fresh resource admission failed')
        guard = ResourceGuard(out, start=start, deadline=deadline,
                              baseline_rss=baseline, sample=_rss_sample,
                              publish=lambda value: atomic_json(out/'progress.json', value))
        guard.progress = progress
        guard.check()
        status['phase'] = 'numerical'
        atomic_json(out/'status.json', status)
        numerical = numerical_checks(budget=guard)
        result = {'numerical': numerical}
        if args.mode == 'numerical_then_tiny_fit':
            status['phase'] = 'tiny_fit'
            atomic_json(out/'status.json', status)
            result['tiny_fit'] = tiny_fit(budget=guard)
        guard.check()
        atomic_json(out/'result.json', result)
        guard.check()
        status.update(status='PASS' if all(x['status'] == 'PASS' for x in result.values()) else 'FAIL',
                      phase='complete',
                      result_sha256=_sha(out/'result.json'), samples=guard.samples,
                      result_bytes=(out/'result.json').stat().st_size)
    except Exception as exc:
        status['status'] = 'FAILED'
        status['failure'] = {'type': type(exc).__name__, 'message': str(exc)}
        if 'guard' in locals():
            status['samples'] = guard.samples
            try:
                if status['phase'] == 'numerical':
                    guard.progress['numerical']['status'] = 'FAIL'
                    if args.mode == 'numerical_then_tiny_fit':
                        guard.progress['tiny_fit']['status'] = 'BLOCKED'
                        for arm in guard.progress['tiny_fit']['arms']:
                            arm['status'] = 'BLOCKED'
                            arm['failure'] = 'blocked by failed numerical checks'
                            arm['unavailable'] = {name: 'not attempted after numerical failure'
                                                  for name in arm['unavailable']}
                elif status['phase'] == 'tiny_fit':
                    guard.progress['tiny_fit']['status'] = 'FAIL'
                guard.persist_progress()
                atomic_json(out/'partial-result.json', guard.progress)
                status['partial_result_sha256'] = _sha(out/'partial-result.json')
            except Exception as write_exc:
                status['partial_write_failure'] = f'{type(write_exc).__name__}: {write_exc}'
    status['utc_end'] = datetime.now(timezone.utc).isoformat()
    status['monotonic_end'] = time.monotonic()
    status['elapsed_seconds'] = status['monotonic_end']-start
    # Use the same atomic helper even if the failure preceded its import.
    from famjet.artifacts import atomic_json
    atomic_json(out/'status.json', status)
    return 0 if status['status'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
