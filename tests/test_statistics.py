"""Deterministic software controls, never population-calibration evidence."""
import math
import numpy as np
import pytest
from copy import deepcopy
from dataclasses import replace
import hashlib
import json
from pathlib import Path


def test_cartesian_draws_match_explicit_duplicate_index_oracle():
    # Catches cell-pair resampling, wrong normalizers and non-shared seed draws.
    from famjet.analysis.statistics import _CrossedSampler
    from famjet.provenance import derive_seed, canonical_hash
    d = np.array([[1., 3.], [5., 11.], [20., 40.]])
    sampler = _CrossedSampler(d, np.array(['a', 'a', 'b']), 17, {'a': .25, 'b': .75})
    got = sampler.append(0, 12)
    def rng(axis, stratum=None):
        return np.random.default_rng(derive_seed(17, 'crossed-v1', canonical_hash(
            {'batch': 0, 'axis': axis, 'stratum': stratum})))
    seeds = rng('seed').multinomial(2, [.5, .5], size=12)
    histories = rng('history', 'a').multinomial(2, [.5, .5], size=12)
    expected = []
    for h, s in zip(histories, seeds):
        hi = np.repeat(np.arange(2), h)
        si = np.repeat(np.arange(2), s)
        expected.append(.25 * np.mean(d[np.ix_(hi, si)]) + .75 * np.mean(d[2, si]))
    np.testing.assert_allclose(got, expected, rtol=1e-14)


def test_shared_seed_axis_across_strata_cancels_opposite_seed_effects():
    from famjet.analysis.statistics import crossed_interval
    r = crossed_interval(np.array([[-1., 1.], [1., -1.]]), np.array(['a', 'b']), 7, 2000)
    assert r['mean'] == 0 and r['interval'] == [0, 0]
    assert r['endpoint_mc'] == 'cap_unmet' and r['draws'] == 128000
    assert r['zero_width_non_aa'] and not r['strong_claim_allowed']


def test_exact_zero_aa_is_only_automatic_degenerate_precision_pass():
    from famjet.analysis.statistics import crossed_interval
    r = crossed_interval(np.zeros((3, 2)), np.array(['a', 'a', 'b']), 3, 2000)
    assert r['mean'] == 0 and r['interval'] == [0, 0] and r['pvalue'] == 1
    assert r['endpoint_mc'] == 'degenerate_zero' and r['draws'] == 2000
    assert not r['strong_claim_allowed']  # population calibration is separate
    c = crossed_interval(np.ones((1, 1)), np.array(['a']), 3, 2000)
    assert c['endpoint_mc'] == 'cap_unmet' and c['draws'] == 128000


def test_both_history_and_seed_axes_change_uncertainty():
    from famjet.analysis.statistics import crossed_interval
    strata = np.array(['a', 'a'])
    h = crossed_interval(np.array([[-2., -2.], [2., 2.]]), strata, 19, 2000)
    s = crossed_interval(np.array([[-3., 3.], [-3., 3.]]), strata, 19, 2000)
    both = crossed_interval(np.array([[-5., 1.], [-1., 5.]]), strata, 19, 2000)
    assert h['interval'] == [-2, 2] and s['interval'] == [-3, 3]
    assert both['interval'] == [-5, 5]


def test_frozen_weights_do_not_follow_stratum_sample_frequency():
    from famjet.analysis.statistics import crossed_interval
    d = np.array([[0., 2.], [0., 2.], [8., 10.]])
    default = crossed_interval(d, np.array(['a', 'a', 'b']), 8, 2000)
    weighted = crossed_interval(d, np.array(['a', 'a', 'b']), 8, 2000,
                                stratum_weights={'a': .25, 'b': .75})
    assert default['mean'] == 5 and weighted['mean'] == 7
    assert weighted['stratum_weights'] == {'a': .25, 'b': .75}


def test_centered_absolute_plusone_p_and_linear_percentiles_are_literal():
    from famjet.analysis.statistics import crossed_interval
    r = crossed_interval(np.array([[-2., 1.], [3., 7.]]), np.array(['a', 'a']), 33, 2000)
    raw = np.array(r['resample_means'])
    np.testing.assert_allclose(r['interval'], np.quantile(raw, [.025, .975], method='linear'))
    k = np.count_nonzero(np.abs(raw - 2.25) >= 2.25)
    assert r['pvalue'] == (1 + k) / (r['draws'] + 1)
    assert r['exceedances'] == k and r['secondary_p_mc'] == 'not_assessed'
    assert r['rng']['quantile_method'] == 'linear'


