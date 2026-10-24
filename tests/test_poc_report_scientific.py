"""Producer-shaped E3/E4 report contracts without entering a scientific run."""

import copy
import hashlib
import math
from pathlib import Path

import pytest

from famjet.provenance import canonical_hash
from famjet_poc.protected import _write_once
from famjet_poc.study import persist_score_rows
from famjet_poc.report_inputs import ArtifactPaths


def _producer_journal():
    controls = ('exact', 'recent', 'latest_lru', 'reservoir', 'buckets', 'laguerre')
    candidates = []
    for family in ('jet', 'bank'):
        for index in range(18):
            selected = index == 0
            item = {'family': family, 'config_hash': f'{family}-{index:02d}',
                    'reader': {'family': family, 'ridge': 1e-6},
                    'status': 'qualified' if selected else 'failed',
                    'loss': (.2 if family == 'jet' else .3) if selected else None}
            if selected:
                item.update(score={'status': 'ok', 'loss': item['loss']},
                            active_static_bytes=1234 if family == 'jet' else 1334,
                            wire_static_bytes=1500 if family == 'jet' else 1600,
                            numeric_parameter_bytes=1234 if family == 'jet' else 1334,
                            costs={'maximum_state_bytes': 9345,
                                   'statics_bytes': 1500 if family == 'jet' else 1600,
                                   'fit_wall_seconds': 1., 'standalone_seconds': 3.,
                                   'evaluation_seconds': 2.}, fit_rows=100,
                            fit_objective=1., fit_ref={'path': '/fixture/model', 'sha256': 'a'*64},
                            rows_ref={'path': '/fixture/rows', 'sha256': 'b'*64, 'bytes': 1})
            else:
                item.update(error='ArithmeticError: singular', failure_stage='numerical_fit')
            candidates.append(item)
    prefixes = [{'family': family, 'prefix': prefix,
                 'status': 'measured', 'score': {'loss': .4},
                 'costs': {'evaluation_seconds': 1.},
                 'fit_ref': {'path': '/fixture/model', 'sha256': 'a'*64},
                 'rows_ref': {'path': '/fixture/rows', 'sha256': 'b'*64, 'bytes': 1}}
                for family in ('jet', 'bank') for prefix in (192, 384)]
    return {'status': 'complete', 'candidate_ledger': candidates,
            'prefix_ledger': prefixes,
            'controls': {name: {'status': 'measured', 'score': {'loss': .5},
                                'costs': {'maximum_state_bytes': 9345,
                                          'statics_bytes': 10,
                                          'evaluation_seconds': 1.}}
                         for name in controls},
            'selected': {family: {'config_hash': f'{family}-00',
                                  'reader': {'family': family, 'ridge': 1e-6},
                                  'loss': .2 if family == 'jet' else .3}
                         for family in ('jet', 'bank')},
            'shared_costs': {'training_cache_bytes': 10,
                             'development_cache_bytes': 20},
            'fit_attempt_count': 40, 'completed_fit_count': 4}


def test_producer_candidate_storage_and_terminal_subset_failure_render():
    from famjet_poc.report_inputs import project_development_journal
    from famjet_poc.report import _science_chart_data, _science_machine, _science_markdown
    journal = _producer_journal()
    journal['prefix_ledger'][0] = {'family': 'jet', 'prefix': 192, 'status': 'failed',
                                   'error': 'ArithmeticError: singular subset',
                                   'failure_stage': 'numerical_fit'}
    projected = project_development_journal(journal)
    assert projected['candidates'][0]['active_static_bytes'] == 1234
    assert projected['prefixes'][0]['score'] is None
    inputs = {'development': {'K16/V8': projected},
              'timing': {'summaries': {name: {'8': {'read_output_seconds': {'p50': .1}}}
                                      for name in ('jet', 'bank', *journal['controls'])}},
              'synthetic': {'paired_panels': {
                  name: {'D': .1, 'lower': .01, 'upper': .2}
                  for name in ('confirmation', 'replication')}},
              'freeze_sha256': 'a'*64, 'release_sha256': 'b'*64,
              'source_sha256': 'c'*64, 'executable_sha256': 'd'*64}
    chart = _science_chart_data(inputs)
    assert chart['methods'][0]['static_bytes'] == 1500
    assert chart['methods'][1]['static_bytes'] == 1600
    machine = {'decision': 'jet_advantage_not_demonstrated',
               'executable_sha256': 'a'*64, 'source_sha256': 'b'*64,
               'release_sha256': 'c'*64, 'git': {'revision': 'test'},
               'qualification': {'status': 'reused_accepted', 'file_count': 16},
               'calibration': {'evidence_sha256': 'd'*64, 'per_cell': 256},
               'development': {'K16/V8': projected},
               'plot': {'directory_name': 'final-charts'},
               'timing': {'summaries': {}}, 'synthetic': {'paired_panels': {
                   name: {'paired_history_count': 3072, 'D': .1, 'lower': .01,
                          'upper': .2, 'superiority': True}
                   for name in ('confirmation', 'replication')},
                   'by_phase_method': {}},
               'real': {'modes': {}, 'paired_block_sensitivity': {},
                        'beijing_manifest_sha256': 'e'*64},
               'stress': {'secondary_task_ledger': [], 'results': []},
               'beijing_source': {'archive': {'sha256': 'f'*64},
                                  'attribution': {'license': 'CC BY 4.0'},
                                  'preparation_version': 'v2'},
               'beijing_source_array_status': 'verified_inventory_not_rehashed',
               'transfer': {'real_development_ledger': [
                   {'family': 'jet', 'config_hash': 'adapted-jet', 'loss': .1,
                    'active_static_bytes': 1234, 'costs': {'evaluation_seconds': 2.},
                    'status': 'qualified'}], 'cache_bytes': 0,
                            'real_probe': {'measured_profile': {'fit_seconds': 1.,
                                                                 'evaluation_seconds': 2.},
                                           'forecast_seconds': 3.},
                            'elapsed_seconds': 4.}}
    markdown = _science_markdown(machine)
    assert 'jet-00' in markdown
    assert 'ridge' in markdown
    assert 'ArithmeticError: singular subset' in markdown
    inputs.update(freeze={'git': machine['git']},
                  scientific={'qualification': machine['qualification'],
                              'calibration': machine['calibration'], 'pairs': {}},
                  real=machine['real'], stress=machine['stress'],
                  transfer=machine['transfer'],
                  beijing_source_inventory={},
                  beijing_source=machine['beijing_source'],
                  beijing_source_array_status=machine['beijing_source_array_status'])
    assert _science_machine(inputs, machine['plot'])['transfer']['real_development_ledger'][0][
        'config_hash'] == 'adapted-jet'


