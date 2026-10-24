import numpy as np
import pytest
import torch
import copy
import hashlib
import json

from famjet.provenance import canonical_json

from famjet_poc.contracts import ShapeSpec, ReaderSpec
from famjet_poc.models import (build_model, feature_map, query_basis, fit_training_metadata,
                               make_fit_manifest, fit_reader, save_model, load_model, _two_age_episodes)
from famjet.types import EventBatch, QueryBatch, Episode


def _episode(index, *, split='training'):
    a, b = float(index + 1), float(2 * index - 1)
    events = EventBatch((f'unit-{index}',), torch.tensor([[0, 1]]), torch.tensor([[1., 2.]], dtype=torch.float64),
                        torch.tensor([[0, 0]]), torch.eye(12, dtype=torch.float64)[[0, 0]][None],
                        torch.tensor([[[a], [b]]], dtype=torch.float64), torch.tensor([2]),
                        torch.ones((1, 2), dtype=torch.bool), torch.ones((1, 2, 1), dtype=torch.bool), 'unit_hour')
    queries = QueryBatch((f'unit-{index}',), torch.tensor([[0, 1]]), torch.tensor([[2., 2.]], dtype=torch.float64),
                         torch.tensor([[0, 0]]), torch.eye(12, dtype=torch.float64)[[0, 0]][None],
                         (('mean', 'contrast'),), torch.zeros((1, 2), dtype=torch.float64),
                         torch.ones((1, 2), dtype=torch.float64), torch.ones((1, 2), dtype=torch.bool), torch.tensor([2]))
    return Episode(events, queries, torch.tensor([[[b], [b - a]]], dtype=torch.float64),
                   torch.ones((1, 2), dtype=torch.bool),
                   {'split': split, 'target_semantics': 'observed_event_targets_v2', 'regime': 'piecewise_stationary',
                    'target_valid': [[True, True]]})


def test_contracts_reject_wrong_shapes_and_unknown_fields():
    with pytest.raises(ValueError):
        ShapeSpec(8, 8)
    with pytest.raises(TypeError):
        ShapeSpec(16, 8, surprise=True)
    with pytest.raises(ValueError):
        ReaderSpec('ridge_v1', 'jet', 8, -1, 1 / 5224, 1, 1e-6, 1e-12)


def test_exact_feature_order_and_query_basis():
    u = np.arange(1, 9, dtype=np.float64)
    mass = np.arange(2, 10, dtype=np.float64)
    feature = feature_map(u, mass, 1e-6, 1e-12)
    assert feature.shape == (33,)
    np.testing.assert_array_equal(feature[1:9], u)
    np.testing.assert_allclose(feature[9:17], u / (mass + 1e-6))
    np.testing.assert_allclose(feature[17:25], np.log1p(mass))
    np.testing.assert_array_equal(feature[25:], 1)
    np.testing.assert_allclose(query_basis(0, 2, 'contrast', 1, 8),
                               [1, 0, np.log(3), 0, 0, np.log(3)**2, 1, 0])
    assert query_basis(0, 2, 'mean', 1, 16).shape == (16,)
    with pytest.raises(ValueError):
        feature_map(u, np.r_[-1, mass[1:]], 1e-6, 1e-12)


def test_model_is_dimension_general_and_reader_change_preserves_snapshot():
    spec = ReaderSpec('ridge_v1', 'jet', 8, 1e-10, 1 / 5224, 1, 1e-6, 1e-12)
    stats = {'schema_version': 2, 'target_semantics': 'observed_event_targets_v2',
             'split': 'training', 'tasks': {'mean': {'scale': 1, 'mean': [0]},
                                           'contrast': {'scale': 1, 'mean': [0]}}}
    model = build_model(ShapeSpec(12, 1), spec, 1, stats)
    state = model.init_state(1, device='cpu', dtype='float64')
    old_hash = state.parameter_hash
    model.coefficients = np.ones(264)
    assert model.init_state(1, device='cpu', dtype='float64').parameter_hash == old_hash
    assert model.parameter_nbytes() >= 264 * 8
    with pytest.raises(ValueError):
        build_model(ShapeSpec(16, 8), ReaderSpec('ridge_v1', 'bank', 12, 1e-10, 1 / 5224, 1, 1e-6, 1e-12), 1, stats)


