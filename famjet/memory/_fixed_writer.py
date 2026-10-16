"""Shared fixed raw writer, exact host-time preparation and snapshot metadata.

Numerical kernels supply small hooks; this adapter never caches raw history.
"""
import math
import torch
from torch import Tensor, nn
from famjet.data.schema import validate_events, validate_queries, validate_rates
from famjet.eval.oracle import exact_time_difference
from famjet.provenance import canonical_hash
from famjet.types import EventBatch, FeatureBatch, QueryBatch, Snapshot


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _finite(tensor, name):
    _require(isinstance(tensor, Tensor) and tensor.is_floating_point()
             and bool(torch.isfinite(tensor).all()), f'{name} must be finite floating')


def _decay(d):
    # Mask BEFORE multiplication: inf*exp(-inf) would poison H and gradients.
    finite = torch.isfinite(d)
    safe = torch.where(finite, d, torch.zeros_like(d))
    a = torch.where(finite, torch.exp(-safe), torch.zeros_like(safe))
    return a, a*safe


def _core_coefficients(rates, gaps):
    """Tensor-only device arithmetic for already prepared elapsed durations."""
    if gaps.ndim == 1:
        d = gaps[:, None, None]*rates[None]
    else:
        d = gaps[:, None, None, :]*rates[None, :, :, None]
    return _decay(d)


def _coefficients(rates, gaps):
    """Return [B,H,J] or [B,H,J,C] decay and moment weights.

    Ordinary products run on the state device. If a CPU FP64 elapsed duration
    cannot be represented in the state dtype, explicitly form the product on
    CPU FP64 before casting weights. This preserves e.g. 1e-40 * 1e40 on MPS
    without sending an unsupported FP64 tensor to Metal. This is host timestamp
    preparation, not torch's implicit MPS fallback; rate gradients are retained.
    """
    host_product = (gaps.device.type == 'cpu' and gaps.dtype == torch.float64
                    and bool((gaps > torch.finfo(rates.dtype).max).any()))
    # Separate transfer from promotion. Native MPS combined .to(cpu,float64)
    # has silently zeroed tiny FP32 rates on the installed torch version.
    r = rates.cpu().to(dtype=torch.float64) if host_product else rates
    g = gaps.to(device=r.device, dtype=r.dtype)
    a, ad = _core_coefficients(r, g)
    return a.to(rates), ad.to(rates)


def _write(key, value, gate, event_present):
    aug = torch.cat((value, torch.ones_like(value[..., :1])), dim=-1)
    g = gate * event_present[:, None].to(gate.dtype)
    return (g[:, :, None, None]*key[:, :, :, None]*aug[:, :, None, :])[:, :, None]


def _raw(events, rates, rate_validator=validate_rates):
    # Always revalidate: callers can mutate tensors after earlier validation.
    validate_events(events); rate_validator(rates)
    _require(rates.ndim == 2 and rates.shape[0] == 1, 'raw EventBatch adapter requires rates [1,J]')
    _require(events.normalization == 'shared', 'raw adapter requires shared normalization')
    _require(events.key_features.dtype == events.values.dtype == rates.dtype
             and events.values.device == rates.device, 'raw keys/values/rates must share device and dtype')
    _require(not ('gate' in events.auxiliary and 'gates' in events.auxiliary), 'provide gate or gates, not both')
    gate = events.auxiliary.get('gate', events.auxiliary.get('gates'))
    if gate is None:
        gate = torch.ones_like(events.values[..., 0])
    if gate.shape == (*events.values.shape[:2], 1):
        gate = gate[..., 0]
    _require(gate.shape == events.values.shape[:2] and gate.device == rates.device,
             'raw gate must be [B,N] or [B,N,1] on core device')
    gate = gate.to(rates)
    _finite(gate, 'converted raw gate')
    return gate * events.validation.write_mask.to(rates.dtype)


def _digest_tensor(value):
    return torch.tensor(list(bytes.fromhex(canonical_hash(value))), dtype=torch.uint8)


def _pack_times(values):
    if all(type(v) is int for v in values):
        return torch.tensor(values, dtype=torch.int64)
    _require(all(type(v) is not int or int(float(v)) == v for v in values),
             'mixed snapshot times cannot be represented losslessly in one timestamp tensor')
    return torch.tensor(values, dtype=torch.float64)


