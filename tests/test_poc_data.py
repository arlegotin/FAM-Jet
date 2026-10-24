from dataclasses import replace
import hashlib
import json
from pathlib import Path

import numpy as np
import pytest
import torch

from famjet.config import load_config
from famjet.data.synthetic import generate_episode as old_generate
from famjet.provenance import canonical_hash, canonical_json
from famjet_poc.contracts import ShapeSpec, PopulationSpec, AccessGrant, source_sha256
from famjet_poc.data import generate_episode, invert_normalized_prediction, iter_beijing


def test_generator_shape_and_protected_access(tmp_path):
    spec = PopulationSpec('poc_numeric_v1', ShapeSpec(12, 1), 'training', 42,
                          (16,), ('piecewise_stationary',), 4, 100)
    ep = generate_episode(spec, 'unit-0')
    assert ep.events.key_features.shape[-1] == 12
    assert ep.events.values.shape[-1] == 1
    assert ep.labels.shape == (1, 4, 1)
    assert ep.metadata['split'] == 'training'
    protected = PopulationSpec('poc_numeric_v1', ShapeSpec(12, 1), 'confirmation', 42,
                               (16,), ('piecewise_stationary',), 4, 100)
    with pytest.raises(ValueError, match='grant'):
        generate_episode(protected, 'unit-0')
    with pytest.raises(ValueError):
        AccessGrant(tmp_path / 'missing', '0' * 64, 'confirmation', 'confirmation')


def test_legacy_golden_four_regimes_exact_public_parity():
    config = load_config(Path('configs/smoke.yaml'))
    spec = PopulationSpec('legacy_golden_v1', ShapeSpec(16, 8), 'training', 42, (128,),
                          ('piecewise_stationary', 'trend_reset', 'periodic_impulses', 'irregular_revisions'),
                          8, config.data.generator.max_query_attempts)
    seen = set()
    for n in range(24):
        ident = f'golden-{n}'
        old = old_generate(config, 42, ident)
        if old.metadata['regime'] in seen:
            continue
        new = generate_episode(spec, ident)
        assert new.metadata['regime'] == old.metadata['regime']
        for attr in ('event_ids', 'timestamps', 'key_ids', 'key_features', 'values', 'present', 'observed'):
            assert torch.equal(getattr(new.events, attr), getattr(old.events, attr)), attr
        for attr in ('query_ids', 'T', 'key_ids', 'key_features', 'age_start', 'age_end', 'present'):
            assert torch.equal(getattr(new.queries, attr), getattr(old.queries, attr)), attr
        assert new.queries.tasks == old.queries.tasks
        assert torch.allclose(new.labels, old.labels, equal_nan=True, rtol=0, atol=0)
        assert torch.equal(new.supported, old.supported)
        seen.add(old.metadata['regime'])
        if len(seen) == 4:
            break
    assert len(seen) == 4


def test_content_grant_binds_population_source_data_and_episode(tmp_path):
    spec = PopulationSpec('poc_numeric_v1', ShapeSpec(12, 1), 'confirmation', 999,
                          (16,), ('trend_reset',), 4, 100)
    path = tmp_path / 'grant.json'
    payload = {'schema_version': 1, 'kind': 'famjet_poc_access', 'phase': 'confirmation',
               'split': 'confirmation', 'source_sha256': source_sha256(),
               'model_sha256': '1' * 64,
               'data_sha256': canonical_hash(spec.to_json()), 'population': spec.to_json(),
               'episode_ids': ['unit-protected-0']}
    raw = canonical_json(payload)
    path.write_bytes(raw)
    grant = AccessGrant(path, hashlib.sha256(raw).hexdigest(), 'confirmation', 'confirmation')
    assert generate_episode(spec, 'unit-protected-0', grant=grant).events.values.shape[-1] == 1
    with pytest.raises(ValueError, match='inventory'):
        generate_episode(spec, 'unit-protected-1', grant=grant)
    path.write_bytes(raw + b' ')
    with pytest.raises(ValueError, match='bytes changed'):
        generate_episode(spec, 'unit-protected-0', grant=grant)


def test_native_inverse_does_not_shift_contrast():
    norm = {'split': 'training', 'mean': 50., 'scale': 20.}
    assert invert_normalized_prediction([1.], 'mean', norm).tolist() == [70.]
    assert invert_normalized_prediction([1.], 'contrast', norm).tolist() == [20.]


def test_tiny_current_v2_beijing_fixture_requires_exact_grant_and_array_replay(tmp_path):
    from famjet.data import beijing
    bulk = tmp_path / 'bulk'; bulk.mkdir()
    norm = {'split': 'training', 'source': 'all_observed_training_events',
            'mean': 20., 'scale': 10.}
    block = {'history_id': 'unit:test:0000', 'split': 'test', 'index': 0,
             'start_tick': 0, 'end_tick': 3, 'start': '2013-03-01', 'end': '2013-03-01'}
    data = {'times': np.array([0, 2], dtype=np.int64), 'keys': np.array([0, 0], dtype=np.int64),
            'values': np.array([10., 30.], dtype=np.float64)}
    normalized = beijing.make_episode(data, block, norm, normalized=True)
    raw = beijing.make_episode(data, block, norm, normalized=False)
    arrpath = bulk / 'unit.npz'
    np.savez(arrpath, times=data['times'], keys=data['keys'], raw_values=data['values'],
             labels_raw=raw.labels.numpy(), labels_normalized=normalized.labels.numpy(),
             supported=raw.supported.numpy(), observed_counts=np.asarray(raw.metadata['observed_counts'], dtype=np.int64))
    block.update(artifact='bulk/unit.npz', sha256=hashlib.sha256(arrpath.read_bytes()).hexdigest())
    seal = beijing._seal({'schema_version': 1, 'dataset': 'beijing_unit_test',
                         'preparation_version': beijing.VERSION,
                         'query_grid_version': beijing.QUERY_GRID,
                         'target_semantics': 'observed_event_targets_v2',
                         'normalization': norm, 'bulk_root': 'bulk', 'splits': {'test': {'blocks': [block]}}})
    manifest = tmp_path / 'beijing.json'; manifest.write_bytes(canonical_json(seal))
    grant_payload = {'schema_version': 1, 'kind': 'famjet_poc_access', 'phase': 'unit_test', 'split': 'test',
                     'model_sha256': '1' * 64,
                     'source_sha256': source_sha256(), 'data_sha256': hashlib.sha256(manifest.read_bytes()).hexdigest(),
                     'population': None, 'episode_ids': [block['history_id']]}
    grantpath = tmp_path / 'grant.json'; grantpath.write_bytes(canonical_json(grant_payload))
    grant = AccessGrant(grantpath, hashlib.sha256(grantpath.read_bytes()).hexdigest(), 'unit_test', 'test')
    with pytest.raises(ValueError, match='grant'):
        list(iter_beijing(manifest, 'test'))
    episodes = list(iter_beijing(manifest, 'test', grant=grant))
    assert len(episodes) == 1
    assert episodes[0].events.values.shape == (1, 2, 1)
    arrpath.write_bytes(arrpath.read_bytes() + b'x')
    with pytest.raises(ValueError, match='modified'):
        list(iter_beijing(manifest, 'test', grant=grant))
