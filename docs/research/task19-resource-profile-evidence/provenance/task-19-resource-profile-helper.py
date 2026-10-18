"""PREPARATION ONLY: six deterministic analysis resource cases; requires release.

Never a population/calibration simulator. Do not run, import, compile, or test
this preparation until root separately authorizes this exact helper + seal.
"""
import argparse
import base64
import csv
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import resource
import signal
import struct
import subprocess
import sys
import threading
import time
import traceback

sys.dont_write_bytecode = True
ROOT = Path('/Users/artemlegotin/Documents/git_alter/FAM-Jet')
PACKAGE = '57c0920f360e47f2c3978f056437143c4262b8ab9653b753df1321402ade9717'
FORMULA = 'integer_additive_interaction_v1'
ENV = {key: '1' for key in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS',
                            'VECLIB_MAXIMUM_THREADS', 'BLIS_NUM_THREADS', 'NUMEXPR_NUM_THREADS')}
ENV.update(OMP_DYNAMIC='FALSE', MKL_DYNAMIC='FALSE')
CASES = [dict(case_id=f'{kind}-S{s}', units=units, seeds=s, seed=1900 + i,
              weights=weights) for i, (kind, units, s, weights) in enumerate([
    ('one', [128], 4, {'g0': 1.}), ('one', [128], 16, {'g0': 1.}),
    ('one', [128], 64, {'g0': 1.}),
    ('three', [32, 64, 32], 4, {'g0': .2, 'g1': .3, 'g2': .5}),
    ('three', [32, 64, 32], 16, {'g0': .2, 'g1': .3, 'g2': .5}),
    ('three', [32, 64, 32], 64, {'g0': .2, 'g1': .3, 'g2': .5})])]
CAP_BYTES = 268435456
CAP_SECONDS = 30.
POLL = .02


def require(ok, message):
    if not ok:
        raise ValueError(message)


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode()


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def digest(value):
    return hashlib.sha256(encoded(value)).hexdigest()


def read(path):
    return json.loads(Path(path).read_bytes())


def create(path, value):
    with Path(path).open('xb') as f:
        f.write(encoded(value)); f.flush(); os.fsync(f.fileno())


def journal(out, event, **fields):
    data = encoded(dict(event=event, utc_seconds=time.time(), monotonic=time.monotonic(), **fields)) + b'\n'
    fd = os.open(out / 'journal.jsonl', os.O_WRONLY | os.O_APPEND)
    try:
        os.write(fd, data); os.fsync(fd)
    finally:
        os.close(fd)


def source_hash():
    return digest({str(p.relative_to(ROOT)): sha(p) for p in sorted((ROOT / 'famjet').rglob('*.py'))})


def elapsed(start):
    # Include civil elapsed time across host sleep as well as monotonic time.
    return max(time.monotonic() - start['monotonic'], time.time() - start['utc_seconds'])


def validate_seal(seal, release):
    require(seal['schema_version'] == 1 and seal['cases'] == CASES and
            seal['formula_version'] == FORMULA and seal['package_source_hash'] == PACKAGE,
            'seal schema/cases/formula/source mismatch')
    require(seal['helper_sha256'] == sha(__file__), 'helper hash mismatch')
    require(release['schema_version'] == 1 and release['status'] == 'root_authorized' and
            release['scope'] == 'task19_six_case_resource_only' and release['approval_id'].strip() and
            release['seal_sha256'] == sha(ARGS.seal) and release['helper_sha256'] == sha(__file__) and
            release['package_source_hash'] == PACKAGE and release['cases'] == CASES and
            release['max_seconds'] == CAP_SECONDS and release['max_incremental_rss_bytes'] == CAP_BYTES,
            'missing or mismatched separate root release')
    require(sys.platform == 'darwin' and sys.version_info[:3] == (3, 13, 5) and
            platform.machine() == 'arm64' and platform.mac_ver()[0] == '26.7.1', 'pinned Darwin/Python required')
    require(all(os.environ.get(k) == v for k, v in ENV.items()), 'single-compute-thread environment mismatch')
    require(subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip() ==
            release['execution_head'], 'execution HEAD differs from release')
    require(not subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT), 'tracked/unignored tree not clean')
    # Root fills the actual epsilon-summary paths/values only after its gate.
    # The role inventory prevents substituting exit0 or a generic passed flag.
    pre = release['epsilon_numerical_prerequisite']
    require(sha(ROOT / pre['path']) == pre['sha256'], 'epsilon prerequisite hash mismatch')
    summary = read(ROOT / pre['path'])
    require({c['role'] for c in pre['checks']} == {'schema', 'status', 'source', 'shape', 'count', 'identity'},
            'epsilon prerequisite requires actual schema/status/source/shape/count/identity checks')
    for check in pre['checks']:
        require(check['path'] and check['expected'] is not None, 'unfilled epsilon prerequisite check')
        require(check['role'] != 'source' or check['expected'] == PACKAGE, 'epsilon prerequisite must use this exact package source')
        actual = summary
        for key in check['path']:
            actual = actual[key]
        require(actual == check['expected'], 'epsilon prerequisite mismatch: ' + check['role'])


