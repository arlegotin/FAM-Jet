"""Public-boundary tests: malformed input must fail before any recurrence."""
import dataclasses
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest
import torch
import yaml


def events(**changes):
    from famjet.types import EventBatch
    fields = dict(history_ids=('h0',), event_ids=torch.tensor([[0, 1, 2]]),
                  timestamps=torch.tensor([[1., 2., 4.]], dtype=torch.float64),
                  key_ids=torch.tensor([[0, 1, 0]]),
                  key_features=torch.ones(1, 3, 2), values=torch.ones(1, 3, 2),
                  lengths=torch.tensor([3]), present=torch.ones(1, 3, dtype=torch.bool),
                  observed=torch.ones(1, 3, 2, dtype=torch.bool), time_unit='seconds')
    fields.update(changes)
    return EventBatch(**fields)


def config_file(tmp_path, mutate):
    value = yaml.safe_load(Path('configs/smoke.yaml').read_text())
    mutate(value)
    path = tmp_path / 'config.yaml'
    path.write_text(yaml.safe_dump(value))
    return path


def test_seed_namespace_is_stable():
    from famjet.provenance import derive_seed
    assert derive_seed(20261013, 'training', 'episode-7') == 7970119185101833104
    assert len({derive_seed(20261013, n, 'episode-7') for n in ('training', 'pilot', 'confirmation')}) == 3
    code = "from famjet.provenance import derive_seed; print(derive_seed(20261013, 'training', 'episode-7'))"
    for salt in ('1', 'random'):
        output = subprocess.check_output([sys.executable, '-c', code], env={**os.environ, 'PYTHONHASHSEED': salt}, text=True)
        assert output.strip() == '7970119185101833104'


def test_canonical_hash_is_utf8_ordered_and_process_stable():
    from famjet.provenance import canonical_hash
    assert canonical_hash({'é': None, 'a': 1}) == '821dcba40aad4ab5a2d27064bd0efbd276edd8a703c4e6c4d4643e20e8d52494'
    code = "from famjet.provenance import canonical_hash; print(canonical_hash({'é': None, 'a': 1}))"
    assert subprocess.check_output([sys.executable, '-c', code], text=True).strip() == canonical_hash({'a': 1, 'é': None})


@pytest.mark.parametrize('bad', [float('nan'), float('inf'), -float('inf'), {'nested': [float('nan')]}, {1: 'key'}, object()])
def test_canonical_hash_rejects_non_json_and_nonfinite(bad):
    from famjet.provenance import canonical_hash
    with pytest.raises((TypeError, ValueError)):
        canonical_hash(bad)


def test_event_validation():
    from famjet.data.schema import validate_events
    batch = events()
    assert batch.validation is None
    assert validate_events(batch) is None
    assert batch.validation.gaps.tolist() == [[0., 1., 2.]]
    assert batch.validation.schema_version == 1


@pytest.mark.parametrize('change', [
    {'timestamps': torch.tensor([[2., 1., 4.]], dtype=torch.float64)},
    {'timestamps': torch.tensor([[1., float('inf'), 4.]], dtype=torch.float64)},
    {'timestamps': torch.tensor([[1., 2., 4.]], dtype=torch.float32)},
    {'timestamps': torch.tensor([[-1e308, 1e308, 1e308]], dtype=torch.float64)},
    {'values': torch.tensor([[[float('nan'), 1.], [1., 1.], [1., 1.]]]), 'observed': torch.zeros(1, 3, 2, dtype=torch.bool)},
    {'key_features': -torch.ones(1, 3, 2)},
    {'present': torch.ones(1, 3)},
    {'observed': torch.ones(1, 3, dtype=torch.bool)},
    {'lengths': torch.tensor([2])},
    {'present': torch.tensor([[True, False, True]])},
    {'observed': torch.tensor([[[True, True], [True, True], [True, True]]]), 'lengths': torch.tensor([2]), 'present': torch.tensor([[True, True, False]])},
    {'event_ids': torch.tensor([[1, 1, 2]])},
    {'timestamps': torch.tensor([[1., 1., 2.]], dtype=torch.float64), 'event_ids': torch.tensor([[1, 0, 2]])},
])
def test_event_validation_rejects_malformed_inputs(change):
    from famjet.data.schema import validate_events
    with pytest.raises(ValueError):
        validate_events(events(**change))


def test_integer_timestamp_subtraction_overflow_is_rejected():
    from famjet.data.schema import validate_events
    with pytest.raises(ValueError, match='overflow'):
        validate_events(events(timestamps=torch.tensor([[-2**63, 0, 2**63-1]], dtype=torch.int64)))