def test_incomplete_subset_remains_blocking():
    from famjet_poc.report_inputs import project_development_journal
    journal = _producer_journal()
    journal['prefix_ledger'][0] = {'family': 'jet', 'prefix': 192,
                                   'status': 'incomplete',
                                   'failure_stage': 'fit_infrastructure_or_data'}
    with pytest.raises(ValueError, match='subset|incomplete'):
        project_development_journal(journal)


@pytest.mark.parametrize('status,mutation', [
    ('qualified', 'both_missing'),
    ('qualified', 'fit_missing'),
    ('qualified', 'rows_missing'),
    ('qualified', 'fit_wrong_type'),
    ('qualified', 'rows_wrong_type'),
    ('qualified', 'fit_incomplete'),
    ('qualified', 'rows_incomplete'),
    ('scored_failure', 'both_missing'),
    ('scored_failure', 'fit_missing'),
    ('scored_failure', 'rows_missing'),
])
def test_candidate_model_and_rows_are_paired_in_hash_bound_development(
        tmp_path, status, mutation):
    """Missing candidate evidence must fail after the journal's own SHA check."""
    from famjet_poc.report_inputs import _verify_development, project_development_journal
    journal = _producer_journal()
    candidate = journal['candidate_ledger'][0 if status == 'qualified' else 1]
    if status == 'scored_failure':
        candidate.update(status='failed', failure_stage='score', loss=.4,
                         score={'status': 'failed', 'loss': .4},
                         fit_ref={'path': '/fixture/model', 'sha256': 'a'*64},
                         rows_ref={'path': '/fixture/rows', 'sha256': 'b'*64, 'bytes': 1})
    if mutation == 'both_missing':
        candidate.pop('fit_ref', None)
        candidate.pop('rows_ref', None)
    elif mutation == 'fit_missing':
        candidate.pop('fit_ref')
    elif mutation == 'rows_missing':
        candidate.pop('rows_ref')
    elif mutation == 'fit_wrong_type':
        candidate['fit_ref'] = '/fixture/model'
    elif mutation == 'rows_wrong_type':
        candidate['rows_ref'] = ['/fixture/rows']
    elif mutation == 'fit_incomplete':
        candidate['fit_ref'] = {'path': '/fixture/model'}
    elif mutation == 'rows_incomplete':
        candidate['rows_ref'] = {'path': '/fixture/rows', 'sha256': 'b'*64}
    with pytest.raises(ValueError, match='candidate model/row evidence'):
        project_development_journal(journal)
    paths, root = _paths(tmp_path)
    ref = _write_once(root / 'development-journal.json', journal)
    stages = {'development_k16': {'result': {'journal_path': ref['path'],
                                             'journal_sha256': ref['sha256']}}}
    freeze = {'inputs': {'study_k16_sha256': ref['sha256']}}
    with pytest.raises(ValueError, match='candidate model/row evidence'):
        _verify_development(paths, stages, freeze)


def _score_row(method, history, query, manifest):
    policy = {'version': 2}
    return {'method': method, 'history_id': history, 'query_id': query,
            'replicate': 0, 'task': 'mean', 'manifest_hash': manifest,
            'target_semantics': 'observed_event_targets_v2',
            'policy': policy, 'policy_hash': canonical_hash(policy)}


