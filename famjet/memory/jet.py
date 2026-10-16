"""Exact first dimensionless moments and a fixed-writer timestamp adapter.

Core state: [B,H,J,K,V+1]; writes: key[B,H,K], value[B,H,V],
gate[B,H]; rates[H,J]. The final column is shared normalization.
Raw EventBatch inputs deliberately support H=1 and shared observations only.
No eventual-query input is accepted by the writer. The identity H=-d_log_rate Z
requires rate-independent writes; it does not assert properties of arbitrary
autograd graphs supplied by callers.
"""
from dataclasses import dataclass
import math

import torch
from torch import Tensor, nn

from famjet.data.schema import validate_events, validate_queries, validate_rates
from famjet.eval.oracle import exact_time_difference
from famjet.provenance import canonical_hash
from famjet.types import EventBatch, FeatureBatch, QueryBatch, Snapshot


@dataclass(frozen=True)
class JetState:
    z: Tensor
    h: Tensor


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _finite(tensor, name):
    _require(isinstance(tensor, Tensor) and tensor.is_floating_point()
             and bool(torch.isfinite(tensor).all()), f'{name} must be finite floating')


def _state_shape(state):
    _require(state.z.ndim == 5 and state.z.shape == state.h.shape,
             'state must contain equal [B,H,J,K,V+1] tensors')
    _require(all(s > 0 for s in state.z.shape) and state.z.shape[-1] >= 2,
             'state dimensions must be positive with V+1 >= 2')
    _require(state.z.device == state.h.device and state.z.dtype == state.h.dtype,
             'state tensors must share device and dtype')
    return state.z.shape


def validate_jet_step(state: JetState, key: Tensor, value: Tensor, gate: Tensor,
                      delta: Tensor, rates: Tensor, event_present: Tensor) -> None:
    """Explicit untimed validation for direct jet/Laguerre core callers.

    Call before stepping untrusted inputs. The cores themselves are tensor-only
    and assume validated finite inputs with delta on the state dtype/device.
    JetMemory validates entire event batches and the incoming state once before
    its recurrence loop instead of calling this per-event boundary.
    """
    b, heads, anchors, k, v1 = _state_shape(state)
    for name, tensor, shape in [('key', key, (b, heads, k)), ('value', value, (b, heads, v1-1)),
                                ('gate', gate, (b, heads)), ('rates', rates, (heads, anchors))]:
        _finite(tensor, name)
        _require(tuple(tensor.shape) == shape, f'{name} has invalid shape')
        _require(tensor.device == state.z.device and tensor.dtype == state.z.dtype,
                 f'{name} must share state device and dtype')
    _finite(state.z, 'state.z'); _finite(state.h, 'state.h')
    _finite(delta, 'delta')
    _require(tuple(delta.shape) == (b,) and bool((delta >= 0).all()), 'delta must be nonnegative [B]')
    _require(delta.device == state.z.device and delta.dtype == state.z.dtype,
             'core delta must share state device and dtype')
    _require(bool((key >= 0).all()) and bool((gate >= 0).all()), 'keys and gates must be nonnegative')
    validate_rates(rates)
    _require(event_present.shape == (b,) and event_present.dtype == torch.bool
             and event_present.device == state.z.device, 'event_present must be device bool [B]')


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


def jet_step(state: JetState, key: Tensor, value: Tensor, gate: Tensor,
             delta: Tensor, rates: Tensor, event_present: Tensor) -> JetState:
    """Decay independently of write presence, then add an age-zero impulse.

    event_present is the write mask: real no-write gaps use delta>0, False;
    padding uses delta=0, False. Inputs must be validated before this tensor-only
    core (see validate_jet_step); delta shares state dtype/device. Public raw
    adapters prepare CPU timestamps and exceptional huge gaps before stepping.
    No tensors are mutated or detached; no host scalars are extracted.
    """
    a, ad = _core_coefficients(rates, delta)
    return _jet_update(state, key, value, gate, event_present, a, ad)


