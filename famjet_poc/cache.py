"""Content-verified public-episode replay and training-only E1 memoization."""
from collections import OrderedDict
from dataclasses import dataclass, field
import hashlib
import json
import os
from pathlib import Path
import tempfile

import numpy as np
import torch

from famjet.data.synthetic import batch_hash
from famjet.eval.state_io import snapshot_from_record, snapshot_hash, snapshot_record, tensor_from_record, tensor_record
from famjet.provenance import canonical_hash, canonical_json
from famjet.types import Episode, EventBatch, QueryBatch
from .contracts import PopulationSpec, source_sha256
from .data import generate_episode
from .models import RidgeMemoryModel, _episode_digest

_SOURCES = ('cache.py', 'wire.py', 'worker.py', 'comparators.py', 'study.py', 'timing.py')
_EVENT_TENSORS = ('event_ids', 'timestamps', 'key_ids', 'key_features', 'values', 'lengths', 'present', 'observed')
_QUERY_TENSORS = ('query_ids', 'T', 'key_ids', 'key_features', 'age_start', 'age_end', 'present', 'lengths')


def e3_source_sha256():
    """E3's explicit content identity; E1's source identity remains untouched."""
    directory = Path(__file__).resolve().parent
    return canonical_hash({name: hashlib.sha256((directory / name).read_bytes()).hexdigest() for name in _SOURCES})


def _atomic(path, raw):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix='.e3-', delete=False) as stream:
        temp = Path(stream.name)
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    try:
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def _record(ep):
    return {'schema_version': 1, 'events': {'history_ids': list(ep.events.history_ids),
            'time_unit': ep.events.time_unit, 'normalization': ep.events.normalization,
            'auxiliary': {k: tensor_record(v) for k, v in ep.events.auxiliary.items()},
            **{k: tensor_record(getattr(ep.events, k)) for k in _EVENT_TENSORS}},
            'queries': {'history_ids': list(ep.queries.history_ids), 'tasks': [list(row) for row in ep.queries.tasks],
                        **{k: tensor_record(getattr(ep.queries, k)) for k in _QUERY_TENSORS}},
            'labels': tensor_record(ep.labels), 'supported': tensor_record(ep.supported),
            'metadata': ep.metadata}


def _restore(record):
    if type(record) is not dict or set(record) != {'schema_version', 'events', 'queries', 'labels', 'supported', 'metadata'} or record['schema_version'] != 1:
        raise ValueError('invalid episode cache schema')
    e, q = record['events'], record['queries']
    if set(e) != {*_EVENT_TENSORS, 'history_ids', 'time_unit', 'normalization', 'auxiliary'} or set(q) != {*_QUERY_TENSORS, 'history_ids', 'tasks'}:
        raise ValueError('invalid episode cache tensor schema')
    events = EventBatch(tuple(e['history_ids']), **{k: tensor_from_record(e[k]) for k in _EVENT_TENSORS},
                        time_unit=e['time_unit'], normalization=e['normalization'],
                        auxiliary={k: tensor_from_record(v) for k, v in e['auxiliary'].items()})
    queries = QueryBatch(tuple(q['history_ids']), **{k: tensor_from_record(q[k]) for k in _QUERY_TENSORS},
                         tasks=tuple(tuple(row) for row in q['tasks']))
    return Episode(events, queries, tensor_from_record(record['labels']),
                   tensor_from_record(record['supported']), record['metadata'])


@dataclass
class CacheManifest:
    root: Path
    entries: list[dict]
    source_sha256: str
    e3_sha256: str
    manifest_sha256: str
    disk_bytes: int
    lru_bytes: int
    memo: OrderedDict = field(default_factory=OrderedDict, repr=False)
    memo_bytes: int = 0

    def get(self, key):
        item = self.memo.get(key)
        if item is not None:
            self.memo.move_to_end(key)
        return item

    def put(self, key, value, nbytes):
        if nbytes > self.lru_bytes:
            return
        if key in self.memo:
            _, old = self.memo.pop(key)
            self.memo_bytes -= old
        while self.memo and self.memo_bytes + nbytes > self.lru_bytes:
            _, (_, old) = self.memo.popitem(last=False)
            self.memo_bytes -= old
        self.memo[key] = (value, nbytes)
        self.memo_bytes += nbytes


