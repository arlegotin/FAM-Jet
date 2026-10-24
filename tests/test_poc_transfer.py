import json

import pytest

from famjet_poc.transfer import (block_sensitivity, native_rows, fit_transfer_modes,
                                 evaluate_equivalent_control, evaluate_real_mode,
                                 PrefreezeTransferInputs, real_scoring_statistics)
from famjet_poc.transfer import verify_prefreeze_cache_entries
from famjet_poc.transfer import admit_real_output
from famjet_poc.transfer import validate_real_method_inventory
from famjet_poc.transfer import (verify_transfer_probe, verify_selected_reference,
                                 probe_transfer_profile)
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
    from famjet.provenance import canonical_hash
    from famjet.eval.metrics import fit_target_statistics
    from famjet_poc.contracts import PopulationSpec, ReaderSpec, ShapeSpec
    from famjet_poc.data import generate_episode
    from famjet_poc.models import (build_model, fit_training_metadata,
                                   make_fit_manifest, fit_reader, save_model, load_model)
    from famjet_poc.study import evaluate_panel, freeze_score_policy, load_score_rows
    from famjet_poc.protected import (episode_count_records, write_count_sidecar,
                                      validate_scored_receipt, _write_once)

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
    contract = {'policy_ref': _write_once(tmp_path / 'real-shape-policy.json', policy),
                'statistics_sha256': canonical_hash(statistics)}
    counts_ref = write_count_sidecar(episode_count_records(ep), policy['manifest_hash'],
                                     tmp_path / 'real-shape-counts')
    receipt = {'score_contract': contract, 'counts_ref': counts_ref}
    actual_rows = load_score_rows(ordinary['rows_ref'])
    assert validate_scored_receipt(receipt, actual_rows, policy['manifest_hash'],
                                   ['equivalent-unit-0'], list(range(8)))['query_count'] == 8
    altered = [dict(row) for row in actual_rows]
    altered[0]['statistics_hash'] = '0' * 64
    with pytest.raises(ValueError, match='contract'):
        validate_scored_receipt(receipt, altered, policy['manifest_hash'],
                                ['equivalent-unit-0'], list(range(8)))
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


def test_real_fit_probe_ref_requires_measured_current_profile(tmp_path):
    import hashlib
    manifest_sha = 'a' * 64
    probe = {'schema_version': 1, 'kind': 'famjet_e4_real_fit_probe',
             'status': 'measured', 'beijing_manifest_sha256': manifest_sha,
             'transfer_source_sha256': 'b' * 64, 'e3_source_sha256': 'c' * 64,
             'worker_limits': {'max_frame_bytes': 1024, 'max_array_bytes': 512,
                               'max_histories': 2},
             'measured_profile': {'train_blocks': 2, 'dev_blocks': 1,
                                  'fit_seconds': 1., 'evaluation_seconds': 2.},
             'forecast_seconds': 100., 'recommended_wall_seconds': 1800,
             'guard_ref': {'path': '/missing/guard', 'sha256': 'd' * 64, 'bytes': 1}}
    path = tmp_path / 'probe.json'
    path.write_text(json.dumps(probe))
    ref = {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
           'bytes': path.stat().st_size}
    with pytest.raises(ValueError, match='guard|probe'):
        verify_transfer_probe(ref, manifest_sha, probe['worker_limits'])
    with pytest.raises(ValueError, match='probe'):
        PrefreezeTransferInputs({'jet': {}, 'bank': {}},
                                {'schema_version': 1, 'phase': 'development',
                                 'manifest_sha256': manifest_sha, 'allocation_id': 'real',
                                 'max_wall_seconds': 1800, 'max_disk_bytes': 1024,
                                 'max_rss_bytes': 2**30}, probe['worker_limits'],
                                2**20, manifest_sha, probe_ref=None)


