"""E3 accidental-leak read boundary; run with ``python -m famjet_poc.worker``."""
import os
import struct
import sys
import hashlib
import resource

os.environ['OMP_NUM_THREADS'] = '1'
os.environ['OPENBLAS_NUM_THREADS'] = '1'
os.environ['MKL_NUM_THREADS'] = '1'
os.environ['VECLIB_MAXIMUM_THREADS'] = '1'
os.environ['NUMEXPR_NUM_THREADS'] = '1'

import torch
import numpy as np

from famjet.data.schema import validate_queries
from famjet.eval.state_io import snapshot_from_record, snapshot_hash, tensor_record
from famjet.memory._fixed_writer import _digest_tensor
from famjet.provenance import canonical_hash, canonical_json
from .models import RidgeMemoryModel
from .wire import _query_from_record, _query_record, _reconstruct, decode_request, export_statics

_DEFAULT_LIMITS = {'max_frame_bytes': 64_000_000, 'max_array_bytes': 32_000_000, 'max_histories': 64}


def _prewarm_static_dependencies():
    """Resolve NumPy's lazy set-operation import before the read I/O guard."""
    if len(np.unique(np.array([0, 1, 1], dtype=np.uint64))) != 2:
        raise RuntimeError('NumPy static set-operation initialization failed')


def _install_guard():
    def guard(event, args):
        if event in {'open', 'os.listdir', 'os.scandir', 'os.system', 'os.exec', 'os.fork', 'os.posix_spawn',
                     'ctypes.dlopen'} or event.startswith(('socket.', 'subprocess.')):
            raise PermissionError('isolated read forbids disk/network/process access')
    sys.addaudithook(guard)


def _result_record(result):
    return {'schema_version': 1,
            'prediction': tensor_record(result.prediction) if result.prediction is not None else None,
            'logits': tensor_record(result.logits) if result.logits is not None else None,
            'support': tensor_record(result.support), 'failure': tensor_record(result.failure),
            'diagnostics': {k: tensor_record(v) for k, v in result.diagnostics.items()}}


def _method_identity(model):
    if type(model) is not RidgeMemoryModel:
        return canonical_hash(export_statics(model))
    allowed = {'shape', 'spec', 't_ref', '_target_statistics', 'writer', '_coefficients',
               'feature_mean', 'feature_scale', 'query_mean', 'query_scale', 'fit_artifact'}
    if set(vars(model)) != allowed or model.fit_artifact is not None:
        raise ValueError('reader has hidden attribute or fit corpus')
    writer_fields = {k: v for k, v in vars(model.writer).items() if type(v) in (int, float, str, bool)}
    arrays = {name: getattr(model, name) for name in
              ('_coefficients', 'feature_mean', 'feature_scale', 'query_mean', 'query_scale')}
    return canonical_hash({'shape': model.shape.to_json(), 'reader': model.spec.to_json(),
                           't_ref': model.t_ref, 'target_statistics': model.target_statistics,
                           'writer_hash': model.writer_hash, 'writer_fields': writer_fields,
                           'writer_keys': sorted(vars(model.writer)),
                           'writer_module_keys': sorted(model.writer._modules),
                           'writer_buffers': {name: tensor_record(value) for name, value in model.writer.named_buffers()},
                           'arrays': {name: {'shape': list(value.shape), 'dtype': str(value.dtype),
                                             'sha256': hashlib.sha256(value.tobytes()).hexdigest()}
                                      for name, value in arrays.items()}})


def _read(body):
    model = _reconstruct(body['statics'])
    accepted = []
    for pair, expected in zip(body['pairs'], body['expected_ids']):
        if type(expected) is not dict or set(expected) != {'history_id', 'query_ids'}:
            raise ValueError('expected ID schema mismatch')
        state = snapshot_from_record(pair['snapshot'], body['writer_hash'])
        query = _query_from_record(pair['queries'])
        if (query.history_ids != (expected['history_id'],) or query.query_ids[0].tolist() != expected['query_ids'] or
                snapshot_hash(state) != pair['snapshot_hash'] or
                not (state.payload['history_hash'][0] == _digest_tensor(expected['history_id'])).all() or
                not (state.payload['time_unit_hash'] == _digest_tensor(pair['time_unit'])).all()):
            raise ValueError('worker history/query/state identity mismatch')
        validate_queries(query, state)
        if query.present.any() and bool((query.T[query.present] < state.last_time[0]).any()):
            raise ValueError('worker requires deferred queries')
        accepted.append((state, query))
    inputs_before = [(snapshot_hash(s), canonical_hash(_query_record(q))) for s, q in accepted]
    method_before = _method_identity(model)
    _install_guard()
    with torch.inference_mode():
        results = [_result_record(model.read(s, q)) for s, q in accepted]
    if inputs_before != [(snapshot_hash(s), canonical_hash(_query_record(q))) for s, q in accepted] or method_before != _method_identity(model):
        raise ValueError('worker read mutated input or method statics/attributes')
    return results


def worker_main():
    try:
        # This uses only a fixed public dummy: no request histories or queries.
        _prewarm_static_dependencies()
        prefix = sys.stdin.buffer.read(8)
        if len(prefix) != 8:
            raise ValueError('missing request frame')
        size = struct.unpack('>Q', prefix)[0]
        if size > _DEFAULT_LIMITS['max_frame_bytes']:
            raise ValueError('request frame too large')
        raw = sys.stdin.buffer.read(size)
        if len(raw) != size or sys.stdin.buffer.read(1) != b'\x04':
            raise ValueError('request frame length mismatch')
        body = decode_request(raw, _DEFAULT_LIMITS)
        results = _read(body)
        error = None
        request_id = body['request_id']
    except Exception as exc:
        results = None
        error = f'{type(exc).__name__}: {exc}'
        request_id = locals().get('body', {}).get('request_id', '0' * 64)
    observed_rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    child_rss = int(observed_rss if os.uname().sysname == 'Darwin' else observed_rss * 1024)
    response = {'schema_version': 1, 'request_id': request_id, 'results': results, 'error': error,
                'child_rss_bytes': child_rss,
                'response_id': canonical_hash({'request_id': request_id, 'results': results,
                                               'error': error, 'child_rss_bytes': child_rss})}
    raw = canonical_json(response)
    sys.stdout.buffer.write(struct.pack('>Q', len(raw)) + raw)
    sys.stdout.buffer.flush()
    # The parent may sample its own RSS while this worker is still live.
    # Ordinary callers close stdin and yield EOF here; sampled calls ACK.
    sys.stdin.buffer.read(1)
    return 0


if __name__ == '__main__':
    raise SystemExit(worker_main())
