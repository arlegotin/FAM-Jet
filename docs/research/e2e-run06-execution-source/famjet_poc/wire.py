"""Strict numeric request/response wire for fresh E3 read interpreters."""
from dataclasses import asdict
import hashlib
import json
import math
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import threading
import time
import resource

import numpy as np
import torch

from famjet.data.schema import validate_queries
from famjet.eval.state_io import snapshot_hash, snapshot_record, tensor_from_record, tensor_record
from famjet.memory._fixed_writer import _digest_tensor
from famjet.memory.exact_store import PackedHistoryMemory
from famjet.memory.reservoir import ReservoirMemory
from famjet.memory.buckets import TemporalBucketsMemory
from famjet.provenance import canonical_hash, canonical_json
from famjet.types import QueryBatch, ReadResult, Snapshot
from .contracts import ReaderSpec, ShapeSpec, source_sha256
from .models import FitArtifact, RidgeMemoryModel, _validate_loaded_fit, build_model

_ROOT = Path(__file__).resolve().parents[1]
_E3_FILES = ('cache.py', 'wire.py', 'worker.py', 'comparators.py', 'study.py', 'timing.py')
_QUERY_TENSORS = ('query_ids', 'T', 'key_ids', 'key_features', 'age_start', 'age_end', 'present', 'lengths')
_RIDGE_ARRAYS = ('coefficients', 'feature_mean', 'feature_scale', 'query_mean', 'query_scale')
_LIMIT_FIELDS = {'max_frame_bytes', 'max_array_bytes', 'max_histories'}


def e3_source_sha256():
    return canonical_hash({name: hashlib.sha256((_ROOT / 'famjet_poc' / name).read_bytes()).hexdigest()
                           for name in _E3_FILES})


def _limits(limits):
    if (type(limits) is not dict or set(limits) != _LIMIT_FIELDS or
            any(type(v) is not int or v <= 0 for v in limits.values()) or
            limits['max_histories'] > 64 or limits['max_frame_bytes'] > 64_000_000 or
            limits['max_array_bytes'] > 32_000_000):
        raise ValueError('invalid finite worker limits')
    return limits


def _query_record(q):
    if type(q) is not QueryBatch:
        raise ValueError('exact QueryBatch required')
    return {'history_ids': list(q.history_ids), 'tasks': [list(row) for row in q.tasks],
            **{name: tensor_record(getattr(q, name)) for name in _QUERY_TENSORS}}


def _query_from_record(q):
    if type(q) is not dict or set(q) != {'history_ids', 'tasks', *_QUERY_TENSORS}:
        raise ValueError('query field inventory mismatch')
    result = QueryBatch(tuple(q['history_ids']), **{name: tensor_from_record(q[name]) for name in _QUERY_TENSORS},
                        tasks=tuple(tuple(row) for row in q['tasks']))
    validate_queries(result)
    return result


def _array_records(value):
    if type(value) is dict:
        if set(value) == {'dtype', 'shape', 'data'}:
            yield value
        else:
            for item in value.values():
                yield from _array_records(item)
    elif type(value) is list:
        for item in value:
            yield from _array_records(item)


