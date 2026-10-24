import hashlib
import json
import os
import subprocess
import sys

import pytest
import torch

from famjet.memory.exact_store import PackedHistoryMemory
from famjet_poc.contracts import PopulationSpec, ShapeSpec
from famjet_poc.data import generate_episode


def _pair(name='unit-wire-0'):
    spec = PopulationSpec('poc_numeric_v1', ShapeSpec(12, 1), 'unit_test', 92,
                          (128,), ('piecewise_stationary',), 8, 512)
    ep = generate_episode(spec, name)
    method = PackedHistoryMemory(None, 1, 'exact', key_dim=12)
    state = method.encode(ep.events, mode='terminal')
    return method, {'snapshot': state, 'queries': ep.queries, 'time_unit': ep.events.time_unit}


def _limits():
    return {'max_frame_bytes': 8_000_000, 'max_array_bytes': 4_000_000, 'max_histories': 64}


def test_wire_rejects_unknown_fields_and_oversized_tensors_before_allocating():
    from famjet_poc.wire import decode_request, encode_request, export_statics

    method, pair = _pair()
    statics = export_statics(method)
    expected = [{'history_id': pair['queries'].history_ids[0],
                 'query_ids': pair['queries'].query_ids[0].tolist()}]
    raw = encode_request(statics, [pair], expected, _limits())
    assert decode_request(raw[8:], _limits())['expected_ids'] == expected
    body = json.loads(raw[8:])
    body['labels'] = [1.]
    with pytest.raises(ValueError, match='field|schema'):
        decode_request(json.dumps(body).encode(), _limits())
    body.pop('labels')
    body['pairs'][0]['snapshot']['payload']['values']['shape'] = [2**60]
    from famjet.provenance import canonical_hash
    body['request_id'] = canonical_hash({'statics': body['statics'], 'pairs': body['pairs'],
                                         'expected_ids': body['expected_ids']})
    with pytest.raises(ValueError, match='array|tensor|byte'):
        decode_request(json.dumps(body).encode(), _limits())


def test_worker_batch_limit_and_read_only_input():
    from famjet_poc.wire import encode_request, export_statics, isolated_read_batch
    from famjet.eval.state_io import snapshot_hash

    method, pair = _pair()
    statics = export_statics(method)
    before = snapshot_hash(pair['snapshot'])
    result = isolated_read_batch(statics, [pair], {'limits': _limits(), 'timeout_seconds': 30.})
    assert len(result) == 1
    assert torch.equal(result[0].prediction, method.read(pair['snapshot'], pair['queries']).prediction)
    assert snapshot_hash(pair['snapshot']) == before
    with pytest.raises(ValueError, match='64|histories'):
        encode_request(statics, [pair] * 65, [{'history_id': f'h-{i}', 'query_ids': [0]} for i in range(65)], _limits())


def test_export_rejects_hidden_history_attribute():
    from famjet_poc.wire import export_statics

    method, _ = _pair()
    method.history_cache = {'forbidden': 'history'}
    with pytest.raises(ValueError, match='attribute|field'):
        export_statics(method)


def test_worker_audit_guard_forbids_disk_and_network_after_imports():
    script = """from famjet_poc.worker import _install_guard
_install_guard()
for operation in (lambda: open('/tmp/no-such-file', 'rb'), lambda: __import__('socket').socket()):
    try:
        operation()
    except PermissionError:
        pass
    else:
        raise AssertionError('forbidden I/O was admitted')
"""
    completed = subprocess.run([sys.executable, '-c', script], capture_output=True, text=True,
                               env={**os.environ, 'OMP_NUM_THREADS': '1'})
    assert completed.returncode == 0, completed.stderr


def test_sixty_four_histories_admitted_but_sixty_five_rejected():
    from dataclasses import replace
    from famjet_poc.wire import encode_request, export_statics

    method, _ = _pair()
    pairs = []
    for index in range(64):
        h = f'unit-wire-batch-{index}'
        # Produce a real snapshot identity by encoding the public event tensors.
        spec = PopulationSpec('poc_numeric_v1', ShapeSpec(12, 1), 'unit_test', 92,
                              (128,), ('piecewise_stationary',), 8, 512)
        episode = generate_episode(spec, h)
        state = method.encode(episode.events, mode='terminal')
        pairs.append({'snapshot': state, 'queries': episode.queries, 'time_unit': episode.events.time_unit})
    expected = [{'history_id': p['queries'].history_ids[0],
                 'query_ids': p['queries'].query_ids[0].tolist()} for p in pairs]
    raw = encode_request(export_statics(method), pairs, expected,
                         {'max_frame_bytes': 64_000_000, 'max_array_bytes': 4_000_000, 'max_histories': 64})
    assert len(raw) > 8
    with pytest.raises(ValueError, match='64|histories'):
        encode_request(export_statics(method), pairs + pairs[:1], expected + expected[:1],
                       {'max_frame_bytes': 64_000_000, 'max_array_bytes': 4_000_000, 'max_histories': 64})


