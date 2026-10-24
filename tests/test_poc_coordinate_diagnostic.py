"""Coordinate rounding remains a failed strict criterion throughout audited replay."""
import copy
from dataclasses import replace
import numpy as np
import pytest
import torch

from famjet.provenance import canonical_hash
from famjet.eval.metrics import fit_target_statistics
from famjet_poc.contracts import PopulationSpec, ReaderSpec, ShapeSpec
from famjet_poc.data import generate_episode
from famjet_poc.models import build_model
from famjet_poc.comparators import laguerre_control


def case(history='unit-comparator-0', queries=8, cancellation=True):
    spec = PopulationSpec('poc_numeric_v1', ShapeSpec(12, 1), 'unit_test', 318,
                          (128,), ('piecewise_stationary',), queries, 512)
    ep = generate_episode(spec, history)
    ep.metadata['split'] = 'training'
    model = build_model(ShapeSpec(12, 1), ReaderSpec('ridge_v1', 'jet', 8, 1e-6,
                        1 / 5224, 1., 1e-6, 1e-12), 1., fit_target_statistics([ep]))
    model.coefficients = np.linspace(-.01, .02, 264)
    if cancellation:
        scale = 1e-6
        events = replace(ep.events, timestamps=ep.events.timestamps.double() * scale)
        queries = replace(ep.queries, T=ep.queries.T.double() * scale,
                             age_start=ep.queries.age_start * scale,
                             age_end=ep.queries.age_end * scale)
        ep = replace(ep, events=events, queries=queries)
    return model, ep


def test_small_cancellation_keeps_original_failure_and_model():
    from famjet_poc.comparators import coordinate_model_sha256
    model, ep = case()
    before = coordinate_model_sha256(model)
    with pytest.raises(ArithmeticError, match='original tolerance'):
        laguerre_control(model, ep.events, ep.queries)
    result = laguerre_control(model, ep.events, ep.queries, diagnostic_mode=True)
    diagnostic = result['coordinate_diagnostics'][ep.events.history_ids[0]]
    assert diagnostic['policy'] == 'fp64_coordinate_diagnostic_v2'
    assert diagnostic['strict_prediction_status'] == 'FAILED'
    assert diagnostic['rtol'] == diagnostic['atol'] == 1e-12
    assert diagnostic['max_prediction_scaled_error'] > 1
    assert diagnostic['state_checks'] == {'z': True, 'h': True}
    assert all(diagnostic['mask_checks'].values())
    assert diagnostic['query_ids'] == list(range(8))
    assert diagnostic['evaluated_scalar_count'] == 8
    assert coordinate_model_sha256(model) == before


def test_ordinary_strict_pass_keeps_diagnostics():
    model, ep = case(cancellation=False)
    result = laguerre_control(model, ep.events, ep.queries)
    assert result['coordinate_diagnostics'][ep.events.history_ids[0]]['strict_prediction_status'] == 'PASSED'


@pytest.mark.parametrize('corruption', ['state', 'finite', 'support', 'failure', 'prediction_valid', 'numeric_supported'])
def test_diagnostic_mode_keeps_state_and_all_five_mask_checks_fatal(monkeypatch, corruption):
    import famjet_poc.comparators as module
    model, ep = case(cancellation=False)
    if corruption == 'state':
        original = module.from_laguerre
        def damaged(*args):
            value = original(*args)
            value.h.add_(1.)
            return value
        monkeypatch.setattr(module, 'from_laguerre', damaged)
    else:
        original = model.read
        calls = 0
        def damaged(*args):
            nonlocal calls
            result = original(*args)
            calls += 1
            if calls == 2:
                if corruption == 'finite':
                    result.prediction[0, 0, 0] = float('nan')
                elif corruption in ('support', 'failure'):
                    getattr(result, corruption)[0, 0].logical_not_()
                else:
                    result.diagnostics[corruption][0, 0].logical_not_()
            return result
        monkeypatch.setattr(model, 'read', damaged)
    with pytest.raises(ArithmeticError):
        laguerre_control(model, ep.events, ep.queries, diagnostic_mode=True)