def _jet_update(state, key, value, gate, event_present, a, ad):
    """Common tensor-only update for device or precomputed host-time weights."""
    a, ad = a[..., None, None], ad[..., None, None]
    return JetState(a*state.z + _write(key, value, gate, event_present),
                    a*state.h + ad*state.z)


def _raw(events, rates):
    # Always revalidate: callers can mutate tensors after earlier validation.
    validate_events(events); validate_rates(rates)
    _require(rates.ndim == 2 and rates.shape[0] == 1, 'raw EventBatch adapter requires rates [1,J]')
    _require(events.normalization == 'shared', 'jet raw adapter requires shared normalization')
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


def _zero(events, rates):
    b, _, k = events.key_features.shape
    shape = (b, 1, rates.shape[1], k, events.values.shape[-1]+1)
    z = events.values.new_zeros(shape)
    return JetState(z, z.clone())


def jet_terminal(events: EventBatch, rates: Tensor, chunk_size: int) -> JetState:
    """Exact sums at each row's final present time, including no-write gaps.

    Weighted keys have shape [B,J,chunk,K]. No event-by-state outer-product
    tensor is built. Chunk accumulation preserves gradients in every write and
    rate; empty rows have zero state.
    """
    _require(type(chunk_size) is int and chunk_size > 0, 'chunk_size must be a positive integer')
    gates = _raw(events, rates)
    state = _zero(events, rates)
    b, n, _ = events.values.shape
    times = events.timestamps.tolist()
    lengths = events.lengths.tolist()
    for start in range(0, n, chunk_size):
        end = min(start+chunk_size, n)
        ages = torch.tensor([[float(exact_time_difference(row[length-1], row[i]))
                              if i < length else 0. for i in range(start, end)]
                             for row, length in zip(times, lengths)], dtype=torch.float64)
        a, ad = _coefficients(rates, ages)
        key = events.key_features[:, start:end] * gates[:, start:end, None]
        aug = torch.cat((events.values[:, start:end], torch.ones_like(events.values[:, start:end, :1])), -1)
        z = torch.einsum('bjck,bcv->bjkv', a[:, 0, :, :, None]*key[:, None], aug)
        h = torch.einsum('bjck,bcv->bjkv', ad[:, 0, :, :, None]*key[:, None], aug)
        state = JetState(state.z + z[:, None], state.h + h[:, None])
    return state


