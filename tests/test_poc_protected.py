import hashlib
import json

import pytest

from famjet.provenance import canonical_hash
from famjet_poc.contracts import PopulationSpec, ShapeSpec
from famjet_poc.protected import (freeze_study, grant_for, seal_release,
                                  read_released_rows, read_released_counts,
                                  infer_release, validate_scientific_plan,
                                  validate_model_commitments, admit_cell, evaluate_cell)
from famjet_poc.inference import STRATA


def _spec():
    return PopulationSpec('poc_numeric_v1', ShapeSpec(16, 8), 'unit_test', 17,
                          (128,), ('piecewise_stationary',), 8, 64)


def _inputs():
    spec = _spec()
    return {'profile': 'unit_test', 'model_pair_sha256': 'a' * 64,
            'populations': [{'phase': 'unit_test', 'split': 'pilot',
                             'spec': spec.to_json(), 'episode_ids': ['tiny-0', 'tiny-1']}],
            'unit_test_admission': {'schema_version': 1, 'kind': 'famjet_e4_unit_test_admission',
                                    'status': 'accepted'},
            'calibration': None}


def test_freeze_is_write_once_and_grant_binds_model_and_id(tmp_path):
    frozen = freeze_study(_inputs(), tmp_path / 'freeze')
    grant = grant_for(frozen, 'unit_test', 'pilot', _spec(), 'a' * 64)
    assert grant.verify(source_sha256=frozen.source_sha256,
                        data_sha256=canonical_hash(_spec().to_json()),
                        model_sha256='a' * 64, population=_spec(), episode_id='tiny-0')
    with pytest.raises(ValueError, match='model'):
        grant_for(frozen, 'unit_test', 'pilot', _spec(), 'b' * 64)
    with pytest.raises(ValueError, match='inventory'):
        grant.verify(source_sha256=frozen.source_sha256,
                     data_sha256=canonical_hash(_spec().to_json()),
                     model_sha256='a' * 64, population=_spec(), episode_id='undeclared')
    with pytest.raises(FileExistsError):
        freeze_study(_inputs(), tmp_path / 'freeze')


def test_release_rejects_missing_or_tampered_method(tmp_path):
    frozen = freeze_study(_inputs(), tmp_path / 'freeze')
    rows = tmp_path / 'jet.json'
    rows.write_text(json.dumps([{'history_id': 'tiny-0', 'method': 'jet'},
                                {'history_id': 'tiny-1', 'method': 'jet'}]))
    receipt = {'run_id': 'unit-jet', 'phase': 'unit_test', 'method': 'jet',
               'history_ids': ['tiny-0', 'tiny-1'], 'rows_path': str(rows),
               'rows_sha256': hashlib.sha256(rows.read_bytes()).hexdigest(),
               'status': 'completed', 'freeze_sha256': frozen.sha256}
    with pytest.raises(ValueError, match='method'):
        seal_release(frozen, [receipt], tmp_path / 'release',
                     expected_methods=('jet', 'bank'))
    rows_bank = tmp_path / 'bank.json'
    rows_bank.write_text(json.dumps([{'history_id': 'tiny-0', 'method': 'bank'},
                                     {'history_id': 'tiny-1', 'method': 'bank'}]))
    bank = {**receipt, 'run_id': 'unit-bank', 'method': 'bank',
            'rows_path': str(rows_bank), 'rows_sha256': hashlib.sha256(rows_bank.read_bytes()).hexdigest()}
    release = seal_release(frozen, [receipt, bank], tmp_path / 'release',
                           expected_methods=('jet', 'bank'))
    released = read_released_rows(release)
    assert iter(released) is released
    assert len(list(released)) == 4
    rows_bank.write_text('[]')
    with pytest.raises(ValueError, match='hash'):
        next(read_released_rows(release))