def test_endpoint_diagnostics_use_four_independent_batches_and_strict_rule():
    from famjet.analysis.statistics import crossed_interval
    r = crossed_interval(np.arange(35.).reshape(7, 5), np.array(['a'] * 7), 29, 2000)
    assert [s['draws'] for s in r['stages']] == [2000 * 2**i for i in range(len(r['stages']))]
    for stage in r['stages']:
        ends = np.asarray(stage['batch_endpoints'])
        np.testing.assert_allclose(stage['endpoint_se'], ends.std(axis=0, ddof=1) / math.sqrt(4))
        assert stage['met'] == bool(np.all(np.asarray(stage['endpoint_se']) < .01 * stage['width']))
    assert r['draws'] in (2000, 4000, 8000, 16000, 32000, 64000, 128000)
    assert len(r['resample_means']) == r['draws']
    assert len(set(r['rng']['axis_seeds'].values())) == len(r['rng']['axis_seeds'])


def test_finite_extreme_means_do_not_overflow_raw_count_sums():
    from famjet.analysis.statistics import crossed_interval
    d = np.array([[1.e308, 1.e308], [1.e308, 1.e308]])
    r = crossed_interval(d, np.array(['a', 'a']), 6, 2000)
    assert r['mean'] == 1.e308 and r['interval'] == [1.e308, 1.e308]
    assert np.isfinite(r['resample_means']).all()


def test_supported_extreme_constant_at_binary64_limit_has_finite_convex_means():
    from famjet.analysis.statistics import crossed_interval
    maximum = np.finfo(float).max
    r = crossed_interval(np.full((7, 3), maximum), np.array(['a'] * 7), 6, 2000)
    assert r['mean'] == maximum and r['interval'] == [maximum, maximum]
    assert r['endpoint_mc'] == 'cap_unmet'


@pytest.mark.parametrize('d,strata,weights', [
    ([[1., np.nan]], ['a'], None), ([[np.inf]], ['a'], None),
    ([[1., 2.]], ['a', 'b'], None), ([], [], None),
    ([[1.]], ['a'], {'b': 1.}), ([[1.]], ['a'], {'a': .5}),
    ([[1.]], ['a'], {'a': -1.}),
])
def test_missing_nonfinite_or_changed_weight_inventory_is_rejected(d, strata, weights):
    from famjet.analysis.statistics import crossed_interval
    with pytest.raises(ValueError):
        crossed_interval(np.array(d), np.array(strata), 1, 2000, stratum_weights=weights)


def test_holm_stepdown_stops_and_retains_adjusted_point_values():
    from famjet.analysis.statistics import holm
    r = holm({'a': .01, 'b': .03, 'c': .04})
    assert {k: v['reject'] for k, v in r.items()} == {'a': True, 'b': False, 'c': False}
    assert {k: v['adjusted_pvalue'] for k, v in r.items()} == {'a': .03, 'b': .06, 'c': .06}
    assert holm({}) == {}
    with pytest.raises(ValueError): holm({'a': float('nan')})


def test_p_mc_bounds_preserve_plusone_and_spend_across_stages_and_family():
    from famjet.analysis.statistics import _p_bounds, holm_mc_guard
    lo, hi = _p_bounds(0, 2000, .01, 3)
    assert lo == 1 / 2001 and .004 < hi < .006
    guard = holm_mc_guard({'a': .01, 'b': .06}, {'a': [.009, .011], 'b': [.04, .07]})
    assert guard['status'] == 'unresolved' and not guard['strong_rejections']['b']
    assert guard['nominal']['a']['reject'] and not guard['nominal']['b']['reject']


