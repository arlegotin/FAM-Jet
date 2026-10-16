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
from torch import Tensor

from famjet.data.schema import validate_rates
from famjet.eval.oracle import exact_time_difference
from famjet.provenance import canonical_hash
from famjet.types import EventBatch, FeatureBatch
from famjet.memory._fixed_writer import (
    FixedWriterMemory, _require, _finite, _core_coefficients, _coefficients,
    _write, _raw,
)


@dataclass(frozen=True)
class JetState:
    z: Tensor
    h: Tensor


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


class JetMemory(FixedWriterMemory):
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

    _state_keys = ('z', 'h')

    @property
    def feature_dim(self):
        return self.rates.numel()*(2*self.value_dim+4)

    def _raw(self, events):
        return _raw(events, self.rates)

    def _zero_payload(self, z):
        return {'z': z, 'h': z.clone()}

    def _step(self, core, *args):
        state = jet_step(JetState(**core), *args)
        return {'z': state.z, 'h': state.h}

    def _weighted_step(self, core, *args):
        state = _jet_update(JetState(**core), *args)
        return {'z': state.z, 'h': state.h}

    def _terminal(self, events):
        state = jet_terminal(events, self.rates, self.chunk_size)
        return {'z': state.z, 'h': state.h}

    def _decay_payload(self, core, a, ad):
        a, ad = a[..., None, None], ad[..., None, None]
        return {'z': a*core['z'], 'h': a*core['h'] + ad*core['z']}

    def _contract(self, core, query_features):
        return contract_jet(JetState(core['z'], core['h']), query_features, self.rates,
                            self.eps, self.support_floor, self.t_ref)
