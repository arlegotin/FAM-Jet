"""Untimed host-side input checks. Never call from a timed recurrence."""
import math

import torch
from torch import Tensor

from famjet.types import EventBatch, EventValidation, QueryBatch, Snapshot


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _tensor(value, name, *, shape=None, dtypes=None, cpu=False, finite=False):
    _require(isinstance(value, Tensor), f'{name} must be a tensor')
    if shape is not None:
        _require(tuple(value.shape) == tuple(shape), f'{name} has invalid shape')
    if dtypes is not None:
        _require(value.dtype in dtypes, f'{name} has invalid dtype')
    if cpu:
        _require(value.device.type == 'cpu', f'{name} must stay on CPU')
    if finite:
        _require(bool(torch.isfinite(value).all()), f'{name} must be finite even under masks')


def _version(value):
    _require(type(value.schema_version) is int and value.schema_version == 1,
             'unsupported schema_version')


def _mask_lengths(present, lengths, b, n):
    _tensor(present, 'present', shape=(b, n), dtypes=(torch.bool,))
    _tensor(lengths, 'lengths', shape=(b,), dtypes=(torch.int64,), cpu=True)
    _require(bool(((lengths >= 0) & (lengths <= n)).all()), 'lengths out of bounds')
    expected = torch.arange(n, device=present.device)[None, :] < lengths.to(present.device)[:, None]
    _require(torch.equal(present, expected), 'present must be a prefix mask matching lengths')


def _history_ids(ids, b):
    _require(isinstance(ids, tuple) and len(ids) == b and all(isinstance(v, str) and v for v in ids),
             'history_ids must contain one nonempty string per history')
    _require(len(set(ids)) == b, 'history_ids must be unique')


def _key_ids(ids, shape):
    _tensor(ids, 'key_ids', shape=shape, dtypes=(torch.int64, torch.uint64), cpu=True)
    # Convert directly to Python ints; never cast uint64 through signed/float.
    _require(all(v >= 0 for row in ids.tolist() for v in row), 'key_ids must be nonnegative')


def _ordinal_ids(ids, lengths, shape, name):
    _tensor(ids, name, shape=shape, dtypes=(torch.int64,), cpu=True)
    for row, length in zip(ids.tolist(), lengths.tolist()):
        active = row[:length]
        _require(all(v >= 0 for v in active) and len(set(active)) == length,
                 f'{name} must be unique nonnegative ordinals within a history')


def _times(value, name, shape):
    _tensor(value, name, shape=shape, dtypes=(torch.float64, torch.int64), cpu=True, finite=True)


def validate_rates(rates: Tensor) -> None:
    _tensor(rates, 'rates', finite=True)
    _require(rates.is_floating_point() and rates.numel() > 0 and bool((rates > 0).all()),
             'rates must be nonempty finite positive floating values')