class FixedWriterMemory(nn.Module):
    """Common H=1 shared-normalization snapshot/stream ownership contract."""
    def init_state(self, batch_size: int, *, device: str, dtype: str) -> Snapshot:
        _require(type(batch_size) is int and batch_size > 0, 'batch_size must be positive integer')
        _require(dtype in {'float32', 'float64'}, 'dtype must be float32 or float64')
        dt = getattr(torch, dtype)
        requested = torch.device(device)
        _require(requested.type == self.rates.device.type
                 and (requested.index is None or requested.index == self.rates.device.index)
                 and dt == self.rates.dtype,
                 'state device/dtype must match module rates')
        z = torch.zeros(batch_size, 1, self.rates.shape[1], self.key_dim, self.value_dim+1, device=device, dtype=dt)
        return Snapshot({**self._zero_payload(z), 'history_hash': torch.zeros(batch_size, 32, dtype=torch.uint8),
                         'time_unit_hash': torch.zeros(32, dtype=torch.uint8),
                         'last_event_id': torch.full((batch_size,), -1, dtype=torch.int64)},
                        torch.zeros(batch_size, dtype=torch.int64), torch.zeros(batch_size, dtype=torch.bool),
                        self._parameter_hash(), torch.zeros(batch_size, dtype=torch.int64))

    def _check_snapshot(self, state):
        _require(state.schema_version == 1 and state.parameter_hash == self._parameter_hash(),
                 'snapshot schema/parameter hash mismatch')
        expected = {*self._state_keys, 'history_hash', 'time_unit_hash', 'last_event_id'}
        _require(set(state.payload) == expected, 'invalid snapshot payload')
        b = state.last_time.numel()
        for name in self._state_keys:
            tensor = state.payload[name]
            _require(tensor.shape == (b, 1, self.rates.shape[1], self.key_dim, self.value_dim+1)
                     and tensor.dtype == self.rates.dtype and tensor.device == self.rates.device,
                     'snapshot state layout mismatch')
        for name, tensor, shape, dtypes in [
            ('last_time', state.last_time, (b,), (torch.int64, torch.float64)),
            ('valid', state.valid, (b,), (torch.bool,)),
            ('event_offset', state.event_offset, (b,), (torch.int64,)),
            ('history_hash', state.payload['history_hash'], (b, 32), (torch.uint8,)),
            ('time_unit_hash', state.payload['time_unit_hash'], (32,), (torch.uint8,)),
            ('last_event_id', state.payload['last_event_id'], (b,), (torch.int64,))]:
            _require(tensor.shape == shape and tensor.dtype in dtypes and tensor.device.type == 'cpu'
                     and bool(torch.isfinite(tensor).all()), f'invalid snapshot {name}')
        _require(bool((state.event_offset >= 0).all()), 'invalid snapshot event_offset')

    def encode(self, events: EventBatch, state: Snapshot | None = None, *, mode='stream') -> Snapshot:
        _require(mode in {'stream', 'terminal'}, 'mode must be stream or terminal')
        gates = self._raw(events)
        _require(events.key_features.shape[-1] == self.key_dim and events.values.shape[-1] == self.value_dim,
                 'raw feature dimensions differ from module')
        b, n, _ = events.values.shape
        if state is None:
            state = self.init_state(b, device=str(self.rates.device), dtype=str(self.rates.dtype).removeprefix('torch.'))
        self._check_snapshot(state)
        _require(state.last_time.shape == (b,), 'snapshot batch size mismatch')
        identity = torch.stack([_digest_tensor(h) for h in events.history_ids])
        unit = _digest_tensor(events.time_unit)
        if bool(state.payload['time_unit_hash'].any()):
            _require(torch.equal(identity, state.payload['history_hash']), 'snapshot history identity mismatch')
            _require(torch.equal(unit, state.payload['time_unit_hash']), 'snapshot time_unit mismatch')
        times, ids = events.timestamps.tolist(), events.event_ids.tolist()
        lengths = events.lengths.tolist()
        last = state.last_time.tolist(); valid = state.valid.tolist(); last_ids = state.payload['last_event_id'].tolist()
        first_gaps = [0.] * b
        for i, length in enumerate(lengths):
            if length and valid[i]:
                gap = exact_time_difference(times[i][0], last[i])
                _require(gap >= 0, 'continued event is before snapshot.last_time')
                _require(gap != 0 or ids[i][0] > last_ids[i], 'continued simultaneous events out of order')
                first_gaps[i] = float(gap)
        core = {name: state.payload[name] for name in self._state_keys}
        for name, tensor in core.items():
            _finite(tensor, f'snapshot.{name}')
        if mode == 'stream':
            # Prepare/validate all host timestamps before entering the tensor
            # recurrence. Padding has zero elapsed time; actual write presence
            # is independent of elapsed time at present unobserved slots.
            gap_rows = [[first_gaps[i] if j == 0 else float(exact_time_difference(times[i][j], times[i][j-1]))
                         if j < lengths[i] else 0. for j in range(n)] for i in range(b)]
            cpu_gaps = torch.tensor(gap_rows, dtype=torch.float64).reshape(b, n)
            exceptional = any(gap > torch.finfo(self.rates.dtype).max for row in gap_rows for gap in row)
            if exceptional:
                # Explicit rare host-time preparation keeps an unrepresentable
                # duration out of the device core and retains rate gradients.
                a, ad = _coefficients(self.rates, cpu_gaps)
            else:
                device_gaps = cpu_gaps.to(self.rates)
            for j in range(n):
                args = (core, events.key_features[:, j, None], events.values[:, j, None], gates[:, j, None])
                if exceptional:
                    core = self._weighted_step(*args, events.validation.write_mask[:, j], a[..., j], ad[..., j])
                else:
                    core = self._step(*args, device_gaps[:, j], self.rates, events.validation.write_mask[:, j])
        else:
            gaps = [float(exact_time_difference(times[i][length-1], last[i])) if length and valid[i] else 0.
                    for i, length in enumerate(lengths)]
            a, ad = _coefficients(self.rates, torch.tensor(gaps, dtype=torch.float64))
            decayed = self._decay_payload(core, a, ad)
            terminal = self._terminal(events)
            core = {name: decayed[name] + terminal[name] for name in self._state_keys}
        for i, length in enumerate(lengths):
            if length:
                last[i] = times[i][length-1]; valid[i] = True; last_ids[i] = ids[i][length-1]
        return Snapshot({**core, 'history_hash': identity, 'time_unit_hash': unit,
                         'last_event_id': torch.tensor(last_ids, dtype=torch.int64)},
                        _pack_times(last), torch.tensor(valid, dtype=torch.bool), self._parameter_hash(),
                        state.event_offset.clone()+events.lengths)

    def advance_copy(self, state: Snapshot, query_time: int | float | Tensor) -> Snapshot:
        self._check_snapshot(state)
        b = state.last_time.numel()
        if isinstance(query_time, Tensor):
            _require(query_time.device.type == 'cpu' and query_time.dtype in (torch.int64, torch.float64)
                     and query_time.shape == (b,), 'query_time must be CPU float64/int64 [B]')
            target = query_time.tolist()
        else:
            _require(type(query_time) in (int, float) and math.isfinite(query_time), 'query_time must be finite')
            target = [query_time] * b
        _require(all(math.isfinite(x) for x in target), 'query_time must be finite')
        payload = self._advance_payload(state, target, [True]*b)
        target = [t if valid else old for t, old, valid in zip(target, state.last_time.tolist(), state.valid.tolist())]
        return Snapshot(payload, _pack_times(target), state.valid.clone(), state.parameter_hash, state.event_offset.clone())

    def _advance_payload(self, state, target, active):
        gaps = []
        for t, old, valid, present in zip(target, state.last_time.tolist(), state.valid.tolist(), active):
            gap = exact_time_difference(t, old) if valid and present else 0
            _require(gap >= 0, 'query time is before snapshot.last_time')
            gaps.append(float(gap))
        a, ad = _coefficients(self.rates, torch.tensor(gaps, dtype=torch.float64))
        payload = {k: v.clone() for k, v in state.payload.items()}
        payload.update(self._decay_payload(state.payload, a, ad))
        return payload

    def features(self, state: Snapshot, queries: QueryBatch) -> FeatureBatch:
        self._check_snapshot(state)
        validate_queries(queries, state)
        identity = torch.stack([_digest_tensor(h) for h in queries.history_ids])
        if bool(state.payload['time_unit_hash'].any()):
            _require(torch.equal(identity, state.payload['history_hash']), 'query history identity mismatch')
        _require(queries.key_features.shape[-1] == self.key_dim, 'query feature dimension mismatch')
        results = []
        # Each query uses an independent temporary. Query order never mutates
        # the snapshot, and Q does not multiply the persistent state capacity.
        for j in range(queries.T.shape[1]):
            # Compute exact gaps directly; writing fractional saved times into
            # an integer query tensor would round even masked timestamps.
            advanced = self._advance_payload(state, queries.T[:, j].tolist(), queries.present[:, j].cpu().tolist())
            f = self._contract(advanced, queries.key_features[:, j:j+1])
            mask = queries.present[:, j:j+1] & state.valid.to(queries.present.device)[:, None]
            results.append(FeatureBatch(f.values, f.supported & mask, f.diagnostics))
        if not results:
            fdim = self.feature_dim
            return FeatureBatch(self.rates.new_empty((state.last_time.numel(), 0, fdim)),
                                torch.empty(state.last_time.numel(), 0, dtype=torch.bool, device=self.rates.device))
        return FeatureBatch(torch.cat([f.values for f in results], 1), torch.cat([f.supported for f in results], 1),
                            {k: torch.cat([f.diagnostics[k] for f in results], 1) for k in results[0].diagnostics})

    def persistent_nbytes(self, state: Snapshot) -> int:
        self._check_snapshot(state)
        tensors = [*state.payload.values(), state.last_time, state.valid, state.event_offset]
        # Logical packed SHA-256 and schema_version, not Python object overhead.
        return sum(t.numel()*t.element_size() for t in tensors) + 32 + 8

    def parameter_nbytes(self) -> int:
        return sum(t.numel()*t.element_size() for t in (*self.parameters(), *self.buffers()))