def test_fit_replays_rows_and_solves_weighted_normal_equations():
    episodes = [_episode(i) for i in range(4)]
    factory = lambda: iter(episodes)
    metadata = fit_training_metadata(factory)
    spec = ReaderSpec('ridge_v1', 'bank', 8, 1e-6, 1 / 5224, 1, 1e-6, 1e-12)
    model = build_model(ShapeSpec(12, 1), spec, metadata['t_ref'], metadata['target_statistics'])
    manifest = make_fit_manifest(model, metadata)
    artifact = fit_reader(model, factory, manifest, chunk_rows=3)
    assert artifact.row_count == 8
    assert artifact.scaled_normal_residual < 1e-7
    assert np.isfinite(model.coefficients).all()
    state = model.encode(episodes[0].events)
    before = state.parameter_hash
    result = model.read(state, episodes[0].queries)
    assert torch.isfinite(result.prediction).all()
    assert state.parameter_hash == before
    changed = [_episode(i) for i in range(4)]
    changed[2].labels[0, 0, 0] += 1
    old_coefficients = model.coefficients
    changed_model = build_model(ShapeSpec(12, 1), spec, metadata['t_ref'], metadata['target_statistics'])
    with pytest.raises(ValueError, match='replay'):
        fit_reader(changed_model, lambda: iter(changed), manifest)
    np.testing.assert_array_equal(model.coefficients, old_coefficients)
    with pytest.raises(ValueError, match='refit'):
        fit_reader(model, factory, manifest)


def test_fit_rejects_development_rows():
    with pytest.raises(ValueError, match='training'):
        fit_training_metadata(lambda: iter([_episode(0, split='development_fit')]))


def test_model_npz_roundtrip_and_tamper_rejection(tmp_path):
    episodes = [_episode(i) for i in range(4)]
    factory = lambda: iter(episodes)
    meta = fit_training_metadata(factory)
    spec = ReaderSpec('ridge_v1', 'jet', 8, 1e-6, 1 / 5224, 1, 1e-6, 1e-12)
    model = build_model(ShapeSpec(12, 1), spec, meta['t_ref'], meta['target_statistics'])
    fit_reader(model, factory, make_fit_manifest(model, meta), chunk_rows=4)
    ref = save_model(model, tmp_path / 'reader.json')
    loaded = load_model(ref.path, ref.sha256)
    np.testing.assert_array_equal(loaded.coefficients, model.coefficients)
    assert loaded.writer_hash == model.writer_hash
    with pytest.raises(ValueError, match='SHA'):
        load_model(ref.path, '0' * 64)
    arrpath = ref.path.with_suffix('.npz')
    arrpath.write_bytes(arrpath.read_bytes() + b'x')
    with pytest.raises(ValueError, match='NPZ'):
        load_model(ref.path, ref.sha256)


def test_loaded_fit_rejects_nested_manifest_and_diagnostic_tampering(tmp_path):
    episodes = [_episode(i) for i in range(4)]
    factory = lambda: iter(episodes)
    meta = fit_training_metadata(factory)
    spec = ReaderSpec('ridge_v1', 'jet', 8, 1e-6, 1 / 5224, 1, 1e-6, 1e-12)
    model = build_model(ShapeSpec(12, 1), spec, meta['t_ref'], meta['target_statistics'])
    fit_reader(model, factory, make_fit_manifest(model, meta), chunk_rows=3)
    ref = save_model(model, tmp_path / 'reader.json')
    original = json.loads(ref.path.read_bytes())
    changes = (
        lambda p: p['fit']['manifest']['reader'].__setitem__('ridge', 1e-3),
        lambda p: p['fit']['manifest'].__setitem__('unexpected', 1),
        lambda p: p['fit']['manifest'].__setitem__('row_sha256', '0' * 64),
        lambda p: p['fit']['manifest'].__setitem__('lock_sha256', '0' * 64),
        lambda p: p['fit']['manifest']['shape'].__setitem__('key_dim', 16),
        lambda p: p['fit']['manifest'].__setitem__('t_ref', 2.),
        lambda p: p['fit'].__setitem__('objective', 'zero'),
        lambda p: p['fit'].__setitem__('failure_status', 'failed'),
        lambda p: p['fit']['solver'].__setitem__('unexpected', 1),
    )
    for change in changes:
        payload = copy.deepcopy(original)
        change(payload)
        raw = canonical_json(payload)
        ref.path.write_bytes(raw)
        with pytest.raises(ValueError):
            load_model(ref.path, hashlib.sha256(raw).hexdigest())
    ref.path.write_bytes(canonical_json(original))
    assert load_model(ref.path, ref.sha256).fit_artifact.failure_status == 'none'