def test_padding_has_zero_gap_and_no_write_but_missing_event_advances_time():
    from famjet.data.schema import validate_events
    batch = events(lengths=torch.tensor([2]), present=torch.tensor([[True, True, False]]), observed=torch.tensor([[[True, True], [False, False], [False, False]]]))
    validate_events(batch)
    assert batch.validation.gaps.tolist() == [[0., 1., 0.]]
    assert batch.validation.write_mask.tolist() == [[True, False, False]]


def test_partial_value_mask_requires_independent_norm():
    from famjet.data.schema import validate_events
    mask = torch.tensor([[[True, False], [True, True], [False, True]]])
    with pytest.raises(ValueError, match='independent'):
        validate_events(events(observed=mask))
    validate_events(events(observed=mask, normalization='independent'))


@pytest.mark.parametrize('rates', [[0.], [-1.], [float('nan')], [float('inf')], []])
def test_rates_require_finite_positive_values(rates):
    from famjet.data.schema import validate_rates
    with pytest.raises(ValueError):
        validate_rates(torch.tensor(rates))


def test_query_times_and_age_bounds_are_validated():
    from famjet.types import QueryBatch
    from famjet.data.schema import validate_queries
    from famjet.types import Snapshot
    query = QueryBatch(history_ids=('h0',), query_ids=torch.tensor([[0]]), T=torch.tensor([[4.]], dtype=torch.float64), key_ids=torch.tensor([[0]]), key_features=torch.ones(1, 1, 2), tasks=(('mean',),), age_start=torch.tensor([[0.]], dtype=torch.float64), age_end=torch.tensor([[2.]], dtype=torch.float64), present=torch.ones(1, 1, dtype=torch.bool), lengths=torch.tensor([1]))
    state = Snapshot(payload={}, last_time=torch.tensor([3.], dtype=torch.float64), valid=torch.tensor([True]), parameter_hash='a'*64, event_offset=torch.tensor([3]))
    validate_queries(query, state)
    with pytest.raises(ValueError, match='before'):
        validate_queries(dataclasses.replace(query, T=torch.tensor([[2.]], dtype=torch.float64)), state)
    with pytest.raises(ValueError):
        validate_queries(dataclasses.replace(query, age_end=torch.tensor([[-1.]], dtype=torch.float64)))
    with pytest.raises(ValueError):
        validate_queries(dataclasses.replace(query, T=torch.tensor([[float('nan')]], dtype=torch.float64)))


def test_resolved_config_round_trip_preserves_blocking_nulls(tmp_path):
    from famjet.config import load_config, save_resolved_config
    config = load_config(Path('configs/smoke.yaml'))
    assert config.model.J == 4 and config.training.optimizer_steps == 2
    assert config.resources.training_envelope_bytes is None
    assert config.confirmation.populations is None
    path = tmp_path / 'resolved.json'
    save_resolved_config(path, config)
    assert load_config(path) == config
    assert json.loads(path.read_text())['confirmation']['populations'] is None


@pytest.mark.parametrize('section', [None, 'model', 'data', 'training', 'resources', 'numerics', 'confirmation'])
def test_resolved_config_rejects_unknown_field(tmp_path, section):
    from famjet.config import load_config
    def mutate(v):
        (v if section is None else v[section])['anchor'] = 1
    with pytest.raises(ValueError, match='anchor'):
        load_config(config_file(tmp_path, mutate))


@pytest.mark.parametrize('section,key,bad', [('model', 'epsilon', 0), ('model', 'K', True), ('data', 'length', -1), ('training', 'optimizer_steps', None), ('training', 'effective_batch', 0), ('numerics', 'rtol', float('nan')), ('resources', 'reserved_fraction_of_derived_envelope', 1), ('resources', 'device', 'bogus'), ('model', 'precision', 'float16')])
def test_config_rejects_invalid_bounds(tmp_path, section, key, bad):
    from famjet.config import load_config
    with pytest.raises(ValueError):
        load_config(config_file(tmp_path, lambda v: v[section].update({key: bad})))


def test_confirmation_rejects_unfrozen_scientific_fields(tmp_path):
    from famjet.config import load_config
    with pytest.raises(ValueError, match='confirmation'):
        load_config(config_file(tmp_path, lambda v: v.update(phase='confirmation')))