def prepare_episode_cache(specs, inventory, root, limits) -> CacheManifest:
    """Generate exactly the declared IDs once; retain sampler failures verbatim."""
    if (type(limits) is not dict or set(limits) != {'disk_bytes', 'lru_bytes'} or
            any(type(v) is not int or v <= 0 for v in limits.values())):
        raise ValueError('positive disk and LRU byte ceilings required')
    if not isinstance(specs, (list, tuple)) or not specs or not all(type(s) is PopulationSpec for s in specs):
        raise ValueError('PopulationSpecs required')
    by_spec = {canonical_hash(s.to_json()): s for s in specs}
    if len(by_spec) != len(specs) or not inventory or type(inventory) is not list:
        raise ValueError('distinct specs and nonempty inventory required')
    ids = set()
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    entries = []
    total = 0
    for index, item in enumerate(inventory):
        if type(item) is not dict or set(item) != {'history_id', 'spec'} or type(item['history_id']) is not str or not item['history_id']:
            raise ValueError('invalid episode inventory')
        h = item['history_id']
        spec_hash = canonical_hash(item['spec'])
        if h in ids or spec_hash not in by_spec or by_spec[spec_hash].namespace not in {'training', 'development_fit', 'unit_test'}:
            raise ValueError('duplicate/unknown/protected episode inventory')
        ids.add(h)
        spec = by_spec[spec_hash]
        ep = generate_episode(spec, h)
        raw = canonical_json(_record(ep))
        total += len(raw)
        if total > limits['disk_bytes']:
            raise MemoryError('episode cache disk admission exceeded')
        name = f'episode-{index:06d}.json'
        _atomic(root / name, raw)
        entries.append({'history_id': h, 'spec_sha256': spec_hash, 'file': name,
                        'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw),
                        'episode_digest': _episode_digest(ep), 'status': ep.metadata['status'],
                        'diagnostics': ep.metadata['diagnostics']})
    body = {'schema_version': 1, 'entries': entries, 'source_sha256': source_sha256(),
            'e3_sha256': e3_source_sha256(), 'disk_bytes': total, 'lru_bytes': limits['lru_bytes']}
    for _ in range(8):
        measured = total + len(canonical_json(body))
        if body['disk_bytes'] == measured:
            break
        body['disk_bytes'] = measured
    raw = canonical_json(body)
    measured = total + len(raw)
    if body['disk_bytes'] != measured or measured > limits['disk_bytes']:
        raise MemoryError('episode cache manifest disk admission exceeded')
    _atomic(root / 'cache-manifest.json', raw)
    return CacheManifest(root, entries, body['source_sha256'], body['e3_sha256'],
                         hashlib.sha256(raw).hexdigest(), measured, limits['lru_bytes'])


def load_episode_cache(root, expected_sha256):
    root = Path(root)
    raw = (root / 'cache-manifest.json').read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected_sha256:
        raise ValueError('cache manifest hash mismatch')
    body = json.loads(raw)
    if (set(body) != {'schema_version', 'entries', 'source_sha256', 'e3_sha256', 'disk_bytes', 'lru_bytes'} or
            body['schema_version'] != 1 or body['source_sha256'] != source_sha256() or body['e3_sha256'] != e3_source_sha256()):
        raise ValueError('cache source/schema mismatch')
    entries = body['entries']
    if (type(entries) is not list or not entries or type(body['lru_bytes']) is not int or body['lru_bytes'] <= 0 or
            type(body['disk_bytes']) is not int or
            any(type(item) is not dict or set(item) != {'history_id', 'spec_sha256', 'file', 'sha256',
                'bytes', 'episode_digest', 'status', 'diagnostics'} or
                item['file'] != f'episode-{index:06d}.json' or
                type(item['history_id']) is not str or not item['history_id'] or
                type(item['bytes']) is not int or item['bytes'] <= 0 or
                any(type(item[key]) is not str or len(item[key]) != 64 for key in
                    ('spec_sha256', 'sha256', 'episode_digest')) for index, item in enumerate(entries)) or
            len({item['history_id'] for item in entries}) != len(entries) or
            body['disk_bytes'] != len(raw) + sum(item['bytes'] for item in entries)):
        raise ValueError('cache manifest inventory/disk mismatch')
    return CacheManifest(root, body['entries'], body['source_sha256'], body['e3_sha256'],
                         expected_sha256, body['disk_bytes'], body['lru_bytes'])