def test_beijing_grant_requires_frozen_model_and_exact_manifest_bytes(tmp_path):
    manifest = tmp_path / 'beijing.json'
    manifest.write_text('{"unit_test":true}')
    inputs = _inputs()
    inputs.update(beijing_manifest_sha256=hashlib.sha256(manifest.read_bytes()).hexdigest(),
                  beijing_test_ids=['test-0'],
                  real_model_commitments={'synthetic_frozen': 'b' * 64})
    frozen = freeze_study(inputs, tmp_path / 'freeze')
    grant = grant_for(frozen, 'unit_test', 'test', manifest, 'b' * 64)
    assert grant.verify(source_sha256=frozen.source_sha256,
                        data_sha256=hashlib.sha256(manifest.read_bytes()).hexdigest(),
                        model_sha256='b' * 64)['episode_ids'] == ['test-0']
    with pytest.raises(ValueError, match='model'):
        grant_for(frozen, 'unit_test', 'test', manifest, 'c' * 64)
    manifest.write_text('{}')
    with pytest.raises(ValueError, match='manifest'):
        grant_for(frozen, 'unit_test', 'test', manifest, 'b' * 64)


def test_inference_uses_complete_equal_task_history_losses(tmp_path):
    frozen = freeze_study(_inputs(), tmp_path / 'freeze')
    receipts = []
    for method, losses in (('jet', [1., 1.]), ('bank', [3., 4.])):
        rows = [{'history_id': history, 'method': method, 'task': task,
                 'loss': loss, 'score_scope': 'primary'}
                for history, loss in zip(('tiny-0', 'tiny-1'), losses)
                for task in ('mean', 'contrast')]
        path = tmp_path / (method + '.json')
        path.write_text(json.dumps(rows))
        receipts.append({'run_id': method, 'phase': 'unit_test', 'method': method,
                         'history_ids': ['tiny-0', 'tiny-1'], 'rows_path': str(path),
                         'rows_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                         'status': 'completed', 'freeze_sha256': frozen.sha256})
    release = seal_release(frozen, receipts, tmp_path / 'release')
    result = infer_release(frozen, release, 'unit_test')
    assert result['D'] == 2.5
    assert result['counts'] == [2]
    rows = json.loads((tmp_path / 'bank.json').read_text())
    rows = [r for r in rows if not (r['history_id'] == 'tiny-1' and r['task'] == 'contrast')]
    (tmp_path / 'bank.json').write_text(json.dumps(rows))
    with pytest.raises(ValueError, match='hash'):
        infer_release(frozen, release, 'unit_test')


def test_scientific_plan_rejects_changed_protected_root_before_grant():
    items = []
    for phase, seed, count in (('pilot', 2026102401902, 16),
                               ('confirmation', 2026102401904, 256),
                               ('replication', 2026102401905, 256)):
        for label in STRATA:
            length, regime = label.split(':')
            spec = PopulationSpec('poc_numeric_v1', ShapeSpec(16, 8), phase, seed,
                                  (int(length),), (regime,), 8, 4096)
            items.append({'phase': phase, 'split': phase, 'cell_id': f'{phase}-{label}',
                          'spec': spec.to_json(), 'episode_ids': [f'budget-v2-20261025-{phase}-{length}-{regime}-{i:03d}' for i in range(count)]})
    assert validate_scientific_plan(items)['history_count'] == 6336
    old_ids = [dict(item) for item in items]
    old_ids[0]['episode_ids'] = [f'pilot-128-piecewise_stationary-{i:03d}' for i in range(16)]
    with pytest.raises(ValueError, match='history inventory'):
        validate_scientific_plan(old_ids)
    changed = [dict(item) for item in items]
    changed[12]['spec'] = {**changed[12]['spec'], 'seed': 1}
    with pytest.raises(ValueError, match='root'):
        validate_scientific_plan(changed)


def test_frozen_pair_hash_must_match_selected_model_refs():
    refs = {'jet': {'path': '/missing/jet.json', 'sha256': 'a' * 64},
            'bank': {'path': '/missing/bank.json', 'sha256': 'b' * 64}}
    with pytest.raises(ValueError, match='pair'):
        validate_model_commitments({'model_pair_sha256': 'c' * 64,
                                    'selected_models': refs,
                                    'selected_k12_models': refs,
                                    'transfer_modes_path': '/missing/modes.json',
                                    'transfer_modes_sha256': 'd' * 64})


def test_grant_rechecks_attested_bundle_after_freeze(tmp_path):
    bundle = tmp_path / 'bundle'
    bundle.mkdir()
    sample = bundle / 'batch.bin'
    sample.write_bytes(b'accepted')
    inputs = _inputs()
    inputs['unit_test_bundle'] = {'schema_version': 1,
                                  'kind': 'famjet_e4_unit_test_bundle',
                                  'directory': str(bundle),
                                  'files': {'batch.bin': hashlib.sha256(b'accepted').hexdigest()}}
    frozen = freeze_study(inputs, tmp_path / 'freeze')
    grant_for(frozen, 'unit_test', 'pilot', _spec(), 'a' * 64)
    sample.write_bytes(b'changed')
    with pytest.raises(ValueError, match='bundle'):
        grant_for(frozen, 'unit_test', 'pilot', _spec(), 'a' * 64)


def test_cell_allocation_counts_all_method_outputs(tmp_path):
    import time
    (tmp_path / 'jet').mkdir()
    (tmp_path / 'jet' / 'rows.json').write_bytes(b'12345')
    with pytest.raises(RuntimeError, match='output'):
        admit_cell(tmp_path, {'max_wall_seconds': 1., 'max_disk_bytes': 4},
                   time.monotonic())


def test_unit_cell_runs_selected_pair_and_all_fixed_controls(tmp_path, monkeypatch):
    from famjet_poc.contracts import ReaderSpec
    from famjet_poc.data import generate_episode
    from famjet_poc.models import (build_model, fit_training_metadata,
                                   make_fit_manifest, fit_reader, save_model)
    spec = _spec()
    episodes = [generate_episode(spec, history) for history in ('tiny-0', 'tiny-1')]
    for episode in episodes:
        episode.metadata['split'] = 'training'
    factory = lambda: iter(episodes)
    metadata = fit_training_metadata(factory)
    refs = {}
    for family in ('jet', 'bank'):
        reader = ReaderSpec('ridge_v1', family, 8, 1e-2, 1 / 5224, 1., 1e-6, 1e-12)
        model = build_model(spec.shape, reader, metadata['t_ref'], metadata['target_statistics'])
        fit_reader(model, factory, make_fit_manifest(model, metadata))
        ref = save_model(model, tmp_path / (family + '.json'))
        refs[family] = {'path': str(ref.path), 'sha256': ref.sha256}
    inputs = _inputs()
    inputs['model_pair_sha256'] = canonical_hash({name: ref['sha256'] for name, ref in refs.items()})
    inputs['populations'][0]['cell_id'] = 'tiny-cell'
    inputs['selected_models'] = refs
    frozen = freeze_study(inputs, tmp_path / 'freeze')
    grant = grant_for(frozen, 'unit_test', 'pilot', spec, inputs['model_pair_sha256'])
    cell = {'cell_id': 'tiny-cell', 'phase': 'unit_test', 'spec': spec.to_json(),
            'episode_ids': ['tiny-0', 'tiny-1'], 'models': refs,
            'allocation': {'schema_version': 1, 'phase': 'unit_test',
                           'manifest_sha256': frozen.sha256, 'allocation_id': 'tiny',
                           'max_wall_seconds': 30, 'max_disk_bytes': 16 * 2**20,
                           'max_rss_bytes': 2**30},
            'worker_limits': {'max_frame_bytes': 2**20,
                              'max_array_bytes': 2**19, 'max_histories': 64}}
    receipts = evaluate_cell(frozen, cell, grant, tmp_path / 'cell')
    assert {item['method'] for item in receipts} == {
        'jet', 'bank', 'exact', 'recent', 'latest_lru', 'reservoir', 'buckets', 'laguerre'}
    assert all(item['counts_ref']['sha256'] == receipts[0]['counts_ref']['sha256']
               and item['score_contract']['policy_ref']['sha256'] == receipts[0]['score_contract']['policy_ref']['sha256']
               for item in receipts)
    release = seal_release(frozen, receipts, tmp_path / 'release',
                           expected_methods=tuple(item['method'] for item in receipts))
    assert len(list(read_released_rows(release, methods=('jet', 'bank')))) == 32
    from test_poc_coordinate_diagnostic import forge_coordinate_model
    altered = [{**item, 'costs': forge_coordinate_model(item['costs'])}
               if item['method'] == 'laguerre' else item for item in receipts]
    with pytest.raises(ValueError, match='coordinate'):
        seal_release(frozen, altered, tmp_path / 'wrong-coordinate-model',
                     expected_methods=tuple(item['method'] for item in receipts))
    counts = list(read_released_counts(release))
    assert len(counts) == 16 and all('observed_counts' in row for row in counts)
    from famjet_poc.study import load_score_rows, persist_score_rows
    jet = receipts[0]
    wrong = load_score_rows(jet['rows_ref'])
    wrong[0]['manifest_hash'] = '0' * 64
    wrong_ref = persist_score_rows(wrong, tmp_path / 'wrong-contract.json')
    changed = [{**jet, 'rows_ref': wrong_ref, 'rows_sha256': wrong_ref['sha256']}, *receipts[1:]]
    with pytest.raises(ValueError, match='contract|manifest'):
        seal_release(frozen, changed, tmp_path / 'wrong-release',
                     expected_methods=tuple(item['method'] for item in receipts))
    missing = load_score_rows(jet['rows_ref'])
    for row in missing:
        if row['history_id'] == 'tiny-0' and row['task'] == 'contrast':
            row['score_scope'] = 'ineligible_diagnostic'
    missing_ref = persist_score_rows(missing, tmp_path / 'missing-task.json')
    changed = [{**jet, 'rows_ref': missing_ref, 'rows_sha256': missing_ref['sha256']}, *receipts[1:]]
    with pytest.raises(ValueError, match='task|eligible|contract'):
        seal_release(frozen, changed, tmp_path / 'missing-release',
                     expected_methods=tuple(item['method'] for item in receipts))
    def forbidden_generation(*args, **kwargs):
        raise AssertionError('protected generation preceded model binding')
    monkeypatch.setattr('famjet_poc.data.generate_episode', forbidden_generation)
    swapped = {**cell, 'models': {**refs, 'bank': refs['jet']}}
    with pytest.raises(ValueError, match='model|family|checkpoint'):
        evaluate_cell(frozen, swapped, grant, tmp_path / 'swapped-cell')
    alternative_bank = build_model(spec.shape,
        ReaderSpec('ridge_v1', 'bank', 8, 1e-6, 1 / 5224, 1., 1e-6, 1e-12),
        metadata['t_ref'], metadata['target_statistics'])
    fit_reader(alternative_bank, factory, make_fit_manifest(alternative_bank, metadata))
    other = save_model(alternative_bank, tmp_path / 'alternative-bank.json')
    changed = {**cell, 'models': {**refs, 'bank': {'path': str(other.path),
                                                   'sha256': other.sha256}}}
    with pytest.raises(ValueError, match='model|pair|checkpoint'):
        evaluate_cell(frozen, changed, grant, tmp_path / 'changed-cell')
    from pathlib import Path
    Path(receipts[0]['counts_ref']['path']).write_text('{}')
    with pytest.raises(ValueError, match='hash'):
        next(read_released_rows(release))