def test_task_adapted_selected_jet_requires_pretest_reference(tmp_path):
    from famjet.provenance import canonical_hash
    from famjet_poc.study import persist_score_rows
    modes = {'task_adapted': {'jet': {'path': 'jet.json', 'sha256': 'a' * 64},
                              'bank': {'path': 'bank.json', 'sha256': 'b' * 64}}}
    with pytest.raises(ValueError, match='reference'):
        verify_selected_reference(modes)
    modes['selected_reference'] = {'status': 'passed', 'model_sha256': 'c' * 64}
    with pytest.raises(ValueError, match='reference'):
        verify_selected_reference(modes)
    policy = {'version': 2}
    row = {'method': 'laguerre', 'history_id': 'dev-0', 'replicate': 0,
           'task': 'mean', 'query_id': 0, 'manifest_hash': 'd' * 64,
           'target_semantics': 'observed_event_targets_v2',
           'policy': policy, 'policy_hash': canonical_hash(policy)}
    row_ref = persist_score_rows([row], tmp_path / 'partial-reference.json')
    modes.update(beijing_manifest_sha256='d' * 64,
                 development_cache=[{'history_id': f'dev-{i}'} for i in range(4)],
                 selected_reference={'status': 'passed', 'model_sha256': 'a' * 64,
                                     'manifest_sha256': 'd' * 64, 'rows_ref': row_ref})
    with pytest.raises(ValueError, match='four-block'):
        verify_selected_reference(modes)


def test_real_profile_probe_measures_public_k12_fit_before_grid(tmp_path, monkeypatch):
    import hashlib
    import time
    from famjet_poc.contracts import PopulationSpec, ShapeSpec
    from famjet_poc.data import generate_episode
    spec = PopulationSpec('poc_numeric_v1', ShapeSpec(12, 1), 'unit_test', 913,
                          (128,), ('piecewise_stationary',), 8, 512)
    training = [generate_episode(spec, f'probe-train-{i}') for i in range(2)]
    development = [generate_episode(spec, 'probe-dev-0')]
    for episode in training:
        episode.metadata['split'] = 'training'
    monkeypatch.setattr('famjet_poc.transfer.iter_beijing',
                        lambda _path, split: iter(training if split == 'training' else development))
    manifest = tmp_path / 'public-manifest.json'
    manifest.write_bytes(b'unit-only-public-profile')
    digest = hashlib.sha256(manifest.read_bytes()).hexdigest()
    allocation = {'schema_version': 1, 'phase': 'probe',
                  'manifest_sha256': digest, 'allocation_id': 'unit-real-profile',
                  'max_wall_seconds': 120, 'max_disk_bytes': 16 * 2**20,
                  'max_rss_bytes': 2**30}
    limits = {'max_frame_bytes': 2**20, 'max_array_bytes': 2**19,
              'max_histories': 64}
    def observer(root):
        return {'tree_rss_bytes': 1, 'run_output_bytes': sum(
                    p.stat().st_size for p in root.rglob('*') if p.is_file()),
                'now_epoch_seconds': time.time(), 'descendant_pids': []}
    ref = probe_transfer_profile(manifest, limits, allocation, tmp_path / 'probe',
                                 observer=observer)
    result = verify_transfer_probe(ref, digest, limits)
    assert result['measured_profile']['train_blocks'] == 2
    assert result['measured_profile']['dev_blocks'] == 1
    assert result['measured_profile']['fit_rows'] > 0


def test_beijing_count_sidecar_keeps_per_query_counts_without_regime_field():
    from famjet_poc.contracts import PopulationSpec, ShapeSpec
    from famjet_poc.data import generate_episode
    from famjet_poc.protected import episode_count_records
    spec = PopulationSpec('poc_numeric_v1', ShapeSpec(12, 1), 'unit_test', 84,
                          (128,), ('piecewise_stationary',), 8, 512)
    episode = generate_episode(spec, 'real-count-unit')
    episode.metadata.pop('regime')
    episode.metadata['preparation_version'] = 'beijing_observed_v2_targets'
    rows = episode_count_records(episode)
    assert len(rows) == 8
    assert [row['query_id'] for row in rows] == list(range(8))
    assert all(row['regime'] == 'beijing_observed' and
               isinstance(row['observed_counts'], list) for row in rows)


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
