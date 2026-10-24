import dataclasses
import hashlib

import numpy as np
import pytest

from famjet_poc.contracts import PopulationSpec, ReaderSpec, ShapeSpec
from famjet_poc.data import generate_episode
from famjet_poc.models import (_episode_digest, build_model, fit_reader,
                               fit_training_metadata, make_fit_manifest)


def _population(namespace='unit_test'):
    return PopulationSpec('poc_numeric_v1', ShapeSpec(12, 1), namespace, 412,
                          (128,), ('piecewise_stationary',), 8, 512)


def _reader(ridge=1e-6):
    return ReaderSpec('ridge_v1', 'jet', 8, ridge, 1 / 5224, 1., 1e-6, 1e-12)


def test_episode_cache_replays_owned_real_tensors_and_detects_tampering(tmp_path):
    from famjet_poc.cache import prepare_episode_cache, episode_factory, load_episode_cache

    spec = _population()
    inventory = [{'history_id': 'unit-cache-0', 'spec': spec.to_json()}]
    cache = prepare_episode_cache([spec], inventory, tmp_path, {'disk_bytes': 8_000_000, 'lru_bytes': 1_000_000})
    factory = episode_factory(cache, ['unit-cache-0'])
    first, second = next(factory()), next(factory())
    direct = generate_episode(spec, 'unit-cache-0')
    assert _episode_digest(first) == _episode_digest(second) == _episode_digest(direct)
    loaded = load_episode_cache(tmp_path, cache.manifest_sha256)
    assert _episode_digest(next(episode_factory(loaded, ['unit-cache-0'])())) == _episode_digest(direct)
    first.events.values[0, 0, 0] += 7
    assert _episode_digest(next(factory())) == _episode_digest(direct)
    with pytest.raises(ValueError, match='inventory'):
        episode_factory(cache, ['not-declared'])
    entry = cache.entries[0]
    path = tmp_path / entry['file']
    path.write_bytes(path.read_bytes() + b' ')
    with pytest.raises(ValueError, match='hash'):
        next(factory())


def test_cached_fit_matches_direct_and_rejects_stale_reader_key(tmp_path):
    from famjet_poc.cache import attach_training_cache, episode_factory, prepare_episode_cache

    spec = _population('training')
    ids = ['unit-fit-0', 'unit-fit-1']
    cache = prepare_episode_cache([spec], [{'history_id': h, 'spec': spec.to_json()} for h in ids],
                                  tmp_path, {'disk_bytes': 16_000_000, 'lru_bytes': 16_000_000})
    factory = episode_factory(cache, ids)
    meta = fit_training_metadata(factory)
    direct = build_model(spec.shape, _reader(), meta['t_ref'], meta['target_statistics'])
    cached = attach_training_cache(build_model(spec.shape, _reader(), meta['t_ref'], meta['target_statistics']),
                                   cache, {'lru_bytes': 16_000_000})
    fit_reader(direct, factory, make_fit_manifest(direct, meta), chunk_rows=32)
    fit_reader(cached, factory, make_fit_manifest(cached, meta), chunk_rows=32)
    np.testing.assert_array_equal(cached.coefficients, direct.coefficients)
    assert cached.cache_stats['raw_hits'] > 0
    new = attach_training_cache(build_model(spec.shape, _reader(1e-2), meta['t_ref'], meta['target_statistics']),
                                cache, {'lru_bytes': 16_000_000})
    assert new._cache_identity != cached._cache_identity
    changed_reference = attach_training_cache(build_model(spec.shape, _reader(), meta['t_ref'] * 2,
                                                          meta['target_statistics']),
                                              cache, {'lru_bytes': 16_000_000})
    assert changed_reference.writer_hash != cached.writer_hash
    assert changed_reference._cache_identity != cached._cache_identity
    cache.e3_sha256 = '0' * 64
    with pytest.raises(ValueError, match='source'):
        attach_training_cache(build_model(spec.shape, _reader(), meta['t_ref'], meta['target_statistics']),
                              cache, {'lru_bytes': 16_000_000})


def test_reused_cache_rejects_changed_spec_and_lower_ceiling(tmp_path):
    from famjet_poc.cache import attach_training_cache, episode_factory, prepare_episode_cache
    from famjet_poc.study import _cache_for

    spec = _population('training')
    inventory = [{'history_id': 'unit-cache-spec-0', 'spec': spec.to_json()}]
    cache = prepare_episode_cache([spec], inventory, tmp_path / 'cache',
                                  {'disk_bytes': 8_000_000, 'lru_bytes': 1_000_000})
    changed = dataclasses.replace(spec, seed=spec.seed + 1)
    changed_inventory = [{'history_id': 'unit-cache-spec-0', 'spec': changed.to_json()}]
    with pytest.raises(ValueError, match='spec|inventory'):
        _cache_for([changed.to_json()], changed_inventory, tmp_path / 'cache',
                   {'disk_bytes': 8_000_000, 'lru_bytes': 1_000_000})
    with pytest.raises((MemoryError, ValueError), match='ceiling|limit|admission'):
        _cache_for([spec.to_json()], inventory, tmp_path / 'cache',
                   {'disk_bytes': cache.disk_bytes - 1, 'lru_bytes': 1_000_000})
    assert _cache_for([spec.to_json()], inventory, tmp_path / 'cache',
                      {'disk_bytes': 8_000_000, 'lru_bytes': 1_000_000},
                      incremental_disk_bytes=0).manifest_sha256 == cache.manifest_sha256
    with pytest.raises(MemoryError, match='disk admission'):
        _cache_for([spec.to_json()], inventory, tmp_path / 'new-cache',
                   {'disk_bytes': 8_000_000, 'lru_bytes': 1_000_000}, incremental_disk_bytes=128)
    meta = fit_training_metadata(episode_factory(cache, ['unit-cache-spec-0']))
    with pytest.raises(ValueError, match='LRU|ceiling|limit'):
        attach_training_cache(build_model(spec.shape, _reader(), meta['t_ref'], meta['target_statistics']), cache,
                              {'lru_bytes': cache.lru_bytes - 1})