def _preflight_arrays(value, limits):
    dtypes = {'bool': 1, 'uint8': 1, 'int8': 1, 'int16': 2, 'uint16': 2,
              'int32': 4, 'uint32': 4, 'float32': 4, 'int64': 8, 'uint64': 8, 'float64': 8}
    for record in _array_records(value):
        shape, dtype, data = record['shape'], record['dtype'], record['data']
        if (dtype not in dtypes or type(shape) is not list or len(shape) > 5 or
                any(type(n) is not int or n < 0 or n > limits['max_array_bytes'] for n in shape) or
                type(data) is not str):
            raise ValueError('invalid tensor layout')
        size = math.prod(shape) * dtypes[dtype]
        if size > limits['max_array_bytes'] or len(data) != 4 * ((size + 2) // 3):
            raise ValueError('tensor byte ceiling exceeded')


def _preflight_statics(statics, limits):
    if (type(statics) is not dict or statics.get('schema_version') != 1 or
            statics.get('kind') not in {'ridge', 'packed', 'reservoir', 'buckets'} or
            type(statics.get('writer_hash')) is not str or len(statics['writer_hash']) != 64 or
            any(ch not in '0123456789abcdef' for ch in statics['writer_hash'])):
        raise ValueError('invalid static kind')
    shape = statics.get('shape')
    if (type(shape) is not dict or set(shape) != {'key_dim', 'value_dim'} or
            (shape.get('key_dim'), shape.get('value_dim')) not in {(12, 1), (16, 8)}):
        raise ValueError('unsupported static shape')
    if statics['kind'] == 'ridge':
        if set(statics) != {'schema_version', 'kind', 'shape', 'reader', 't_ref', 'target_statistics', 'writer_hash', 'arrays'}:
            raise ValueError('reader static field inventory mismatch')
        reader = ReaderSpec.from_json(statics['reader'])
        if type(statics['t_ref']) not in (int, float) or not math.isfinite(statics['t_ref']) or statics['t_ref'] <= 0:
            raise ValueError('reader reference time schema mismatch')
        if type(statics['arrays']) is not dict or set(statics['arrays']) != set(_RIDGE_ARRAYS):
            raise ValueError('reader static array inventory mismatch')
        expected_arrays = {'coefficients': [33 * reader.query_width], 'feature_mean': [32],
                           'feature_scale': [32], 'query_mean': [reader.query_width - 1],
                           'query_scale': [reader.query_width - 1]}
        for name, expected_shape in expected_arrays.items():
            _record_layout(statics['arrays'][name], expected_shape, {'float64'}, name)
        stats = statics.get('target_statistics')
        required = {'schema_version', 'target_semantics', 'split', 'variance_ddof', 'pooling',
                    'constant_policy', 'tasks'}
        if (type(stats) is not dict or set(stats) != required or stats['schema_version'] != 2 or
                stats['target_semantics'] != 'observed_event_targets_v2' or stats['split'] != 'training' or
                stats['variance_ddof'] != 0 or stats['pooling'] != 'queries_within_task_then_coordinate_variances' or
                stats['constant_policy'] != 'include_in_scale_pool; report_absolute_error_separately; all_constant_scale_null' or
                type(stats['tasks']) is not dict or set(stats['tasks']) != {'mean', 'contrast'}):
            raise ValueError('reader training statics field inventory mismatch')
        for task in ('mean', 'contrast'):
            entry = stats['tasks'][task]
            if (type(entry) is not dict or set(entry) != {'status', 'count', 'mean', 'coordinate_variance',
                    'pooled_variance', 'scale', 'constant_coordinates', 'class_distribution'} or
                    entry['status'] != 'ok' or type(entry['count']) is not int or entry['count'] <= 0 or
                    type(entry['mean']) is not list or len(entry['mean']) != shape['value_dim'] or
                    type(entry['coordinate_variance']) is not list or len(entry['coordinate_variance']) != shape['value_dim'] or
                    type(entry['constant_coordinates']) is not list or len(entry['constant_coordinates']) != shape['value_dim'] or
                    not all(type(x) is bool for x in entry['constant_coordinates']) or
                    entry['class_distribution'] is not None or
                    any(type(x) not in (int, float) or not math.isfinite(x) for x in
                        (*entry['mean'], *entry['coordinate_variance'], entry['pooled_variance'], entry['scale'])) or
                    entry['scale'] <= 0):
                raise ValueError('reader training statics numeric schema mismatch')
    else:
        if set(statics) != {'schema_version', 'kind', 'shape', 'constructor', 'writer_hash'}:
            raise ValueError('control static field inventory mismatch')
        c = statics.get('constructor')
        if type(c) is not dict:
            raise ValueError('control constructor schema mismatch')
        expected_fields = ({'capacity', 'value_dim', 'policy', 'key_dim', 'value_dtype'} if statics['kind'] == 'packed' else
                           {'capacity', 'value_dim', 'seed', 'key_dim', 'value_dtype', 'accumulation_dtype'} if statics['kind'] == 'reservoir' else
                           {'capacity', 'value_dim', 'key_dim', 'value_dtype', 'accumulation_dtype', 'normalization'})
        if set(c) != expected_fields or c['key_dim'] != shape['key_dim'] or c['value_dim'] != shape['value_dim']:
            raise ValueError('control constructor field/shape mismatch')
        if (type(c['value_dtype']) is not str or c['value_dtype'] not in {'float32', 'float64'} or
                statics['kind'] != 'packed' and (type(c['accumulation_dtype']) is not str or c['accumulation_dtype'] not in {'float32', 'float64'}) or
                statics['kind'] == 'packed' and c['policy'] not in {'exact', 'recent', 'latest_lru'} or
                statics['kind'] == 'buckets' and c['normalization'] not in {'shared', 'independent'}):
            raise ValueError('control constructor precision/policy mismatch')
        capacity = c.get('capacity')
        if statics['kind'] == 'packed' and c.get('policy') == 'exact':
            if capacity is not None:
                raise ValueError('exact control capacity must be null')
        elif (type(capacity) is not int or capacity <= 0 or
              capacity * (64 + 16 * shape['value_dim']) > limits['max_array_bytes']):
            raise ValueError('control capacity exceeds allocation ceiling')


def _record_layout(record, shape, dtypes, name):
    if (type(record) is not dict or set(record) != {'dtype', 'shape', 'data'} or
            record.get('shape') != shape or record.get('dtype') not in dtypes):
        raise ValueError(f'invalid registered tensor layout: {name}')


def _preflight_pair(pair, statics, expected):
    if type(pair) is not dict or set(pair) != {'snapshot', 'snapshot_hash', 'queries', 'time_unit'}:
        raise ValueError('pair field inventory mismatch')
    s, q = pair['snapshot'], pair['queries']
    if (type(s) is not dict or set(s) != {'schema_version', 'parameter_hash', 'payload', 'last_time', 'valid', 'event_offset'} or
            s['schema_version'] != 1 or s['parameter_hash'] != statics['writer_hash'] or
            type(s['payload']) is not dict or pair['snapshot_hash'] != canonical_hash(s) or
            type(pair['time_unit']) is not str or not pair['time_unit']):
        raise ValueError('snapshot schema/writer/hash mismatch before reconstruction')
    c = statics.get('constructor', {})
    k, v = statics['shape']['key_dim'], statics['shape']['value_dim']
    kind = statics['kind']
    payload = {'history_hash': ([1, 32], {'uint8'}), 'time_unit_hash': ([32], {'uint8'})}
    if kind == 'ridge':
        width = 4 if statics['reader']['family'] == 'jet' else 8
        for name in ('z', 'h') if statics['reader']['family'] == 'jet' else ('z',):
            payload[name] = ([1, 1, width, k, v + 1], {'float64'})
        payload['last_event_id'] = ([1], {'int64'})
    else:
        capacity = c['capacity'] if c['capacity'] is not None else s['payload'].get('occupied', {}).get('shape', [None, None])[1]
        if type(capacity) is not int or capacity < 0:
            raise ValueError('invalid packed snapshot capacity')
        slot = [1, capacity]
        payload.update({name: (slot, {'uint64'}) for name in ('key_ids', 'event_ids', 'time_words')})
        payload.update({name: (slot, {'bool'}) for name in ('time_is_tick', 'occupied')})
        payload['values'] = ([1, capacity, v], {c.get('accumulation_dtype', c['value_dtype']) if kind == 'buckets' else c['value_dtype']})
        obs_width = 1 if kind == 'buckets' and c['normalization'] == 'shared' else v
        payload['observed'] = ([1, capacity, obs_width], {'bool'})
        payload.update({name: ([1, 1], {'int64'}) for name in ('size', 'seen', 'discarded')})
        payload.update({'last_time_word': ([1, 1], {'uint64'}), 'last_time_is_tick': ([1, 1], {'bool'}),
                        'last_valid': ([1, 1], {'bool'}), 'last_event_id': ([1, 1], {'uint64'})})
        if kind == 'packed':
            if c['policy'] == 'latest_lru':
                payload['recency'] = (slot, {'int64'})
            if c['policy'] == 'recent':
                payload['cursor'] = ([1, 1], {'int64'})
        elif kind == 'reservoir':
            payload.update({'total_writes': ([1, 1], {'int64'}), 'rng_counter': ([1, 1], {'uint64'}),
                            'seed': ([1, 1], {'uint64'}), 'algorithm_version': ([1, 1], {'int64'}),
                            'write_ordinals': (slot, {'int64'})})
        else:
            payload.update({'end_time_words': (slot, {'uint64'}), 'end_time_is_tick': (slot, {'bool'}),
                            'counts': ([1, capacity, obs_width], {'int64'}), 'recency': (slot, {'int64'}),
                            'sum_failed': ([1, capacity, v], {'bool'}),
                            'total_writes': ([1, 1], {'int64'}), 'merges': ([1, 1], {'int64'}),
                            'evicted_keys': ([1, 1], {'int64'}), 'algorithm_version': ([1, 1], {'int64'})})
            if c['normalization'] == 'independent':
                payload['event_counts'] = (slot, {'int64'})
    if set(s['payload']) != set(payload):
        raise ValueError('registered snapshot payload inventory mismatch')
    for name, (shape, dtypes) in payload.items():
        _record_layout(s['payload'][name], shape, dtypes, name)
    for name, dtypes in (('last_time', {'int64', 'float64'}), ('valid', {'bool'}), ('event_offset', {'int64'})):
        _record_layout(s[name], [1], dtypes, name)
    if (type(q) is not dict or set(q) != {'history_ids', 'tasks', *_QUERY_TENSORS} or
            q['history_ids'] != [expected['history_id']] or type(q['tasks']) is not list or len(q['tasks']) != 1):
        raise ValueError('registered query field/identity schema mismatch')
    qshape = q['query_ids'].get('shape') if type(q['query_ids']) is dict else None
    if type(qshape) is not list or len(qshape) != 2 or qshape[0] != 1 or type(qshape[1]) is not int or qshape[1] <= 0:
        raise ValueError('registered query shape mismatch')
    count = qshape[1]
    if (type(q['tasks'][0]) is not list or len(q['tasks'][0]) != count or
            any(type(task) is not str or not task for task in q['tasks'][0]) or
            len(expected['query_ids']) > count):
        raise ValueError('registered query task/ID inventory mismatch')
    layouts = {'query_ids': ([1, count], {'int64'}), 'T': ([1, count], {'int64', 'float64'}),
               'key_ids': ([1, count], {'int64', 'uint64'}),
               'key_features': ([1, count, k], {'float32', 'float64'}),
               'age_start': ([1, count], {'float64'}), 'age_end': ([1, count], {'float64'}),
               'present': ([1, count], {'bool'}), 'lengths': ([1], {'int64'})}
    for name, (shape, dtypes) in layouts.items():
        _record_layout(q[name], shape, dtypes, name)


def _exact_attributes(model, names):
    if set(vars(model)) != names:
        raise ValueError('unregistered model attribute/field')


def export_statics(model):
    """Reject training subclasses, hidden attributes and nonfinite statics."""
    if type(model) is RidgeMemoryModel:
        _exact_attributes(model, {'shape', 'spec', 't_ref', '_target_statistics', 'writer', '_coefficients',
                                  'feature_mean', 'feature_scale', 'query_mean', 'query_scale', 'fit_artifact'})
        if type(model.fit_artifact) is not FitArtifact:
            raise ValueError('verified fitted reader required')
        expected_writer = build_model(model.shape, model.spec, model.t_ref, model.target_statistics).writer
        if (type(model.writer) is not type(expected_writer) or
                set(vars(model.writer)) != set(vars(expected_writer)) or
                set(model.writer._parameters) != set(expected_writer._parameters) or
                set(model.writer._buffers) != set(expected_writer._buffers) or
                set(model.writer._modules) != set(expected_writer._modules)):
            raise ValueError('reader writer has unregistered attribute or module')
        for name, expected_value in vars(expected_writer).items():
            if name.startswith('_') or name == 'training':
                continue
            actual_value = vars(model.writer)[name]
            if type(actual_value) is not type(expected_value) or actual_value != expected_value:
                raise ValueError('reader writer static attribute differs from registered construction')
        _validate_loaded_fit(model, asdict(model.fit_artifact),
                             {'rates': model.writer.rates.detach().cpu().numpy(),
                              **{name: np.asarray(getattr(model, name)) for name in _RIDGE_ARRAYS}})
        arrays = {name: tensor_record(torch.from_numpy(np.array(getattr(model, name), copy=True))) for name in _RIDGE_ARRAYS}
        statics = {'schema_version': 1, 'kind': 'ridge', 'shape': model.shape.to_json(),
                   'reader': model.spec.to_json(), 't_ref': model.t_ref,
                   'target_statistics': model.target_statistics, 'writer_hash': model.writer_hash,
                   'arrays': arrays}
    elif type(model) is PackedHistoryMemory:
        _exact_attributes(model, {'capacity', 'value_dim', 'policy', 'key_dim', 'value_dtype'})
        statics = {'schema_version': 1, 'kind': 'packed', 'shape': {'key_dim': model.key_dim, 'value_dim': model.value_dim},
                   'constructor': {'capacity': model.capacity, 'value_dim': model.value_dim, 'policy': model.policy,
                                   'key_dim': model.key_dim, 'value_dtype': model.value_dtype},
                   'writer_hash': model._parameter_hash()}
    elif type(model) in {ReservoirMemory, TemporalBucketsMemory}:
        _exact_attributes(model, {'_factory', '_store_kwargs', 'capacity', 'value_dim', 'value_dtype', 'key_dim', 'policy'})
        statics = {'schema_version': 1, 'kind': 'reservoir' if type(model) is ReservoirMemory else 'buckets',
                   'shape': {'key_dim': model.key_dim, 'value_dim': model.value_dim},
                   'constructor': {**model._store_kwargs, 'key_dim': model.key_dim},
                   'writer_hash': model._parameter_hash()}
    else:
        raise ValueError('unregistered method class or training subclass')
    _reconstruct(statics)
    return statics


def _reconstruct(statics):
    if type(statics) is not dict or statics.get('schema_version') != 1 or statics.get('kind') not in {'ridge', 'packed', 'reservoir', 'buckets'}:
        raise ValueError('invalid static schema')
    kind = statics['kind']
    if kind == 'ridge':
        if set(statics) != {'schema_version', 'kind', 'shape', 'reader', 't_ref', 'target_statistics', 'writer_hash', 'arrays'} or set(statics['arrays']) != set(_RIDGE_ARRAYS):
            raise ValueError('reader static field inventory mismatch')
        model = build_model(ShapeSpec.from_json(statics['shape']), ReaderSpec.from_json(statics['reader']),
                            statics['t_ref'], statics['target_statistics'])
        expected = {'coefficients': (33 * model.spec.query_width,), 'feature_mean': (32,), 'feature_scale': (32,),
                    'query_mean': (model.spec.query_width - 1,), 'query_scale': (model.spec.query_width - 1,)}
        arrays = {name: tensor_from_record(statics['arrays'][name]).numpy() for name in _RIDGE_ARRAYS}
        for name, arr in arrays.items():
            if arr.dtype != np.float64 or arr.shape != expected[name] or not np.isfinite(arr).all():
                raise ValueError('invalid finite FP64 reader static array')
        if np.any(arrays['feature_scale'] <= 0) or np.any(arrays['query_scale'] <= 0):
            raise ValueError('invalid reader scale')
        model.coefficients = arrays['coefficients']
        for name in _RIDGE_ARRAYS[1:]:
            setattr(model, name, arrays[name].copy())
    else:
        if set(statics) != {'schema_version', 'kind', 'shape', 'constructor', 'writer_hash'}:
            raise ValueError('control static field inventory mismatch')
        c = statics['constructor']
        if type(c) is not dict:
            raise ValueError('invalid constructor schema')
        if kind == 'packed':
            if set(c) != {'capacity', 'value_dim', 'policy', 'key_dim', 'value_dtype'}:
                raise ValueError('packed constructor field inventory mismatch')
            model = PackedHistoryMemory(**c)
        elif kind == 'reservoir':
            if set(c) != {'capacity', 'value_dim', 'seed', 'key_dim', 'value_dtype', 'accumulation_dtype'}:
                raise ValueError('reservoir constructor field inventory mismatch')
            model = ReservoirMemory(**c)
        else:
            if set(c) != {'capacity', 'value_dim', 'key_dim', 'value_dtype', 'accumulation_dtype', 'normalization'}:
                raise ValueError('bucket constructor field inventory mismatch')
            model = TemporalBucketsMemory(**c)
        if statics['shape'] != {'key_dim': model.key_dim, 'value_dim': model.value_dim}:
            raise ValueError('control shape mismatch')
    writer = model.writer_hash if kind == 'ridge' else model._parameter_hash()
    if writer != statics['writer_hash']:
        raise ValueError('writer/static identity mismatch')
    return model


def encode_request(statics, pairs, expected_ids, limits):
    limits = _limits(limits)
    _preflight_statics(statics, limits)
    _preflight_arrays(statics, limits)
    if type(pairs) is not list or not pairs or len(pairs) > limits['max_histories'] or len(pairs) > 64:
        raise ValueError('worker supports 1..64 histories')
    if type(expected_ids) is not list or len(expected_ids) != len(pairs):
        raise ValueError('expected ID inventory mismatch')
    encoded = []
    seen = set()
    for pair, expected in zip(pairs, expected_ids):
        if type(pair) is not dict or set(pair) != {'snapshot', 'queries', 'time_unit'} or type(pair['snapshot']) is not Snapshot or type(pair['time_unit']) is not str:
            raise ValueError('invalid snapshot/query pair fields')
        snapshot, query = pair['snapshot'], pair['queries']
        validate_queries(query, snapshot)
        if (len(query.history_ids) != 1 or type(expected) is not dict or set(expected) != {'history_id', 'query_ids'} or
                expected['history_id'] != query.history_ids[0] or expected['query_ids'] != query.query_ids[0].tolist() or
                expected['history_id'] in seen):
            raise ValueError('expected history/query IDs mismatch')
        seen.add(expected['history_id'])
        if snapshot.parameter_hash != statics['writer_hash'] or not torch.equal(snapshot.payload['history_hash'][0], _digest_tensor(expected['history_id'])) or not torch.equal(snapshot.payload['time_unit_hash'], _digest_tensor(pair['time_unit'])):
            raise ValueError('snapshot writer/history/time identity mismatch')
        if query.present.any() and bool((query.T[query.present] < snapshot.last_time[0]).any()):
            raise ValueError('deferred queries required')
        encoded.append({'snapshot': snapshot_record(snapshot), 'snapshot_hash': snapshot_hash(snapshot),
                        'queries': _query_record(query), 'time_unit': pair['time_unit']})
    body = {'schema_version': 1, 'e1_source': source_sha256(), 'e3_source': e3_source_sha256(),
            'statics': statics, 'statics_hash': canonical_hash(statics), 'writer_hash': statics['writer_hash'],
            'limits': limits,
            'request_id': canonical_hash({'statics': statics, 'pairs': encoded, 'expected_ids': expected_ids,
                                          'limits': limits}),
            'expected_ids': expected_ids, 'pairs': encoded}
    _preflight_arrays(body, limits)
    for pair, expected in zip(encoded, expected_ids):
        _preflight_pair(pair, statics, expected)
    raw = canonical_json(body)
    if len(raw) > limits['max_frame_bytes']:
        raise ValueError('frame byte ceiling exceeded')
    _reconstruct(statics)
    return struct.pack('>Q', len(raw)) + raw


def decode_request(raw, limits):
    maximum = _limits(limits)
    if len(raw) > maximum['max_frame_bytes']:
        raise ValueError('frame byte ceiling exceeded')
    body = json.loads(raw)
    required = {'schema_version', 'e1_source', 'e3_source', 'statics', 'statics_hash', 'writer_hash',
                'request_id', 'expected_ids', 'pairs', 'limits'}
    if type(body) is not dict or set(body) != required or body['schema_version'] != 1:
        raise ValueError('request field/schema mismatch')
    limits = _limits(body['limits'])
    if any(limits[key] > maximum[key] for key in _LIMIT_FIELDS) or len(raw) > limits['max_frame_bytes']:
        raise ValueError('request exceeds admitted caller/worker limits')
    if (body['e1_source'] != source_sha256() or body['e3_source'] != e3_source_sha256() or
            body['statics_hash'] != canonical_hash(body['statics']) or body['writer_hash'] != body['statics'].get('writer_hash') or
            body['request_id'] != canonical_hash({'statics': body['statics'], 'pairs': body['pairs'],
                                                  'expected_ids': body['expected_ids'], 'limits': limits})):
        raise ValueError('request source/hash mismatch')
    if (type(body['pairs']) is not list or type(body['expected_ids']) is not list or
            not 0 < len(body['pairs']) <= min(64, limits['max_histories']) or
            len(body['expected_ids']) != len(body['pairs'])):
        raise ValueError('worker history count exceeds 64')
    _preflight_statics(body['statics'], limits)
    seen = set()
    for expected in body['expected_ids']:
        if (type(expected) is not dict or set(expected) != {'history_id', 'query_ids'} or
                type(expected['history_id']) is not str or not expected['history_id'] or
                expected['history_id'] in seen or type(expected['query_ids']) is not list or
                not expected['query_ids'] or len(expected['query_ids']) > limits['max_array_bytes'] // 8 or
                any(type(q) is not int or q < 0 for q in expected['query_ids']) or
                len(set(expected['query_ids'])) != len(expected['query_ids'])):
            raise ValueError('expected history/query ID schema mismatch')
        seen.add(expected['history_id'])
    _preflight_arrays(body, limits)
    for pair, expected in zip(body['pairs'], body['expected_ids']):
        _preflight_pair(pair, body['statics'], expected)
    return body


def _result_from_record(record):
    if type(record) is not dict or set(record) != {'schema_version', 'prediction', 'logits', 'support', 'failure', 'diagnostics'} or record['schema_version'] != 1:
        raise ValueError('response result schema mismatch')
    return ReadResult(tensor_from_record(record['prediction']) if record['prediction'] is not None else None,
                      tensor_from_record(record['logits']) if record['logits'] is not None else None,
                      tensor_from_record(record['support']), tensor_from_record(record['failure']),
                      {k: tensor_from_record(v) for k, v in record['diagnostics'].items()})


def _parent_rss_bytes():
    observed = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return int(observed if os.uname().sysname == 'Darwin' else observed * 1024)


def _run_worker(command, frame, env, directory, timeout, sample_rss):
    if not sample_rss:
        return subprocess.run(command, input=frame + b'\x04', stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              cwd=directory, env=env, close_fds=True, timeout=timeout), None
    baseline = _parent_rss_bytes()
    with subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          cwd=directory, env=env, close_fds=True) as process:
        outcome = {}
        def exchange():
            try:
                process.stdin.write(frame + b'\x04')
                process.stdin.flush()
                prefix = process.stdout.read(8)
                if len(prefix) != 8:
                    raise ValueError('missing worker response frame')
                size = struct.unpack('>Q', prefix)[0]
                if size > 64_000_000:
                    raise ValueError('worker response frame byte ceiling exceeded')
                raw = process.stdout.read(size)
                if len(raw) != size:
                    raise ValueError('incomplete worker response frame')
                parent_rss = _parent_rss_bytes()
                body = json.loads(raw)
                child_rss = body.get('child_rss_bytes')
                outcome['sampling'] = {'parent_pid': os.getpid(), 'child_pid': process.pid,
                    'sample_count': 1 if type(child_rss) is int and child_rss > 0 else 0,
                    'parent_lifetime_peak_bytes': parent_rss, 'child_lifetime_peak_bytes': child_rss,
                    'sum_lifetime_peaks_bytes': parent_rss + child_rss if type(child_rss) is int and child_rss > 0 else None,
                    'parent_baseline_lifetime_peak_bytes': baseline,
                    'parent_lifetime_peak_increment_bytes': max(0, parent_rss - baseline),
                    'sampling_method': 'child_report_then_parent_sample_before_live_child_ack',
                    'rss_kind': 'conservative_sum_of_per_process_lifetime_peaks_at_live_handshake'}
                process.stdin.write(b'\x06')
                process.stdin.close()
                outcome['stdout'] = prefix + raw
                outcome['stderr'] = process.stderr.read()
                process.wait()
            except Exception as exc:
                outcome['error'] = exc
        thread = threading.Thread(target=exchange, daemon=True)
        thread.start()
        thread.join(timeout)
        if thread.is_alive():
            process.kill()
            thread.join(timeout=5)
            process.wait()
            raise TimeoutError('isolated read worker timed out and was reaped')
        if 'error' in outcome:
            process.kill()
            process.wait()
            raise RuntimeError('worker frame exchange failed') from outcome['error']
        return subprocess.CompletedProcess(command, process.returncode,
                                           outcome['stdout'], outcome['stderr']), outcome['sampling']