def test_config_rejects_duplicate_keys(tmp_path):
    from famjet.config import load_config
    path = tmp_path / 'duplicate.yaml'
    path.write_text(Path('configs/smoke.yaml').read_text() + '\nseed: 1\n')
    with pytest.raises(ValueError, match='duplicate'):
        load_config(path)


def test_artifact_missing_is_not_zero(tmp_path):
    from famjet.artifacts import atomic_json
    path = tmp_path / 'artifact.json'
    atomic_json(path, {'schema_version': 1, 'status': 'missing', 'loss': None})
    assert json.loads(path.read_text()) == {'schema_version': 1, 'status': 'missing', 'loss': None}
    before = path.read_bytes()
    with pytest.raises(ValueError):
        atomic_json(path, {'schema_version': 1, 'loss': float('nan')})
    assert path.read_bytes() == before
    assert list(tmp_path.iterdir()) == [path]


def test_provenance_keeps_code_data_and_parameters_distinct(tmp_path):
    from famjet.provenance import build_provenance
    from famjet.config import load_config
    result = build_provenance(config=load_config(Path('configs/smoke.yaml')), source_revision='3c11ac8', source_diff='', data_identity={'split': 'training'}, parameters={'rates': [0.1]}, lock_path=Path('requirements.lock'), environment={'device': 'cpu'})
    assert result['schema_version'] == 1
    assert result['source']['revision'] == '3c11ac8'
    assert len({result[name] for name in ('config_hash', 'data_hash', 'parameter_hash', 'lock_hash', 'environment_hash')}) == 5
    assert result['source']['diff_hash'] != result['parameter_hash']


def test_unsupported_schema_is_rejected():
    from famjet.data.schema import validate_events
    with pytest.raises(ValueError, match='schema'):
        validate_events(events(schema_version=2))


def test_full_uint64_key_ids_round_trip_and_validate(tmp_path):
    from famjet.artifacts import atomic_json
    from famjet.data.schema import validate_events, validate_queries
    from famjet.types import QueryBatch
    ids = torch.tensor([[2**63+7, 2**64-1, 0]], dtype=torch.uint64, device='cpu')
    batch = events(key_ids=ids)
    validate_events(batch)
    query = QueryBatch(history_ids=('h0',), query_ids=torch.tensor([[0]]),
                       T=torch.tensor([[4.]], dtype=torch.float64), key_ids=ids[:, :1],
                       key_features=torch.ones(1, 1, 2), tasks=(('latest',),),
                       age_start=torch.zeros(1, 1, dtype=torch.float64),
                       age_end=torch.zeros(1, 1, dtype=torch.float64),
                       present=torch.ones(1, 1, dtype=torch.bool), lengths=torch.tensor([1]))
    validate_queries(query)
    path = tmp_path / 'ids.json'
    atomic_json(path, {'schema_version': 1, 'key_ids': batch.key_ids.tolist()})
    assert json.loads(path.read_text())['key_ids'] == [[9223372036854775815, 18446744073709551615, 0]]


def test_validation_record_is_cleared_after_invalid_mutation():
    from famjet.data.schema import validate_events
    batch = events()
    validate_events(batch)
    batch.values[0, 0, 0] = float('nan')
    with pytest.raises(ValueError):
        validate_events(batch)
    assert batch.validation is None


def test_atomic_json_cleans_up_after_replace_failure(tmp_path, monkeypatch):
    from famjet.artifacts import atomic_json
    import famjet.artifacts
    path = tmp_path / 'result.json'
    atomic_json(path, {'schema_version': 1, 'status': 'old'})
    def fail_replace(source, target):
        raise OSError('simulated filesystem replace failure')
    monkeypatch.setattr(famjet.artifacts.os, 'replace', fail_replace)
    with pytest.raises(OSError):
        atomic_json(path, {'schema_version': 1, 'status': 'new'})
    assert json.loads(path.read_text())['status'] == 'old'
    assert list(tmp_path.iterdir()) == [path]


def test_provenance_copies_identity_inputs():
    from famjet.config import load_config
    from famjet.provenance import build_provenance
    data, environment = {'split': ['training']}, {'device': 'cpu'}
    result = build_provenance(config=load_config(Path('configs/smoke.yaml')),
                              source_revision='3c11ac8', source_diff='',
                              data_identity=data, parameters={},
                              lock_path=Path('requirements.lock'), environment=environment)
    data['split'].append('confirmation')
    environment['device'] = 'mps'
    assert result['data_identity'] == {'split': ['training']}
    assert result['environment'] == {'device': 'cpu'}
