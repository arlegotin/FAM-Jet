"""Frozen arithmetic controls and independently stepped Laguerre coordinates."""
from dataclasses import replace
import time

import torch

from famjet.data.schema import validate_events, validate_queries
from famjet.eval.oracle import exact_time_difference
from famjet.memory.coordinates import from_laguerre, laguerre_step
from famjet.memory.exact_store import PackedHistoryMemory
from famjet.memory.reservoir import ReservoirMemory
from famjet.memory.buckets import TemporalBucketsMemory
from famjet.provenance import canonical_hash, canonical_json
from famjet.types import Snapshot
from .contracts import ShapeSpec
from .models import RidgeMemoryModel
from .wire import export_statics


def _control_constructor(kind, capacity, shape, seed):
    common = {'key_dim': shape.key_dim, 'value_dtype': 'float64'}
    if kind in {'recent', 'latest_lru'}:
        tail = {**common, 'policy': kind}
        return PackedHistoryMemory(capacity, shape.value_dim, **tail), tail
    if kind == 'reservoir':
        tail = {**common, 'seed': seed, 'accumulation_dtype': 'float64'}
        return ReservoirMemory(capacity, shape.value_dim, **tail), tail
    tail = {**common, 'accumulation_dtype': 'float64', 'normalization': 'shared'}
    return TemporalBucketsMemory(capacity, shape.value_dim, **tail), tail


def build_controls(shape, budget, training_statistics, seed) -> dict:
    if type(shape) is not ShapeSpec or type(budget) is not int or budget <= 0 or type(seed) is not int or seed < 0:
        raise ValueError('valid shape, positive state budget and reservoir seed required')
    expected_budget = 9345 if shape == ShapeSpec(16, 8) else 1665
    if budget != expected_budget:
        raise ValueError('shape-specific frozen persistent budget required')
    if (type(training_statistics) is not dict or training_statistics.get('split') != 'training' or
            training_statistics.get('target_semantics') != 'observed_event_targets_v2'):
        raise ValueError('training priors required')
    exact = PackedHistoryMemory(None, shape.value_dim, 'exact', key_dim=shape.key_dim, value_dtype='float64')
    controls = {'exact': {'method': exact, 'capacity': None, 'bounded': False, 'state_budget': None,
                          'training_statistics': training_statistics, 'static_bytes': len(canonical_json(export_statics(exact))),
                          'constructor_tail': {'policy': 'exact', 'key_dim': shape.key_dim, 'value_dtype': 'float64'}}}
    for kind in ('recent', 'latest_lru', 'reservoir', 'buckets'):
        def usage(capacity):
            method, tail = _control_constructor(kind, capacity, shape, seed)
            state = method.init_state(1, device='cpu', dtype='float64')
            return method.persistent_nbytes(state), method, tail
        low, high = 0, 1
        while usage(high)[0] <= budget:
            low, high = high, high * 2
        while high - low > 1:
            mid = (low + high) // 2
            if usage(mid)[0] <= budget:
                low = mid
            else:
                high = mid
        byte_fitting_capacity = low
        if kind == 'latest_lru':
            low = min(shape.key_dim, low)
        if low == 0:
            raise ValueError('no positive control capacity fits persistent budget')
        used, method, tail = usage(low)
        if kind != 'latest_lru' and usage(low + 1)[0] <= budget:
            raise AssertionError('capacity search failed maximality')
        controls[kind] = {'method': method, 'capacity': low, 'bounded': True,
                          'state_budget': budget, 'max_state_bytes': used, 'unused_bytes': budget - used,
                          'byte_fitting_capacity': byte_fitting_capacity,
                          'static_bytes': len(canonical_json(export_statics(method))),
                          'constructor_tail': tail, 'training_statistics': training_statistics,
                          'constructor_sha256': canonical_hash({'kind': kind, 'capacity': low, **tail})}
    return controls