def episode_factory(cache: CacheManifest, history_ids):
    if type(cache) is not CacheManifest or cache.source_sha256 != source_sha256() or cache.e3_sha256 != e3_source_sha256():
        raise ValueError('cache source identity changed')
    lookup = {entry['history_id']: entry for entry in cache.entries}
    ids = tuple(history_ids)
    if not ids or len(set(ids)) != len(ids) or any(h not in lookup for h in ids):
        raise ValueError('unknown or repeated history inventory')

    def factory():
        for h in ids:
            entry = lookup[h]
            path = cache.root / entry['file']
            if path.name != entry['file'] or path.resolve().parent != cache.root.resolve():
                raise ValueError('unsafe cache path')
            raw = path.read_bytes()
            if len(raw) != entry['bytes'] or hashlib.sha256(raw).hexdigest() != entry['sha256']:
                raise ValueError('episode cache hash mismatch')
            ep = _restore(json.loads(raw))
            if ep.events.history_ids != (h,) or _episode_digest(ep) != entry['episode_digest']:
                raise ValueError('episode cache replay hash mismatch')
            yield ep
    return factory


class CachedTrainingModel(RidgeMemoryModel):
    """Training-only unstandardized memo; serialization returns a base E1 model."""

    def encode(self, events, state=None, *, mode='stream'):
        if mode != 'terminal' or state is not None:
            return super().encode(events, state, mode=mode)
        key = canonical_hash({'kind': 'terminal', 'identity': self._cache_identity, 'events': batch_hash(events),
                              'time_unit': events.time_unit})
        item = self._cache.get(key)
        if item is None:
            state = super().encode(events, state, mode=mode)
            rec = snapshot_record(state)
            self._cache.put(key, rec, len(canonical_json(rec)))
            self.cache_stats['terminal_misses'] += 1
            return state
        self.cache_stats['terminal_hits'] += 1
        result = snapshot_from_record(item[0], self.writer_hash)
        if not self._terminal_checked:
            direct = super().encode(events, state, mode=mode)
            if snapshot_hash(direct) != snapshot_hash(result):
                raise ValueError('terminal cache/base mismatch')
            self._terminal_checked = True
        return result

    def _raw_features(self, state, queries):
        key = canonical_hash({'kind': 'raw', 'identity': self._cache_identity,
                              'state': snapshot_hash(state), 'queries': batch_hash(queries)})
        item = self._cache.get(key)
        if item is None:
            values = super()._raw_features(state, queries)
            copy = tuple(np.array(x, copy=True) for x in values)
            self._cache.put(key, copy, sum(x.nbytes for x in copy))
            self.cache_stats['raw_misses'] += 1
            return values
        self.cache_stats['raw_hits'] += 1
        values = tuple(np.array(x, copy=True) for x in item[0])
        if not self._raw_checked:
            direct = super()._raw_features(state, queries)
            if any(not np.array_equal(a, b, equal_nan=True) for a, b in zip(values, direct)):
                raise ValueError('raw cache/base mismatch')
            self._raw_checked = True
        return values


def attach_training_cache(model, cache, limits) -> CachedTrainingModel:
    if type(model) is not RidgeMemoryModel or model.fit_artifact is not None or type(cache) is not CacheManifest:
        raise ValueError('fresh base RidgeMemoryModel and cache required')
    if cache.source_sha256 != source_sha256() or cache.e3_sha256 != e3_source_sha256():
        raise ValueError('training cache source identity mismatch')
    if type(limits) is not dict or set(limits) != {'lru_bytes'} or type(limits['lru_bytes']) is not int or limits['lru_bytes'] <= 0 or limits['lru_bytes'] > cache.lru_bytes:
        raise ValueError('invalid training LRU admission')
    attached = CachedTrainingModel(model.shape, model.spec, model.t_ref, model.target_statistics)
    attached._cache = cache
    attached._cache_identity = canonical_hash({'e1_source': source_sha256(), 'e3_source': e3_source_sha256(),
        'cache_manifest': cache.manifest_sha256, 'shape': model.shape.to_json(), 'reader': model.spec.to_json(),
        't_ref': model.t_ref, 'writer': model.writer_hash, 'feature_version': 'ridge_raw_v1'})
    attached.cache_stats = {'terminal_hits': 0, 'terminal_misses': 0, 'raw_hits': 0, 'raw_misses': 0}
    attached._terminal_checked = False
    attached._raw_checked = False
    return attached