def isolated_read_batch(statics, pairs, policy):
    """One clean interpreter, one framed request, explicit timeout and optional journal."""
    if type(policy) is not dict or not {'limits', 'timeout_seconds'} <= set(policy) or set(policy) - {'limits', 'timeout_seconds', 'journal_path', 'sample_rss'}:
        raise ValueError('worker policy requires limits and timeout')
    if 'sample_rss' in policy and type(policy['sample_rss']) is not bool:
        raise ValueError('sample_rss must be boolean')
    timeout = policy['timeout_seconds']
    if type(timeout) not in (int, float) or not math.isfinite(timeout) or timeout <= 0:
        raise ValueError('positive worker timeout required')
    expected = [{'history_id': pair['queries'].history_ids[0], 'query_ids': pair['queries'].query_ids[0].tolist()} for pair in pairs]
    frame = encode_request(statics, pairs, expected, policy['limits'])
    request_hash = hashlib.sha256(frame).hexdigest()
    env = {k: v for k, v in os.environ.items() if k in {'SYSTEMROOT', 'WINDIR'}}
    env.update(OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1',
               VECLIB_MAXIMUM_THREADS='1', NUMEXPR_NUM_THREADS='1')
    bootstrap = 'import sys; sys.path.insert(0, '+repr(str(_ROOT))+'); from famjet_poc.worker import worker_main; raise SystemExit(worker_main())'
    started = time.perf_counter()
    journal = {'request_sha256': request_hash, 'expected_ids': expected, 'status': 'incomplete'}
    try:
        with tempfile.TemporaryDirectory(prefix='famjet-e3-worker-') as directory:
            completed, sampling = _run_worker([sys.executable, '-I', '-c', bootstrap], frame,
                                              env, directory, timeout, policy.get('sample_rss', False))
        if sampling is not None:
            journal['rss_sampling'] = sampling
        if completed.returncode or len(completed.stdout) < 8:
            raise RuntimeError('worker failed: ' + completed.stderr.decode(errors='replace')[-1000:])
        size = struct.unpack('>Q', completed.stdout[:8])[0]
        if size > policy['limits']['max_frame_bytes'] or size != len(completed.stdout) - 8:
            raise ValueError('worker response frame mismatch')
        response = json.loads(completed.stdout[8:])
        if (type(response) is not dict or set(response) != {'schema_version', 'request_id', 'response_id', 'results', 'error', 'child_rss_bytes'} or
                response['schema_version'] != 1 or type(response['child_rss_bytes']) is not int or response['child_rss_bytes'] <= 0):
            raise ValueError('worker response schema mismatch')
        request_id = json.loads(frame[8:])['request_id']
        if response['request_id'] != request_id or response['response_id'] != canonical_hash({'request_id': request_id, 'results': response['results'], 'error': response['error'], 'child_rss_bytes': response['child_rss_bytes']}):
            raise ValueError('worker response identity mismatch: '+str({'expected_request_id': request_id,
                'observed_request_id': response['request_id'], 'child_error': response['error']})[:1000])
        if response['error'] is not None:
            raise RuntimeError('worker read failed: ' + response['error'])
        if len(response['results']) != len(pairs):
            raise ValueError('worker result inventory mismatch')
        _preflight_arrays(response['results'], policy['limits'])
        result = [_result_from_record(r) for r in response['results']]
        for output, pair in zip(result, pairs):
            query = pair['queries']
            expected_shape = (*query.T.shape, statics['shape']['value_dim'])
            if (output.prediction is None or output.logits is not None or
                    output.prediction.shape != expected_shape or output.prediction.dtype != torch.float64 or
                    output.support.shape != query.T.shape or output.failure.shape != query.T.shape or
                    output.failure.dtype != torch.bool):
                raise ValueError('worker result shape/dtype mismatch')
        journal.update(status='ok', response_sha256=hashlib.sha256(completed.stdout).hexdigest(),
                       elapsed_seconds=time.perf_counter() - started)
        return result
    except Exception as exc:
        journal.update(status='failed', error=f'{type(exc).__name__}: {exc}',
                       elapsed_seconds=time.perf_counter() - started)
        raise
    finally:
        if 'journal_path' in policy:
            path = Path(policy['journal_path'])
            path.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(dir=path.parent, prefix='.attempt-', delete=False) as stream:
                temp = Path(stream.name)
                stream.write(canonical_json(journal))
            os.replace(temp, path)