def dependencies(seal):
    require(source_hash() == PACKAGE, 'actual package source changed')
    for item in seal['files']:
        require(sha(ROOT / item['path']) == item['sha256'], 'pinned file changed: ' + item['path'])
    require(sha(Path(sys.executable).resolve()) == seal['python_executable_sha256'], 'interpreter bytes changed')
    site = ROOT / '.venv/lib/python3.13/site-packages'
    # RECORD hashes are sealed now; verify installed runtime code/library bytes
    # only on release. Do not read dependency test datasets or scientific inputs.
    # Unhashed bytecode entries are not a claim of bytecode integrity.
    for name in ('numpy-2.5.4.dist-info', 'scipy-1.18.1.dist-info'):
        with (site / name / 'RECORD').open(newline='') as f:
            for filename, commitment, size in csv.reader(f):
                runtime_code = filename.endswith(('.py', '.so', '.dylib')) and not any(
                    part in filename.split('/') for part in ('tests', 'test', 'benchmarks'))
                if commitment and runtime_code:
                    kind, wanted = commitment.split('=', 1)
                    require(kind == 'sha256', 'unexpected distribution hash')
                    path = (site / filename).resolve()
                    require(path.is_relative_to(ROOT / '.venv'), 'distribution entry escapes virtualenv')
                    actual = base64.urlsafe_b64encode(bytes.fromhex(sha(path))).decode().rstrip('=')
                    require(actual == wanted and path.stat().st_size == int(size), 'installed dependency changed: ' + filename)


def input_bytes(case):
    # Exact dyadic numbers from integer indices, no random population generator.
    # d = (g-1)/4 + (2h-Hg+1)/32 + (2s-S+1)/16
    #     + (((h+1)*(s+3)+5g) % 17 - 8)/64.
    raw = bytearray(); strata = []
    for g, h_count in enumerate(case['units']):
        for h in range(h_count):
            strata.append(f'g{g}')
            for s in range(case['seeds']):
                numerator = (16 * (g - 1) + 2 * (2 * h - h_count + 1) +
                             4 * (2 * s - case['seeds'] + 1) + ((h + 1) * (s + 3) + 5 * g) % 17 - 8)
                raw.extend(struct.pack('<d', numerator / 64))
    return bytes(raw), strata


def validate_result(result, case):
    require(result['schema_version'] == 1 and result['seed'] == case['seed'] and
            result['stratum_weights'] == case['weights'], 'result schema/seed/weights mismatch')
    n = result['draws']
    require(type(n) is int and n in (2000, 4000, 8000, 16000, 32000, 64000, 128000) and
            len(result['resample_means']) == n, 'actual draw count mismatch')
    require([s['draws'] for s in result['stages']] == [2000 * 2**i for i in range(len(result['stages']))] and
            result['stages'][-1]['draws'] == n, 'actual adaptive stage inventory mismatch')
    require(result['endpoint_mc'] in ('met', 'cap_unmet', 'degenerate_zero') and
            (result['endpoint_mc'] != 'cap_unmet' or n == 128000), 'endpoint status/cap mismatch')
    require(result['limitations']['independent_units'] == 128 and
            result['limitations']['paired_training_replicates'] == case['seeds'] and
            result['rng']['algorithm'] == 'numpy.PCG64.multinomial' and
            result['rng']['key_version'] == 'crossed-v1' and result['rng']['chunk_size'] == 256 and
            result['rng']['numpy_version'] == '2.5.4' and
            result['rng']['quantile_method'] == 'linear' and result['rng']['batch_order'] == [0, 1, 2, 3] and
            result['rng']['append_policy'] == 'equal_increments_at_total_doubling' and
            result['rng']['arithmetic'] == 'power_of_two_scaled_stratum_centered_normalized_multinomial_counts' and
            len(result['rng']['axis_seeds']) == 4 * (1 + len(case['units'])) and
            result['rng']['root_seed'] == case['seed'] and not result['strong_claim_allowed'] and
            result['p_mc_error_budget'] is None and result['secondary_p_mc'] == 'not_assessed',
            'actual algorithm/shape/precision/permission identity mismatch')
    require(len(result['interval']) == 2 and all(math.isfinite(x) for x in result['interval']) and
            math.isfinite(result['mean']) and all(math.isfinite(x) for x in result['resample_means']),
            'nonfinite actual profile result')
    require(all(len(s['batch_endpoints']) == 4 and all(len(pair) == 2 for pair in s['batch_endpoints'])
                for s in result['stages']), 'actual four-batch endpoint shape mismatch')