def analysis_case(tmp_path, duplicate_queries=False):
    """Actual v2 scorer, invented software-only predictions/seeds, no model run."""
    import torch
    from test_metrics import case
    from famjet.eval.metrics import score_predictions
    from famjet.eval.isolation import source_identity
    from famjet.provenance import canonical_hash, canonical_json
    from famjet.analysis.statistics import unfilled_calibration_policy
    _, stats, policy = case()
    query_ids = [0, 1] if duplicate_queries else [0]
    policy['expected_inventory'] = [
        {'history_id': h, 'replicate': s, 'regime': 'r', 'tasks': {'mean': query_ids}}
        for h in ['station-a', 'station-b', 'station-c', 'station-d'] for s in [0, 1]]
    rows = []
    for cell in policy['expected_inventory']:
        for method in ['baseline', 'candidate']:
            for q in query_ids:
                b, _, _ = case(prediction=(4. if method == 'baseline' else 2.,))
                b = replace(b, history_ids=(cell['history_id'],), query_ids=torch.tensor([[q]]))
                b.metadata['scoring_v2'].update(method=method, replicate=cell['replicate'])
                # Deliberately exercise an explicitly scored failed prediction.
                if method == 'baseline' and cell['history_id'] == 'station-a':
                    b.failure[:] = True
                rows.extend(score_predictions(b, stats, policy))
    asset = tmp_path / 'frozen-test-only-input.json'
    asset.write_bytes(canonical_json(stats))
    runs = [{'run_id': f'test-{method}-{s}', 'method': method, 'replicate': s}
            for method in ['baseline', 'candidate'] for s in [0, 1]]
    manifest = {
        'schema_version': 1, 'scope_id': 'software-only-cluster-control',
        'namespace': 'test_only', 'test_only': True, 'score_manifest_hash': 'a' * 64,
        'source_hash': source_identity(), 'scoring_policy': policy,
        'statistics_hash': canonical_hash(stats),
        'methods': ['baseline', 'candidate'], 'expected_runs': runs,
        'units': [{'unit_id': 'cluster-0', 'stratum': 'r', 'history_ids': ['station-a', 'station-b']},
                  {'unit_id': 'cluster-1', 'stratum': 'r', 'history_ids': ['station-c', 'station-d']}],
        'comparisons': {'primary': {'pair': ['baseline', 'candidate'], 'role': 'primary', 'seed': 73},
                        'secondary': {'pair': ['candidate', 'baseline'], 'role': 'secondary', 'seed': 74}},
        'files': [{'role': role, 'path': asset.name, 'sha256': hashlib.sha256(asset.read_bytes()).hexdigest()}
                  for role in ['source', 'dependencies', 'data', 'config', 'weights', 'statistics']],
        'release_record': 'release.json', 'calibration_policy': unfilled_calibration_policy(),
        'calibration_evidence': [], 'p_mc_error_budget': None,
    }
    paths = [tmp_path / 'manifest.json', tmp_path / 'unblinded.json', tmp_path / 'analysis.json']
    write_case(paths, manifest, rows)
    return paths, manifest, rows


def write_case(paths, manifest, rows):
    from famjet.provenance import canonical_hash, canonical_json
    mp, rp, _ = paths
    mp.write_bytes(canonical_json(manifest))
    rp.write_bytes(canonical_json(rows))
    release = {'schema_version': 1, 'mode': 'test_only', 'manifest_hash': canonical_hash(manifest),
               'scope_id': manifest['scope_id'], 'rows_sha256': hashlib.sha256(rp.read_bytes()).hexdigest(),
               'expected_runs_hash': canonical_hash(manifest['expected_runs']),
               'authorization': {'authority': 'test_only', 'recorded_at': 'software-fixture'},
               'runs': [{**run, 'status': 'completed', 'rows_hash': canonical_hash([
                   r for r in rows if r['method'] == run['method'] and r['replicate'] == run['replicate']])}
                        for run in manifest['expected_runs']]}
    (mp.parent / manifest['release_record']).write_bytes(canonical_json(release))


def test_testonly_e2e_reuses_scoring_preserves_failures_and_cluster_units(tmp_path):
    from famjet.analysis.statistics import analyze_confirmation
    paths, _, rows = analysis_case(tmp_path)
    r = analyze_confirmation(*paths)
    assert r['status'] == 'analyzed_test_only' and not r['gate']['confirmation_allowed']
    assert r['gate']['calibration'] == 'not_run'
    assert r['gate']['implementation'] == 'not_run'  # Parsing a contract is not source acceptance.
    assert r['methods']['baseline']['fallback_count'] == 2
    assert r['comparisons']['primary']['effects'] == [[2.5, 2.5], [1., 1.]]
    assert r['comparisons']['primary']['mean'] == 1.75
    assert r['comparisons']['primary']['unit_order'] == ['cluster-0', 'cluster-1']
    assert r['secondary']['nominal']['secondary']['pvalue'] > 0
    assert r['secondary']['status'] == 'not_assessed'
    assert r['row_count'] == len(rows) and Path(paths[2]).exists()
    assert r['strong_primary_rejection'] is False


