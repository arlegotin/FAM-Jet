"""Approximate crossed inference; software precision never qualifies a population.

The versioned input boundary and scientific gates are described in
docs/statistical-protocol.md. No training or evaluation takes place here.
"""
import math
import hashlib
import json
from pathlib import Path
import numpy as np
from scipy.stats import beta

from famjet.provenance import canonical_hash, canonical_json, derive_seed


def _weights(strata, supplied):
    groups = sorted(set(strata.tolist()))
    weights = {g: 1 / len(groups) for g in groups} if supplied is None else dict(supplied)
    if (set(weights) != set(groups) or any(type(w) not in (int, float) or
            not math.isfinite(w) or w <= 0 for w in weights.values()) or
            not math.isclose(math.fsum(weights.values()), 1., rel_tol=0, abs_tol=1e-12)):
        raise ValueError('complete frozen positive normalized stratum weights required')
    return weights


class _CrossedSampler:
    """Normalized multinomial counts exactly encode repeated Cartesian indices.

    Power-of-two scaling protects representable means from raw count-sum
    overflow. It is a numerical rescaling, not a change of estimand or weights.
    """
    chunk_size = 256

    def __init__(self, d, strata, seed, weights=None):
        d = np.asarray(d, dtype=np.float64)
        strata = np.asarray(strata)
        if (d.ndim != 2 or min(d.shape) < 1 or not np.isfinite(d).all() or
                strata.shape != (d.shape[0],) or
                any(type(g) is not str or not g for g in strata.tolist())):
            raise ValueError('complete finite history-by-paired-seed matrix and string strata required')
        if type(seed) is not int or not 0 <= seed < 2**63:
            raise ValueError('nonnegative signed-64-bit seed required')
        self.weights = _weights(strata, weights)
        magnitude = float(np.max(np.abs(d)))
        self.scale = math.ldexp(1., math.frexp(magnitude)[1] - 1) if magnitude else 1.
        self.data = {g: d[strata == g] / self.scale for g in self.weights}
        # Center each stratum before reduction: constants (including max-float)
        # stay exact instead of accumulating normalization rounding into overflow.
        self.offsets = {g: float(x.min() / 2 + x.max() / 2) for g, x in self.data.items()}
        self.centered = {g: x - self.offsets[g] for g, x in self.data.items()}
        self.seed, self.s = seed, d.shape[1]
        self.streams, self.axis_seeds = {}, {}
        self.mean_scaled = math.fsum(w * (self.offsets[g] + float((x / x.size).sum()))
                                     for g, w in self.weights.items() for x in [self.centered[g]])

    def _rng(self, batch, axis, stratum=None):
        key = canonical_hash({'batch': batch, 'axis': axis, 'stratum': stratum})
        if key not in self.streams:
            seed = derive_seed(self.seed, 'crossed-v1', key)
            self.axis_seeds[key] = seed
            self.streams[key] = np.random.default_rng(seed)
        return self.streams[key]

    def append(self, batch, count):
        chunks = []
        for start in range(0, count, self.chunk_size):
            n = min(self.chunk_size, count - start)
            # One common paired-seed count vector across every stratum.
            u = self._rng(batch, 'seed').multinomial(self.s, np.full(self.s, 1 / self.s), size=n) / self.s
            means = np.zeros(n)
            for g, x in self.centered.items():
                h = len(x)
                w = self._rng(batch, 'history', g).multinomial(h, np.full(h, 1 / h), size=n) / h
                means += self.weights[g] * (self.offsets[g] + np.sum((w @ x) * u, axis=1))
            with np.errstate(over='raise', invalid='raise'):
                try:
                    chunks.append(means * self.scale)
                except FloatingPointError as exc:
                    raise ValueError('nonrepresentable crossed mean') from exc
        return np.concatenate(chunks)


def _p_bounds(k, n, error_budget, family_size):
    """Clopper-Pearson conditional tail bounds, Bonferroni over 7 stages × m.

    The budget must be explicitly frozen by the caller. No scientific default
    is supplied. Transform bounds to the specified plus-one p convention.
    """
    if (type(error_budget) not in (int, float) or not 0 < error_budget < 1 or
            type(family_size) is not int or family_size < 1):
        raise ValueError('explicit p-MC error budget and family size required')
    tail = error_budget / (7 * family_size * 2)
    lower = 0. if k == 0 else float(beta.ppf(tail, k, n - k + 1))
    upper = 1. if k == n else float(beta.ppf(1 - tail, k + 1, n - k))
    return [(1 + n * lower) / (n + 1), (1 + n * upper) / (n + 1)]


