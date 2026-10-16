"""Equal-payload independent exponential anchors with the shared fixed writer.

State [B,H,M,K,V+1] includes one normalization column at EVERY pole. No
finite differences, sorting or pole separation are required by the reader.
Core callers validate once before stepping; public adapters always revalidate.
"""
import math

import torch
from torch import Tensor, nn

from famjet.eval.oracle import exact_time_difference
from famjet.provenance import canonical_hash
from famjet.types import EventBatch, FeatureBatch
from famjet.memory._fixed_writer import (
    FixedWriterMemory, _require, _finite, _core_coefficients, _coefficients,
    _write, _raw,
)


def validate_bank_rates(rates: Tensor, *, no_decay: bool = False) -> None:
    """Zero rates require the explicit bank-only no_decay variant."""
    _require(type(no_decay) is bool, 'no_decay must be a static bool')
    _finite(rates, 'rates')
    _require(rates.ndim == 2 and rates.numel() > 0, 'rates must be nonempty [H,M]')
    _require(bool((rates >= 0 if no_decay else rates > 0).all()),
             'rates must be positive (zero requires no_decay=True)')


def _state_shape(state):
    _require(isinstance(state, Tensor) and state.is_floating_point() and state.ndim == 5,
             'state must be floating [B,H,M,K,V+1]')
    _require(all(s > 0 for s in state.shape) and state.shape[-1] >= 2,
             'state dimensions must be positive with V+1 >= 2')
    return state.shape


def validate_exp_step(state: Tensor, key: Tensor, value: Tensor, gate: Tensor,
                      delta: Tensor, rates: Tensor, event_present: Tensor,
                      *, no_decay: bool = False) -> None:
    """Untimed direct-core boundary; masked invalid numbers still reject."""
    b, h, m, k, v1 = _state_shape(state)
    _finite(state, 'state')
    for name, x, shape in [('key', key, (b, h, k)), ('value', value, (b, h, v1-1)),
                           ('gate', gate, (b, h)), ('delta', delta, (b,)), ('rates', rates, (h, m))]:
        _finite(x, name)
        _require(x.shape == shape and x.device == state.device and x.dtype == state.dtype,
                 f'{name} must match core shape/device/dtype')
    _require(bool((key >= 0).all()) and bool((gate >= 0).all()) and bool((delta >= 0).all()),
             'key/gate/delta must be nonnegative')
    validate_bank_rates(rates, no_decay=no_decay)
    _require(event_present.shape == (b,) and event_present.dtype == torch.bool
             and event_present.device == state.device, 'event_present must be device bool [B]')


def _exp_update(state, key, value, gate, event_present, a):
    return a[..., None, None]*state + _write(key, value, gate, event_present)


def exp_step(state: Tensor, key: Tensor, value: Tensor, gate: Tensor, delta: Tensor,
             rates: Tensor, event_present: Tensor) -> Tensor:
    """Tensor-only decay plus impulse; false write mask does not cancel time.

    Inputs must be finite and validated before this core. Padding has delta0;
    real no-write gaps have positive delta and false event_present. Zero poles
    are legal only following validate_exp_step(..., no_decay=True).
    """
    a, _ = _core_coefficients(rates, delta)
    return _exp_update(state, key, value, gate, event_present, a)


def exp_terminal(events: EventBatch, rates: Tensor, chunk_size: int,
                 *, no_decay: bool = False) -> Tensor:
    """Chunked exact terminal sum with [B,M,chunk,K] weighted keys."""
    _require(type(chunk_size) is int and chunk_size > 0, 'chunk_size must be positive integer')
    gates = _raw(events, rates, lambda r: validate_bank_rates(r, no_decay=no_decay))
    b, n, k = events.key_features.shape
    state = events.values.new_zeros((b, 1, rates.shape[1], k, events.values.shape[-1]+1))
    times, lengths = events.timestamps.tolist(), events.lengths.tolist()
    for start in range(0, n, chunk_size):
        end = min(start+chunk_size, n)
        ages = torch.tensor([[float(exact_time_difference(row[length-1], row[j])) if j < length else 0.
                              for j in range(start, end)] for row, length in zip(times, lengths)], dtype=torch.float64)
        a, _ = _coefficients(rates, ages)
        key = events.key_features[:, start:end]*gates[:, start:end, None]
        aug = torch.cat((events.values[:, start:end], torch.ones_like(events.values[:, start:end, :1])), -1)
        contribution = torch.einsum('bmck,bcv->bmkv', a[:, 0, :, :, None]*key[:, None], aug)
        state = state + contribution[:, None]
    return state