def laguerre_control(model, events, queries) -> dict:
    """Step L0/L1 per event, recover Z/H only at the reader boundary."""
    if type(model) is not RidgeMemoryModel or model.spec.family != 'jet':
        raise ValueError('base frozen Jet reader required')
    validate_events(events)
    validate_queries(queries)
    if events.history_ids != queries.history_ids:
        raise ValueError('history identities differ')
    b, n = events.event_ids.shape
    if any(int(length) != n for length in events.lengths):
        raise ValueError('independent Laguerre control requires unpadded histories')
    events = replace(events, key_features=events.key_features.to(torch.float64),
                     values=events.values.to(torch.float64))
    validate_events(events)
    gates = model.writer._raw(events)
    base = model.init_state(b, device='cpu', dtype='float64')
    l0 = torch.zeros_like(base.payload['z'])
    l1 = torch.zeros_like(l0)
    direct = None
    previous = [None] * b
    started = time.perf_counter()
    with torch.no_grad():
        for j in range(n):
            times = events.timestamps[:, j].tolist()
            gaps = [0. if previous[i] is None else float(exact_time_difference(times[i], previous[i])) for i in range(b)]
            l0, l1 = laguerre_step(l0, l1, events.key_features[:, j, None].to(torch.float64),
                                   events.values[:, j, None].to(torch.float64), gates[:, j, None],
                                   torch.tensor(gaps, dtype=torch.float64), model.writer.rates,
                                   events.validation.write_mask[:, j])
            event = replace(events, **{name: getattr(events, name)[:, j:j+1] for name in
                                    ('event_ids', 'timestamps', 'key_ids', 'key_features', 'values', 'present', 'observed')},
                            lengths=torch.ones_like(events.lengths),
                            auxiliary={k: v[:, j:j+1] for k, v in events.auxiliary.items()})
            direct = model.encode(event, direct, mode='stream')
            previous = times
        coordinate_seconds = time.perf_counter() - started
        converted = from_laguerre(l0, l1)
        recovered = Snapshot({**direct.payload, 'z': converted.z, 'h': converted.h},
                             direct.last_time.clone(), direct.valid.clone(), direct.parameter_hash,
                             direct.event_offset.clone())
        converted_seconds = time.perf_counter() - started - coordinate_seconds
        left = model.read(direct, queries)
        right = model.read(recovered, queries)
    finite = torch.isfinite(left.prediction) & torch.isfinite(right.prediction)
    prediction_error = float(torch.max(torch.abs(left.prediction[finite] - right.prediction[finite]))) if bool(finite.any()) else 0.
    state_error = max(float(torch.max(torch.abs(direct.payload[key] - recovered.payload[key]))) for key in ('z', 'h'))
    if not (torch.equal(torch.isfinite(left.prediction), torch.isfinite(right.prediction)) and
            torch.equal(left.failure, right.failure)):
        raise ArithmeticError('Laguerre reader support/failure parity changed')
    if (not torch.allclose(direct.payload['z'], recovered.payload['z'], rtol=1e-12, atol=1e-12) or
            not torch.allclose(direct.payload['h'], recovered.payload['h'], rtol=1e-12, atol=1e-12) or
            not torch.allclose(left.prediction[finite], right.prediction[finite], rtol=1e-12, atol=1e-12) or
            not torch.equal(left.support, right.support) or
            any(not torch.equal(left.diagnostics[name], right.diagnostics[name]) for name in
                ('prediction_valid', 'numeric_supported'))):
        raise ArithmeticError('Laguerre FP64 state/prediction parity exceeded original tolerance')
    return {'result': right, 'direct_result': left, 'recovered_state': recovered,
            'event_count': b * n, 'max_state_absolute_error': state_error,
            'max_prediction_absolute_error': prediction_error,
            'coordinate_seconds': coordinate_seconds, 'conversion_seconds': converted_seconds,
            'equivalent_state_bytes': sum(t.numel() * t.element_size() for t in (l0, l1)),
            'equivalent_metadata_bytes': model.persistent_nbytes(recovered) -
                                         sum(t.numel() * t.element_size() for t in (recovered.payload['z'], recovered.payload['h']))}