def crossed_interval(d: np.ndarray, strata: np.ndarray, seed: int, draws: int, *,
                     stratum_weights=None, p_mc_error_budget=None, p_mc_family_size=1) -> dict:
    """Literal adaptive 95% percentile procedure, retaining every draw and stage.

    `draws` is the mandated initial total (2000), not a selectable favorable
    fixed budget. Four persistent independent batches append equal increments.
    """
    if type(draws) is not int or draws != 2000:
        raise ValueError('initial draws must be 2000 under the frozen doubling rule')
    sampler = _CrossedSampler(d, strata, seed, stratum_weights)
    if p_mc_error_budget is not None:
        _p_bounds(0, draws, p_mc_error_budget, p_mc_family_size)
    zero = bool(np.all(np.asarray(d) == 0))
    batches = [np.empty(0) for _ in range(4)]
    stages = []
    total = draws
    while True:
        for b in range(4):
            batches[b] = np.concatenate([batches[b], sampler.append(b, total // 4 - len(batches[b]))])
        scaled = [b / sampler.scale for b in batches]
        pooled = np.concatenate(scaled)
        endpoints = np.quantile(pooled, [.025, .975], method='linear')
        batch_ends = np.array([np.quantile(b, [.025, .975], method='linear') for b in scaled])
        se = batch_ends.std(axis=0, ddof=1) / math.sqrt(4)
        width = float(endpoints[1] - endpoints[0])
        met = bool(np.all(se < .01 * width))
        # Width can genuinely exceed binary64 even when both endpoints exist.
        # Never serialize infinity or silently reinterpret that statistic.
        with np.errstate(over='raise', invalid='raise'):
            try:
                interval = (endpoints * sampler.scale).tolist()
                stage = {'draws': total, 'batch_endpoints': (batch_ends * sampler.scale).tolist(),
                         'endpoint_se': (se * sampler.scale).tolist(),
                         'width': float(np.float64(width) * sampler.scale), 'met': met}
            except FloatingPointError as exc:
                raise ValueError('nonrepresentable endpoint statistic') from exc
        stages.append(stage)
        if met or zero or total == 128000:
            break
        total *= 2
    observed = sampler.mean_scaled
    k = int(np.count_nonzero(np.abs(pooled - observed) >= abs(observed)))
    p = (1 + k) / (total + 1)
    bounds = None if p_mc_error_budget is None else _p_bounds(k, total, p_mc_error_budget, p_mc_family_size)
    return {'schema_version': 1, 'mean': float(observed * sampler.scale), 'interval': interval,
            'pvalue': p, 'exceedances': k, 'draws': total, 'seed': seed,
            'stratum_weights': sampler.weights, 'resample_means': np.concatenate(batches).tolist(),
            'stages': stages, 'endpoint_mc': 'degenerate_zero' if zero else 'met' if met else 'cap_unmet',
            'zero_width_non_aa': width == 0 and not zero,
            'secondary_p_mc': 'not_assessed',  # Bounds alone do not assess a frozen Holm family.
            'p_mc_bounds': bounds, 'p_mc_error_budget': p_mc_error_budget,
            'strong_claim_allowed': False,  # Requires population/design gates, separately.
            'rng': {'algorithm': 'numpy.PCG64.multinomial', 'numpy_version': np.__version__,
                    'key_version': 'crossed-v1', 'root_seed': seed, 'axis_seeds': sampler.axis_seeds,
                    'chunk_size': sampler.chunk_size, 'batch_order': [0, 1, 2, 3],
                    'append_policy': 'equal_increments_at_total_doubling', 'quantile_method': 'linear',
                    'arithmetic': 'power_of_two_scaled_stratum_centered_normalized_multinomial_counts'},
            'limitations': {'independent_units': len(d), 'paired_training_replicates': sampler.s,
                            'coverage': 'unqualified_approximate',
                            'seed_cluster_scarcity': 'report_actual_counts_no_universal_sufficiency'}}


def holm(pvalues: dict[str, float], alpha: float = .05) -> dict:
    """Nominal Holm step-down, stable name tie-break; p calibration is external."""
    if not 0 < alpha < 1 or any(type(k) is not str or not k or
            type(p) not in (int, float) or not math.isfinite(p) or not 0 <= p <= 1
            for k, p in pvalues.items()):
        raise ValueError('finite named probabilities and alpha in (0,1) required')
    result, previous, active = {}, 0., True
    for i, (name, p) in enumerate(sorted(pvalues.items(), key=lambda item: (item[1], item[0]))):
        factor = len(pvalues) - i
        adjusted = min(1., max(previous, factor * p))
        active = active and p <= alpha / factor
        result[name] = {'pvalue': p, 'adjusted_pvalue': adjusted,
                        'reject': bool(active), 'threshold': alpha / factor, 'rank': i + 1}
        previous = adjusted
    return result


def holm_mc_guard(pvalues, bounds, alpha=.05):
    """Keep nominal Holm; withhold strong rejection when bounds disagree."""
    nominal = holm(pvalues, alpha)
    if bounds is None or any(bounds.get(k) is None for k in pvalues):
        return {'nominal': nominal, 'status': 'not_assessed',
                'strong_rejections': {k: False for k in pvalues}}
    if set(bounds) != set(pvalues) or any(len(b) != 2 or not 0 <= b[0] <= b[1] <= 1 for b in bounds.values()):
        raise ValueError('complete ordered p-MC bounds required')
    lower = holm({k: b[0] for k, b in bounds.items()}, alpha)
    upper = holm({k: b[1] for k, b in bounds.items()}, alpha)
    agreement = all(lower[k]['reject'] == upper[k]['reject'] for k in pvalues)
    return {'nominal': nominal, 'lower_bound_holm': lower, 'upper_bound_holm': upper,
            'status': 'adequate' if agreement else 'unresolved',
            'strong_rejections': {k: bool(agreement and nominal[k]['reject'] and upper[k]['reject']) for k in pvalues}}


def unfilled_calibration_policy() -> dict:
    """Explicit unknowns: these are decisions for prospective approval, not defaults."""
    return dict(schema_version=1, **{key: None for key in (
        'scope_id', 'source_hash', 'coverage_floor', 'type1_ceiling', 'fwer_ceiling',
        'power_floor', 'outer_n', 'outer_error_budget', 'domain', 'required_cells',
        'selection_stream', 'validation_stream', 'nuisance_authorization')})


def _nonempty_identifier(value):
    return type(value) is str and bool(value.strip())


def evaluate_gate(evidence: dict, frozen_policy: dict) -> dict:
    """Fail closed; recompute scoped calibration decisions from retained counts.

    No qualifying simulations are supplied or executed by this module. Binomial
    bounds spend the declared outer error budget across all required cells.
    Allocation selection and validation must use distinct frozen streams.
    """
    reasons, cells = [], {}
    policy_hash = canonical_hash(frozen_policy)
    required = set(unfilled_calibration_policy()) - {'nuisance_authorization'}
    missing = sorted(k for k in required if frozen_policy.get(k) is None)
    if missing:
        reasons.append('unfilled calibration policy: ' + ', '.join(missing))
    else:
        p = frozen_policy
        valid = (all(_nonempty_identifier(p[k]) for k in
                     ('scope_id', 'source_hash', 'selection_stream', 'validation_stream')) and
                 p['schema_version'] == 1 and p['scope_id'] == evidence.get('scope_id') and
                 p['source_hash'] == evidence.get('source_hash') and
                 type(p['outer_n']) is int and p['outer_n'] > 0 and
                 type(p['outer_error_budget']) in (int, float) and 0 < p['outer_error_budget'] < 1 and
                 p['domain'] and p['selection_stream'] != p['validation_stream'] and
                 all(type(p[k]) in (int, float) and 0 <= p[k] <= 1 for k in
                     ('coverage_floor', 'type1_ceiling', 'fwer_ceiling', 'power_floor')) and
                 isinstance(p['required_cells'], list) and bool(p['required_cells']))
        valid = valid and {c.get('metric') for c in p['required_cells']} == {'coverage', 'type1', 'fwer', 'power'}
        if not valid:
            reasons.append('invalid or mismatched frozen calibration policy')
        else:
            specs = p['required_cells']
            records = evidence.get('calibration_cells', [])
            ids = [r.get('cell_id') for r in records]
            spec_ids = [s.get('cell_id') for s in specs]
            if len(set(ids)) != len(ids) or len(set(spec_ids)) != len(spec_ids) or set(ids) - set(spec_ids):
                reasons.append('duplicate or undeclared calibration cells')
            else:
                for spec in specs:
                    cid = spec.get('cell_id')
                    record = next((r for r in records if r.get('cell_id') == cid), None)
                    metric = spec.get('metric')
                    if record is None:
                        cells[cid] = {'status': 'not_run'}
                        continue
                    n, k = record.get('trials'), record.get('successes')
                    if (metric not in ('coverage', 'type1', 'fwer', 'power') or
                            type(n) is not int or n != p['outer_n'] or type(k) is not int or not 0 <= k <= n or
                            any(record.get(key) != value for key, value in (
                                ('scope_id', p['scope_id']), ('source_hash', p['source_hash']),
                                ('policy_hash', policy_hash), ('rng_stream', p['validation_stream']),
                                ('fixture_hash', spec.get('fixture_hash')), ('allocation', spec.get('allocation')))) or
                            not spec.get('fixture_hash') or not spec.get('allocation')):
                        cells[cid] = {'status': 'unresolved', 'reason': 'incomplete/mismatched calibration evidence'}
                        continue
                    tail = p['outer_error_budget'] / (2 * len(specs))
                    lower = 0. if k == 0 else float(beta.ppf(tail, k, n - k + 1))
                    upper = 1. if k == n else float(beta.ppf(1 - tail, k + 1, n - k))
                    minimum = metric in ('coverage', 'power')
                    threshold = p[metric + ('_floor' if minimum else '_ceiling')]
                    qualified = lower >= threshold if minimum else upper <= threshold
                    rejected = upper < threshold if minimum else lower > threshold
                    cells[cid] = {'status': 'qualified' if qualified else 'rejected' if rejected else 'unresolved',
                                  'successes': k, 'trials': n, 'bounds': [lower, upper],
                                  'metric': metric, 'threshold': threshold, 'evidence': record}
    statuses = [c['status'] for c in cells.values()]
    calibration = ('rejected' if 'rejected' in statuses else
                   'qualified' if statuses and all(s == 'qualified' for s in statuses) and not reasons else
                   'not_run' if not statuses or all(s == 'not_run' for s in statuses) else 'unresolved')
    if calibration != 'qualified': reasons.append('population calibration is ' + calibration)
    if evidence.get('implementation') != 'pass': reasons.append('implementation not accepted')
    endpoint = evidence.get('endpoint_mc', [])
    if not endpoint or any(s not in ('met', 'degenerate_zero') for s in endpoint):
        reasons.append('endpoint Monte Carlo precision unresolved')
    if evidence.get('secondary_p_mc') != 'adequate': reasons.append('secondary p Monte Carlo precision unresolved')
    for key in ('resource_status', 'baseline_status', 'nuisance_domain_status'):
        if evidence.get(key) != 'pass': reasons.append(key + ' not accepted')
    allowed = not reasons
    auth = frozen_policy.get('nuisance_authorization')
    nuisance = bool(evidence.get('implementation') == 'pass' and isinstance(auth, dict) and
                    all(_nonempty_identifier(evidence.get(k)) and _nonempty_identifier(auth.get(k))
                        for k in ('scope_id', 'source_hash')) and
                    auth.get('scope_id') == evidence.get('scope_id') and
                    auth.get('source_hash') == evidence.get('source_hash') and _nonempty_identifier(auth.get('authority')) and
                    auth.get('status') == 'authorized' and isinstance(auth.get('allocation'), dict) and auth['allocation'] and
                    all(type(auth.get(k)) in (int, float) and math.isfinite(auth[k]) and auth[k] > 0
                        for k in ('max_seconds', 'max_bytes')))
    return {'implementation': evidence.get('implementation', 'not_run'), 'calibration': calibration,
            'calibration_cells': cells, 'endpoint_mc': endpoint,
            'secondary_p_mc': evidence.get('secondary_p_mc', 'not_assessed'),
            'scope_id': evidence.get('scope_id'), 'policy_hash': policy_hash,
            'eligibility': 'eligible' if allowed else 'inconclusive' if calibration == 'rejected' else 'blocked',
            'unresolved_reasons': reasons, 'nuisance_only_allowed': nuisance,
            'confirmation_allowed': allowed}


def _read_json(path):
    def reject_constant(value):
        raise ValueError('nonfinite JSON constant: ' + value)
    def unique_pairs(pairs):
        out = {}
        for key, value in pairs:
            if key in out: raise ValueError('duplicate JSON key: ' + key)
            out[key] = value
        return out
    return json.loads(Path(path).read_text(), parse_constant=reject_constant, object_pairs_hook=unique_pairs)


def _require(condition, message):
    if not condition: raise ValueError(message)


def _sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def _contract(manifest, manifest_path, unblinded):
    """Validate frozen inventory and administrative release BEFORE reading scores."""
    from famjet.eval.isolation import source_identity
    m = manifest
    required = {'schema_version', 'scope_id', 'namespace', 'test_only', 'score_manifest_hash',
                'source_hash', 'statistics_hash', 'scoring_policy', 'methods', 'expected_runs', 'units', 'comparisons',
                'files', 'release_record', 'calibration_policy', 'calibration_evidence', 'p_mc_error_budget'}
    _require(required <= m.keys(), 'incomplete versioned analysis manifest')
    _require(m['schema_version'] == 1 and _nonempty_identifier(m['scope_id']), 'invalid analysis schema/scope')
    _require(type(m['test_only']) is bool and m['namespace'] == ('test_only' if m['test_only'] else
             'protected_replication' if m['namespace'] == 'protected_replication' else 'protected_confirmation'),
             'invalid test-only/protected namespace')
    _require(m['source_hash'] == source_identity(), 'analysis source hash mismatch')
    methods = m['methods']
    _require(methods and len(set(methods)) == len(methods) and
             all(type(s) is str and s for s in methods), 'explicit unique expected methods required')
    policy = m['scoring_policy']
    _require(policy.get('version') == 2 and policy.get('expected_inventory'), 'frozen v2 scoring policy required')
    _require(bool(policy['task_weights']) and set(policy['task_weights']) == set(policy['primary_tasks']) and
             all(math.isclose(w, 1 / len(policy['task_weights']), rel_tol=0, abs_tol=1e-12)
                 for w in policy['task_weights'].values()), 'primary tasks require equal frozen weights')
    inventory = policy['expected_inventory']
    # Compare the actual declared inventory, not the weight keys to themselves.
    _weights(np.array([c['regime'] for c in inventory]), policy['regime_weights'])
    histories = {c['history_id'] for c in inventory}
    replicates = {c['replicate'] for c in inventory}
    _require(all(type(s) is int and s >= 0 for s in replicates), 'explicit paired replicate IDs required')
    _require(len(inventory) == len(histories) * len(replicates) and
             {(c['history_id'], c['replicate']) for c in inventory} ==
             {(h, s) for h in histories for s in replicates}, 'incomplete or duplicate expected crossed matrix')
    for cell in inventory:
        _require(type(cell['history_id']) is str and bool(cell['history_id']) and
                 cell['regime'] in policy['regime_weights'] and
                 set(cell['tasks']) == set(policy['task_weights']) and
                 all(queries and len(set(queries)) == len(queries) and
                     all(type(q) is int and q >= 0 for q in queries) for queries in cell['tasks'].values()),
                 'invalid expected query/task/history inventory')
    expected_run_cells = {(method, s) for method in methods for s in replicates}
    runs = m['expected_runs']
    _require(len({r['run_id'] for r in runs}) == len(runs) == len(expected_run_cells) and
             {(r['method'], r['replicate']) for r in runs} == expected_run_cells,
             'incomplete expected paired run inventory')
    units = m['units']
    members = [h for u in units for h in u['history_ids']]
    _require(units and len({u['unit_id'] for u in units}) == len(units) and
             all(u['history_ids'] for u in units) and len(set(members)) == len(members) and
             set(members) == histories, 'complete disjoint expected history/cluster units required')
    for u in units:
        _require(all(c['regime'] == u['stratum'] for c in inventory if c['history_id'] in u['history_ids']),
                 'cluster/history stratum mismatch')
    _weights(np.array([u['stratum'] for u in units]), policy['regime_weights'])
    comparisons = m['comparisons']
    _require(sum(c['role'] == 'primary' for c in comparisons.values()) == 1, 'exactly one frozen primary comparison required')
    _require(set(methods) == {v for c in comparisons.values() for v in c['pair']}, 'undeclared or unused comparison method')
    for c in comparisons.values():
        _require(len(c['pair']) == 2 and c['pair'][0] != c['pair'][1] and
                 c['role'] in ('primary', 'secondary', 'exploratory') and
                 type(c['seed']) is int and 0 <= c['seed'] < 2**63, 'invalid frozen comparison/pair/seed')
    secondary_count = sum(c['role'] == 'secondary' for c in comparisons.values())
    _require(m['test_only'] or not secondary_count or m['p_mc_error_budget'] is not None,
             'scientific secondary family requires a frozen p-MC error budget')
    if m['p_mc_error_budget'] is not None:
        _p_bounds(0, 2000, m['p_mc_error_budget'], max(1, secondary_count))
    _require({f['role'] for f in m['files']} == {'source', 'dependencies', 'data', 'config', 'weights', 'statistics'},
             'missing source/dependency/data/config/weight/statistics commitments')
    for record in m['files']:
        _require(_sha(manifest_path.parent / record['path']) == record['sha256'], 'frozen input file hash mismatch: ' + record['path'])
        if record['role'] == 'statistics':
            _require(canonical_hash(_read_json(manifest_path.parent / record['path'])) == m['statistics_hash'],
                     'frozen training statistics content/hash mismatch')
    release = _read_json(manifest_path.parent / m['release_record'])
    _require(release['schema_version'] == 1 and release['manifest_hash'] == canonical_hash(m) and
             release['scope_id'] == m['scope_id'] and release['rows_sha256'] == _sha(unblinded) and
             release['expected_runs_hash'] == canonical_hash(runs), 'unblind release/hash mismatch')
    _require(release['mode'] == ('test_only' if m['test_only'] else 'legitimate') and
             release['authorization']['authority'] == ('test_only' if m['test_only'] else 'task21_unblind_v1') and
             release['authorization']['recorded_at'], 'legitimate unblinding or explicit test-only release required')
    _require(len(release['runs']) == len(runs) and
             {r['run_id'] for r in release['runs']} == {r['run_id'] for r in runs},
             'incomplete released run inventory')
    for expected in runs:
        record = next(r for r in release['runs'] if r['run_id'] == expected['run_id'])
        _require(all(record[k] == v for k, v in expected.items()) and record['status'] == 'completed' and
                 type(record.get('rows_hash')) is str and len(record['rows_hash']) == 64,
                 'incomplete or changed released run record')
    design = m.get('design_evidence', {})
    _require(design.get('implementation') != 'pass' or design.get('implementation_source_hash') == m['source_hash'],
             'implementation acceptance source hash mismatch')
    base_evidence = {**design, 'implementation': design.get('implementation', 'not_run'),
                     'calibration_cells': m['calibration_evidence'], 'scope_id': m['scope_id'],
                     'source_hash': m['source_hash']}
    preliminary = evaluate_gate(base_evidence, m['calibration_policy'])
    if not m['test_only']:
        _require(preliminary['calibration'] == 'qualified' and base_evidence['implementation'] == 'pass' and
                 all(base_evidence.get(k) == 'pass' for k in
                 ('resource_status', 'baseline_status', 'nuisance_domain_status')),
                 'scientific unblinding blocked by calibration/design eligibility')
    return release, base_evidence


def analyze_confirmation(manifest: Path, unblinded: Path, out: Path) -> dict:
    """Analyze complete v2 score rows, or write a retained fail-closed error report.

    `out` is a fresh JSON FILE. Raw effects/draws, all scored-row diagnostics and
    input hashes remain auditable. Inputs are never rewritten or overwritten.
    """
    from famjet.eval.metrics import aggregate_scores, history_effects, history_effects_inventory, _loss_mean
    manifest, unblinded, out = Path(manifest), Path(unblinded), Path(out)
    _require(not out.exists() and out.resolve() not in (manifest.resolve(), unblinded.resolve()), 'fresh analysis output path required')
    report = {'schema_version': 1, 'status': 'blocked', 'errors': [], 'comparisons': {}, 'methods': {},
              'gate': {'confirmation_allowed': False, 'nuisance_only_allowed': False, 'eligibility': 'blocked'},
              'strong_primary_rejection': False}
    try:
        m = _read_json(manifest)
        release, evidence = _contract(m, manifest, unblinded)
        rows = _read_json(unblinded)
        report.update(manifest_hash=canonical_hash(m), rows_sha256=_sha(unblinded), row_count=len(rows),
                      scope_id=m['scope_id'], namespace=m['namespace'], source_hash=m['source_hash'])
        _require(rows and {r['method'] for r in rows} == set(m['methods']), 'complete expected method inventory required')
        for row in rows:
            _require(row['schema_version'] == 2 and row['manifest_hash'] == m['score_manifest_hash'] and
                     row['statistics_hash'] == m['statistics_hash'] and
                     row['target_semantics'] == 'observed_event_targets_v2' and
                     row['policy'] == m['scoring_policy'] and row['policy_hash'] == canonical_hash(m['scoring_policy']),
                     'row/frozen scoring policy or provenance mismatch')
        for expected in m['expected_runs']:
            record = next(r for r in release['runs'] if r['run_id'] == expected['run_id'])
            _require(all(record[k] == v for k, v in expected.items()) and record['status'] == 'completed' and
                     record['rows_hash'] == canonical_hash([r for r in rows if
                         r['method'] == expected['method'] and r['replicate'] == expected['replicate']]),
                     'incomplete or changed released run record')
        for method in m['methods']:
            report['methods'][method] = aggregate_scores([r for r in rows if r['method'] == method])
        secondary_count = sum(c['role'] == 'secondary' for c in m['comparisons'].values())
        for name, comparison in m['comparisons'].items():
            pair = tuple(comparison['pair'])
            inventory = history_effects_inventory(rows, pair)
            effects = history_effects(rows, pair)
            positions = {h: i for i, h in enumerate(inventory['history_order'])}
            # Equal member histories within each declared independent temporal unit.
            # Every station in a cluster travels with that one unit resample.
            units = m['units']
            d = np.array([[_loss_mean(effects[positions[h], s] for h in u['history_ids'])
                           for s in range(effects.shape[1])] for u in units])
            result = crossed_interval(d, np.array([u['stratum'] for u in units]), comparison['seed'], 2000,
                                      stratum_weights=m['scoring_policy']['regime_weights'],
                                      p_mc_error_budget=m['p_mc_error_budget'] if comparison['role'] == 'secondary' else None,
                                      p_mc_family_size=max(1, secondary_count))
            result.update(pair=list(pair), role=comparison['role'], orientation='baseline_minus_candidate',
                          effects=d.tolist(), history_effects=effects.tolist(),
                          history_order=inventory['history_order'], replicate_order=inventory['replicate_order'],
                          unit_order=[u['unit_id'] for u in units], units=units,
                          unit_aggregation='equal_member_histories_within_declared_unit')
            report['comparisons'][name] = result
        secondaries = {k: r for k, r in report['comparisons'].items() if r['role'] == 'secondary'}
        guard = holm_mc_guard({k: r['pvalue'] for k, r in secondaries.items()},
                              {k: r['p_mc_bounds'] for k, r in secondaries.items()})
        report['secondary'] = guard
        for result in secondaries.values():
            result['secondary_p_mc'] = guard['status']
        evidence.update(endpoint_mc=[r['endpoint_mc'] for r in report['comparisons'].values() if r['role'] != 'exploratory'],
                        secondary_p_mc=guard['status'])
        report['gate'] = evaluate_gate(evidence, m['calibration_policy'])
        if m['test_only']:
            report['gate'].update(confirmation_allowed=False, nuisance_only_allowed=False, eligibility='blocked')
            report['gate']['unresolved_reasons'].append('test-only scope cannot authorize confirmation or nuisance execution')
        allowed = report['gate']['confirmation_allowed'] and not m['test_only']
        primary = next(r for r in report['comparisons'].values() if r['role'] == 'primary')
        report['nominal_primary_null_excluded'] = primary['interval'][0] > 0 or primary['interval'][1] < 0
        report['strong_primary_rejection'] = bool(allowed and report['nominal_primary_null_excluded'])
        report['strong_secondary_rejections'] = {k: bool(allowed and v) for k, v in guard['strong_rejections'].items()}
        report['status'] = 'analyzed_test_only' if m['test_only'] else 'analyzed' if allowed else 'analyzed_inconclusive'
        report['raw_score_rows'] = rows
    except (ValueError, KeyError, TypeError, OSError, OverflowError) as exc:
        report['errors'].append({'type': type(exc).__name__, 'message': str(exc)})
        report['gate']['confirmation_allowed'] = False
        report['gate']['nuisance_only_allowed'] = False
    out.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive creation prevents clobbering a concurrent or earlier analysis.
    with out.open('xb') as handle:
        handle.write(canonical_json(report))
    return report
