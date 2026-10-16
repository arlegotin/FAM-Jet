"""Versioned numeric snapshots, content identity and atomic single-writer saves.

The portable format packs each tensor independently on CPU, detaches autograd,
retains exact dtype/bit patterns, and deliberately does not restore aliases,
strides or device placement. It never unpickles Python objects. This is a stream
snapshot, not an optimizer/model/RNG training checkpoint.
"""
import base64
import binascii
import json
import math
import os
from pathlib import Path
import tempfile

import numpy as np
import torch

from famjet.provenance import canonical_hash, canonical_json
from famjet.types import SCHEMA_VERSION, Snapshot

FORMAT_VERSION = 1
_DTYPES = {name: np.dtype(name) for name in
           ('bool', 'uint8', 'int8', 'int16', 'int32', 'int64', 'uint16', 'uint32', 'uint64', 'float16', 'float32', 'float64')}


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _digest(value):
    _require(type(value) is str and len(value) == 64 and all(c in '0123456789abcdef' for c in value),
             'parameter hash must be a SHA-256 hex digest')


def retained_tensor_chain(tensor):
    """Audit a tensor and strongly retained view bases, deduplicated by identity.

    Storage aliasing alone does not describe retention: a view's base can carry
    a separate Python cache or gradient even when the view has neither.
    """
    seen = set()
    while tensor is not None and id(tensor) not in seen:
        seen.add(id(tensor))
        _require(type(tensor) in (torch.Tensor, torch.nn.Parameter) and tensor.layout == torch.strided,
                 'only dense numeric tensors are supported')
        _require(not vars(tensor), 'unregistered/hidden tensor attribute (including retained base)')
        yield tensor
        tensor = tensor._base


def tensor_record(tensor):
    """Lossless, owned CPU bytes; NaN is a bit pattern, never a JSON number."""
    # Audit before detach/clone loses the references we need to inspect.
    for _ in retained_tensor_chain(tensor):
        pass
    name = str(tensor.dtype).removeprefix('torch.')
    _require(name in _DTYPES, 'unsupported tensor dtype')
    # numpy() marks the exposed Torch storage non-resizable. Always expose a
    # private allocation so hashing/export cannot change caller ownership.
    array = tensor.detach().cpu().contiguous().clone().numpy().astype(_DTYPES[name].newbyteorder('<'), copy=False)
    return dict(dtype=name, shape=list(tensor.shape), data=base64.b64encode(array.tobytes()).decode('ascii'))


