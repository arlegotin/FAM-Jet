from dataclasses import replace

import numpy as np
import pytest
import torch

from famjet.eval.metrics import aggregate_scores, fit_target_statistics
from famjet.types import ReadResult
from famjet_poc.contracts import PopulationSpec, ShapeSpec
from famjet_poc.data import generate_episode


def _episode():
    spec = PopulationSpec('poc_numeric_v1', ShapeSpec(12, 1), 'unit_test', 318,
                          (128,), ('piecewise_stationary',), 8, 512)
    return generate_episode(spec, 'unit-score-0')


def _invalidate(ep, indices):
    metadata = dict(ep.metadata)
    mask = [list(row) for row in metadata['target_valid']]
    supported = ep.supported.clone()
    labels = ep.labels.clone()
    for j in indices:
        mask[0][j] = False
        supported[0, j] = False
        labels[0, j] = float('nan')
    metadata['target_valid'] = mask
    return replace(ep, labels=labels, supported=supported, metadata=metadata)


def test_study_manifest_freezes_balanced_prefixes_and_grid():
    from famjet_poc.study import study_manifest

    manifest = study_manifest({'profile': 'study', 'shape': ShapeSpec(12, 1).to_json(),
                               'training_seed': 13, 'development_seed': 29,
                               'max_query_attempts': 512,
                               'cache_limits': {'disk_bytes': 1_073_741_824, 'lru_bytes': 67_108_864},
                               'worker_limits': {'max_frame_bytes': 64_000_000,
                                                 'max_array_bytes': 32_000_000, 'max_histories': 64}})
    assert len(manifest['training_inventory']) == 768
    assert len(manifest['development_inventory']) == 192
    assert len(manifest['candidates']) == 36
    assert manifest['stream_chunk_size'] == 128 and manifest['stream_mode'] == 'stream'
    for prefix, per_cell in ((192, 16), (384, 32), (768, 64)):
        counts = {}
        for item in manifest['training_inventory'][:prefix]:
            cell = (item['spec']['lengths'][0], item['spec']['regimes'][0])
            counts[cell] = counts.get(cell, 0) + 1
        assert len(counts) == 12 and set(counts.values()) == {per_cell}


def test_score_results_retains_invalid_diagnostic_and_valid_failed_fallback():
    from famjet_poc.study import freeze_score_policy, score_results

    ep = _episode()
    stats = fit_target_statistics([replace(ep, metadata={**ep.metadata, 'split': 'training'})])
    invalid = next(j for j, t in enumerate(ep.queries.tasks[0]) if t == 'mean')
    ep = _invalidate(ep, [invalid])
    policy = freeze_score_policy([ep], tasks=('mean', 'contrast'))
    failure = torch.zeros_like(ep.queries.present)
    valid_failure = next(j for j, t in enumerate(ep.queries.tasks[0]) if t == 'contrast' and ep.metadata['target_valid'][0][j])
    failure[0, valid_failure] = True
    result = ReadResult(torch.zeros_like(ep.labels), None, torch.ones_like(failure), failure,
                        {'prediction_valid': torch.ones_like(failure), 'numeric_supported': torch.ones_like(failure)})
    rows = score_results([ep], [{'result': result, 'trigger': None, 'state_bytes': 222}],
                         stats, policy, 'unit-method')
    assert len(rows) == int(ep.queries.lengths[0])
    diagnostic = next(r for r in rows if r['query_id'] == invalid)
    assert diagnostic['eligible'] is False and diagnostic['score_scope'] == 'ineligible_diagnostic'
    failed = next(r for r in rows if r['query_id'] == valid_failure)
    assert failed['eligible'] and failed['fallback'] and failed['loss'] is not None
    assert aggregate_scores([r for r in rows if r['eligible']])['status'] == 'ok'


