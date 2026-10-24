import pytest

from famjet_poc.transfer import (block_sensitivity, native_rows, fit_transfer_modes,
                                 evaluate_equivalent_control, evaluate_real_mode,
                                 PrefreezeTransferInputs, real_scoring_statistics)
from famjet_poc.transfer import verify_prefreeze_cache_entries
from famjet_poc.transfer import admit_real_output
from famjet_poc.transfer import validate_real_method_inventory
from famjet_poc.protected import FrozenStudyRef


def test_native_contrast_scales_without_pollutant_offset():
    rows = [{'history_id': 'h', 'task': 'mean', 'prediction': [1.], 'target': [2.]},
            {'history_id': 'h', 'task': 'contrast', 'prediction': [1.], 'target': [2.]}]
    converted = native_rows(rows, {'split': 'training', 'mean': 50., 'scale': 20.})
    assert converted[0]['native_prediction'] == [70.]
    assert converted[0]['native_target'] == [90.]
    assert converted[1]['native_prediction'] == [20.]
    assert converted[1]['native_target'] == [40.]
    assert converted[1]['native_mse_micrograms2'] == 400.


def test_block_sensitivity_groups_stations_in_shared_cluster():
    rows = [
        {'history_id': 'h0', 'cluster_28d': 'a', 'cluster_56d': 'A', 'station': 'north', 'loss': 1.},
        {'history_id': 'h0', 'cluster_28d': 'a', 'cluster_56d': 'A', 'station': 'south', 'loss': 3.},
        {'history_id': 'h1', 'cluster_28d': 'b', 'cluster_56d': 'A', 'station': 'north', 'loss': 5.},
        {'history_id': 'h2', 'cluster_28d': 'c', 'cluster_56d': 'B', 'station': 'south', 'loss': 7.},
    ]
    result = block_sensitivity(rows, {'28d': 3, '56d': 2})
    assert result['28d']['cluster_count'] == 3
    assert result['56d']['cluster_count'] == 2
    assert result['28d']['cluster_means']['a'] == 2.
    assert result['56d']['cluster_means']['A'] == 3.5
    with pytest.raises(ValueError, match='cluster'):
        block_sensitivity(rows, {'28d': 28, '56d': 14})


def test_fitting_rejects_frozen_study_before_creating_weights(tmp_path):
    frozen = FrozenStudyRef(tmp_path / 'freeze.json', 'a' * 64, 'b' * 64, 'c' * 64)
    with pytest.raises(ValueError, match='pre-freeze'):
        fit_transfer_modes(frozen, tmp_path / 'beijing.json', tmp_path / 'out')
    assert not (tmp_path / 'out').exists()