def contract_bank(state: Tensor, query_features: Tensor, rates: Tensor, eps: float,
                  support_floor: float, t_ref: float, *, no_decay: bool = False) -> FeatureBatch:
    """Per-anchor r[V], log1p(z), log(lambda*t_ref), support; width H*M*(V+3).

    Every raw numerator u and denominator z is exposed in diagnostics, together
    with r and per-anchor support. The explicit no-decay variant uses log-rate
    sentinel0 and a static no_decay diagnostic; log(0) is never evaluated.
    No unused no-decay columns are added to reader inputs. Numerical failures
    zero the affected anchor features and retain a per-query failure flag.
    """
    b, h, m, k, _ = _state_shape(state)
    validate_bank_rates(rates, no_decay=no_decay)
    _require(rates.shape == (h, m) and rates.device == state.device and rates.dtype == state.dtype,
             'rates must match state shape/device/dtype')
    for name, x, positive in [('eps', eps, True), ('support_floor', support_floor, False), ('t_ref', t_ref, True)]:
        _require(isinstance(x, (int, float)) and math.isfinite(x) and (x > 0 if positive else x >= 0),
                 f'invalid {name}')
    represented_eps = torch.tensor(eps, dtype=state.dtype)
    _require(bool(torch.isfinite(represented_eps)) and represented_eps.item() > 0,
             'eps must remain finite positive in state dtype')
    _finite(query_features, 'query_features')
    _require(query_features.device == state.device and query_features.dtype == state.dtype
             and bool((query_features >= 0).all()), 'query features must be nonnegative on state device/dtype')
    if query_features.ndim == 3:
        query_features = query_features[:, :, None].expand(-1, -1, h, -1)
    _require(query_features.ndim == 4 and query_features.shape[0] == b
             and query_features.shape[2:] == (h, k), 'query features must be [B,Q,K] or [B,Q,H,K]')
    contractions = torch.einsum('bqhk,bhmkv->bqhmv', query_features, state)
    u, z = contractions[..., :-1], contractions[..., -1]
    finite = torch.isfinite(contractions).all(-1) & (z >= 0)
    anchor_support = finite & (z > support_floor)
    safe_z = torch.where(finite, z, torch.zeros_like(z))
    denominator = safe_z + eps
    denominator_ok = torch.isfinite(denominator) & (denominator > 0)
    denominator = torch.where(denominator_ok, denominator, torch.ones_like(denominator))
    r = u / denominator[..., None]
    zero = rates == 0
    # Static variant flag authorizes the zero pole; mask BEFORE logarithm.
    log_rate = torch.log(torch.where(zero, torch.ones_like(rates), rates)) + math.log(t_ref)
    log_rate = torch.where(zero, torch.zeros_like(log_rate), log_rate)[None, None].expand_as(z)
    structured = torch.cat((r, torch.log1p(safe_z)[..., None], log_rate[..., None],
                            anchor_support.to(z.dtype)[..., None]), -1)
    failed = ~finite | ~denominator_ok | ~torch.isfinite(structured).all(-1)
    structured = torch.where(failed[..., None], torch.zeros_like(structured), structured)
    return FeatureBatch(structured.flatten(2), (anchor_support & ~failed).any(dim=(-1, -2)), {
        'u': u, 'z': z, 'r': r, 'anchor_support': anchor_support,
        'no_decay': zero[None, None].expand_as(z), 'failure': failed.any(dim=(-1, -2)),
    })


def _log_bounds(count, log_min, log_max):
    _require(type(count) is int and count > 0, 'count must be positive integer')
    _require(all(isinstance(x, (int, float)) and math.isfinite(x) for x in (log_min, log_max))
             and log_min < log_max, 'finite ordered log bounds required')


def log_rate_grid(count: int, log_min: float, log_max: float, *, device='cpu', dtype=torch.float32) -> Tensor:
    """Fixed broad grid in natural-log rate coordinates, not a forced stencil."""
    _log_bounds(count, log_min, log_max)
    rates = torch.linspace(log_min, log_max, count, device=device, dtype=dtype).exp()[None]
    validate_bank_rates(rates)
    return rates