def test_missing_primary_task_blocks_without_redraw():
    from famjet_poc.study import freeze_score_policy

    ep = _episode()
    invalid = [j for j, t in enumerate(ep.queries.tasks[0]) if t == 'contrast']
    with pytest.raises(ValueError, match='eligible|task'):
        freeze_score_policy([_invalidate(ep, invalid)], tasks=('mean', 'contrast'))


def test_selection_uses_loss_then_static_bytes_then_hash_and_keeps_failure():
    from famjet_poc.study import select_candidate

    ledger = [{'config_hash': 'a', 'status': 'failed', 'loss': None},
              {'config_hash': 'b', 'status': 'qualified', 'loss': 0.2, 'active_static_bytes': 110},
              {'config_hash': 'c', 'status': 'qualified', 'loss': 0.2 + 5e-13, 'active_static_bytes': 100},
              {'config_hash': 'd', 'status': 'qualified', 'loss': 0.3, 'active_static_bytes': 50}]
    assert select_candidate(ledger)['config_hash'] == 'c'
    assert ledger[0]['status'] == 'failed'


def test_selection_tied_active_storage_ignores_wire_json_length():
    from famjet_poc.study import select_candidate

    ledger = [{'config_hash': 'a', 'status': 'qualified', 'loss': .2,
               'active_static_bytes': 512, 'wire_static_bytes': 900},
              {'config_hash': 'b', 'status': 'qualified', 'loss': .2 + 5e-13,
               'active_static_bytes': 512, 'wire_static_bytes': 800}]
    assert select_candidate(ledger)['config_hash'] == 'a'


def test_score_results_matches_causal_score_episode_on_valid_tiny_case():
    from famjet.eval.runner import score_episode
    from famjet_poc.contracts import ReaderSpec
    from famjet_poc.models import build_model
    from famjet_poc.study import _stream_snapshot, freeze_score_policy, score_results

    ep = _episode()
    assert all(ep.metadata['target_valid'][0])
    stats = fit_target_statistics([replace(ep, metadata={**ep.metadata, 'split': 'training'})])
    model = build_model(ShapeSpec(12, 1),
                        ReaderSpec('ridge_v1', 'jet', 8, 1e-6, 1 / 5224, 1., 1e-6, 1e-12), 1., stats)
    policy = freeze_score_policy([ep])
    state, trigger, nbytes = _stream_snapshot(model, ep)
    assert trigger is None
    rows = score_results([ep], [{'result': model.read(state, ep.queries), 'trigger': None,
                                 'state_bytes': nbytes}], stats, policy, 'ridge')
    reference = score_episode(model, ep, method='ridge', policy=policy,
                              manifest_hash=policy['full_inventory_hash'])
    for actual, expected in zip(rows, reference):
        assert actual['query_id'] == expected['query_id']
        assert actual['loss'] == expected['loss']
        assert actual['fallback'] == expected['fallback']


def test_probe_requires_phase_bound_finite_allocation(tmp_path):
    from famjet_poc.study import probe_feasibility, study_manifest

    manifest = study_manifest({'profile': 'unit_test', 'shape': ShapeSpec(12, 1).to_json(),
                               'training_seed': 13, 'development_seed': 29, 'max_query_attempts': 512,
                               'cache_limits': {'disk_bytes': 8_000_000, 'lru_bytes': 1_000_000},
                               'worker_limits': {'max_frame_bytes': 8_000_000,
                                                 'max_array_bytes': 4_000_000, 'max_histories': 64}})
    with pytest.raises(ValueError, match='allocation'):
        probe_feasibility(manifest, tmp_path, {'override': True})


