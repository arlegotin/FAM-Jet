"""Controlled inference worker, not an OS sandbox against malicious administrators.

Only explicitly registered built-in constructors run here. New TaskModels must
extend this registry with a reconstructible static schema/weights and a writer
hash; no callable, arbitrary pickle, history object, loader or path is accepted.
The child starts a fresh interpreter, receives numeric input over pipes, checks
source identity and denies ordinary disk/network/process access during reading.
Startup/import and result serialization are outside the timed read boundary.
"""
from dataclasses import fields
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import tempfile

import torch

from famjet.data.schema import validate_queries
from famjet.memory._fixed_writer import _digest_tensor
from famjet.memory.exact_store import PackedHistoryMemory
from famjet.memory.reservoir import ReservoirMemory, HybridMemory
from famjet.memory.buckets import TemporalBucketsMemory
from famjet.memory.jet import JetMemory
from famjet.memory.expbank import ExpBankMemory, BoundedRates
from famjet.provenance import canonical_hash, canonical_json
from famjet.types import QueryBatch, ReadResult, FeatureBatch
from famjet.eval.state_io import (snapshot_record, snapshot_from_record, snapshot_hash,
                                  tensor_record, tensor_from_record)

REGISTRY_VERSION = 1
_REGISTRY = {'packed': PackedHistoryMemory, 'reservoir': ReservoirMemory, 'hybrid': HybridMemory,
             'buckets': TemporalBucketsMemory, 'jet': JetMemory, 'bank': ExpBankMemory}