def test_worker_detects_method_attribute_added_during_read():
    from famjet_poc.wire import encode_request, export_statics

    method, pair = _pair()
    expected = [{'history_id': pair['queries'].history_ids[0],
                 'query_ids': pair['queries'].query_ids[0].tolist()}]
    frame = encode_request(export_statics(method), [pair], expected, _limits())
    script = """import json, sys
from famjet.memory.exact_store import PackedHistoryMemory
from famjet_poc.worker import _read
original = PackedHistoryMemory.read
def retaining(self, state, queries):
    result = original(self, state, queries)
    self.history_cache = {'forbidden': 'retained'}
    return result
PackedHistoryMemory.read = retaining
try:
    _read(json.loads(sys.stdin.buffer.read()))
except ValueError as exc:
    if 'mutated' not in str(exc) and 'attribute' not in str(exc):
        raise
else:
    raise AssertionError('worker admitted hidden method state')
"""
    completed = subprocess.run([sys.executable, '-c', script], input=frame[8:],
                               capture_output=True, env={**os.environ, 'OMP_NUM_THREADS': '1'})
    assert completed.returncode == 0, completed.stderr.decode()


def test_ridge_worker_uses_loaded_base_and_rejects_hidden_writer_history(tmp_path):
    from famjet_poc.cache import attach_training_cache, episode_factory, prepare_episode_cache
    from famjet_poc.contracts import ReaderSpec
    from famjet_poc.models import build_model, fit_reader, fit_training_metadata, load_model, make_fit_manifest, save_model
    from famjet_poc.wire import export_statics, isolated_read_batch

    spec = PopulationSpec('poc_numeric_v1', ShapeSpec(12, 1), 'training', 412,
                          (128,), ('piecewise_stationary',), 8, 512)
    ids = ['unit-ridge-wire-0', 'unit-ridge-wire-1']
    cache = prepare_episode_cache([spec], [{'history_id': h, 'spec': spec.to_json()} for h in ids],
                                  tmp_path / 'cache', {'disk_bytes': 8_000_000, 'lru_bytes': 8_000_000})
    factory = episode_factory(cache, ids)
    meta = fit_training_metadata(factory)
    reader = ReaderSpec('ridge_v1', 'jet', 8, 1e-6, 1 / 5224, 1., 1e-6, 1e-12)
    fitted = attach_training_cache(build_model(spec.shape, reader, meta['t_ref'], meta['target_statistics']),
                                   cache, {'lru_bytes': 8_000_000})
    fit_reader(fitted, factory, make_fit_manifest(fitted, meta), chunk_rows=32)
    with pytest.raises(ValueError, match='subclass|class'):
        export_statics(fitted)
    ref = save_model(fitted, tmp_path / 'loaded.json')
    model = load_model(ref.path, ref.sha256)
    assert type(model).__name__ == 'RidgeMemoryModel'
    ep = generate_episode(PopulationSpec('poc_numeric_v1', ShapeSpec(12, 1), 'unit_test', 991,
                                         (128,), ('piecewise_stationary',), 8, 512), 'unit-ridge-read-0')
    pair = {'snapshot': model.encode(ep.events, mode='terminal'), 'queries': ep.queries,
            'time_unit': ep.events.time_unit}
    statics = export_statics(model)
    result = isolated_read_batch(statics, [pair], {'limits': _limits(), 'timeout_seconds': 30.})[0]
    torch.testing.assert_close(result.prediction, model.read(pair['snapshot'], ep.queries).prediction,
                               equal_nan=True, atol=0., rtol=0.)
    model.writer.history_cache = {'forbidden': 'history'}
    with pytest.raises(ValueError, match='attribute|writer'):
        export_statics(model)
    del model.writer.history_cache
    model.writer.eps *= 10
    with pytest.raises(ValueError, match='writer|static'):
        export_statics(model)


def test_worker_journal_keeps_simultaneous_parent_child_rss_samples(tmp_path):
    from famjet_poc.wire import export_statics, isolated_read_batch

    method, pair = _pair()
    journal = tmp_path / 'attempt.json'
    isolated_read_batch(export_statics(method), [pair],
                        {'limits': _limits(), 'timeout_seconds': 30.,
                         'journal_path': str(journal), 'sample_rss': True})
    record = json.loads(journal.read_bytes())
    assert record['status'] == 'ok'
    assert record['rss_sampling']['parent_pid'] == os.getpid()
    assert record['rss_sampling']['sample_count'] > 0
    assert record['rss_sampling']['sum_lifetime_peaks_bytes'] is not None
    assert record['rss_sampling']['rss_kind'] == 'conservative_sum_of_per_process_lifetime_peaks_at_live_handshake'


def test_wire_rejects_huge_control_capacity_before_constructor_allocation():
    from famjet.provenance import canonical_hash
    from famjet_poc.wire import decode_request, encode_request, export_statics

    method, pair = _pair()
    body = json.loads(encode_request(export_statics(method), [pair],
                      [{'history_id': pair['queries'].history_ids[0],
                        'query_ids': pair['queries'].query_ids[0].tolist()}], _limits())[8:])
    body['statics']['constructor']['capacity'] = 2**60
    body['statics']['constructor']['policy'] = 'recent'
    body['statics_hash'] = canonical_hash(body['statics'])
    body['request_id'] = canonical_hash({'statics': body['statics'], 'pairs': body['pairs'],
                                         'expected_ids': body['expected_ids']})
    with pytest.raises(ValueError, match='capacity|allocation'):
        decode_request(json.dumps(body).encode(), _limits())