def contract_jet(state: JetState, query_features: Tensor, rates: Tensor, eps: float,
                 support_floor: float, t_ref: float) -> FeatureBatch:
    """Structured [B,Q,H*J*(2V+4)] features and unnormalized diagnostics.

    Per-anchor order: r[V], dlog_rate_r[V], log1p(z), smoothed_age,
    log(lambda*t_ref), support. Query support is ANY supported anchor; exact
    dimensionless_age=b/z and physical mean_age=b/(lambda*z) are diagnostic
    features only where z>support_floor. Raw u,h,z,b remain available for later
    generic readers. Unsupported ages use safe denominators BEFORE division.
    """
    bsz, heads, anchors, k, _ = _state_shape(state)
    validate_rates(rates)
    _require(rates.shape == (heads, anchors) and rates.device == state.z.device
             and rates.dtype == state.z.dtype, 'rates must match state [H,J]')
    for name, x, positive in [('eps', eps, True), ('support_floor', support_floor, False), ('t_ref', t_ref, True)]:
        _require(isinstance(x, (int, float)) and math.isfinite(x) and (x > 0 if positive else x >= 0),
                 f'{name} must be finite and {"positive" if positive else "nonnegative"}')
    represented_eps = torch.tensor(eps, dtype=state.z.dtype)
    _require(bool(torch.isfinite(represented_eps)) and represented_eps.item() > 0,
             'eps must remain finite positive in state dtype')
    _finite(query_features, 'query_features')
    _require(query_features.device == state.z.device and query_features.dtype == state.z.dtype
             and bool((query_features >= 0).all()), 'query features must be nonnegative on state device/dtype')
    if query_features.ndim == 3:
        query_features = query_features[:, :, None, :].expand(-1, -1, heads, -1)
    _require(query_features.ndim == 4 and query_features.shape[0] == bsz
             and query_features.shape[2:] == (heads, k), 'query features must be [B,Q,K] or [B,Q,H,K]')
    cz = torch.einsum('bqhk,bhjkv->bqhjv', query_features, state.z)
    ch = torch.einsum('bqhk,bhjkv->bqhjv', query_features, state.h)
    u, z, h, moment = cz[..., :-1], cz[..., -1], ch[..., :-1], ch[..., -1]
    finite = torch.isfinite(cz).all(-1) & torch.isfinite(ch).all(-1) & (z >= 0)
    anchor_support = finite & (z > support_floor)
    safe_z = torch.where(finite, z, torch.zeros_like(z))
    denominator = safe_z + eps
    denominator_ok = torch.isfinite(denominator) & (denominator > 0)
    denominator = torch.where(denominator_ok, denominator, torch.ones_like(denominator))
    r = u / denominator[..., None]
    # Center the numerator before division rather than subtracting two already
    # normalized large terms; delayed reads otherwise amplify cancellation.
    derivative = (r*moment[..., None] - h) / denominator[..., None]
    safe_mass = torch.where(anchor_support, z, torch.ones_like(z))
    exact_age = torch.where(anchor_support, moment, torch.zeros_like(moment)) / safe_mass
    mean_age = exact_age / rates[None, None]
    smoothed_age = moment / denominator
    log_rate = (torch.log(rates) + math.log(t_ref))[None, None].expand_as(z)
    structured = torch.cat((r, derivative, torch.log1p(safe_z)[..., None],
                            smoothed_age[..., None], log_rate[..., None], anchor_support.to(z.dtype)[..., None]), -1)
    failed = ~finite | ~denominator_ok | ~torch.isfinite(structured).all(-1) | ~torch.isfinite(mean_age)
    structured = torch.where(failed[..., None], torch.zeros_like(structured), structured)
    supported = (anchor_support & ~failed).any(dim=(-1, -2))
    return FeatureBatch(structured.flatten(2), supported, {
        'u': u, 'h': h, 'z': z, 'b': moment, 'r': r, 'dlog_rate_r': derivative,
        'smoothed_age': smoothed_age, 'dimensionless_age': exact_age, 'mean_age': mean_age,
        'anchor_support': anchor_support, 'failure': failed.any(dim=(-1, -2)),
    })


def _digest_tensor(value):
    return torch.tensor(list(bytes.fromhex(canonical_hash(value))), dtype=torch.uint8)


def _pack_times(values):
    if all(type(v) is int for v in values):
        return torch.tensor(values, dtype=torch.int64)
    _require(all(type(v) is not int or int(float(v)) == v for v in values),
             'mixed snapshot times cannot be represented losslessly in one timestamp tensor')
    return torch.tensor(values, dtype=torch.float64)


