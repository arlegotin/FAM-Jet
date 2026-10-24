"""Small independent controls for conditional history inference."""
import hashlib
import json
import math
from pathlib import Path

import numpy as np
import pytest
from scipy.integrate import quad
from scipy.optimize import brentq

from famjet_poc import inference as inf


def test_hand_calculated_welch_and_sign_reversal():
    d = np.array([1., 3., 2., 6.])
    groups = np.array([0, 0, 1, 1])
    out = inf.conditional_interval(d, groups, weights=[.5, .5])
    assert out['D'] == pytest.approx(3.)
    assert out['V'] == pytest.approx(1.25)
    assert out['df'] == pytest.approx(25/17)
    reverse = inf.conditional_interval(-d, groups, weights=[.5, .5])
    assert reverse['lower'] == pytest.approx(-out['upper'])
    assert reverse['upper'] == pytest.approx(-out['lower'])
    assert out['endpoint_mc'] == 'not_applicable_analytic'


def test_zero_variance_only_explicit_identical():
    with pytest.raises(ValueError):
        inf.conditional_interval([0, 0, 0, 0], [0, 0, 1, 1])
    out = inf.conditional_interval([0, 0, 0, 0], [0, 0, 1, 1], identical_method=True)
    assert (out['lower'], out['upper'], out['superiority']) == (0, 0, False)
    with pytest.raises(ValueError):
        inf.conditional_interval([1, 1, 1, 1], [0, 0, 1, 1], identical_method=True)


def test_numeric_reference_is_independent_pdf_integral():
    for df in (1, 2, 5, 30, 128, 1535):
        c = inf.reference_t_quantile(df)
        log_norm = math.lgamma((df + 1) / 2) - math.lgamma(df / 2) - .5 * math.log(df * math.pi)
        tail = quad(lambda x: math.exp(log_norm - (df + 1) / 2 * math.log1p(x*x/df)), c, math.inf,
                    epsabs=1e-13)[0]
        assert tail == pytest.approx(.025, abs=2e-12)
        assert abs(inf.t_critical(df) - c) <= 1e-10 * max(1, c)


def test_manifest_one_pair_per_history_and_exact_inventory():
    manifest = {'units': 'history', 'panel': 'unit_test', 'history_ids_by_stratum': {'0': ['a', 'b'], '1': ['c', 'd']},
                'weights': [.5, .5]}
    rows = [{'history_id': k, 'stratum': s, 'jet_loss': j, 'bank_loss': b, 'units': 'history'}
            for s, k, j, b in [(0, 'a', 1., 2.), (0, 'b', 2., 5.),
                               (1, 'c', 1., 3.), (1, 'd', 2., 8.)]]
    d, strata = inf.validate_history_pairs(rows, manifest)
    assert d.tolist() == [1., 3., 2., 6.]
    assert strata.tolist() == [0, 0, 1, 1]
    for bad in (rows + [rows[0]], rows[:-1], [{**rows[0], 'units': 'query'}] + rows[1:],
                [{**rows[0], 'bank_loss': float('nan')}] + rows[1:]):
        with pytest.raises(ValueError):
            inf.validate_history_pairs(bad, manifest)
    with pytest.raises(ValueError):
        inf.validate_history_pairs(rows, {**manifest, 'weights': [.6, .4]})


def test_laws_seeds_and_translation_small_batch():
    for fixture in range(1, 9):
        batch = inf.calibration_batch(fixture, 0, 3, per_cell=4)
        assert len(batch['D']) == 3
        assert len(batch['status']) == 3
        assert batch['counts']['total'] == 3
        assert batch['counter_commitment'] == inf.calibration_batch(fixture, 0, 3, per_cell=4)['counter_commitment']
        assert np.array_equal(batch['D'], inf.calibration_batch(fixture, 0, 3, per_cell=4)['D'])
        assert batch['shift_coverage_equal'] is True
        assert batch['law']['fixture'] == fixture
    a = inf.fixture_scales(7)
    b = inf.fixture_scales(8)
    assert a.shape == b.shape == (12,)
    assert np.all(a > 0)
    assert np.all(b.reshape(3, 4)[:, [1, 3]] < 0)