def test_public_score_results_rejects_incomplete_expected_inventory():
    from famjet_poc.study import freeze_score_policy, score_results

    first = _episode()
    spec = PopulationSpec('poc_numeric_v1', ShapeSpec(12, 1), 'unit_test', 318,
                          (128,), ('piecewise_stationary',), 8, 512)
    second = generate_episode(spec, 'unit-score-1')
    policy = freeze_score_policy([first, second])
    stats = fit_target_statistics([replace(first, metadata={**first.metadata, 'split': 'training'}),
                                   replace(second, metadata={**second.metadata, 'split': 'training'})])
    failure = torch.ones_like(first.queries.present)
    result = ReadResult(torch.full_like(first.labels, float('nan')), None, ~failure, failure,
                        {'prediction_valid': ~failure, 'numeric_supported': ~failure})
    with pytest.raises(ValueError, match='incomplete'):
        score_results([first], [{'result': result, 'trigger': None, 'state_bytes': 10}],
                      stats, policy, 'ridge')


def test_development_requires_successful_probe_before_cache_generation(tmp_path, monkeypatch):
    from famjet_poc import study

    manifest = study.study_manifest({'profile': 'unit_test', 'shape': ShapeSpec(12, 1).to_json(),
                                     'training_seed': 13, 'development_seed': 29, 'max_query_attempts': 512,
                                     'cache_limits': {'disk_bytes': 8_000_000, 'lru_bytes': 1_000_000},
                                     'worker_limits': {'max_frame_bytes': 8_000_000,
                                                       'max_array_bytes': 4_000_000, 'max_histories': 64}})
    monkeypatch.setattr(study, '_cache_for', lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError('premature cache generation')))
    allocation = {'schema_version': 1, 'phase': 'development', 'manifest_sha256': manifest['manifest_sha256'],
                  'allocation_id': 'unit-no-probe', 'max_wall_seconds': 10.,
                  'max_disk_bytes': 8_000_000, 'max_rss_bytes': 1_000_000_000}
    with pytest.raises(ValueError, match='probe'):
        study.run_development(manifest, tmp_path, allocation)


def test_probe_measures_one_tiny_fit_and_worker_batch_with_full_work_forecast(tmp_path):
    from famjet_poc.study import probe_feasibility, study_manifest

    manifest = study_manifest({'profile': 'unit_test', 'shape': ShapeSpec(12, 1).to_json(),
                               'training_seed': 412, 'development_seed': 318, 'max_query_attempts': 512,
                               'cache_limits': {'disk_bytes': 8_000_000, 'lru_bytes': 8_000_000},
                               'worker_limits': {'max_frame_bytes': 8_000_000,
                                                 'max_array_bytes': 4_000_000, 'max_histories': 64}})
    allocation = {'schema_version': 1, 'phase': 'probe', 'manifest_sha256': manifest['manifest_sha256'],
                  'allocation_id': 'unit-probe', 'max_wall_seconds': 60.,
                  'max_disk_bytes': 8_000_000, 'max_rss_bytes': 2_000_000_000}
    result = probe_feasibility(manifest, tmp_path, allocation)
    assert result['status'] == 'measured', result.get('error')
    assert result['fit_rows'] > 0 and result['costs']['worker_batches'] == 1
    assert result['forecast']['expected_fit_attempts'] == 36
    assert result['forecast']['development_history_passes'] >= 36
    assert result['forecast']['development_event_steps'] >= 36 * 128


def test_probe_existing_output_rejects_different_manifest_before_generation(tmp_path, monkeypatch):
    import json
    from famjet_poc import study

    manifest = study.study_manifest({'profile': 'unit_test', 'shape': ShapeSpec(12, 1).to_json(),
                                     'training_seed': 412, 'development_seed': 318, 'max_query_attempts': 512,
                                     'cache_limits': {'disk_bytes': 8_000_000, 'lru_bytes': 8_000_000},
                                     'worker_limits': {'max_frame_bytes': 8_000_000,
                                                       'max_array_bytes': 4_000_000, 'max_histories': 64}})
    (tmp_path / 'probe.json').write_text(json.dumps({'phase': 'probe', 'manifest_sha256': '0' * 64}))
    monkeypatch.setattr(study, '_cache_for', lambda *a, **k: (_ for _ in ()).throw(AssertionError('cache touched')))
    allocation = {'schema_version': 1, 'phase': 'probe', 'manifest_sha256': manifest['manifest_sha256'],
                  'allocation_id': 'unit-probe-bind', 'max_wall_seconds': 60.,
                  'max_disk_bytes': 8_000_000, 'max_rss_bytes': 2_000_000_000}
    with pytest.raises(ValueError, match='manifest|probe'):
        study.probe_feasibility(manifest, tmp_path, allocation)