def worker(out, seal, release, start):
    baseline = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss  # Darwin bytes.
    create(out / 'baseline.json', dict(rss_highwater_bytes=baseline, pid=os.getpid(), execution_id=start['execution_id']))
    stage = ['dependency_preflight']

    def memory_watch():
        try:
            while True:
                peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
                record = dict(schema_version=1, execution_id=start['execution_id'], stage=stage[0],
                              baseline_bytes=baseline, peak_bytes=peak, incremental_bytes=max(0, peak - baseline))
                temp = out / 'telemetry.tmp'
                temp.write_bytes(encoded(record)); temp.replace(out / 'telemetry.json')
                if record['incremental_bytes'] > CAP_BYTES:
                    journal(out, 'worker_rss_budget_violation', **record); os._exit(73)
                time.sleep(POLL)
        except BaseException:
            try:
                journal(out, 'memory_watch_failure', traceback=traceback.format_exc())
            finally:
                os._exit(74)

    threading.Thread(target=memory_watch, daemon=True).start()
    try:
        dependencies(seal)
        sys.path.insert(0, str(ROOT))
        import numpy as np
        import scipy
        from famjet.analysis.statistics import crossed_interval
        require(np.__version__ == '2.5.4' and scipy.__version__ == '1.18.1', 'runtime dependency version mismatch')
        create(out / 'runtime.json', dict(python=sys.version, numpy=np.__version__, scipy=scipy.__version__,
                                        requested_compute_threads=1, environment=ENV,
                                        blas_backend='pinned_build_Accelerate',
                                        thread_count='environment_requested_not_independently_introspected'))
        completed = []
        for case in CASES:
            require(elapsed(start) < CAP_SECONDS, 'global time budget exhausted before next case')
            stage[0] = case['case_id']; folder = out / case['case_id']; folder.mkdir()
            raw, strata = input_bytes(case)
            with (folder / 'effects.f64le').open('xb') as f:
                f.write(raw)
            descriptor = dict(schema_version=1, execution_id=start['execution_id'], case=case,
                              formula_version=FORMULA, shape=[128, case['seeds']], dtype='<f8',
                              input_scope='deterministic_software_resource_fixture',
                              layout='C_rows_stratum_then_local_history_columns_shared_seed',
                              strata=strata, raw_sha256=sha(folder / 'effects.f64le'),
                              package_source_hash=PACKAGE, helper_sha256=sha(__file__))
            create(folder / 'input.json', descriptor)
            d = np.frombuffer(raw, dtype='<f8').reshape(128, case['seeds'])
            require(d.shape == (128, case['seeds']) and d.tobytes() == raw and np.isfinite(d).all(), 'actual input shape/bytes invalid')
            journal(out, 'case_start', case=case, input_hash=digest(descriptor), global_seconds=elapsed(start))
            before = time.monotonic()
            result = crossed_interval(d, np.asarray(strata), case['seed'], 2000, stratum_weights=case['weights'])
            call_seconds = time.monotonic() - before
            validate_result(result, case)
            create(folder / 'result.json', result)
            peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
            require(peak - baseline <= CAP_BYTES, 'worker peak RSS budget violated')
            require(elapsed(start) < CAP_SECONDS, 'global time budget exhausted after case')
            record = dict(schema_version=1, execution_id=start['execution_id'], case=case,
                          scientific_qualification=False,
                          input_hash=digest(descriptor), result_sha256=sha(folder / 'result.json'),
                          draws=result['draws'], endpoint_mc=result['endpoint_mc'], call_seconds=call_seconds,
                          global_seconds=elapsed(start), baseline_bytes=baseline, peak_bytes=peak,
                          incremental_peak_bytes=max(0, peak - baseline), package_source_hash=PACKAGE)
            create(folder / 'summary.json', record); completed.append(record)
            journal(out, 'case_complete', **record)
            # cap_unmet is an endpoint measurement, not an operational error.
        require(source_hash() == PACKAGE, 'source changed during resource run')
        create(out / 'worker-summary.json', dict(schema_version=1, status='complete_resource_only',
               execution_id=start['execution_id'], package_source_hash=PACKAGE, cases=completed,
               global_seconds=elapsed(start), scientific_qualification=False))
    except BaseException as exc:
        journal(out, 'worker_error', stage=stage[0], error_type=type(exc).__name__,
                error=str(exc), traceback=traceback.format_exc())
        raise