def test_duplicated_questions_do_not_narrow_cluster_uncertainty(tmp_path):
    from famjet.analysis.statistics import analyze_confirmation
    a = tmp_path / 'a'; b = tmp_path / 'b'; a.mkdir(); b.mkdir()
    left = analyze_confirmation(*analysis_case(a)[0])
    right = analyze_confirmation(*analysis_case(b, duplicate_queries=True)[0])
    for field in ['mean', 'interval', 'draws', 'resample_means']:
        assert left['comparisons']['primary'][field] == right['comparisons']['primary'][field]


@pytest.mark.parametrize('mutation', ['missing_row', 'duplicate_row', 'target', 'query', 'policy',
                                    'missing_unit', 'wrong_unit_stratum', 'missing_run', 'infinite_loss'])
def test_complete_frozen_inventory_and_pairing_cannot_be_reconstructed_from_survivors(tmp_path, mutation):
    from famjet.analysis.statistics import analyze_confirmation
    paths, m, rows = analysis_case(tmp_path)
    if mutation == 'missing_row': rows.pop()
    elif mutation == 'duplicate_row': rows.append(deepcopy(rows[-1]))
    elif mutation == 'target': rows[-1]['target'] = [999.]
    elif mutation == 'query': rows[-1]['query_id'] = 999
    elif mutation == 'policy': rows[-1]['policy']['expected_inventory'].pop()
    elif mutation == 'missing_unit': m['units'].pop()
    elif mutation == 'wrong_unit_stratum': m['units'][0]['stratum'] = 'wrong'
    elif mutation == 'missing_run': m['expected_runs'].pop()
    elif mutation == 'infinite_loss': rows[-1].update(loss=None, infinite_loss=True)
    write_case(paths, m, rows)  # Even correctly resealed incomplete evidence must fail.
    r = analyze_confirmation(*paths)
    assert r['status'] == 'blocked' and not r['gate']['confirmation_allowed']
    assert r['errors'] and json.loads(paths[2].read_text())['status'] == 'blocked'


@pytest.mark.parametrize('mutation', ['file', 'rows', 'manifest', 'release', 'scientific_namespace', 'statistics_hash'])
def test_hash_and_unblind_evidence_fail_closed(tmp_path, mutation):
    from famjet.analysis.statistics import analyze_confirmation
    paths, m, rows = analysis_case(tmp_path)
    if mutation == 'file': (tmp_path / m['files'][0]['path']).write_text('changed')
    elif mutation == 'rows': paths[1].write_text('[]')
    elif mutation == 'manifest':
        m['scope_id'] = 'changed'; paths[0].write_text(json.dumps(m))
    elif mutation == 'release': (tmp_path / 'release.json').unlink()
    elif mutation == 'statistics_hash':
        for row in rows: row['statistics_hash'] = 'b' * 64
        write_case(paths, m, rows)
    else:
        m.update(test_only=False, namespace='protected_confirmation'); write_case(paths, m, rows)
    r = analyze_confirmation(*paths)
    assert r['status'] == 'blocked' and r['errors']


def test_unknown_calibration_and_endpoint_or_p_precision_cannot_become_permission():
    from famjet.analysis.statistics import evaluate_gate, unfilled_calibration_policy
    evidence = {'implementation': 'pass', 'calibration_cells': [], 'endpoint_mc': ['met'],
                'secondary_p_mc': 'adequate', 'scope_id': 'test', 'source_hash': 'a' * 64}
    r = evaluate_gate(evidence, unfilled_calibration_policy())
    assert r['calibration'] == 'not_run' and r['eligibility'] == 'blocked'
    assert not r['confirmation_allowed'] and not r['nuisance_only_allowed']
    assert r['unresolved_reasons']