def test_fit_memory_ledger_names_bounded_copies_and_unknowns():
    episodes = [_episode(i) for i in range(4)]
    factory = lambda: iter(episodes)
    meta = fit_training_metadata(factory)
    spec = ReaderSpec('ridge_v1', 'bank', 8, 1e-6, 1 / 5224, 1, 1e-6, 1e-12)
    model = build_model(ShapeSpec(12, 1), spec, meta['t_ref'], meta['target_statistics'])
    ledger = fit_reader(model, factory, make_fit_manifest(model, meta), chunk_rows=3).memory_ledger
    arrays = ledger['logical_arrays_bytes']
    p = 33 * spec.query_width
    assert arrays['gram'] == arrays['normal_matrix'] == arrays['ridge_identity_temporary'] == p * p * 8
    assert arrays['buffered_phi'] == arrays['stacked_design'] == arrays['weighted_design'] == 3 * p * 8
    assert arrays['max_episode_raw_features'] >= 2 * 1 * 33 * 8
    assert arrays['max_advanced_snapshot_copy'] >= arrays['max_episode_writer_state']
    assert arrays['artifact_coefficient_values'] == p * 8
    assert arrays['artifact_rate_values'] == 8 * 8
    assert ledger['known_simultaneous_groups_bytes']['chunk_flush'] >= sum(
        arrays[k] for k in ('gram', 'rhs', 'buffered_phi', 'stacked_design', 'weighted_design'))
    assert ledger['unmeasured']['solver_workspace_bytes'] is None
    assert ledger['unmeasured']['process_rss_bytes'] is None


def test_qualification_initializes_closed_inventory_and_records_exception_without_running(monkeypatch, tmp_path):
    import famjet_poc.models as models
    def stop_before_numeric(*args, **kwargs):
        raise RuntimeError('injected source fixture failure')
    monkeypatch.setattr(models, '_two_age_episodes', stop_before_numeric)
    with pytest.raises(RuntimeError, match='injected'):
        models.qualify_models(tmp_path)
    payload = json.loads((tmp_path / 'qualification.json').read_bytes())
    assert len(payload['cases']) == 8
    assert payload['cases'][0]['status'] == 'failed_exception'
    assert all(c['status'] == 'pending' for c in payload['cases'][1:])
    assert payload['all_passed'] is False


def test_qualification_keeps_completed_case_when_next_case_throws(monkeypatch, tmp_path):
    import famjet_poc.models as models
    calls = 0
    def simulated_case(*args):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise ArithmeticError('injected later case failure')
        return {'gate': True, 'model_file': 'unit-only.json', 'model_sha256': '0' * 64}
    monkeypatch.setattr(models, '_run_qualification_case', simulated_case)
    with pytest.raises(ArithmeticError, match='later case'):
        models.qualify_models(tmp_path)
    payload = json.loads((tmp_path / 'qualification.json').read_bytes())
    assert [c['status'] for c in payload['cases']] == ['passed', 'failed_exception'] + ['pending'] * 6
    assert payload['cases'][0]['model_file'] == 'unit-only.json'
    assert payload['cases'][1]['exception_type'] == 'ArithmeticError'
    recorded = (tmp_path / 'qualification.json').read_bytes()
    with pytest.raises(ValueError, match='existing qualification journal'):
        models.qualify_models(tmp_path)
    assert (tmp_path / 'qualification.json').read_bytes() == recorded


def test_ridge_matches_independent_augmented_svd_objective():
    episodes = [_episode(i) for i in range(4)]
    factory = lambda: iter(episodes)
    meta = fit_training_metadata(factory)
    spec = ReaderSpec('ridge_v1', 'jet', 8, 1e-4, 1 / 5224, 1, 1e-6, 1e-12)
    model = build_model(ShapeSpec(12, 1), spec, meta['t_ref'], meta['target_statistics'])
    fit = fit_reader(model, factory, make_fit_manifest(model, meta), chunk_rows=2)
    x, y, w = [], [], []
    for ep in episodes:
        phi, valid, _ = model.design(model.encode(ep.events), ep.queries)
        assert valid.all()
        for j, task in enumerate(('mean', 'contrast')):
            x.append(phi[0, j, 0]); y.append(float(ep.labels[0, j, 0]))
            w.append(1 / meta['target_statistics']['tasks'][task]['scale']**2)
    x, y, w = np.stack(x), np.asarray(y), np.asarray(w)
    w /= w.sum()
    augmented_x = np.vstack((np.sqrt(w)[:, None] * x, np.sqrt(spec.ridge) * np.eye(x.shape[1])))
    augmented_y = np.r_[np.sqrt(w) * y, np.zeros(x.shape[1])]
    reference = np.linalg.lstsq(augmented_x, augmented_y, rcond=None)[0]
    np.testing.assert_allclose(model.coefficients, reference, atol=1e-7, rtol=1e-6)
    expected_objective = float(np.sum(w * (x @ reference - y)**2) + spec.ridge * np.sum(reference**2))
    assert abs(fit.objective - expected_objective) < 1e-8