def test_cp_boundaries_are_integer_and_edge_cases():
    bounds = inf.calibration_boundaries()
    assert bounds['N'] == 20000 and bounds['K'] == 32
    for kind, label in [('coverage', 'lower'), ('power', 'lower'), ('null_rejection', 'upper')]:
        k = bounds[kind]['pass_count']
        if label == 'lower':
            assert inf.cp_bounds(k, 20000, bounds['tail'])[0] >= bounds[kind]['threshold']
            assert inf.cp_bounds(k-1, 20000, bounds['tail'])[0] < bounds[kind]['threshold']
        else:
            assert inf.cp_bounds(k, 20000, bounds['tail'])[1] <= bounds[kind]['threshold']
            assert inf.cp_bounds(k+1, 20000, bounds['tail'])[1] > bounds[kind]['threshold']
    assert inf.cp_bounds(0, 20000, bounds['tail'])[0] == 0
    assert inf.cp_bounds(20000, 20000, bounds['tail'])[1] == 1


def test_incomplete_run_has_all_fixture_inventory(tmp_path, monkeypatch):
    monkeypatch.setattr(inf.time, 'monotonic', lambda: 100.)
    out = tmp_path / 'calibration'
    result = inf.run_calibration(out, deadline_monotonic=99.)
    assert result['status'] == 'incomplete'
    evidence = json.loads((out / 'evidence.json').read_text())
    assert len(evidence['fixtures']) == 8
    assert all(v['completed'] == 0 for v in evidence['fixtures'].values())
    assert inf.validate_calibration(evidence, {'out': out})['status'] == 'incomplete'
    with pytest.raises(FileExistsError):
        inf.run_calibration(out, deadline_monotonic=99.)


def test_validation_rejects_corrupt_commitments(tmp_path, monkeypatch):
    monkeypatch.setattr(inf.time, 'monotonic', lambda: 100.)
    out = tmp_path / 'calibration'
    evidence = inf.run_calibration(out, deadline_monotonic=99.)
    for changed in ({**evidence, 'source': {'sha256': '0'*64}},
                    {**evidence, 'fixture_hash': '0'*64},
                    {**evidence, 'counter_protocol': 'wrong'}):
        assert inf.validate_calibration(changed, {'out': out})['status'] == 'fail'


def test_primary_manifest_requires_fixed_12_cell_allocation():
    ids = {str(g): [f'{g}-{i}' for i in range(16)] for g in range(12)}
    manifest = {'units': 'history', 'panel': 'nuisance', 'strata': list(inf.STRATA),
                'history_ids_by_stratum': ids, 'weights': [1/12]*12}
    rows = [{'history_id': hid, 'stratum': g, 'jet_loss': 0.,
             'bank_loss': float(i), 'units': 'history'}
            for g in range(12) for i, hid in enumerate(ids[str(g)])]
    d, g = inf.validate_history_pairs(rows, manifest)
    assert len(d) == 192 and len(g) == 192
    with pytest.raises(ValueError):
        inf.validate_history_pairs(rows[:-1], manifest)
    with pytest.raises(ValueError):
        inf.validate_history_pairs(rows, {**manifest, 'panel': 'confirmation'})
    with pytest.raises(ValueError):
        inf.validate_history_pairs(rows, {**manifest, 'strata': list(reversed(inf.STRATA))})
    with pytest.raises(ValueError):
        inf.validate_history_pairs(rows, {**manifest, 'history_ids_by_stratum': {str(k): v for k, v in list(ids.items())[:-1]}})


def test_small_probe_records_forecast_without_calibration_gate(tmp_path):
    out = tmp_path/'small-probe'
    evidence = inf._run(out, deadline_monotonic=math.inf, attempt=0,
                        role=inf.PROBE, kind='probe', total=1)
    assert evidence['status'] == 'complete'
    assert evidence['resource']['forecast_main_seconds'] > 0
    assert evidence['resource']['peak_rss_bytes'] > 0
    assert inf.validate_calibration(evidence, {'out': out})['status'] == 'fail'


def test_frozen_cp_counts_and_counter_draw_golden():
    b = inf.calibration_boundaries()
    assert (b['coverage']['pass_count'], b['null_rejection']['pass_count'],
            b['power']['pass_count']) == (18926, 1074, 15231)
    seed = inf._counter_seed(2026102401901, 'e2e-inference-calibration-v1', 1, 0, 0)
    assert seed == 948535344999345170
    assert inf._draw(1, seed, 4) == pytest.approx(
        [-.14982072960966342, -.5428505605896189, -1.9905315627064792, .6407196330461474])