@pytest.mark.parametrize('mutation', ['status', 'missing', 'method'])
def test_incomplete_release_rejected_before_score_json_is_parsed(tmp_path, mutation):
    from famjet.analysis.statistics import analyze_confirmation
    paths, _, _ = analysis_case(tmp_path)
    record_path = tmp_path / 'release.json'
    release = json.loads(record_path.read_text())
    paths[1].write_text('invalid unopened score JSON')
    release['rows_sha256'] = hashlib.sha256(paths[1].read_bytes()).hexdigest()
    if mutation == 'status': release['runs'][0]['status'] = 'failed'
    elif mutation == 'missing': release['runs'].pop()
    else: release['runs'][0]['method'] = 'other'
    record_path.write_text(json.dumps(release))
    result = analyze_confirmation(*paths)
    assert result['status'] == 'blocked'
    assert result['errors'][0]['type'] == 'ValueError'
    assert 'released run' in result['errors'][0]['message']


@pytest.mark.parametrize('mutation', ['missing_cell', 'duplicate_cell', 'empty_queries', 'duplicate_query'])
def test_malformed_expected_matrix_rejected_before_score_json_is_parsed(tmp_path, mutation):
    from famjet.analysis.statistics import analyze_confirmation
    paths, manifest, rows = analysis_case(tmp_path)
    cells = manifest['scoring_policy']['expected_inventory']
    if mutation == 'missing_cell': cells.pop()
    elif mutation == 'duplicate_cell': cells.append(deepcopy(cells[-1]))
    elif mutation == 'empty_queries': cells[0]['tasks']['mean'] = []
    else: cells[0]['tasks']['mean'] = [0, 0]
    write_case(paths, manifest, rows)
    paths[1].write_text('invalid unopened score JSON')
    release_path = tmp_path / 'release.json'
    release = json.loads(release_path.read_text())
    release['rows_sha256'] = hashlib.sha256(paths[1].read_bytes()).hexdigest()
    release_path.write_text(json.dumps(release))
    result = analyze_confirmation(*paths)
    assert result['status'] == 'blocked'
    assert result['errors'][0]['type'] == 'ValueError'
    assert 'expected' in result['errors'][0]['message']


def artificial_gate_case():
    """Invented counts/loose thresholds test gate branches, not scientific tolerances."""
    from famjet.analysis.statistics import unfilled_calibration_policy
    from famjet.provenance import canonical_hash
    p = unfilled_calibration_policy()
    p.update(scope_id='software-only', source_hash='a' * 64, coverage_floor=.1,
             type1_ceiling=.9, fwer_ceiling=.9, power_floor=.1, outer_n=10,
             outer_error_budget=.1, domain='invented-gate-control',
             selection_stream='software-selection', validation_stream='software-validation',
             required_cells=[{'cell_id': metric, 'metric': metric, 'fixture_hash': 'b' * 64,
                              'allocation': {'histories': 2, 'seeds': 2}}
                             for metric in ['coverage', 'type1', 'fwer', 'power']])
    records = [{**s, 'successes': 10 if s['metric'] in ['coverage', 'power'] else 0,
                'trials': 10, 'scope_id': p['scope_id'], 'source_hash': p['source_hash'],
                'policy_hash': canonical_hash(p), 'rng_stream': p['validation_stream']}
               for s in p['required_cells']]
    evidence = {'implementation': 'pass', 'scope_id': p['scope_id'], 'source_hash': p['source_hash'],
                'calibration_cells': records, 'endpoint_mc': ['met'], 'secondary_p_mc': 'adequate',
                'resource_status': 'pass', 'baseline_status': 'pass', 'nuisance_domain_status': 'pass'}
    return evidence, p


def test_gate_recomputes_count_bounds_and_retains_rejected_sampling_cells():
    from famjet.analysis.statistics import evaluate_gate
    evidence, policy = artificial_gate_case()
    assert evaluate_gate(evidence, policy)['calibration'] == 'qualified'
    evidence['calibration_cells'][0]['successes'] = 0
    r = evaluate_gate(evidence, policy)
    assert r['calibration_cells']['coverage']['status'] == 'unresolved'  # loose floor .1
    policy['coverage_floor'] = .9
    from famjet.provenance import canonical_hash
    for record in evidence['calibration_cells']: record['policy_hash'] = canonical_hash(policy)
    r = evaluate_gate(evidence, policy)
    assert r['calibration'] == 'rejected' and not r['confirmation_allowed']
    assert r['calibration_cells']['coverage']['successes'] == 0