def test_resume_allocation_clock_charges_previous_wall_time(monkeypatch):
    from famjet_poc import study

    monkeypatch.setattr(study.time, 'time', lambda: 103.)
    monkeypatch.setattr(study.time, 'monotonic', lambda: 1000.)
    monkeypatch.setattr(study, '_rss_bytes', lambda: 1)
    started = study._resume_allocation_started({'allocation_started_epoch_seconds': 100.})
    allocation = {'max_wall_seconds': 10., 'max_disk_bytes': 1000, 'max_rss_bytes': 1000}
    assert study._admit(started, allocation)['remaining_wall_seconds'] == pytest.approx(7.)
    monkeypatch.setattr(study.time, 'monotonic', lambda: 1007.1)
    with pytest.raises(RuntimeError, match='allocation'):
        study._admit(started, allocation)


def test_development_resume_exhausted_clock_blocks_before_cache_reopen(tmp_path, monkeypatch):
    import hashlib
    import json
    from famjet_poc import study

    manifest = study.study_manifest({'profile': 'unit_test', 'shape': ShapeSpec(12, 1).to_json(),
                                     'training_seed': 412, 'development_seed': 318, 'max_query_attempts': 512,
                                     'cache_limits': {'disk_bytes': 8_000_000, 'lru_bytes': 8_000_000},
                                     'worker_limits': {'max_frame_bytes': 8_000_000,
                                                       'max_array_bytes': 4_000_000, 'max_histories': 64}})
    probe = tmp_path / 'probe.json'
    probe.write_text(json.dumps({'phase': 'probe', 'manifest_sha256': manifest['manifest_sha256'],
                                 'status': 'measured', 'feasible': True}))
    allocation = {'schema_version': 1, 'phase': 'development', 'manifest_sha256': manifest['manifest_sha256'],
                  'allocation_id': 'unit-resume-expired', 'max_wall_seconds': 10.,
                  'max_disk_bytes': 8_000_000, 'max_rss_bytes': 2_000_000_000,
                  'probe_ref': {'path': str(probe), 'sha256': hashlib.sha256(probe.read_bytes()).hexdigest()}}
    (tmp_path / 'development.json').write_text(json.dumps({
        'manifest_sha256': manifest['manifest_sha256'], 'allocation': allocation,
        'allocation_started_epoch_seconds': 100.}))
    monkeypatch.setattr(study.time, 'time', lambda: 111.)
    monkeypatch.setattr(study.time, 'monotonic', lambda: 1000.)
    monkeypatch.setattr(study, '_rss_bytes', lambda: 1)
    monkeypatch.setattr(study, '_cache_for', lambda *a, **k: (_ for _ in ()).throw(AssertionError('cache reopened')))
    with pytest.raises(RuntimeError, match='allocation'):
        study.run_development(manifest, tmp_path, allocation)