def supervise(out, seal, release):
    require(not out.exists() and out.is_relative_to(ROOT / 'artifacts/task19'), 'fresh task19 artifact directory required')
    out.mkdir(parents=True)
    with (out / 'journal.jsonl').open('xb'):
        pass
    start = dict(monotonic=time.monotonic(), utc_seconds=time.time(),
                 execution_id=f"{release['approval_id']}-{os.getpid()}-{time.time_ns()}")
    create(out / 'start.json', start)
    journal(out, 'supervisor_start', expected_cases=CASES, release_sha256=sha(ARGS.release), seal_sha256=sha(ARGS.seal))
    parent_baseline = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    failure = None; samples = []; child = None
    try:
        with (out / 'worker.stdout.log').open('xb') as stdout, (out / 'worker.stderr.log').open('xb') as stderr:
            child = subprocess.Popen([sys.executable, '-I', '-B', str(Path(__file__).resolve()),
                '--seal', str(ARGS.seal), '--release', str(ARGS.release), '--out', str(out), '--worker'],
                cwd=ROOT, env={'PATH': '/usr/bin:/bin', 'LC_ALL': 'C', 'LANG': 'C', **ENV},
                stdout=stdout, stderr=stderr, start_new_session=True)
            while child.poll() is None:
                total = elapsed(start)
                if total >= CAP_SECONDS:
                    failure = 'global_30_second_budget_exceeded'; break
                current = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
                telemetry_path = out / 'telemetry.json'
                telemetry = read(telemetry_path) if telemetry_path.exists() else None
                baseline_path = out / 'baseline.json'
                if baseline_path.exists():
                    baseline = read(baseline_path)
                    require(baseline['pid'] == child.pid and baseline['execution_id'] == start['execution_id'], 'stale worker baseline')
                    ps = subprocess.run(['/bin/ps', '-o', 'rss=', '-p', str(child.pid)], capture_output=True, text=True,
                                        timeout=min(.1, max(.001, CAP_SECONDS - total)))
                    live = int(ps.stdout.strip()) * 1024 if ps.returncode == 0 and ps.stdout.strip() else 0
                    peak = max(live, telemetry['peak_bytes'] if telemetry else baseline['rss_highwater_bytes'])
                    additional = max(0, peak - baseline['rss_highwater_bytes']) + max(0, current - parent_baseline)
                    samples.append(dict(seconds=total, worker_rss_bytes=live, combined_incremental_bytes=additional))
                    if additional > CAP_BYTES:
                        failure = 'global_incremental_rss_budget_exceeded'; break
                time.sleep(POLL)
            if failure:
                journal(out, 'supervisor_budget_stop', reason=failure, global_seconds=elapsed(start))
                os.killpg(child.pid, signal.SIGKILL)
            child.wait()
        require(failure is None, failure or 'resource failure')
        require(child.returncode == 0, f'worker exit {child.returncode}; no retry')
        summary = read(out / 'worker-summary.json')
        require(summary['schema_version'] == 1 and summary['status'] == 'complete_resource_only' and
                summary['execution_id'] == start['execution_id'] and summary['package_source_hash'] == PACKAGE and
                [r['case'] for r in summary['cases']] == CASES and len(summary['cases']) == 6 and
                summary['scientific_qualification'] is False, 'actual worker summary/identity/count invalid')
        for case, record in zip(CASES, summary['cases']):
            folder = out / case['case_id']; actual = read(folder / 'summary.json'); descriptor = read(folder / 'input.json')
            require(actual == record and actual['execution_id'] == start['execution_id'] and
                    actual['case'] == case and descriptor['case'] == case and descriptor['shape'] == [128, case['seeds']] and
                    descriptor['strata'] == [f'g{g}' for g, count in enumerate(case['units']) for _ in range(count)] and
                    descriptor['dtype'] == '<f8' and descriptor['input_scope'] == 'deterministic_software_resource_fixture' and
                    descriptor['execution_id'] == start['execution_id'] and descriptor['formula_version'] == FORMULA and
                    descriptor['package_source_hash'] == PACKAGE and descriptor['helper_sha256'] == sha(__file__) and
                    descriptor['raw_sha256'] == sha(folder / 'effects.f64le') and
                    (folder / 'effects.f64le').stat().st_size == 128 * case['seeds'] * 8 and
                    record['input_hash'] == digest(descriptor) and record['result_sha256'] == sha(folder / 'result.json'),
                    'actual fresh input/result/summary identity or shape mismatch')
            result = read(folder / 'result.json'); validate_result(result, case)
            require(result['draws'] == record['draws'] and result['endpoint_mc'] == record['endpoint_mc'], 'summary/result mismatch')
            require(record['incremental_peak_bytes'] + max(0, resource.getrusage(resource.RUSAGE_SELF).ru_maxrss - parent_baseline) <= CAP_BYTES,
                    'combined historical peak RSS exceeds budget')
        require(elapsed(start) < CAP_SECONDS and source_hash() == PACKAGE, 'final global time/source check failed')
        create(out / 'summary.json', dict(schema_version=1, status='complete_resource_only',
               execution_id=start['execution_id'], package_source_hash=PACKAGE, cases=summary['cases'],
               source_commit=seal['accepted_source_commit'], execution_head=release['execution_head'],
               approval_id=release['approval_id'], helper_sha256=sha(__file__), seal_sha256=sha(ARGS.seal),
               release_sha256=sha(ARGS.release), global_seconds=elapsed(start), samples=samples,
               scientific_qualification=False, confirmation_allowed=False, nuisance_only_allowed=False))
        journal(out, 'supervisor_complete', summary_sha256=sha(out / 'summary.json'), global_seconds=elapsed(start))
        return 0
    except BaseException as exc:
        if child is not None and child.poll() is None:
            os.killpg(child.pid, signal.SIGKILL); child.wait()
        journal(out, 'supervisor_failure', error_type=type(exc).__name__, error=str(exc), traceback=traceback.format_exc(),
                global_seconds=elapsed(start), worker_returncode=None if child is None else child.returncode)
        if not (out / 'summary.json').exists():
            create(out / 'summary.json', dict(schema_version=1, status='failed_resource_only',
                   execution_id=start['execution_id'], expected_cases=CASES, error_type=type(exc).__name__,
                   error=str(exc), global_seconds=elapsed(start), samples=samples,
                   scientific_qualification=False, confirmation_allowed=False, nuisance_only_allowed=False))
        return 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--seal', required=True, type=Path)
    parser.add_argument('--release', required=True, type=Path)
    parser.add_argument('--out', required=True, type=Path)
    parser.add_argument('--worker', action='store_true')
    ARGS = parser.parse_args()
    ARGS.seal = ARGS.seal.resolve(); ARGS.release = ARGS.release.resolve(); ARGS.out = ARGS.out.resolve()
    if ARGS.worker:
        SEAL, RELEASE = read(ARGS.seal), read(ARGS.release)
        validate_seal(SEAL, RELEASE)
        worker(ARGS.out, SEAL, RELEASE, read(ARGS.out / 'start.json'))
    else:
        # Preflight errors get a fresh journal too; numerical work never starts.
        require(not ARGS.out.exists() and ARGS.out.is_relative_to(ROOT / 'artifacts/task19'),
                'fresh task19 artifact directory required')
        try:
            SEAL, RELEASE = read(ARGS.seal), read(ARGS.release)
            validate_seal(SEAL, RELEASE)
        except BaseException as exc:
            ARGS.out.mkdir(parents=True)
            with (ARGS.out / 'journal.jsonl').open('xb'):
                pass
            journal(ARGS.out, 'preflight_failure', error_type=type(exc).__name__, error=str(exc),
                    traceback=traceback.format_exc())
            create(ARGS.out / 'summary.json', dict(schema_version=1, status='preflight_failed_resource_only',
                   error_type=type(exc).__name__, error=str(exc), scientific_qualification=False,
                   confirmation_allowed=False, nuisance_only_allowed=False))
            sys.exit(1)
        sys.exit(supervise(ARGS.out, SEAL, RELEASE))