def test_equivalent_control_uses_pinned_e3_rows_and_rejects_bank(tmp_path):
    import numpy as np
    from famjet.eval.metrics import fit_target_statistics
    from famjet_poc.contracts import PopulationSpec, ReaderSpec, ShapeSpec
    from famjet_poc.data import generate_episode
    from famjet_poc.models import (build_model, fit_training_metadata,
                                   make_fit_manifest, fit_reader, save_model, load_model)
    from famjet_poc.study import evaluate_panel, freeze_score_policy, load_score_rows

    spec = PopulationSpec('poc_numeric_v1', ShapeSpec(12, 1), 'unit_test', 318,
                          (128,), ('piecewise_stationary',), 8, 512)
    ep = generate_episode(spec, 'equivalent-unit-0')
    ep.metadata['split'] = 'training'
    train = generate_episode(spec, 'equivalent-unit-1')
    train.metadata['split'] = 'training'
    training_factory = lambda: iter([ep, train])
    metadata = fit_training_metadata(training_factory)
    statistics = metadata['target_statistics']
    policy = freeze_score_policy([ep])
    allocation = {'schema_version': 1, 'phase': 'unit_test',
                  'manifest_sha256': policy['manifest_hash'], 'allocation_id': 'equiv-test',
                  'max_wall_seconds': 30, 'max_disk_bytes': 2**20,
                  'max_rss_bytes': 2**30}
    limits = {'max_frame_bytes': 2**20, 'max_array_bytes': 2**19, 'max_histories': 64}
    jet = build_model(ShapeSpec(12, 1), ReaderSpec('ridge_v1', 'jet', 8, 1e-6,
                      1 / 5224, 1., 1e-6, 1e-12), metadata['t_ref'], statistics)
    fit_reader(jet, training_factory, make_fit_manifest(jet, metadata))
    saved = save_model(jet, tmp_path / 'jet.json')
    jet = load_model(saved.path, saved.sha256)
    ordinary = evaluate_panel(jet, lambda: iter([ep]), policy, statistics, 'jet',
                              tmp_path / 'ordinary', allocation, limits)
    equivalent = evaluate_equivalent_control(jet, lambda: iter([ep]), policy, statistics,
                                             tmp_path / 'equivalent', allocation, limits)
    left = [(r['query_id'], r['prediction'], r['loss']) for r in load_score_rows(ordinary['rows_ref'])]
    right = [(r['query_id'], r['prediction'], r['loss']) for r in load_score_rows(equivalent['rows_ref'])]
    assert [item[0] for item in left] == [item[0] for item in right]
    for (_, prediction_left, loss_left), (_, prediction_right, loss_right) in zip(left, right):
        assert prediction_left == pytest.approx(prediction_right, rel=1e-12, abs=1e-12)
        assert loss_left == pytest.approx(loss_right, rel=1e-12, abs=1e-12)
    assert equivalent['costs']['deployment_latency_status'] == 'unmeasured_reference_validation_entangled'
    bank = build_model(ShapeSpec(12, 1), ReaderSpec('ridge_v1', 'bank', 8, 1e-6,
                       1 / 5224, 1., 1e-6, 1e-12), metadata['t_ref'], statistics)
    with pytest.raises(ValueError, match='Jet'):
        evaluate_equivalent_control(bank, lambda: iter([ep]), policy, statistics,
                                    tmp_path / 'bank', allocation, limits)


def test_real_mode_rejects_unknown_method_before_test_manifest_access(tmp_path):
    with pytest.raises(ValueError, match='method'):
        evaluate_real_mode({'mode_name': 'synthetic_frozen', 'family': 'invented',
                            'modes_ref': {'path': '/missing/modes.json', 'sha256': 'a' * 64},
                            'manifest': '/missing/test.json', 'allocation': {},
                            'worker_limits': {}}, None, tmp_path / 'out')
    assert not (tmp_path / 'out').exists()


def test_prefreeze_real_fit_requires_finite_whole_stage_allocation():
    with pytest.raises(ValueError, match='allocation'):
        PrefreezeTransferInputs({'jet': {}, 'bank': {}},
                                {'max_wall_seconds': 0},
                                {'max_histories': 64}, 2**20, 'a' * 64)


def test_real_scoring_uses_manifest_training_statistics_for_every_mode():
    from pathlib import Path
    stats = real_scoring_statistics(Path('configs/manifests/beijing_v2_targets.json'))
    assert stats['split'] == 'training'
    assert stats['tasks']['mean']['count'] == 2322
    assert stats['tasks']['contrast']['count'] == 2314


def test_prefreeze_episode_cache_bytes_are_rechecked(tmp_path):
    import hashlib
    path = tmp_path / 'episode.json'
    path.write_bytes(b'owned')
    entries = [{'path': str(path), 'sha256': hashlib.sha256(b'owned').hexdigest(),
                'bytes': 5, 'history_id': 'h', 'episode_digest': 'a' * 64}]
    assert verify_prefreeze_cache_entries(entries) == 5
    path.write_bytes(b'other')
    with pytest.raises(ValueError, match='cache'):
        verify_prefreeze_cache_entries(entries)


def test_real_mode_checks_all_output_bytes_after_native_persistence(tmp_path):
    (tmp_path / 'rows.json').write_bytes(b'12345')
    with pytest.raises(RuntimeError, match='output'):
        admit_real_output(tmp_path, {'max_disk_bytes': 4})


def test_real_comparison_release_requires_every_declared_method():
    receipts = [{'mode': 'synthetic_frozen', 'method': 'jet', 'status': 'completed'}]
    with pytest.raises(ValueError, match='method'):
        validate_real_method_inventory(receipts, ('synthetic_frozen',), ('jet', 'bank'))
