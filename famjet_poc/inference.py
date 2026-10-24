"""Conditional-on-frozen-fits history inference and prospective calibration.

This module imports no model, data, or torch code. Its source identity is deliberately
limited to this engine, the seed implementation, and the locked dependencies.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import platform
import resource
import sys
import time

import numpy as np
import scipy
from scipy.integrate import quad
from scipy.optimize import brentq
from scipy.special import betaincinv
from scipy.stats import t as student_t

from famjet.provenance import canonical_hash, derive_seed

ENGINE = 'conditional_history_welch_v1'
LENGTHS = (128, 512, 2048)
REGIMES = ('piecewise_stationary', 'trend_reset', 'periodic_impulses', 'irregular_revisions')
STRATA = tuple(f'{length}:{regime}' for length in LENGTHS for regime in REGIMES)
FIXTURES = tuple(range(1, 9))
N = 20000
K = 32
ATTEMPTS = {
    1: (2026102401901, 'e2e-inference-calibration-v1', 128),
    2: (2026102401903, 'e2e-inference-calibration-v2', 256),
}
PROBE = (2026102401900, 'e2e-inference-probe-v1', 128)
SEED_ROLES = {
    'nuisance': (2026102401902, 'e2e-inference-nuisance-v1'),
    'confirmation': (2026102401904, 'e2e-inference-confirmation-v1'),
    'replication': (2026102401905, 'e2e-inference-replication-v1'),
}
LAW_DESCRIPTORS = (
    'standard_normal', 'centered_scaled_lognormal', 'negative_centered_scaled_lognormal',
    'scaled_student_t5', 'centered_scaled_bernoulli_0.02',
    'negative_centered_scaled_bernoulli_0.02', 'heterogeneous_normal',
    'heterogeneous_signed_lognormal',
)
FIXTURE_HASH = canonical_hash({'laws': LAW_DESCRIPTORS, 'strata': STRATA,
                               'scales': (.5, 1., 1.5, 2.), 'scale_denominator': 1.875,
                               'shifts': (0., .05, -.05), 'N': N, 'attempts': {str(k): v for k, v in ATTEMPTS.items()}})
COUNTER_PROTOCOL = 'derive_seed(root,namespace,canonical_hash({fixture,outer,stratum,draw:history_effect})); PCG64; history-index order'


def _finite(x):
    return bool(np.all(np.isfinite(x)))


def source_identity():
    """Scoped source/dependency commitment, stable when future PoC files are added."""
    root = Path(__file__).resolve().parent.parent
    paths = ('famjet_poc/inference.py', 'famjet/provenance.py', 'requirements.lock')
    hashes = {p: hashlib.sha256((root / p).read_bytes()).hexdigest() for p in paths}
    return {'sha256': canonical_hash(hashes), 'files': hashes, 'python': platform.python_version(),
            'numpy': np.__version__, 'scipy': scipy.__version__,
            'bit_generator': 'numpy.random.PCG64'}


def reference_t_quantile(df: float) -> float:
    """Independent integral and root reference for the positive 97.5% t quantile."""
    if not math.isfinite(df) or df <= 0:
        raise ValueError('positive finite df required')
    log_norm = math.lgamma((df + 1) / 2) - math.lgamma(df / 2) - .5 * math.log(df * math.pi)
    def upper(x):
        return quad(lambda z: math.exp(log_norm - .5 * (df + 1) * math.log1p(z*z/df)),
                    x, math.inf, epsabs=1e-13, epsrel=1e-13)[0]
    hi = 2.
    while upper(hi) > .025:
        hi *= 2
    return float(brentq(lambda x: upper(x) - .025, 0., hi, xtol=1e-13))


def t_critical(df: float) -> float:
    value = float(student_t.ppf(.975, df))
    if not math.isfinite(value):
        raise ValueError('nonfinite t quantile')
    return value


def conditional_interval(d, strata, *, weights=None, identical_method=False):
    """Finite JSON-compatible stratified Welch interval for paired history losses."""
    d = np.asarray(d, dtype=np.float64)
    strata = np.asarray(strata)
    if d.ndim != 1 or strata.ndim != 1 or len(d) != len(strata) or not len(d) or not _finite(d):
        raise ValueError('finite one-dimensional paired history data required')
    if strata.dtype.kind not in 'iu' or np.any(strata < 0):
        raise ValueError('integer contiguous strata required')
    g = int(np.max(strata)) + 1
    if set(strata.tolist()) != set(range(g)):
        raise ValueError('all contiguous strata required')
    w = np.full(g, 1/g) if weights is None else np.asarray(weights, dtype=np.float64)
    if w.shape != (g,) or not _finite(w) or np.any(w <= 0) or not math.isclose(float(w.sum()), 1., abs_tol=1e-14):
        raise ValueError('positive normalized weights required')
    if identical_method and np.any(d != 0):
        raise ValueError('identical-method claim contradicts paired losses')
    counts = [int(np.count_nonzero(strata == i)) for i in range(g)]
    if any(n < 2 for n in counts):
        raise ValueError('at least two histories per stratum required')
    means = np.array([np.mean(d[strata == i]) for i in range(g)])
    vars_ = np.array([np.var(d[strata == i], ddof=1) for i in range(g)])
    a = w*w*vars_/counts
    D = float(w @ means)
    V = float(np.sum(a))
    if not math.isfinite(D) or not math.isfinite(V) or V < 0:
        raise ValueError('nonrepresentable Welch estimate')
    if V == 0:
        if not identical_method or D != 0:
            raise ValueError('zero variance blocks non-identical inference')
        return {'engine': ENGINE, 'status': 'identical_method', 'D': 0., 'V': 0., 'df': None,
                'lower': 0., 'upper': 0., 'p_two_sided': 1., 'superiority': False,
                'endpoint_mc': 'not_applicable_analytic', 'p_mc': 'not_applicable_analytic',
                'draws': 0, 'units': 'history', 'counts': counts}
    denom = float(np.sum(a*a/(np.asarray(counts)-1)))
    df = V*V/denom
    critical = t_critical(df)
    width = critical*math.sqrt(V)
    lo, hi = D-width, D+width
    p = float(2*student_t.sf(abs(D)/math.sqrt(V), df))
    if not all(map(math.isfinite, (df, width, lo, hi, p))):
        raise ValueError('nonrepresentable Welch endpoints')
    return {'engine': ENGINE, 'status': 'ok', 'D': D, 'V': V, 'df': df,
            'lower': lo, 'upper': hi, 'p_two_sided': p, 'superiority': lo > 0,
            'endpoint_mc': 'not_applicable_analytic', 'p_mc': 'not_applicable_analytic',
            'draws': 0, 'units': 'history', 'counts': counts}


def validate_history_pairs(rows, manifest):
    """Require exactly one pre-averaged paired loss per committed history ID."""
    if type(manifest) is not dict or manifest.get('units') != 'history' or manifest.get('panel') not in {'unit_test', 'nuisance', 'confirmation', 'replication'}:
        raise ValueError('history manifest required')
    inventory = manifest.get('history_ids_by_stratum')
    if type(inventory) is not dict or sorted(inventory, key=lambda x: int(x)) != [str(i) for i in range(len(inventory))]:
        raise ValueError('contiguous stratum inventory required')
    panel = manifest['panel']
    if panel != 'unit_test':
        if manifest.get('strata') != list(STRATA):
            raise ValueError('primary stratum labels and order required')
        expected_per_cell = 16 if panel == 'nuisance' else 128
        if len(inventory) != 12 or any(len(ids) != expected_per_cell for ids in inventory.values()):
            raise ValueError('fixed 12-stratum panel allocation required')
    weights = manifest.get('weights')
    if weights is None or len(weights) != len(inventory) or not np.allclose(weights, np.full(len(inventory), 1/len(inventory)), atol=0, rtol=0):
        raise ValueError('committed equal weights required')
    expected = {}
    for key, ids in inventory.items():
        if type(ids) is not list or len(ids) < 2:
            raise ValueError('at least two IDs per stratum required')
        for hid in ids:
            if type(hid) is not str or not hid or hid in expected:
                raise ValueError('invalid or duplicate manifest history ID')
            expected[hid] = int(key)
    if type(rows) not in (list, tuple) or len(rows) != len(expected):
        raise ValueError('incomplete paired history inventory')
    observed = {}
    for row in rows:
        if type(row) is not dict or set(row) != {'history_id', 'stratum', 'jet_loss', 'bank_loss', 'units'}:
            raise ValueError('one paired history loss record required')
        hid = row['history_id']
        if (type(hid) is not str or hid not in expected or hid in observed or
                type(row['stratum']) is not int or row['stratum'] != expected[hid] or row['units'] != 'history'):
            raise ValueError('history ID, unit, or stratum mismatch')
        j, b = row['jet_loss'], row['bank_loss']
        if type(j) not in (float, int) or type(b) not in (float, int) or not math.isfinite(j) or not math.isfinite(b):
            raise ValueError('finite paired losses required')
        difference = float(b-j)
        if not math.isfinite(difference):
            raise ValueError('nonrepresentable paired loss')
        observed[hid] = difference
    if observed.keys() != expected.keys():
        raise ValueError('missing history')
    ordered = [(observed[hid], int(key)) for key, ids in inventory.items() for hid in ids]
    return np.array([v for v, _ in ordered], dtype=np.float64), np.array([g for _, g in ordered], dtype=np.int64)


def fixture_scales(fixture_id):
    if fixture_id not in FIXTURES:
        raise ValueError('unknown fixture')
    base = np.ones(12)
    if fixture_id in (7, 8):
        base = np.tile(np.array([.5, 1., 1.5, 2.])/math.sqrt(1.875), 3)
    if fixture_id == 8:
        base *= np.tile([1., -1., 1., -1.], 3)
    return base


def _draw(fixture_id, seed, n):
    rng = np.random.Generator(np.random.PCG64(seed))
    if fixture_id in (1, 7):
        return rng.standard_normal(n)
    if fixture_id in (2, 3, 8):
        z = rng.standard_normal(n)
        x = (np.exp(z)-math.exp(.5))/math.sqrt(math.exp(2)-math.e)
        return -x if fixture_id == 3 else x
    if fixture_id == 4:
        return rng.standard_t(5, n)*math.sqrt(3/5)
    b = rng.binomial(1, .02, n)
    x = (b-.02)/math.sqrt(.02*.98)
    return -x if fixture_id == 6 else x


def _counter_seed(root, namespace, fixture, outer, stratum):
    identity = canonical_hash({'fixture': fixture, 'outer': outer, 'stratum': stratum,
                               'draw': 'history_effect'})
    return derive_seed(root, namespace, identity)


def _batch(fixture_id, outer_start, count, per_cell, role):
    if (fixture_id not in FIXTURES or type(outer_start) is not int or outer_start < 0 or
            type(count) is not int or not 1 <= count <= 64 or
            type(per_cell) is not int or per_cell < 2 or outer_start+count > N):
        raise ValueError('invalid bounded calibration batch')
    root, namespace, _ = role
    seeds = np.empty((count, 12), dtype=np.uint64)
    d = np.empty((count, 12, per_cell), dtype=np.float64)
    scales = fixture_scales(fixture_id)
    for r in range(count):
        for g in range(12):
            seed = _counter_seed(root, namespace, fixture_id, outer_start+r, g)
            seeds[r, g] = seed
            d[r, g, :] = .25*scales[g]*_draw(fixture_id, seed, per_cell)
    mean = d.mean(axis=2)
    var = d.var(axis=2, ddof=1)
    a = var/(12*12*per_cell)
    D = mean.mean(axis=1)
    V = a.sum(axis=1)
    with np.errstate(divide='ignore', invalid='ignore', over='ignore'):
        df = V*V / (a*a).sum(axis=1) * (per_cell-1)
        half = student_t.ppf(.975, df)*np.sqrt(V)
    lower = D-half
    upper = D+half
    status = np.isfinite(D)&np.isfinite(V)&np.isfinite(df)&np.isfinite(lower)&np.isfinite(upper)&(V>0)&(df>0)
    cover = status & (lower <= 0) & (upper >= 0)
    null_reject = ~cover
    pos_power = status & (lower+.05 > 0)
    neg_power = status & (upper-.05 < 0)
    # Shifted intervals are exact translations for this location-equivariant statistic.
    shift_equal = bool(np.array_equal((lower+.05 <= .05)&(upper+.05 >= .05),
                                      (lower <= 0)&(upper >= 0)) and
                       np.array_equal((lower-.05 <= -.05)&(upper-.05 >= -.05),
                                      (lower <= 0)&(upper >= 0)))
    counts = {'total': count, 'coverage': int(cover.sum()), 'null_rejection': int(null_reject.sum()),
              'positive_power': int(pos_power.sum()), 'negative_power': int(neg_power.sum()),
              'invalid': int((~status).sum())}
    commitment = hashlib.sha256(seeds.astype('<u8', copy=False).tobytes()).hexdigest()
    return {'fixture_id': fixture_id, 'outer_start': outer_start, 'count': count,
            'per_cell': per_cell, 'root': root, 'namespace': namespace,
            'counter_commitment': commitment, 'D': D, 'V': V, 'df': df,
            'lower': lower, 'upper': upper, 'status': status,
            'counts': counts, 'shift_coverage_equal': shift_equal,
            'law': {'fixture': fixture_id, 'descriptor': LAW_DESCRIPTORS[fixture_id-1]}}


def calibration_batch(fixture_id, outer_start, count, *, per_cell=128, attempt=1):
    if attempt not in ATTEMPTS or per_cell != ATTEMPTS[attempt][2] and per_cell > 64:
        raise ValueError('attempt/per-cell mismatch')
    return _batch(fixture_id, outer_start, count, per_cell, ATTEMPTS[attempt])


def cp_bounds(successes, trials, tail):
    if type(successes) is not int or type(trials) is not int or not 0 <= successes <= trials or trials < 1 or not 0 < tail < .5:
        raise ValueError('invalid binomial inputs')
    lower = 0. if successes == 0 else float(betaincinv(successes, trials-successes+1, tail))
    upper = 1. if successes == trials else float(betaincinv(successes+1, trials-successes, 1-tail))
    return lower, upper


def calibration_boundaries():
    """Prospective integer CP boundaries, computed before any calibration draw."""
    tail = .005/(2*K)
    def min_lower(threshold):
        lo, hi = 0, N
        while lo < hi:
            mid = (lo+hi)//2
            if cp_bounds(mid, N, tail)[0] >= threshold:
                hi = mid
            else:
                lo = mid+1
        return lo
    def max_upper(threshold):
        lo, hi = 0, N
        while lo < hi:
            mid = (lo+hi+1)//2
            if cp_bounds(mid, N, tail)[1] <= threshold:
                lo = mid
            else:
                hi = mid-1
        return lo
    return {'N': N, 'K': K, 'tail': tail,
            'coverage': {'threshold': .94, 'pass_count': min_lower(.94), 'side': 'lower'},
            'null_rejection': {'threshold': .06, 'pass_count': max_upper(.06), 'side': 'upper'},
            'power': {'threshold': .75, 'pass_count': min_lower(.75), 'side': 'lower'}}


def _atomic_json(path, value):
    temp = path.with_suffix(path.suffix+'.tmp')
    with temp.open('w') as f:
        json.dump(value, f, sort_keys=True, allow_nan=False)
        f.write('\n')
        f.flush()
        os.fsync(f.fileno())
    os.replace(temp, path)


def _rss_bytes():
    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return int(value if sys.platform == 'darwin' else value*1024)


def _initial_evidence(attempt, role, per_cell, kind):
    return {'schema': 1, 'engine': ENGINE, 'kind': kind, 'status': 'incomplete', 'attempt': attempt,
            'N': N if kind == 'calibration' else 64, 'per_cell': per_cell,
            'source': source_identity(), 'fixture_hash': FIXTURE_HASH,
            'counter_protocol': COUNTER_PROTOCOL, 'root': role[0], 'namespace': role[1],
            'boundaries': calibration_boundaries(), 'strata': list(STRATA),
            'fixtures': {str(f): {'completed': 0, 'counts': {'total': 0, 'coverage': 0,
                 'null_rejection': 0, 'positive_power': 0, 'negative_power': 0, 'invalid': 0},
                 'batches': []} for f in FIXTURES},
            'resource': {'start_monotonic': time.monotonic(), 'end_monotonic': None,
                         'peak_rss_bytes': _rss_bytes(), 'artifact_bytes': 0}}


def _store_batch(out, evidence, batch):
    fixture = str(batch['fixture_id'])
    start = batch['outer_start']
    name = f'fixture-{fixture}-outer-{start:05d}.npz'
    path = out/name
    temp = out/(name+'.tmp')
    with temp.open('wb') as f:
        np.savez_compressed(f, **{k: batch[k] for k in ('D', 'V', 'df', 'lower', 'upper', 'status')})
        f.flush()
        os.fsync(f.fileno())
    os.replace(temp, path)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    record = {'file': name, 'sha256': digest, 'outer_start': start, 'count': batch['count'], 'per_cell': batch['per_cell'],
              'counter_commitment': batch['counter_commitment'], 'counts': batch['counts'],
              'shift_coverage_equal': batch['shift_coverage_equal']}
    item = evidence['fixtures'][fixture]
    item['batches'].append(record)
    item['completed'] += batch['count']
    for k, v in batch['counts'].items():
        item['counts'][k] += v
    evidence['resource']['peak_rss_bytes'] = max(evidence['resource']['peak_rss_bytes'], _rss_bytes())
    evidence['resource']['artifact_bytes'] = sum(p.stat().st_size for p in out.iterdir() if p.is_file())
    if evidence['resource']['peak_rss_bytes'] > 256*1024**2 or evidence['resource']['artifact_bytes'] > 128*1024**2:
        evidence['status'] = 'fail'
        _atomic_json(out/'evidence.json', evidence)
        raise RuntimeError('resource cap exceeded')
    _atomic_json(out/'evidence.json', evidence)


def _run(out, *, deadline_monotonic, attempt, role, kind, total):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=False)
    evidence = _initial_evidence(attempt, role, role[2], kind)
    _atomic_json(out/'evidence.json', evidence)
    if (type(deadline_monotonic) not in (float, int) or
            (not math.isfinite(deadline_monotonic) and not (kind == 'probe' and deadline_monotonic == math.inf))):
        raise ValueError('finite monotonic deadline required for calibration')
    try:
        for fixture in FIXTURES:
            for start in range(0, total, 64):
                if time.monotonic() >= deadline_monotonic:
                    evidence['resource']['end_monotonic'] = time.monotonic()
                    _atomic_json(out/'evidence.json', evidence)
                    return evidence
                batch = _batch(fixture, start, min(64, total-start), role[2], role)
                _store_batch(out, evidence, batch)
        evidence['status'] = 'complete'
        if kind == 'probe':
            elapsed = time.monotonic() - evidence['resource']['start_monotonic']
            evidence['resource']['probe_seconds'] = elapsed
            evidence['resource']['forecast_main_seconds'] = elapsed * N / total
            evidence['resource']['model_tuning_seconds'] = 0.
    except Exception as exc:
        evidence['status'] = 'fail'
        evidence['error'] = f'{type(exc).__name__}: {exc}'
        raise
    finally:
        evidence['resource']['end_monotonic'] = time.monotonic()
        _atomic_json(out/'evidence.json', evidence)
    return evidence


def probe_calibration(out):
    """Run a fresh 64-per-law timing probe with disjoint counters; never a gate."""
    return _run(out, deadline_monotonic=math.inf, attempt=0, role=PROBE, kind='probe', total=64)


def run_calibration(out, *, deadline_monotonic, attempt=1):
    """Stream the fixed 20k × 8 campaign into a fresh, failure-retaining directory."""
    if attempt not in ATTEMPTS:
        raise ValueError('only prospective attempts 1 and 2 exist')
    return _run(out, deadline_monotonic=deadline_monotonic, attempt=attempt,
                role=ATTEMPTS[attempt], kind='calibration', total=N)


def validate_calibration(evidence, policy):
    """Reopen all batch bytes and commitments before evaluating all 32 CP guards."""
    try:
        out = Path(policy['out'])
        if type(evidence) is not dict or evidence.get('kind') != 'calibration':
            return {'status': 'fail', 'reason': 'not calibration evidence'}
        attempt = evidence['attempt']
        if attempt not in ATTEMPTS or evidence['source'] != source_identity() or evidence['fixture_hash'] != FIXTURE_HASH or evidence['counter_protocol'] != COUNTER_PROTOCOL or evidence['boundaries'] != calibration_boundaries() or evidence['N'] != N or evidence['per_cell'] != ATTEMPTS[attempt][2] or (evidence['root'], evidence['namespace']) != ATTEMPTS[attempt][:2]:
            return {'status': 'fail', 'reason': 'source, fixture, counter, or boundary mismatch'}
        if evidence != json.loads((out/'evidence.json').read_text()):
            return {'status': 'fail', 'reason': 'evidence file mismatch'}
        if set(evidence['fixtures']) != {str(f) for f in FIXTURES} or evidence['status'] == 'fail':
            return {'status': 'fail', 'reason': 'fixture inventory or execution failure'}
        total_file_bytes = sum(p.stat().st_size for p in out.iterdir() if p.is_file())
        if total_file_bytes > 128*1024**2 or evidence['resource']['peak_rss_bytes'] > 256*1024**2:
            return {'status': 'fail', 'reason': 'resource cap'}
        all_counts = {}
        for f in FIXTURES:
            item = evidence['fixtures'][str(f)]
            expected_start = 0
            counts = {key: 0 for key in ('total', 'coverage', 'null_rejection', 'positive_power', 'negative_power', 'invalid')}
            for record in item['batches']:
                if (record['outer_start'] != expected_start or not 1 <= record['count'] <= 64 or
                        record['per_cell'] != ATTEMPTS[attempt][2]):
                    return {'status': 'fail', 'reason': 'batch sequence mismatch'}
                path = out/record['file']
                if path.name != f'fixture-{f}-outer-{expected_start:05d}.npz' or hashlib.sha256(path.read_bytes()).hexdigest() != record['sha256']:
                    return {'status': 'fail', 'reason': 'batch hash mismatch'}
                seeds = np.array([[_counter_seed(ATTEMPTS[attempt][0], ATTEMPTS[attempt][1], f, r, g)
                                   for g in range(12)] for r in range(expected_start, expected_start+record['count'])], dtype='<u8')
                if hashlib.sha256(seeds.tobytes()).hexdigest() != record['counter_commitment']:
                    return {'status': 'fail', 'reason': 'seed commitment mismatch'}
                with np.load(path, allow_pickle=False) as raw:
                    if set(raw.files) != {'D', 'V', 'df', 'lower', 'upper', 'status'}:
                        return {'status': 'fail', 'reason': 'batch fields mismatch'}
                    D, V, df, lo, hi, status = (raw[k] for k in ('D', 'V', 'df', 'lower', 'upper', 'status'))
                if any(x.shape != (record['count'],) for x in (D,V,df,lo,hi,status)) or status.dtype != bool:
                    return {'status': 'fail', 'reason': 'batch shape mismatch'}
                valid = np.isfinite(D)&np.isfinite(V)&np.isfinite(df)&np.isfinite(lo)&np.isfinite(hi)&(V>0)&(df>0)
                if not np.array_equal(status, valid):
                    return {'status': 'fail', 'reason': 'status mismatch'}
                recomputed = student_t.ppf(.975, df[valid])*np.sqrt(V[valid])
                if not np.all(np.abs(lo[valid]-(D[valid]-recomputed)) <= 1e-10*np.maximum(1, np.abs(lo[valid]))) or not np.all(np.abs(hi[valid]-(D[valid]+recomputed)) <= 1e-10*np.maximum(1, np.abs(hi[valid]))):
                    return {'status': 'fail', 'reason': 'endpoint mismatch'}
                cover = valid&(lo<=0)&(hi>=0)
                check = {'total': len(D), 'coverage': int(cover.sum()), 'null_rejection': int((~cover).sum()),
                         'positive_power': int((valid&(lo+.05>0)).sum()),
                         'negative_power': int((valid&(hi-.05<0)).sum()), 'invalid': int((~valid).sum())}
                if check != record['counts'] or record['shift_coverage_equal'] is not True:
                    return {'status': 'fail', 'reason': 'rate count mismatch'}
                for key, value in check.items():
                    counts[key] += value
                expected_start += record['count']
            if counts != item['counts'] or expected_start != item['completed'] or expected_start > N:
                return {'status': 'fail', 'reason': 'fixture total mismatch'}
            all_counts[str(f)] = counts
        if evidence['status'] != 'complete' or any(v['total'] != N for v in all_counts.values()):
            return {'status': 'incomplete', 'counts': all_counts}
        b = evidence['boundaries']
        guards = {}
        for f, counts in all_counts.items():
            guards[f] = {'coverage': counts['coverage'] >= b['coverage']['pass_count'],
                         'null_rejection': counts['null_rejection'] <= b['null_rejection']['pass_count'],
                         'positive_power': counts['positive_power'] >= b['power']['pass_count'],
                         'negative_power': counts['negative_power'] >= b['power']['pass_count']}
        passed = all(all(v.values()) for v in guards.values())
        return {'status': 'pass' if passed else 'fail', 'guards': guards, 'counts': all_counts}
    except (ValueError, TypeError, KeyError, OSError, IndexError, OverflowError) as exc:
        return {'status': 'fail', 'reason': f'invalid evidence: {exc}'}