def test_two_age_source_fixture_matches_hand_targets():
    ep = _two_age_episodes(ShapeSpec(12, 1), 1, 2026102402, 'training')[0]
    old = ep.events.values[0, :12, 0]
    recent = ep.events.values[0, 12:, 0]
    assert ep.labels.shape == (1, 48, 1)
    assert torch.allclose(ep.labels[0, :12, 0], recent)
    assert torch.allclose(ep.labels[0, 12:24, 0], old)
    assert torch.allclose(ep.labels[0, 24:36, 0], recent - old)
    assert torch.allclose(ep.labels[0, 36:, 0], recent - old)


def test_core_scorer_accepts_fitted_reader_snapshot_interface():
    from famjet.eval.runner import score_episode
    episodes = [_episode(i) for i in range(4)]
    factory = lambda: iter(episodes)
    meta = fit_training_metadata(factory)
    spec = ReaderSpec('ridge_v1', 'jet', 8, 1e-6, 1 / 5224, 1, 1e-6, 1e-12)
    model = build_model(ShapeSpec(12, 1), spec, meta['t_ref'], meta['target_statistics'])
    fit_reader(model, factory, make_fit_manifest(model, meta))
    rows = score_episode(model, episodes[0], method='poc_jet', manifest_hash='0' * 64)
    assert len(rows) == 2
    assert {row['task'] for row in rows} == {'mean', 'contrast'}
    assert all(row['target_semantics'] == 'observed_event_targets_v2' for row in rows)


def test_jet_raw_state_features_and_read_leave_snapshot_unchanged():
    stats = {'schema_version': 2, 'target_semantics': 'observed_event_targets_v2', 'split': 'training',
             'tasks': {task: {'status': 'ok', 'scale': 1., 'mean': [0.] * 8}
                       for task in ('mean', 'contrast')}}
    spec = ReaderSpec('ridge_v1', 'jet', 16, 1e-10, 1 / 5224, 1, 1e-6, 1e-12)
    model = build_model(ShapeSpec(16, 8), spec, 1., stats)
    key = torch.nn.functional.one_hot(torch.tensor([[3]]), 16).to(torch.float64)
    values = torch.arange(1., 9., dtype=torch.float64).reshape(1, 1, 8)
    events = EventBatch(('raw',), torch.tensor([[0]]), torch.tensor([[0.]], dtype=torch.float64),
                        torch.tensor([[3]]), key, values, torch.tensor([1]), torch.tensor([[True]]),
                        torch.ones((1, 1, 8), dtype=torch.bool), 'unit_hour')
    state = model.encode(events)
    original_z = state.payload['z'].clone()
    original_h = state.payload['h'].clone()
    queries = QueryBatch(('raw',), torch.tensor([[0, 1]]), torch.tensor([[2., 3.]], dtype=torch.float64),
                         torch.tensor([[3, 3]]), key.repeat(1, 2, 1), (('mean', 'contrast'),),
                         torch.zeros((1, 2), dtype=torch.float64),
                         torch.ones((1, 2), dtype=torch.float64), torch.ones((1, 2), dtype=torch.bool), torch.tensor([2]))
    raw, valid, numeric = model._raw_features(state, queries)
    rates = model.writer.rates.numpy()[0]
    mass = np.r_[np.exp(-2 * rates), 2 * rates * np.exp(-2 * rates)]
    np.testing.assert_allclose(raw[0, 0, 0, 1:9], mass)
    np.testing.assert_allclose(raw[0, 0, 0, 9:17], mass / (mass + spec.epsilon))
    assert valid.all() and numeric.all()
    model.read(state, queries)
    assert torch.equal(state.payload['z'], original_z)
    assert torch.equal(state.payload['h'], original_h)