def tensor_from_record(record):
    _require(type(record) is dict and set(record) == {'dtype', 'shape', 'data'}, 'invalid tensor schema')
    name, shape, data = record['dtype'], record['shape'], record['data']
    _require(type(name) is str and name in _DTYPES and type(shape) is list and len(shape) <= 32
             and all(type(n) is int and n >= 0 for n in shape) and type(data) is str, 'invalid tensor layout')
    try:
        raw = base64.b64decode(data, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise ValueError('invalid tensor bytes') from exc
    dtype = _DTYPES[name].newbyteorder('<')
    _require(math.prod(shape)*dtype.itemsize == len(raw), 'tensor byte count mismatch')
    # Copy makes storage writable and independent of both JSON and other fields.
    array = np.frombuffer(raw, dtype=dtype).astype(_DTYPES[name], copy=True).reshape(shape)
    return torch.from_numpy(array).clone()


def validate_snapshot(snapshot):
    """Generic schema/metadata validation; method-specific layout validates later."""
    _require(type(snapshot) is Snapshot and type(snapshot.schema_version) is int
             and snapshot.schema_version == SCHEMA_VERSION, 'snapshot schema mismatch')
    _require(set(vars(snapshot)) == {'payload', 'last_time', 'valid', 'parameter_hash', 'event_offset', 'schema_version'},
             'unregistered/hidden snapshot attribute')
    _digest(snapshot.parameter_hash)
    _require(type(snapshot.payload) is dict and all(type(k) is str and k for k in snapshot.payload),
             'invalid snapshot payload schema')
    _require(type(snapshot.last_time) is torch.Tensor and snapshot.last_time.ndim == 1
             and snapshot.last_time.numel() > 0 and snapshot.last_time.device.type == 'cpu'
             and snapshot.last_time.dtype in (torch.int64, torch.float64)
             and bool(torch.isfinite(snapshot.last_time).all()), 'invalid snapshot last_time')
    b = snapshot.last_time.numel()
    for name, dtype in (('valid', torch.bool), ('event_offset', torch.int64)):
        tensor = getattr(snapshot, name)
        _require(type(tensor) is torch.Tensor and tensor.shape == (b,) and tensor.dtype == dtype
                 and tensor.device.type == 'cpu', f'invalid snapshot {name}')
    _require(bool((snapshot.event_offset >= 0).all()), 'invalid snapshot event_offset')
    for name, tensor in snapshot.payload.items():
        _require(type(tensor) is torch.Tensor and tensor.layout == torch.strided, f'invalid snapshot tensor {name}')
        _require(str(tensor.dtype).removeprefix('torch.') in _DTYPES, f'unsupported snapshot dtype {name}')
        # Numerical payload may preserve a failed kernel's inf/NaN evidence.
        # Method validators decide admissibility; metadata times stay finite.


def snapshot_record(snapshot):
    validate_snapshot(snapshot)
    return dict(schema_version=snapshot.schema_version, parameter_hash=snapshot.parameter_hash,
                payload={k: tensor_record(v) for k, v in snapshot.payload.items()},
                **{k: tensor_record(getattr(snapshot, k)) for k in ('last_time', 'valid', 'event_offset')})


def snapshot_from_record(record, expected_parameter_hash):
    _require(type(record) is dict and set(record) == {'schema_version', 'parameter_hash', 'payload',
             'last_time', 'valid', 'event_offset'}, 'invalid snapshot schema')
    _require(record['schema_version'] == SCHEMA_VERSION, 'snapshot schema mismatch')
    _digest(expected_parameter_hash)
    _require(record['parameter_hash'] == expected_parameter_hash, 'snapshot parameter hash mismatch')
    _require(type(record['payload']) is dict, 'invalid snapshot payload schema')
    snapshot = Snapshot({k: tensor_from_record(v) for k, v in record['payload'].items()},
                        *(tensor_from_record(record[k]) for k in ('last_time', 'valid')),
                        record['parameter_hash'], tensor_from_record(record['event_offset']), record['schema_version'])
    validate_snapshot(snapshot)
    return snapshot


def snapshot_hash(snapshot):
    """Content identity includes numeric payload, source identities and offsets."""
    return canonical_hash(snapshot_record(snapshot))


def inference_snapshot(snapshot):
    """Explicit inference boundary; original training graph and APIs are untouched."""
    return snapshot_from_record(snapshot_record(snapshot), snapshot.parameter_hash)


def state_bytes(snapshot):
    body = dict(format='famjet.snapshot', format_version=FORMAT_VERSION, **snapshot_record(snapshot))
    return canonical_json(dict(body=body, checksum=canonical_hash(body)))


def _decode(raw, expected_parameter_hash=None):
    try:
        record = json.loads(raw)
        _require(type(record) is dict and set(record) == {'body', 'checksum'}, 'invalid state file schema')
        body = record['body']
        _require(canonical_hash(body) == record['checksum'], 'snapshot checksum mismatch')
        _require(type(body) is dict and body.get('format') == 'famjet.snapshot'
                 and body.get('format_version') == FORMAT_VERSION, 'state file schema/version mismatch')
        body = dict(body); del body['format']; del body['format_version']
        return snapshot_from_record(body, expected_parameter_hash if expected_parameter_hash is not None else body.get('parameter_hash'))
    except (KeyError, TypeError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ValueError('invalid state file schema') from exc


def _atomic_replace(path, raw):
    name = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=path.name+'.', suffix='.tmp', delete=False) as stream:
            name = stream.name
            stream.write(raw); stream.flush(); os.fsync(stream.fileno())
        os.replace(name, path)
        fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    finally:
        if name is not None and os.path.exists(name):
            os.unlink(name)


def save_state(path: Path, snapshot: Snapshot) -> None:
    """Atomically replace, preserving validated old bytes as ``name.previous``.

    Single writer required. A corrupt primary refuses overwrite; recovery is an
    explicit load of .previous. fsync+rename provides local-filesystem crash
    durability, not cross-filesystem/distributed transactional guarantees.
    """
    path = Path(path)
    raw = state_bytes(snapshot)  # validate everything before touching disk
    if path.exists():
        previous = path.read_bytes()
        _decode(previous)
        _atomic_replace(path.with_suffix(path.suffix+'.previous'), previous)
    _atomic_replace(path, raw)


def load_state(path: Path, expected_parameter_hash: str) -> Snapshot:
    return _decode(Path(path).read_bytes(), expected_parameter_hash)