class BoundedRates(nn.Module):
    """Learn log rates via sigmoid coordinates; coincidence and reordering legal.

    forward() returns [1,count]. Initialization spans the interior 10–90% of
    supplied log bounds. Set logits directly or optimize them for tuned grids;
    no sorting, minimum spacing, finite difference reader or trainer is imposed.
    """
    def __init__(self, count: int, log_min: float, log_max: float):
        super().__init__()
        _log_bounds(count, log_min, log_max)
        self.log_min, self.log_max = float(log_min), float(log_max)
        coordinates = torch.linspace(.1, .9, count) if count > 1 else torch.tensor([.5])
        self.logits = nn.Parameter(torch.logit(coordinates)[None])
        validate_bank_rates(self())

    def forward(self) -> Tensor:
        return torch.exp(self.log_min + (self.log_max-self.log_min)*torch.sigmoid(self.logits))


class ExpBankMemory(FixedWriterMemory):
    """H=1 bank kernel; fixed/tuned tensor or a registered BoundedRates source.

    External Tensor rates are cloned as differentiable buffers, as in JetMemory.
    A BoundedRates source is registered as a submodule, so optimizers and byte
    accounting see its logits, and every encode/read obtains current rates.
    Changing rates invalidates previous snapshots. No learned reader is added.
    """
    _state_keys = ('z',)

    def __init__(self, rates: Tensor | BoundedRates, key_dim: int, value_dim: int, *,
                 eps=1e-8, support_floor=1e-12, t_ref=1., chunk_size=128, no_decay=False):
        super().__init__()
        self.no_decay = no_decay
        initial = rates() if isinstance(rates, BoundedRates) else rates
        validate_bank_rates(initial, no_decay=no_decay)
        _require(initial.shape[0] == 1, 'raw writer requires rates [1,M]')
        _require(type(key_dim) is int and key_dim > 0 and type(value_dim) is int and value_dim > 0,
                 'key_dim and value_dim must be positive integers')
        _require(type(chunk_size) is int and chunk_size > 0, 'chunk_size must be positive integer')
        for name, x, allow_zero in [('eps', eps, False), ('support_floor', support_floor, True), ('t_ref', t_ref, False)]:
            _require(isinstance(x, (int, float)) and math.isfinite(x) and (x >= 0 if allow_zero else x > 0), f'invalid {name}')
        if isinstance(rates, BoundedRates):
            self.rate_source = rates
        else:
            self.register_buffer('_fixed_rates', rates.clone())
        self.key_dim, self.value_dim = key_dim, value_dim
        self.eps, self.support_floor, self.t_ref, self.chunk_size = eps, support_floor, t_ref, chunk_size

    @property
    def rates(self):
        return self.rate_source() if hasattr(self, 'rate_source') else self._fixed_rates

    @property
    def feature_dim(self):
        return self.rates.numel()*(self.value_dim+3)

    @property
    def feature_spec(self):
        return {'anchor_order': 'caller-supplied', 'anchor_fields': ('r', 'log1p_z', 'log_rate_t_ref', 'support'),
                'value_dim': self.value_dim, 'no_decay_variant': self.no_decay,
                'no_decay_anchors': (self.rates.detach().cpu() == 0).tolist(), 'width': self.feature_dim}

    def _parameter_hash(self):
        return canonical_hash({'kernel': 'expbank-v1-fixed-shared', 'rates': self.rates.detach().cpu().tolist(),
                               'key_dim': self.key_dim, 'value_dim': self.value_dim, 'no_decay': self.no_decay})

    def _raw(self, events):
        return _raw(events, self.rates, lambda r: validate_bank_rates(r, no_decay=self.no_decay))

    def _zero_payload(self, z):
        return {'z': z}

    def _step(self, core, *args):
        return {'z': exp_step(core['z'], *args)}

    def _weighted_step(self, core, key, value, gate, mask, a, ad):
        return {'z': _exp_update(core['z'], key, value, gate, mask, a)}

    def _terminal(self, events):
        return {'z': exp_terminal(events, self.rates, self.chunk_size, no_decay=self.no_decay)}

    def _decay_payload(self, core, a, ad):
        return {'z': a[..., None, None]*core['z']}

    def _contract(self, core, query_features):
        return contract_bank(core['z'], query_features, self.rates, self.eps, self.support_floor,
                             self.t_ref, no_decay=self.no_decay)