def test_normalized_score_rows_roundtrip_policy_and_reject_tampering(tmp_path):
    import hashlib
    import json
    from famjet_poc.study import freeze_score_policy, load_score_rows, persist_score_rows, score_results

    ep = _episode()
    stats = fit_target_statistics([replace(ep, metadata={**ep.metadata, 'split': 'training'})])
    policy = freeze_score_policy([ep])
    failure = torch.zeros_like(ep.queries.present)
    result = ReadResult(torch.zeros_like(ep.labels), None, ~failure, failure,
                        {'prediction_valid': ~failure, 'numeric_supported': ~failure})
    rows = score_results([ep], [{'result': result, 'trigger': None, 'state_bytes': 10}], stats, policy, 'ridge')
    ref = persist_score_rows(rows, tmp_path / 'rows.json')
    packed = json.loads((tmp_path / 'rows.json').read_bytes())
    assert len(packed['policies']) == 1
    assert all('policy' not in row and 'policy_ref' in row for row in packed['rows'])
    restored = load_score_rows(ref)
    assert restored == rows
    assert restored[0]['policy'] is restored[-1]['policy']
    assert aggregate_scores(restored) == aggregate_scores(rows)
    packed['policies'][next(iter(packed['policies']))]['primary_tasks'] = []
    raw = json.dumps(packed).encode()
    (tmp_path / 'rows.json').write_bytes(raw)
    altered = {**ref, 'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw)}
    with pytest.raises(ValueError, match='policy|hash'):
        load_score_rows(altered)


def test_resume_audits_terminal_score_aggregate_and_paths(tmp_path):
    from famjet_poc.study import _audit_terminal_entries, freeze_score_policy, persist_score_rows, score_results

    ep = _episode()
    stats = fit_target_statistics([replace(ep, metadata={**ep.metadata, 'split': 'training'})])
    policy = freeze_score_policy([ep])
    failure = torch.zeros_like(ep.queries.present)
    result = ReadResult(torch.zeros_like(ep.labels), None, ~failure, failure,
                        {'prediction_valid': ~failure, 'numeric_supported': ~failure})
    rows = score_results([ep], [{'result': result, 'trigger': None, 'state_bytes': 10}], stats, policy, 'ridge')
    ref = persist_score_rows(rows, tmp_path / 'rows.json')
    summary = aggregate_scores([r for r in rows if r['score_scope'] == 'primary'])
    journal = {'candidate_ledger': [], 'prefix_ledger': [],
               'controls': {'ridge': {'status': 'measured', 'rows_ref': ref, 'score': summary}}}
    _audit_terminal_entries(journal, policy, tmp_path)
    journal['controls']['ridge']['score'] = {**summary, 'loss': 999.}
    with pytest.raises(ValueError, match='aggregate'):
        _audit_terminal_entries(journal, policy, tmp_path)
    journal['controls']['ridge']['score'] = summary
    journal['controls']['ridge']['rows_ref'] = {**ref, 'path': str(tmp_path.parent / 'rows.json')}
    with pytest.raises(ValueError, match='escapes'):
        _audit_terminal_entries(journal, policy, tmp_path)


def test_resume_accepts_bound_primary_and_partial_eligibility_diagnostics(tmp_path):
    from famjet_poc.study import _audit_terminal_entries, freeze_score_policy, load_score_rows, persist_score_rows, score_results

    original = _episode()
    invalid = next(j for j, task in enumerate(original.queries.tasks[0]) if task == 'mean')
    ep = _invalidate(original, [invalid])
    stats = fit_target_statistics([replace(original, metadata={**original.metadata, 'split': 'training'})])
    policy = freeze_score_policy([ep])
    failure = torch.zeros_like(ep.queries.present)
    result = ReadResult(torch.zeros_like(ep.labels), None, ~failure, failure,
                        {'prediction_valid': ~failure, 'numeric_supported': ~failure})
    rows = score_results([ep], [{'result': result, 'trigger': None, 'state_bytes': 10}], stats, policy, 'ridge')
    assert {r['score_scope'] for r in rows} == {'primary', 'ineligible_diagnostic'}
    ref = persist_score_rows(rows, tmp_path / 'partial.json')
    assert load_score_rows(ref) == rows
    summary = aggregate_scores([r for r in rows if r['score_scope'] == 'primary'])
    journal = {'candidate_ledger': [], 'prefix_ledger': [],
               'controls': {'ridge': {'status': 'measured', 'rows_ref': ref, 'score': summary}}}
    _audit_terminal_entries(journal, policy, tmp_path)


def test_public_panel_evaluator_reuses_worker_and_normalized_rows(tmp_path):
    from famjet.memory.exact_store import PackedHistoryMemory
    from famjet_poc.study import evaluate_panel, freeze_score_policy, load_score_rows

    ep = _episode()
    stats = fit_target_statistics([replace(ep, metadata={**ep.metadata, 'split': 'training'})])
    policy = freeze_score_policy([ep])
    allocation = {'schema_version': 1, 'phase': 'unit_test', 'manifest_sha256': policy['full_inventory_hash'],
                  'allocation_id': 'unit-panel', 'max_wall_seconds': 30.,
                  'max_disk_bytes': 8_000_000, 'max_rss_bytes': 2_000_000_000}
    result = evaluate_panel(PackedHistoryMemory(None, 1, 'exact', key_dim=12),
                            lambda: iter([ep]), policy, stats, 'exact', tmp_path, allocation,
                            {'max_frame_bytes': 8_000_000, 'max_array_bytes': 4_000_000,
                             'max_histories': 64})
    rows = load_score_rows(result['rows_ref'])
    assert len(rows) == int(ep.queries.lengths[0])
    assert result['summary'] == aggregate_scores([r for r in rows if r['score_scope'] == 'primary'])
    assert result['costs']['worker_batches'] == 1


def test_explicit_manifest_identity_flows_into_scored_rows():
    from famjet_poc.study import freeze_score_policy, score_results

    ep = _episode()
    stats = fit_target_statistics([replace(ep, metadata={**ep.metadata, 'split': 'training'})])
    policy = freeze_score_policy([ep], manifest_hash='a' * 64)
    failure = torch.zeros_like(ep.queries.present)
    result = ReadResult(torch.zeros_like(ep.labels), None, ~failure, failure,
                        {'prediction_valid': ~failure, 'numeric_supported': ~failure})
    rows = score_results([ep], [{'result': result, 'trigger': None, 'state_bytes': 10}], stats, policy, 'ridge')
    assert {row['manifest_hash'] for row in rows} == {'a' * 64}
    assert policy['full_inventory_hash'] != policy['manifest_hash']


def test_mean_only_secondary_policy_preserves_other_queries_as_diagnostics():
    from famjet_poc.study import freeze_score_policy, score_results

    ep = _episode()
    ep = _invalidate(ep, [j for j, task in enumerate(ep.queries.tasks[0]) if task == 'contrast'])
    original = _episode()
    stats = fit_target_statistics([replace(original, metadata={**original.metadata, 'split': 'training'})])
    policy = freeze_score_policy([ep], tasks=('mean',))
    failure = torch.zeros_like(ep.queries.present)
    result = ReadResult(torch.zeros_like(ep.labels), None, ~failure, failure,
                        {'prediction_valid': ~failure, 'numeric_supported': ~failure})
    rows = score_results([ep], [{'result': result, 'trigger': None, 'state_bytes': 10}], stats, policy, 'ridge')
    assert {r['task'] for r in rows if r['score_scope'] == 'primary'} == {'mean'}
    assert {r['task'] for r in rows if r['score_scope'] == 'ineligible_diagnostic'} == {'contrast'}


def test_beijing_regime_is_derived_without_mutating_episode_metadata():
    from famjet_poc.study import freeze_score_policy

    ep = _episode()
    metadata = {k: v for k, v in ep.metadata.items() if k != 'regime'}
    metadata.update(preparation_version='beijing_observed_v2_targets', normalization='training_standardized')
    ep = replace(ep, metadata=metadata)
    policy = freeze_score_policy([ep])
    assert policy['expected_inventory'][0]['regime'] == 'beijing_observed'
    assert 'regime' not in ep.metadata