def test_e3_producer_scores_every_query_and_validates_audit(tmp_path):
    from famjet_poc.study import _evaluate, freeze_score_policy
    from famjet_poc.comparators import validate_coordinate_audits
    import time
    model, train = case(cancellation=False)
    from famjet_poc.models import fit_training_metadata, fit_reader, make_fit_manifest
    metadata = fit_training_metadata(lambda: iter([train]))
    model = build_model(model.shape, model.spec, metadata['t_ref'], metadata['target_statistics'])
    fit_reader(model, lambda: iter([train]), make_fit_manifest(model, metadata))
    _, ep = case()
    policy = freeze_score_policy([ep])
    allocation = {'max_wall_seconds': 60, 'max_rss_bytes': 2**30, 'max_disk_bytes': 2**24}
    limits = {'max_frame_bytes': 2**22, 'max_array_bytes': 2**21, 'max_histories': 64}
    rows, summary, costs = _evaluate(model, lambda: iter([ep]), policy, model.target_statistics,
                                    'laguerre', limits, tmp_path, time.monotonic(), allocation,
                                    equivalent=True)
    assert len(rows) == 8
    assert all(row['prediction'] is not None for row in rows)
    assert summary['status'] == 'ok'
    diagnostic = validate_coordinate_audits(costs, rows)
    assert diagnostic['strict_prediction_failed_histories'] == 1
    assert diagnostic['query_count'] == 8
    from famjet_poc.protected import (episode_count_records, write_count_sidecar,
                                      validate_scored_receipt, _write_once)
    receipt = {'method': 'laguerre', 'costs': costs,
               'score_contract': {'policy_ref': _write_once(tmp_path / 'policy.json', policy),
                                  'statistics_sha256': canonical_hash(model.target_statistics)},
               'counts_ref': write_count_sidecar(episode_count_records(ep), policy['manifest_hash'], tmp_path / 'counts')}
    assert validate_scored_receipt(receipt, rows, policy['manifest_hash'],
                                  list(ep.events.history_ids), list(range(8)))['query_count'] == 8
    missing = {**receipt, 'costs': {}}
    with pytest.raises(ValueError, match='coordinate'):
        validate_scored_receipt(missing, rows, policy['manifest_hash'],
                                list(ep.events.history_ids), list(range(8)))
    fallback_ep = replace(ep, events=replace(ep.events, observed=torch.zeros_like(ep.events.observed)))
    fallback_rows, fallback_summary, fallback_costs = _evaluate(model, lambda: iter([fallback_ep]),
        policy, model.target_statistics, 'laguerre', limits, tmp_path / 'fallback', time.monotonic(),
        allocation, equivalent=True)
    assert len(fallback_rows) == 8 and all(row['fallback'] for row in fallback_rows)
    assert all(np.isfinite(row['loss']) for row in fallback_rows)
    assert fallback_summary['fallback_count'] == 8
    assert validate_coordinate_audits(fallback_costs, fallback_rows)['evaluated_scalar_count'] == 0
    for damage in ('missing', 'digest', 'history', 'status', 'count', 'max', 'model', 'mask_integer', 'state_integer'):
        bad = copy.deepcopy(costs)
        audits = bad['stream_audits']
        item = audits[ep.events.history_ids[0]]['coordinate_diagnostic']
        if damage == 'missing':
            audits[ep.events.history_ids[0]].pop('coordinate_diagnostic')
        elif damage == 'digest':
            bad['stream_audits_sha256'] = '0' * 64
        elif damage == 'history':
            item['query_ids'].pop()
        elif damage == 'status':
            item['strict_prediction_status'] = 'PASSED'
        elif damage == 'count':
            item['evaluated_scalar_count'] = 0
        elif damage == 'max':
            item['max_prediction_scaled_error'] = 0.
        elif damage == 'mask_integer':
            item['mask_checks']['support'] = 1
        elif damage == 'state_integer':
            item['state_checks']['h'] = 1
        else:
            item['model_numeric_sha256'] = '0' * 64
        if damage != 'digest':
            bad['stream_audits_sha256'] = canonical_hash(audits)
        with pytest.raises(ValueError, match='coordinate'):
            validate_coordinate_audits(bad, rows)