def test_validator_rejects_wrong_per_cell_and_tampered_endpoints(tmp_path):
    out = tmp_path/'mini'
    out.mkdir()
    evidence = inf._initial_evidence(1, inf.ATTEMPTS[1], 128, 'calibration')
    inf._atomic_json(out/'evidence.json', evidence)
    wrong = inf.calibration_batch(1, 0, 2, per_cell=4)
    inf._store_batch(out, evidence, wrong)
    assert inf.validate_calibration(evidence, {'out': out})['status'] == 'fail'
    out = tmp_path/'proper-mini'
    out.mkdir()
    evidence = inf._initial_evidence(1, inf.ATTEMPTS[1], 128, 'calibration')
    inf._atomic_json(out/'evidence.json', evidence)
    inf._store_batch(out, evidence, inf.calibration_batch(1, 0, 2))
    record = evidence['fixtures']['1']['batches'][0]
    assert record['per_cell'] == 128
    assert inf.validate_calibration(evidence, {'out': out})['status'] == 'incomplete'
    original_counter = record['counter_commitment']
    record['counter_commitment'] = '0'*64
    inf._atomic_json(out/'evidence.json', evidence)
    assert inf.validate_calibration(evidence, {'out': out})['status'] == 'fail'
    record['counter_commitment'] = original_counter
    inf._atomic_json(out/'evidence.json', evidence)
    path = out/record['file']
    with np.load(path, allow_pickle=False) as raw:
        arrays = {key: raw[key] for key in raw.files}
    arrays['lower'][0] += 1.
    with path.open('wb') as f:
        np.savez_compressed(f, **arrays)
    record['sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
    inf._atomic_json(out/'evidence.json', evidence)
    assert inf.validate_calibration(evidence, {'out': out})['status'] == 'fail'


def test_corrupt_batch_archive_fails_closed(tmp_path):
    out = tmp_path/'mini'
    out.mkdir()
    evidence = inf._initial_evidence(1, inf.ATTEMPTS[1], 128, 'calibration')
    inf._atomic_json(out/'evidence.json', evidence)
    inf._store_batch(out, evidence, inf.calibration_batch(1, 0, 1))
    record = evidence['fixtures']['1']['batches'][0]
    path = out/record['file']
    path.write_bytes(b'not an npz')
    record['sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
    inf._atomic_json(out/'evidence.json', evidence)
    assert inf.validate_calibration(evidence, {'out': out})['status'] == 'fail'


def test_all_eight_law_counter_goldens():
    expected = {
        1: (948535344999345170, [-.149820729610, -.542850560590, -1.990531562706]),
        2: (6699546442157085238, [-.679145468603, -.004292886045, -.714816792229]),
        3: (8306756001222137961, [.442498351086, .340723473413, -.495239524249]),
        4: (149281877869079080, [-.298343401774, -.723620650550, .622633681170]),
        5: (7386029752827658339, [-.142857142857]*3),
        6: (1401643839256172385, [.142857142857]*3),
        7: (3329326528524377422, [.290591979156, 1.070446698633, 1.457068948869]),
        8: (2649680144688190211, [-.522314024266, 6.110002128763, .135296334612]),
    }
    assert len(inf.LAW_DESCRIPTORS) == 8
    for fixture, (seed_expected, draws_expected) in expected.items():
        seed = inf._counter_seed(2026102401901, 'e2e-inference-calibration-v1', fixture, 0, 0)
        assert seed == seed_expected
        assert inf._draw(fixture, seed, 3) == pytest.approx(draws_expected, abs=1e-12)


def test_fake_clock_retains_partial_progress_and_full_inventory(tmp_path, monkeypatch):
    monkeypatch.setattr(inf, 'N', 2)
    ticks = iter([0., 0., 100., 100., 100.])
    monkeypatch.setattr(inf.time, 'monotonic', lambda: next(ticks))
    out = tmp_path/'partial'
    evidence = inf.run_calibration(out, deadline_monotonic=50.)
    assert evidence['status'] == 'incomplete'
    assert evidence['fixtures']['1']['completed'] == 2
    assert len(evidence['fixtures']) == 8
    assert all(evidence['fixtures'][str(f)]['completed'] == 0 for f in range(2, 9))
    assert inf.validate_calibration(evidence, {'out': out})['status'] == 'incomplete'