def validate_events(events: EventBatch) -> None:
    """Populate a separate validation record after all checks pass.

    First-event gap is zero (initial state has no prior event); a streaming
    adapter checks/subtracts its previous snapshot time before processing that
    first event. Missing observations advance time; padding never does.
    Revalidate after mutating batch tensors; records are not cache guarantees.
    """
    events.validation = None
    _version(events)
    _tensor(events.values, 'values', finite=True)
    _require(events.values.ndim == 3 and events.values.is_floating_point(), 'values must be floating [B,N,V]')
    b, n, v = events.values.shape
    _require(b > 0 and v > 0, 'batch/value dimensions must be positive')
    _history_ids(events.history_ids, b)
    _mask_lengths(events.present, events.lengths, b, n)
    _times(events.timestamps, 'timestamps', (b, n))
    _ordinal_ids(events.event_ids, events.lengths, (b, n), 'event_ids')
    _key_ids(events.key_ids, (b, n))
    _tensor(events.key_features, 'key_features', finite=True)
    _require(events.key_features.ndim == 3 and tuple(events.key_features.shape[:2]) == (b, n)
             and events.key_features.shape[2] > 0 and events.key_features.is_floating_point(),
             'key_features must be floating [B,N,K]')
    _require(bool((events.key_features >= 0).all()), 'key features must be nonnegative')
    _tensor(events.observed, 'observed', shape=(b, n, v), dtypes=(torch.bool,))
    _require(all(t.device == events.values.device for t in (events.key_features, events.present, events.observed)),
             'core tensors and masks must share a device')
    _require(not bool((events.observed & ~events.present[:, :, None]).any()), 'padding cannot be observed')
    _require(events.normalization in {'shared', 'independent'}, 'unknown normalization')
    if events.normalization == 'shared':
        _require(bool((events.observed == events.observed[:, :, :1]).all()),
                 'partial value observation requires independent normalization')
    _require(isinstance(events.time_unit, str) and bool(events.time_unit.strip()), 'time_unit must be explicit')
    _require(isinstance(events.auxiliary, dict), 'auxiliary must be a tensor mapping')
    for name, tensor in events.auxiliary.items():
        _require(isinstance(name, str), 'auxiliary names must be strings')
        _tensor(tensor, f'auxiliary.{name}', finite=True)
        _require(tensor.ndim >= 2 and tuple(tensor.shape[:2]) == (b, n), 'auxiliary must start with [B,N]')
        if name in {'gate', 'gates'}:
            _require(bool((tensor >= 0).all()), 'gates must be nonnegative')
    gaps = torch.zeros((b, n), dtype=torch.float64, device='cpu')
    for i, (row, ids, length) in enumerate(zip(events.timestamps.tolist(), events.event_ids.tolist(), events.lengths.tolist())):
        for j in range(1, length):
            gap = row[j] - row[j-1]  # Python int subtraction cannot wrap
            _require(gap >= 0, 'negative timestamp gap: out-of-order live events')
            if events.timestamps.dtype == torch.int64:
                _require(gap <= 2**63-1, 'integer timestamp subtraction overflow')
            _require(math.isfinite(gap), 'timestamp gap must be finite')
            if gap == 0:
                _require(ids[j] > ids[j-1], 'simultaneous events require stable event_id order')
            gaps[i, j] = gap
    events.validation = EventValidation(gaps=gaps, write_mask=events.present & events.observed.any(dim=-1))


def validate_queries(queries: QueryBatch, state: Snapshot | None = None) -> None:
    """Validate public fields; optionally reject reads before saved stream time.

    Empty-state queries remain legal inputs but unsupported; adapters preserve
    the validity mask when producing reads. Task-specific target semantics are
    enforced by the corresponding target builder.
    """
    _version(queries)
    _tensor(queries.T, 'T')
    _require(queries.T.ndim == 2, 'T must be [B,Q]')
    b, q = queries.T.shape
    _history_ids(queries.history_ids, b)
    _times(queries.T, 'T', (b, q))
    _mask_lengths(queries.present, queries.lengths, b, q)
    _ordinal_ids(queries.query_ids, queries.lengths, (b, q), 'query_ids')
    _key_ids(queries.key_ids, (b, q))
    _tensor(queries.key_features, 'key_features', finite=True)
    _require(queries.key_features.ndim == 3 and tuple(queries.key_features.shape[:2]) == (b, q)
             and queries.key_features.shape[2] > 0 and queries.key_features.is_floating_point(),
             'query key_features must be floating [B,Q,K]')
    _require(bool((queries.key_features >= 0).all()), 'query key features must be nonnegative')
    _require(isinstance(queries.tasks, tuple) and len(queries.tasks) == b
             and all(isinstance(row, tuple) and len(row) == q and all(isinstance(t, str) and t for t in row)
                     for row in queries.tasks), 'tasks must contain [B,Q] nonempty task names')
    for name in ('age_start', 'age_end'):
        _tensor(getattr(queries, name), name, shape=(b, q), dtypes=(torch.float64,), cpu=True, finite=True)
    _require(bool(((queries.age_start >= 0) & (queries.age_end >= queries.age_start)).all()),
             'age endpoints must be nonnegative and ordered')
    if state is not None:
        _version(state)
        _times(state.last_time, 'last_time', (b,))
        _tensor(state.valid, 'valid', shape=(b,), dtypes=(torch.bool,))
        _tensor(state.event_offset, 'event_offset', shape=(b,), dtypes=(torch.int64,), cpu=True)
        _require(bool((state.event_offset >= 0).all()), 'event_offset must be nonnegative')
        _require(isinstance(state.parameter_hash, str) and len(state.parameter_hash) == 64
                 and all(c in '0123456789abcdef' for c in state.parameter_hash), 'invalid parameter hash')
        for row, length, last, valid in zip(queries.T.tolist(), queries.lengths.tolist(), state.last_time.tolist(), state.valid.cpu().tolist()):
            if valid:
                _require(all(t >= last for t in row[:length]), 'query time is before snapshot.last_time')