@pytest.mark.parametrize('failure', ['partial_counts', 'wrong_source', 'same_stream', 'missing_metric', 'endpoint', 'p_mc', 'baseline'])
def test_qualified_label_cannot_override_missing_scope_counts_or_other_gates(failure):
    from famjet.analysis.statistics import evaluate_gate
    from famjet.provenance import canonical_hash
    e, p = artificial_gate_case()
    if failure == 'partial_counts': e['calibration_cells'][0]['trials'] = 9
    elif failure == 'wrong_source': e['calibration_cells'][0]['source_hash'] = 'c' * 64
    elif failure == 'same_stream': p['selection_stream'] = p['validation_stream']
    elif failure == 'missing_metric':
        p['required_cells'] = p['required_cells'][:1]; e['calibration_cells'] = e['calibration_cells'][:1]
        for record in e['calibration_cells']: record['policy_hash'] = canonical_hash(p)
    elif failure == 'endpoint': e['endpoint_mc'] = ['cap_unmet']
    elif failure == 'p_mc': e['secondary_p_mc'] = 'unresolved'
    elif failure == 'baseline': e['baseline_status'] = 'not_run'
    r = evaluate_gate(e, p)
    assert not r['confirmation_allowed'] and r['unresolved_reasons']


def qualified_analysis_case(tmp_path, *, scientific=False, secondary=True, budget=.1):
    """Invented fully passing gate evidence; never a scientific dataset/release."""
    from famjet.provenance import canonical_hash
    paths, manifest, rows = analysis_case(tmp_path)
    evidence, policy = artificial_gate_case()
    policy.update(scope_id=manifest['scope_id'], source_hash=manifest['source_hash'])
    policy['nuisance_authorization'] = {
        'scope_id': manifest['scope_id'], 'source_hash': manifest['source_hash'],
        'authority': 'software-only-invented-authority', 'status': 'authorized',
        'allocation': {'histories': 2, 'seeds': 2}, 'max_seconds': 1., 'max_bytes': 1024}
    for record in evidence['calibration_cells']:
        record.update(scope_id=manifest['scope_id'], source_hash=manifest['source_hash'],
                      policy_hash=canonical_hash(policy))
    manifest.update(calibration_policy=policy, calibration_evidence=evidence['calibration_cells'],
                    p_mc_error_budget=budget, design_evidence={
                        key: evidence[key] for key in ['implementation', 'resource_status',
                                                      'baseline_status', 'nuisance_domain_status']})
    manifest['design_evidence']['implementation_source_hash'] = manifest['source_hash']
    if not secondary: manifest['comparisons'].pop('secondary')
    if scientific: manifest.update(test_only=False, namespace='protected_confirmation')
    write_case(paths, manifest, rows)
    if scientific:
        release_path = paths[0].parent / manifest['release_record']
        release = json.loads(release_path.read_text())
        release.update(mode='legitimate')
        release['authorization']['authority'] = 'task21_unblind_v1'
        release_path.write_text(json.dumps(release))
    return paths, manifest, rows


def unopened_score_sentinel(paths, manifest):
    paths[1].write_text('invalid unopened score JSON')
    release_path = paths[0].parent / manifest['release_record']
    release = json.loads(release_path.read_text())
    release['rows_sha256'] = hashlib.sha256(paths[1].read_bytes()).hexdigest()
    release_path.write_text(json.dumps(release))


def test_qualified_test_only_analysis_exports_no_confirmation_or_nuisance_permission(tmp_path):
    from famjet.analysis.statistics import analyze_confirmation
    r = analyze_confirmation(*qualified_analysis_case(tmp_path)[0])
    assert r['status'] == 'analyzed_test_only' and not r['errors']
    assert r['gate']['calibration'] == 'qualified'  # Artificial counts retained as diagnostics.
    assert r['gate']['endpoint_mc'] == ['met', 'met']
    assert r['gate']['secondary_p_mc'] == 'adequate'
    assert r['secondary']['nominal']['secondary']['reject']
    assert r['methods']['baseline']['fallback_count'] == 2
    assert not r['gate']['confirmation_allowed'] and not r['gate']['nuisance_only_allowed']
    assert r['gate']['eligibility'] == 'blocked'
    assert any('test-only' in reason for reason in r['gate']['unresolved_reasons'])
    assert not r['strong_primary_rejection'] and not any(r['strong_secondary_rejections'].values())