def _paths(tmp_path):
    root = tmp_path / 'run'
    root.mkdir()
    return ArtifactPaths(root, str(root / 'freeze' / 'study-freeze-v1.json')), root


def test_rebased_selected_reference_uses_e4_complete_query_guard(tmp_path):
    from famjet_poc.report_inputs import verify_selected_reference_rebased
    paths, root = _paths(tmp_path)
    manifest = 'a'*64
    rows = [_score_row('laguerre', f'dev-{i}', query, manifest)
            for i in range(4) for query in range(120)]
    ref = persist_score_rows(rows, root / 'rows.json')
    modes = {'beijing_manifest_sha256': manifest,
             'task_adapted': {'jet': {'sha256': 'b'*64}},
             'development_cache': [{'history_id': f'dev-{i}'} for i in range(4)],
             'selected_reference': {'status': 'passed', 'model_sha256': 'b'*64,
                                    'manifest_sha256': manifest, 'rows_ref': ref}}
    assert verify_selected_reference_rebased(paths, modes)['status'] == 'passed'
    rows[-1]['method'] = 'jet'
    bad_ref = persist_score_rows(rows, root / 'bad-rows.json')
    bad = copy.deepcopy(modes)
    bad['selected_reference']['rows_ref'] = bad_ref
    with pytest.raises(ValueError, match='reference'):
        verify_selected_reference_rebased(paths, bad)


def test_rebased_probe_uses_e4_measured_forecast_guard(tmp_path):
    from famjet_poc.report_inputs import verify_transfer_probe_rebased
    from famjet_poc.cache import e3_source_sha256
    from famjet_poc import transfer
    paths, root = _paths(tmp_path)
    manifest = 'a'*64
    limits = {'max_frame_bytes': 1024, 'max_array_bytes': 512, 'max_histories': 2}
    allocation = {'phase': 'probe', 'manifest_sha256': manifest}
    guard = _write_once(root / 'guard.json', {
        'kind': 'famjet_e4_live_stage_guard', 'status': 'completed',
        'violation': None, 'allocation': allocation,
        'samples': [{'tree_rss_bytes': 1}]})
    rows = persist_score_rows([_score_row('real-profile-probe', 'dev-0', 0, manifest)],
                              root / 'probe-rows.json')
    measured = {'train_blocks': 2, 'dev_blocks': 1, 'cache_seconds': 1.,
                'fit_seconds': 1., 'evaluation_seconds': 1., 'fit_rows': 1,
                'probe_output_bytes': 1, 'peak_tree_rss_bytes': 1,
                'development_query_count': 1}
    forecast = 43/3 + 36*(39/2 + 4)
    probe = {'schema_version': 1, 'kind': 'famjet_e4_real_fit_probe',
             'status': 'measured', 'beijing_manifest_sha256': manifest,
             'transfer_source_sha256': hashlib.sha256(Path(transfer.__file__).read_bytes()).hexdigest(),
             'e3_source_sha256': e3_source_sha256(), 'worker_limits': limits,
             'measured_profile': measured, 'forecast_seconds': forecast,
             'recommended_wall_seconds': max(1800, math.ceil((2*forecast+180)/300)*300),
             'forecast_output_bytes': 200, 'recommended_disk_bytes': 2*2**30,
             'recommended_rss_bytes': 1610612736, 'allocation': allocation,
             'guard_ref': guard, 'score_rows_ref': rows}
    ref = _write_once(root / 'probe.json', probe)
    assert verify_transfer_probe_rebased(paths, ref, manifest, limits)['status'] == 'measured'
    bad = copy.deepcopy(probe)
    bad['forecast_seconds'] += 1
    bad_ref = _write_once(root / 'bad-probe.json', bad)
    with pytest.raises(ValueError, match='forecast|probe'):
        verify_transfer_probe_rebased(paths, bad_ref, manifest, limits)


def test_distinct_hash_valid_cell_counts_and_real_method_mismatch_are_rejected(tmp_path):
    from famjet_poc.report_inputs import require_shared_cell_counts, require_real_method_rows
    paths, root = _paths(tmp_path)
    left = _write_once(root / 'counts-left.json', {'records': [1]})
    right = _write_once(root / 'counts-right.json', {'records': [2]})
    receipts = [{'phase': 'confirmation', 'cell_id': 'cell', 'method': method,
                 'counts_ref': ref} for method, ref in (('jet', left), ('bank', right))]
    with pytest.raises(ValueError, match='count'):
        require_shared_cell_counts(paths, receipts)
    row_ref = persist_score_rows([_score_row('jet', 'h', 0, 'a'*64)], root / 'wrong-method.json')
    from famjet_poc.study import load_score_rows
    with pytest.raises(ValueError, match='method'):
        require_real_method_rows('bank', load_score_rows(paths.ref(row_ref)))