class JetMemory(nn.Module):
    """Focused H=1 fixed raw writer; no learned reader, fallback or task model.

    Snapshots own all history-dependent tensors, including identity/time-unit
    hashes and last event IDs. Parameters and configuration stay on the module;
    encoding/read calls never cache histories or query-dependent state there.
    """
    def __init__(self, rates: Tensor, key_dim: int, value_dim: int, *, eps=1e-8,
                 support_floor=1e-12, t_ref=1., chunk_size=128):
        super().__init__()
        validate_rates(rates)
        _require(rates.ndim == 2 and rates.shape[0] == 1, 'JetMemory raw writer requires rates [1,J]')
        _require(type(key_dim) is int and key_dim > 0 and type(value_dim) is int and value_dim > 0,
                 'key_dim and value_dim must be positive integers')
        _require(type(chunk_size) is int and chunk_size > 0, 'chunk_size must be positive integer')
        for name, x, allow_zero in [('eps', eps, False), ('support_floor', support_floor, True), ('t_ref', t_ref, False)]:
            _require(isinstance(x, (int, float)) and math.isfinite(x) and (x >= 0 if allow_zero else x > 0), f'invalid {name}')
        self.register_buffer('rates', rates.clone())
        self.key_dim, self.value_dim = key_dim, value_dim
        self.eps, self.support_floor, self.t_ref, self.chunk_size = eps, support_floor, t_ref, chunk_size

    def _parameter_hash(self):
        return canonical_hash({'kernel': 'jet-v1-fixed-shared', 'rates': self.rates.detach().cpu().tolist(),
                               'key_dim': self.key_dim, 'value_dim': self.value_dim})

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
        return Snapshot({'z': z, 'h': z.clone(), 'history_hash': torch.zeros(batch_size, 32, dtype=torch.uint8),
                         'time_unit_hash': torch.zeros(32, dtype=torch.uint8),
                         'last_event_id': torch.full((batch_size,), -1, dtype=torch.int64)},
                        torch.zeros(batch_size, dtype=torch.int64), torch.zeros(batch_size, dtype=torch.bool),
                        self._parameter_hash(), torch.zeros(batch_size, dtype=torch.int64))

    def _check_snapshot(self, state):
        _require(state.schema_version == 1 and state.parameter_hash == self._parameter_hash(),
                 'snapshot schema/parameter hash mismatch')
        expected = {'z', 'h', 'history_hash', 'time_unit_hash', 'last_event_id'}
        _require(set(state.payload) == expected, 'invalid snapshot payload')
        b = state.last_time.numel()
        z = state.payload['z']; h = state.payload['h']
        _require(z.shape == (b, 1, self.rates.shape[1], self.key_dim, self.value_dim+1)
                 and h.shape == z.shape and z.dtype == h.dtype == self.rates.dtype
                 and z.device == h.device == self.rates.device, 'snapshot state layout mismatch')
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
        gates = _raw(events, self.rates)
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
        core = JetState(state.payload['z'], state.payload['h'])
        _finite(core.z, 'snapshot.z'); _finite(core.h, 'snapshot.h')
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
                    core = _jet_update(*args, events.validation.write_mask[:, j], a[..., j], ad[..., j])
                else:
                    core = jet_step(*args, device_gaps[:, j], self.rates, events.validation.write_mask[:, j])
        else:
            gaps = [float(exact_time_difference(times[i][length-1], last[i])) if length and valid[i] else 0.
                    for i, length in enumerate(lengths)]
            a, ad = _coefficients(self.rates, torch.tensor(gaps, dtype=torch.float64))
            a, ad = a[..., None, None], ad[..., None, None]
            terminal = jet_terminal(events, self.rates, self.chunk_size)
            core = JetState(a*core.z + terminal.z, a*core.h + ad*core.z + terminal.h)
        for i, length in enumerate(lengths):
            if length:
                last[i] = times[i][length-1]; valid[i] = True; last_ids[i] = ids[i][length-1]
        return Snapshot({'z': core.z, 'h': core.h, 'history_hash': identity, 'time_unit_hash': unit,
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
        a, ad = a[..., None, None], ad[..., None, None]
        payload = {k: v.clone() for k, v in state.payload.items()}
        payload['z'] = a*state.payload['z']
        payload['h'] = a*state.payload['h'] + ad*state.payload['z']
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
            f = contract_jet(JetState(advanced['z'], advanced['h']),
                             queries.key_features[:, j:j+1], self.rates, self.eps, self.support_floor, self.t_ref)
            mask = queries.present[:, j:j+1] & state.valid.to(queries.present.device)[:, None]
            results.append(FeatureBatch(f.values, f.supported & mask, f.diagnostics))
        if not results:
            fdim = self.rates.numel()*(2*self.value_dim+4)
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