@pytest.mark.parametrize('budget', [None, 0., 1., 'not-a-budget', True])
def test_scientific_secondary_budget_must_be_frozen_before_score_parsing(tmp_path, budget):
    from famjet.analysis.statistics import analyze_confirmation
    paths, manifest, _ = qualified_analysis_case(tmp_path, scientific=True, budget=budget)
    unopened_score_sentinel(paths, manifest)
    r = analyze_confirmation(*paths)
    assert r['status'] == 'blocked'
    assert r['errors'][0]['type'] == 'ValueError'
    assert 'budget' in r['errors'][0]['message']


def test_primary_only_scientific_preflight_allows_null_secondary_budget_without_future_mc(tmp_path):
    from famjet.analysis.statistics import _contract
    paths, manifest, _ = qualified_analysis_case(tmp_path, scientific=True, secondary=False, budget=None)
    unopened_score_sentinel(paths, manifest)
    _, evidence = _contract(manifest, paths[0], paths[1])
    assert 'endpoint_mc' not in evidence and 'secondary_p_mc' not in evidence


@pytest.mark.parametrize('field', ['scope_id', 'source_hash', 'selection_stream', 'validation_stream'])
@pytest.mark.parametrize('invalid', ['', ' \t ', 17, [], {}])
def test_matching_invalid_calibration_provenance_cannot_qualify(field, invalid):
    from famjet.analysis.statistics import evaluate_gate
    from famjet.provenance import canonical_hash
    e, p = artificial_gate_case()
    p[field] = invalid
    if field in ('scope_id', 'source_hash'): e[field] = invalid
    for record in e['calibration_cells']:
        if field in ('scope_id', 'source_hash'): record[field] = invalid
        if field == 'validation_stream': record['rng_stream'] = invalid
        record['policy_hash'] = canonical_hash(p)
    r = evaluate_gate(e, p)
    assert r['calibration'] != 'qualified' and not r['confirmation_allowed']
    assert not r['nuisance_only_allowed'] and r['unresolved_reasons']


def nuisance_case():
    from famjet.analysis.statistics import unfilled_calibration_policy
    e = {'implementation': 'pass', 'scope_id': 'bounded-software-nuisance', 'source_hash': 'a' * 64}
    p = unfilled_calibration_policy()
    p['nuisance_authorization'] = {**e, 'authority': 'software-only-authority', 'status': 'authorized',
                                   'allocation': {'histories': 2, 'seeds': 2},
                                   'max_seconds': 1., 'max_bytes': 1024}
    return e, p


def test_explicit_nuisance_permission_does_not_require_unfilled_calibration_streams():
    from famjet.analysis.statistics import evaluate_gate
    e, p = nuisance_case()
    r = evaluate_gate(e, p)
    assert r['calibration'] == 'not_run' and r['nuisance_only_allowed']
    assert not r['confirmation_allowed'] and p['selection_stream'] is p['validation_stream'] is None


@pytest.mark.parametrize('field', ['scope_id', 'source_hash', 'authority'])
@pytest.mark.parametrize('invalid', ['', ' \t ', 17, []])
def test_invalid_nuisance_scope_source_or_authority_cannot_authorize(field, invalid):
    from famjet.analysis.statistics import evaluate_gate
    e, p = nuisance_case()
    if field in ('scope_id', 'source_hash'): e[field] = invalid
    p['nuisance_authorization'][field] = invalid
    assert not evaluate_gate(e, p)['nuisance_only_allowed']


@pytest.mark.parametrize('invalid', ['untyped-allocation', 17])
def test_nuisance_authorization_requires_an_explicit_allocation_mapping(invalid):
    from famjet.analysis.statistics import evaluate_gate
    e, p = nuisance_case()
    p['nuisance_authorization']['allocation'] = invalid
    assert not evaluate_gate(e, p)['nuisance_only_allowed']


def test_positive_weight_regime_without_declared_units_is_rejected_before_score_parsing(tmp_path):
    from famjet.analysis.statistics import analyze_confirmation
    paths, manifest, rows = analysis_case(tmp_path)
    manifest['scoring_policy']['regime_weights'] = {'r': .5, 'absent': .5}
    write_case(paths, manifest, rows)
    unopened_score_sentinel(paths, manifest)
    r = analyze_confirmation(*paths)
    assert r['status'] == 'blocked' and r['errors'][0]['type'] == 'ValueError'
    assert 'stratum weights' in r['errors'][0]['message']
