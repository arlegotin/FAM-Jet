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


def case(history='unit-comparator-0', queries=8, cancellation=True, shape=ShapeSpec(12, 1)):
    spec = PopulationSpec('poc_numeric_v1', shape, 'unit_test', 318,
                          (128,), ('piecewise_stationary',), queries, 512)
    ep = generate_episode(spec, history)
    ep.metadata['split'] = 'training'
    model = build_model(shape, ReaderSpec('ridge_v1', 'jet', 8, 1e-6,
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
    diagnostic = validate_coordinate_audits(costs, rows, expected_model=model)
    assert diagnostic['strict_prediction_failed_histories'] == 1
    assert diagnostic['query_count'] == 8
    from famjet_poc.protected import (episode_count_records, write_count_sidecar,
                                      validate_scored_receipt, _write_once)
    receipt = {'method': 'laguerre', 'costs': costs,
               'score_contract': {'policy_ref': _write_once(tmp_path / 'policy.json', policy),
                                  'statistics_sha256': canonical_hash(model.target_statistics)},
               'counts_ref': write_count_sidecar(episode_count_records(ep), policy['manifest_hash'], tmp_path / 'counts')}
    assert validate_scored_receipt(receipt, rows, policy['manifest_hash'],
                                  list(ep.events.history_ids), list(range(8)), coordinate_model=model)['query_count'] == 8
    missing = {**receipt, 'costs': {}}
    with pytest.raises(ValueError, match='coordinate'):
        validate_scored_receipt(missing, rows, policy['manifest_hash'],
                                list(ep.events.history_ids), list(range(8)), coordinate_model=model)
    fallback_ep = replace(ep, events=replace(ep.events, observed=torch.zeros_like(ep.events.observed)))
    fallback_rows, fallback_summary, fallback_costs = _evaluate(model, lambda: iter([fallback_ep]),
        policy, model.target_statistics, 'laguerre', limits, tmp_path / 'fallback', time.monotonic(),
        allocation, equivalent=True)
    assert len(fallback_rows) == 8 and all(row['fallback'] for row in fallback_rows)
    assert all(np.isfinite(row['loss']) for row in fallback_rows)
    assert fallback_summary['fallback_count'] == 8
    assert validate_coordinate_audits(fallback_costs, fallback_rows, expected_model=model)['evaluated_scalar_count'] == 0
    empty_bad = copy.deepcopy(fallback_costs)
    empty_bad['stream_audits'][ep.events.history_ids[0]]['coordinate_diagnostic']['max_prediction_scaled_error'] = .5
    empty_bad['stream_audits_sha256'] = canonical_hash(empty_bad['stream_audits'])
    empty_bad['coordinate_diagnostic_summary']['max_prediction_scaled_error'] = .5
    with pytest.raises(ValueError, match='coordinate'):
        validate_coordinate_audits(empty_bad, fallback_rows, expected_model=model)
    dimension_bad = copy.deepcopy(fallback_costs)
    d = dimension_bad['stream_audits'][ep.events.history_ids[0]]['coordinate_diagnostic']
    d['value_dim'] = 2
    d['total_scalar_count'] = 16
    dimension_bad['coordinate_diagnostic_summary']['total_scalar_count'] = 16
    dimension_bad['stream_audits_sha256'] = canonical_hash(dimension_bad['stream_audits'])
    dimension_rows = [{**row, 'raw_prediction': [None, None]} for row in fallback_rows]
    with pytest.raises(ValueError, match='coordinate'):
        validate_coordinate_audits(dimension_bad, dimension_rows, expected_model=model)
    with pytest.raises(ValueError, match='coordinate'):
        validate_coordinate_audits(costs, rows, expected_model=None)
    for damage in ('missing', 'digest', 'history', 'status', 'count', 'max', 'model', 'mask_integer', 'state_integer', 'coherent_model'):
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
        elif damage == 'coherent_model':
            bad['coordinate_model_sha256'] = '0' * 64
            item['model_numeric_sha256'] = '0' * 64
        elif damage == 'mask_integer':
            item['mask_checks']['support'] = 1
        elif damage == 'state_integer':
            item['state_checks']['h'] = 1
        else:
            item['model_numeric_sha256'] = '0' * 64
        if damage != 'digest':
            bad['stream_audits_sha256'] = canonical_hash(audits)
        with pytest.raises(ValueError, match='coordinate'):
            validate_coordinate_audits(bad, rows, expected_model=model)


def selected_producer(root, shape=ShapeSpec(12, 1)):
    """Actual fitted numeric model and E3 rows, in the E4 selected-reference envelope."""
    import time
    from famjet_poc.models import fit_training_metadata, fit_reader, make_fit_manifest, save_model
    from famjet_poc.study import _evaluate, freeze_score_policy, persist_score_rows
    from famjet_poc.comparators import coordinate_model_sha256
    root.mkdir(parents=True, exist_ok=True)
    model, train = case(cancellation=False, shape=shape)
    metadata = fit_training_metadata(lambda: iter([train]))
    model = build_model(model.shape, model.spec, metadata['t_ref'], metadata['target_statistics'])
    fit_reader(model, lambda: iter([train]), make_fit_manifest(model, metadata))
    saved = save_model(model, root / 'jet.json')
    episodes = [case(f'dev-{i}', queries=120, shape=shape)[1] for i in range(4)]
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


def forge_coordinate_model(costs):
    bad = copy.deepcopy(costs)
    bad['coordinate_model_sha256'] = '0' * 64
    for audit in bad['stream_audits'].values():
        audit['coordinate_diagnostic']['model_numeric_sha256'] = '0' * 64
    bad['stream_audits_sha256'] = canonical_hash(bad['stream_audits'])
    return bad


def test_resume_rejects_coherent_wrong_numeric_model(tmp_path):
    from famjet_poc.study import _audit_terminal_entries, load_score_rows, persist_score_rows
    modes = selected_producer(tmp_path)
    selected = modes['selected_reference']
    rows = load_score_rows(selected['rows_ref'])
    policy = next(row['policy'] for row in rows if row['score_scope'] == 'primary')
    candidate_rows = [{**row, 'method': 'candidate-jet'} for row in rows]
    candidate_ref = persist_score_rows(candidate_rows, tmp_path / 'candidate-rows.json')
    candidate = {'family': 'jet', 'config_hash': 'candidate-jet', 'status': 'qualified',
                 'loss': selected['summary']['loss'], 'active_static_bytes': 1,
                 'fit_ref': modes['task_adapted']['jet'], 'rows_ref': candidate_ref, 'score': selected['summary']}
    journal = {'candidate_ledger': [candidate], 'prefix_ledger': [],
               'selected': {'jet': {'fit_ref': modes['task_adapted']['jet']}},
               'controls': {'laguerre': {'status': 'measured', 'rows_ref': selected['rows_ref'],
                   'score': selected['summary'], 'costs': selected['costs']}}}
    _audit_terminal_entries(journal, policy, tmp_path)
    journal['controls']['laguerre']['costs'] = forge_coordinate_model(selected['costs'])
    with pytest.raises(ValueError, match='coordinate'):
        _audit_terminal_entries(journal, policy, tmp_path)


@pytest.mark.parametrize('phase', ['synthetic', 'synthetic_frozen', 'task_adapted'])
def test_shared_release_validator_binds_phase_checkpoint(tmp_path, phase):
    from famjet_poc.models import load_model
    from famjet_poc.study import load_score_rows
    from famjet_poc.protected import (_write_once, episode_count_records, write_count_sidecar,
                                      validate_scored_receipt)
    modes = selected_producer(tmp_path)
    selected = modes['selected_reference']
    rows = load_score_rows(selected['rows_ref'])
    ref = modes['task_adapted']['jet']
    model = load_model(ref['path'], ref['sha256'])
    policy = next(row['policy'] for row in rows if row['score_scope'] == 'primary')
    records = [record for i in range(4) for record in episode_count_records(case(f'dev-{i}', queries=120)[1])]
    receipt = {'method': 'laguerre', 'mode': phase,
               'model_pair_sha256': canonical_hash({'jet': ref}),
               'costs': selected['costs'],
               'score_contract': {'policy_ref': _write_once(tmp_path / 'policy.json', policy),
                                  'statistics_sha256': canonical_hash(model.target_statistics)},
               'counts_ref': write_count_sidecar(records, 'a' * 64, tmp_path / 'counts')}
    arguments = (receipt, rows, 'a' * 64, [f'dev-{i}' for i in range(4)], list(range(120)))
    assert validate_scored_receipt(*arguments, coordinate_model=model)['query_count'] == 480
    receipt['costs'] = forge_coordinate_model(receipt['costs'])
    with pytest.raises(ValueError, match='coordinate'):
        validate_scored_receipt(*arguments, coordinate_model=model)


def test_portable_development_and_stress_bind_frozen_selected_models(tmp_path):
    import shutil
    from test_poc_report_scientific import _producer_journal
    from famjet_poc.protected import _write_once
    from famjet_poc.report_inputs import ArtifactPaths, _verify_development, _verify_stress
    from famjet_poc.pipeline import secondary_ledger, stress_inventory
    original = tmp_path / 'original'
    producers = {key: selected_producer(original / key, shape)
                 for key, shape in (('k16', ShapeSpec(16, 8)), ('k12', ShapeSpec(12, 1)))}
    stages, journals = {}, {}
    freeze = {'inputs': {}}
    for key, producer in producers.items():
        selected = producer['selected_reference']
        model_ref = producer['task_adapted']['jet']
        journal = _producer_journal()
        journal['selected']['jet']['fit_ref'] = model_ref
        for item in [*journal['candidate_ledger'], *journal['prefix_ledger']]:
            if 'fit_ref' in item:
                item['fit_ref'] = model_ref
                item['rows_ref'] = selected['rows_ref']
        for name, item in journal['controls'].items():
            item['rows_ref'] = selected['rows_ref']
            if name == 'laguerre':
                item['costs'] = selected['costs']
        journals[key] = journal
        ref = _write_once(original / key / 'journal.json', journal)
        stages['development_' + key] = {'result': {'journal_path': ref['path'], 'journal_sha256': ref['sha256']}}
        freeze['inputs']['study_' + key + '_sha256'] = ref['sha256']
        freeze['inputs']['selected_models' if key == 'k16' else 'selected_k12_models'] = {'jet': model_ref}
    selected = producers['k16']['selected_reference']
    results = [{'mode': 'noise', 'method': 'laguerre', 'status': 'implemented/scored', 'reason': None,
                'summary': selected['summary'], 'costs': selected['costs'],
                'rows_ref': selected['rows_ref'], 'tasks': ['mean', 'contrast']}]
    stress = {'kind': 'famjet_e4_public_stress', 'inventory_sha256': canonical_hash(stress_inventory()),
              'results': results, 'secondary_task_ledger': secondary_ledger(results)}
    stress_ref = _write_once(original / 'stress.json', stress)
    stress_stage = {'result': {'results_path': stress_ref['path'], 'results_sha256': stress_ref['sha256']}}
    copied = tmp_path / 'copied'
    shutil.copytree(original, copied)
    shutil.rmtree(original)
    paths = ArtifactPaths(copied, original / 'freeze/study-freeze-v1.json')
    assert set(_verify_development(paths, stages, freeze)) == {'K16/V8', 'K12/V1'}
    assert _verify_stress(paths, stress_stage, freeze)['results'][0]['method'] == 'laguerre'
    for key in producers:
        bad_journal = copy.deepcopy(journals[key])
        bad_journal['controls']['laguerre']['costs'] = forge_coordinate_model(bad_journal['controls']['laguerre']['costs'])
        ref = _write_once(copied / key / 'forged-journal.json', bad_journal)
        # Commit the altered outer journal while retaining the independently frozen Jet.
        ref['path'] = str(original / key / 'forged-journal.json')
        bad_stages = copy.deepcopy(stages)
        bad_stages['development_' + key]['result'] = {'journal_path': ref['path'], 'journal_sha256': ref['sha256']}
        bad_freeze = copy.deepcopy(freeze)
        bad_freeze['inputs']['study_' + key + '_sha256'] = ref['sha256']
        with pytest.raises(ValueError, match='coordinate'):
            _verify_development(paths, bad_stages, bad_freeze)
    stress['results'][0]['costs'] = forge_coordinate_model(stress['results'][0]['costs'])
    stress['secondary_task_ledger'] = secondary_ledger(stress['results'])
    ref = _write_once(copied / 'forged-stress.json', stress)
    bad_stage = {'result': {'results_path': str(original / 'forged-stress.json'), 'results_sha256': ref['sha256']}}
    with pytest.raises(ValueError, match='coordinate'):
        _verify_stress(paths, bad_stage, freeze)