def selected_producer(root):
    """Actual fitted numeric model and E3 rows, in the E4 selected-reference envelope."""
    import time
    from famjet_poc.models import fit_training_metadata, fit_reader, make_fit_manifest, save_model
    from famjet_poc.study import _evaluate, freeze_score_policy, persist_score_rows
    from famjet_poc.comparators import coordinate_model_sha256
    root.mkdir(parents=True, exist_ok=True)
    model, train = case(cancellation=False)
    metadata = fit_training_metadata(lambda: iter([train]))
    model = build_model(model.shape, model.spec, metadata['t_ref'], metadata['target_statistics'])
    fit_reader(model, lambda: iter([train]), make_fit_manifest(model, metadata))
    saved = save_model(model, root / 'jet.json')
    episodes = [case(f'dev-{i}', queries=120)[1] for i in range(4)]
    policy = freeze_score_policy(episodes, manifest_hash='a' * 64)
    allocation = {'max_wall_seconds': 60, 'max_rss_bytes': 2**30, 'max_disk_bytes': 2**26}
    limits = {'max_frame_bytes': 2**24, 'max_array_bytes': 2**23, 'max_histories': 64}
    rows, summary, costs = _evaluate(model, lambda: iter(episodes), policy, model.target_statistics,
                  'laguerre', limits, root, time.monotonic(), allocation, equivalent=True)
    ref = persist_score_rows(rows, root / 'rows.json')
    return {'task_adapted': {'jet': {'path': str(saved.path), 'sha256': saved.sha256}},
            'beijing_manifest_sha256': 'a' * 64,
            'development_cache': [{'history_id': f'dev-{i}'} for i in range(4)],
            'selected_reference': {'schema_version': 2, 'status': 'diagnostic_complete',
                'policy': 'fp64_coordinate_diagnostic_v2', 'model_sha256': saved.sha256,
                'model_numeric_sha256': coordinate_model_sha256(model),
                'manifest_sha256': 'a' * 64, 'rows_ref': ref, 'summary': summary, 'costs': costs}}


def test_e4_e5_selected_model_complete_inventory_and_status_are_bound(tmp_path):
    from famjet_poc.transfer import verify_selected_reference
    from famjet_poc.report_inputs import ArtifactPaths, verify_selected_reference_rebased
    import shutil
    root = tmp_path / 'original'
    modes = selected_producer(root)
    assert verify_selected_reference(modes)['status'] == 'diagnostic_complete'
    assert modes['selected_reference']['costs']['coordinate_diagnostic_summary']['strict_prediction_status'] == 'FAILED'
    copied = tmp_path / 'copy'
    shutil.copytree(root, copied)
    shutil.rmtree(root)
    paths = ArtifactPaths(copied, root / 'freeze/study-freeze-v1.json')
    assert verify_selected_reference_rebased(paths, modes) == modes['selected_reference']
    for damage in ('missing', 'incomplete', 'status', 'model', 'model_numeric', 'summary', 'forged'):
        bad = copy.deepcopy(modes)
        ref = bad['selected_reference']
        if damage == 'missing':
            ref['costs'].pop('stream_audits')
        elif damage == 'incomplete':
            ref['costs']['stream_audits'].pop('dev-0')
            ref['costs']['stream_audits_sha256'] = canonical_hash(ref['costs']['stream_audits'])
        elif damage == 'status':
            ref['status'] = 'passed'
        elif damage == 'model':
            ref['model_sha256'] = 'b' * 64
        elif damage == 'model_numeric':
            ref['model_numeric_sha256'] = 'b' * 64
        elif damage == 'summary':
            ref['costs'].pop('coordinate_diagnostic_summary')
        else:
            d = ref['costs']['stream_audits']['dev-0']['coordinate_diagnostic']
            d['strict_prediction_status'] = 'PASSED'
            ref['costs']['stream_audits_sha256'] = canonical_hash(ref['costs']['stream_audits'])
        with pytest.raises(ValueError, match='coordinate|reference'):
            verify_selected_reference_rebased(paths, bad)


def test_report_exposes_failed_read_criteria_for_every_phase_and_prior_cost(tmp_path):
    from famjet_poc.report import coordinate_report, coordinate_markdown
    modes = selected_producer(tmp_path / 'producer')
    costs = modes['selected_reference']['costs']
    inputs = {'development': {'K16': {'controls': {'laguerre': {'costs': costs}}}},
              'synthetic': {'by_phase_method': {'confirmation/laguerre': {'costs': [costs]}}},
              'stress': {'results': [{'method': 'laguerre', 'costs': costs}]},
              'transfer': {'selected_reference': modes['selected_reference']},
              'real': {'modes': {mode: {'laguerre': {'costs': costs}}
                                for mode in ('synthetic_frozen', 'task_adapted')}}}
    diagnostic = coordinate_report(inputs)
    assert len(diagnostic['panels']) == 6
    assert all(d['strict_prediction_status'] == 'FAILED' for d in diagnostic['panels'].values())
    text = coordinate_markdown(diagnostic)
    assert 'FAILED' in text and 'PASSED' in text
    assert '1728.763838625' in text and '848740352' in text
    assert 'e2e-laguerre-actual-diagnostic-report.md' in text
    assert 'not established' in text