_ROOT = Path(__file__).resolve().parents[2]


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def source_identity():
    """Identity of trusted package code; data files are never read for this hash."""
    return canonical_hash({str(p.relative_to(_ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                           for p in sorted((_ROOT/'famjet').rglob('*.py'))})


def _tree(value):
    """Compare every instance field against reconstruction, including hooks/caches."""
    if isinstance(value, torch.Tensor):
        return tensor_record(value)
    if isinstance(value, torch.nn.Module):
        return {'class': type(value).__qualname__, 'fields':
                {k: _tree(v) for k, v in vars(value).items() if k != 'training'}}
    if isinstance(value, dict):
        return {k: _tree(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_tree(v) for v in value]
    if isinstance(value, set) and not value:
        return []
    if value is None or type(value) in (str, int, float, bool):
        return value
    # Summary factories are fixed class identities, never executable wire data.
    if value is PackedHistoryMemory:
        return value.__name__
    from famjet.memory.reservoir import Reservoir, HybridStore
    from famjet.memory.buckets import TemporalBuckets
    if value is Reservoir or value is HybridStore or value is TemporalBuckets:
        return value.__name__
    raise ValueError('unregistered/hidden method attribute')


def _reconstruct(spec):
    _require(type(spec) is dict and set(spec) == {'registry_version', 'kind', 'schema', 'weights'},
             'invalid method schema')
    _require(spec['registry_version'] == REGISTRY_VERSION and spec['kind'] in _REGISTRY,
             'unregistered method/schema version')
    kind, schema = spec['kind'], spec['schema']
    _require(type(schema) is dict and type(spec['weights']) is dict, 'invalid method schema')
    if kind not in ('jet', 'bank'):
        _require(not spec['weights'], 'unexpected packed weights')
        return _REGISTRY[kind](**schema)
    schema = dict(schema)
    rate_spec = schema.pop('rate_source')
    if rate_spec is None:
        _require(set(spec['weights']) == {'rates'}, 'invalid rate weights')
        rates = tensor_from_record(spec['weights']['rates'])
    else:
        _require(kind == 'bank' and set(spec['weights']) == {'logits'}, 'invalid learned rate schema')
        logits = tensor_from_record(spec['weights']['logits'])
        rates = BoundedRates(**rate_spec).to(dtype=logits.dtype)
        _require(rates.logits.shape == logits.shape, 'rate weight shape mismatch')
        with torch.no_grad():
            rates.logits.copy_(logits)
    return _REGISTRY[kind](rates, **schema)


def export_method(method):
    """Strict static inventory. Subclasses and unregistered instance state reject."""
    kinds = {cls: kind for kind, cls in _REGISTRY.items()}
    _require(type(method) in kinds, 'method type is not registered for isolated inference')
    kind = kinds[type(method)]; weights = {}
    if kind == 'packed':
        schema = {k: getattr(method, k) for k in ('capacity', 'value_dim', 'policy', 'key_dim', 'value_dtype')}
    elif kind in ('reservoir', 'hybrid', 'buckets'):
        schema = dict(method._store_kwargs, key_dim=method.key_dim)
    else:
        schema = {k: getattr(method, k) for k in ('key_dim', 'value_dim', 'eps', 'support_floor', 't_ref', 'chunk_size')}
        schema['rate_source'] = None
        if kind == 'bank':
            schema['no_decay'] = method.no_decay
        if kind == 'bank' and hasattr(method, 'rate_source'):
            source = method.rate_source
            _require(type(source) is BoundedRates, 'unregistered rate source')
            schema['rate_source'] = dict(count=source.logits.numel(), log_min=source.log_min, log_max=source.log_max)
            weights['logits'] = tensor_record(source.logits)
        else:
            weights['rates'] = tensor_record(method.rates)
    spec = dict(registry_version=REGISTRY_VERSION, kind=kind, schema=schema, weights=weights)
    reconstructed = _reconstruct(spec)
    # Tensor bytes are compared after CPU transfer; device/graph identity is not
    # serialized. Inference is CPU FP64/declared dtype, not an MPS timing claim.
    original = _tree(method) if isinstance(method, torch.nn.Module) else _tree(vars(method))
    restored = _tree(reconstructed) if isinstance(reconstructed, torch.nn.Module) else _tree(vars(reconstructed))
    _require(original == restored, 'unregistered/hidden method state differs from static constructor schema')
    return spec


def model_identity(method):
    """Full inference configuration/weights hash; separate from writer state hash."""
    return canonical_hash(export_method(method))


def _query_record(query):
    _require(type(query) is QueryBatch, 'query schema mismatch')
    return {f.name: tensor_record(getattr(query, f.name)) if isinstance(getattr(query, f.name), torch.Tensor)
            else getattr(query, f.name) for f in fields(QueryBatch)}


def _query_from_record(record):
    _require(type(record) is dict and set(record) == {f.name for f in fields(QueryBatch)}, 'query schema mismatch')
    record = dict(record)
    for k in ('query_ids', 'T', 'key_ids', 'key_features', 'age_start', 'age_end', 'present', 'lengths'):
        record[k] = tensor_from_record(record[k])
    record['history_ids'] = tuple(record['history_ids'])
    record['tasks'] = tuple(tuple(row) for row in record['tasks'])
    return QueryBatch(**record)


def _check_input(method, state, query):
    _require(state.parameter_hash == method._parameter_hash(), 'snapshot parameter hash mismatch')
    method.persistent_nbytes(state)  # method layout/counters and source hashes
    validate_queries(query, state)
    if bool(state.payload['time_unit_hash'].any()):
        identity = torch.stack([_digest_tensor(h) for h in query.history_ids])
        _require(torch.equal(identity, state.payload['history_hash']), 'query history identity mismatch')


def _result_record(result):
    _require(type(result) in (ReadResult, FeatureBatch), 'invalid isolated result schema')
    return dict(kind=type(result).__name__, fields={f.name:
                ({k: tensor_record(v) for k, v in result.diagnostics.items()} if f.name == 'diagnostics'
                 else tensor_record(getattr(result, f.name)) if isinstance(getattr(result, f.name), torch.Tensor)
                 else getattr(result, f.name)) for f in fields(result)})


def _result_from_record(record):
    cls = {'ReadResult': ReadResult, 'FeatureBatch': FeatureBatch}[record['kind']]
    values = dict(record['fields'])
    _require(set(values) == {f.name for f in fields(cls)}, 'invalid result schema')
    for k, v in values.items():
        if k == 'diagnostics': values[k] = {name: tensor_from_record(t) for name, t in v.items()}
        elif type(v) is dict: values[k] = tensor_from_record(v)
    return cls(**values)


def result_json(result):
    """Finite JSON reporting view; internal NaNs remain explicit in ReadResult."""
    def numeric(value):
        if isinstance(value, torch.Tensor): return numeric(value.detach().cpu().tolist())
        if isinstance(value, dict): return {k: numeric(v) for k, v in value.items()}
        if isinstance(value, list): return [numeric(v) for v in value]
        if isinstance(value, float) and not math.isfinite(value): return None
        return value
    return {f.name: numeric(getattr(result, f.name)) for f in fields(result)}


def _install_io_guard():
    """Accidental-leak guard after trusted imports, not a native-code sandbox."""
    def guard(event, args):
        if event in {'open', 'os.listdir', 'os.scandir', 'os.system', 'os.exec', 'os.fork', 'os.posix_spawn',
                     'ctypes.dlopen'} or event.startswith(('socket.', 'subprocess.')):
            raise PermissionError('isolated read: disk/network/process access forbidden')
    sys.addaudithook(guard)


def _worker(request):
    _require(request['source_hash'] == source_identity(), 'worker source identity mismatch')
    _require(request['model_hash'] == canonical_hash(request['method']), 'worker model identity mismatch')
    method = _reconstruct(request['method'])
    if isinstance(method, torch.nn.Module): method.eval()
    state = snapshot_from_record(request['state'], method._parameter_hash())
    query = _query_from_record(request['queries'])
    _check_input(method, state, query)
    state_before, query_before = snapshot_hash(state), canonical_hash(_query_record(query))
    method_before = model_identity(method)
    _install_io_guard()
    with torch.inference_mode():
        result = getattr(method, request['operation'])(state, query)
    _require(snapshot_hash(state) == state_before and canonical_hash(_query_record(query)) == query_before,
             'isolated reader mutated read-only inputs')
    _require(model_identity(method) == method_before, 'isolated reader retained hidden history/cache')
    return _result_record(result)


def _isolated(method, state, queries, operation, timeout):
    _require(type(timeout) in (float, int) and math.isfinite(timeout) and timeout > 0, 'invalid worker timeout')
    spec = export_method(method)
    _require(operation in ('read', 'features') and callable(getattr(method, operation, None)),
             'kernel has no task read; TaskModel supplies the trained reader')
    _check_input(method, state, queries)
    request = dict(method=spec, state=snapshot_record(state), queries=_query_record(queries), operation=operation,
                   model_hash=canonical_hash(spec), source_hash=source_identity())
    # -I ignores PYTHONPATH/user-site/environment injection; only trusted package
    # source is inserted. close_fds removes inherited raw handles. Cwd is empty.
    bootstrap = 'import sys; sys.path.insert(0, '+repr(str(_ROOT))+'); from famjet.eval.isolation import _main; _main()'
    env = {k: v for k, v in os.environ.items() if k in ('SYSTEMROOT', 'WINDIR')}
    env.update(PYTORCH_ENABLE_MPS_FALLBACK='0', PYTORCH_MPS_FAST_MATH='0', OMP_NUM_THREADS='1')
    with tempfile.TemporaryDirectory(prefix='famjet-read-') as directory:
        try:
            completed = subprocess.run([sys.executable, '-I', '-c', bootstrap], input=canonical_json(request),
                                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=directory, env=env,
                                       close_fds=True, timeout=timeout)
        except subprocess.TimeoutExpired as exc:
            # subprocess.run kills and waits for the child before raising.
            raise TimeoutError('isolated read worker timed out and was reaped') from exc
    _require(completed.returncode == 0, 'isolated worker failed: '+completed.stderr.decode(errors='replace')[-2000:])
    response = json.loads(completed.stdout)
    _require(response.get('ok') is True, 'isolated read failed: '+response.get('error', 'invalid response'))
    return _result_from_record(response['result'])


def isolated_read(method, state, queries, *, timeout=60.) -> ReadResult:
    """Read a complete B/Q query batch in one clean CPU inference worker."""
    return _isolated(method, state, queries, 'read', timeout)


def isolated_features(method, state, queries, *, timeout=60.) -> FeatureBatch:
    """Kernel boundary until a trained TaskModel owns task predictions (Task 11)."""
    return _isolated(method, state, queries, 'features', timeout)


def _main():
    try:
        request = json.loads(sys.stdin.buffer.read())
        response = dict(ok=True, result=_worker(request))
    except Exception as exc:
        response = dict(ok=False, error=f'{type(exc).__name__}: {exc}')
    sys.stdout.buffer.write(canonical_json(response))


if __name__ == '__main__':
    _main()
