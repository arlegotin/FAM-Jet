"""Frozen arithmetic controls and independently stepped Laguerre coordinates."""
from dataclasses import replace
import time
import math

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


COORDINATE_POLICY = 'fp64_coordinate_diagnostic_v2'
_COORDINATE_MASKS = ('finite', 'support', 'failure', 'prediction_valid', 'numeric_supported')


def coordinate_model_sha256(model):
    """Identity of the unchanged numeric reader, also valid for unfitted unit controls."""
    return canonical_hash({'shape': model.shape.to_json(), 'reader': model.spec.to_json(),
        't_ref': model.t_ref, 'writer_hash': model.writer_hash,
        'target_statistics': model.target_statistics,
        'arrays': {name: getattr(model, name).tolist() for name in
                   ('coefficients', 'feature_mean', 'feature_scale', 'query_mean', 'query_scale')}})


def _errors(left, right):
    delta = torch.abs(left - right)
    scaled = delta / (1e-12 + 1e-12 * torch.abs(right))
    return (float(delta.max()) if delta.numel() else 0.,
            float(scaled.max()) if scaled.numel() else 0.)


def laguerre_control(model, events, queries, *, diagnostic_mode=False) -> dict:
    """Step L0/L1 per event, recover Z/H only at the reader boundary."""
    if type(diagnostic_mode) is not bool:
        raise ValueError('explicit boolean diagnostic mode required')
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
    masks = {'finite': (torch.isfinite(left.prediction), torch.isfinite(right.prediction)),
             'support': (left.support, right.support), 'failure': (left.failure, right.failure),
             **{name: (left.diagnostics[name], right.diagnostics[name])
                for name in ('prediction_valid', 'numeric_supported')}}
    if any(not torch.equal(a, b) for a, b in masks.values()):
        raise ArithmeticError('Laguerre reader support/failure/semantic mask parity changed')
    for key in ('z', 'h'):
        if (not bool(torch.isfinite(direct.payload[key]).all()) or
                not bool(torch.isfinite(recovered.payload[key]).all()) or
                not torch.allclose(direct.payload[key], recovered.payload[key], rtol=1e-12, atol=1e-12)):
            raise ArithmeticError('Laguerre FP64 state parity exceeded original tolerance')
    strict_pass = torch.allclose(left.prediction[finite], right.prediction[finite], rtol=1e-12, atol=1e-12)
    if not strict_pass and not diagnostic_mode:
        raise ArithmeticError('Laguerre FP64 state/prediction parity exceeded original tolerance')
    diagnostics = {}
    model_hash = coordinate_model_sha256(model)
    for i, history in enumerate(events.history_ids):
        present = queries.present[i]
        valid = finite[i] & present[:, None]
        absolute, scaled = _errors(left.prediction[i][valid], right.prediction[i][valid])
        failed = valid & ~torch.isclose(left.prediction[i], right.prediction[i], rtol=1e-12, atol=1e-12)
        state_errors = {key: _errors(direct.payload[key][i], recovered.payload[key][i]) for key in ('z', 'h')}
        diagnostics[history] = {
            'schema_version': 2, 'policy': COORDINATE_POLICY, 'atol': 1e-12, 'rtol': 1e-12,
            'history_id': history, 'model_numeric_sha256': model_hash,
            'query_ids': queries.query_ids[i][present].tolist(),
            'query_count': int(present.sum()), 'value_dim': model.shape.value_dim,
            'total_scalar_count': int(present.sum()) * model.shape.value_dim,
            'evaluated_scalar_count': int(valid.sum()),
            'strict_prediction_failed_scalars': int(failed.sum()),
            'strict_prediction_failed_queries': int(failed.any(dim=-1).sum()),
            'strict_prediction_status': 'FAILED' if bool(failed.any()) else 'PASSED',
            'state_checks': {'z': True, 'h': True},
            'mask_checks': {name: True for name in _COORDINATE_MASKS},
            'state_errors': {key: {'absolute': value[0], 'scaled': value[1]} for key, value in state_errors.items()},
            'max_state_absolute_error': max(value[0] for value in state_errors.values()),
            'max_state_scaled_error': max(value[1] for value in state_errors.values()),
            'max_prediction_absolute_error': absolute, 'max_prediction_scaled_error': scaled}
    prediction_error = max(d['max_prediction_absolute_error'] for d in diagnostics.values())
    state_error = max(d['max_state_absolute_error'] for d in diagnostics.values())
    return {'result': right, 'direct_result': left, 'recovered_state': recovered,
            'coordinate_diagnostics': diagnostics,
            'event_count': b * n, 'max_state_absolute_error': state_error,
            'max_prediction_absolute_error': prediction_error,
            'coordinate_seconds': coordinate_seconds, 'conversion_seconds': converted_seconds,
            'diagnostic_seconds': time.perf_counter() - started - coordinate_seconds - converted_seconds,
            'equivalent_state_bytes': sum(t.numel() * t.element_size() for t in (l0, l1)),
            'equivalent_metadata_bytes': model.persistent_nbytes(recovered) -
                                         sum(t.numel() * t.element_size() for t in (recovered.payload['z'], recovered.payload['h']))}


def validate_coordinate_audits(costs, rows, *, model_numeric_sha256=None, require_summary=True):
    """Pure validation of complete immutable history/query diagnostics and their summary."""
    def reject():
        raise ValueError('coordinate diagnostic audit/model/inventory/status mismatch')
    if type(costs) is not dict or not rows:
        reject()
    audits = costs.get('stream_audits')
    if type(audits) is not dict or costs.get('stream_audits_sha256') != canonical_hash(audits):
        reject()
    inventory = {}
    for row in rows:
        if row.get('method') != 'laguerre':
            reject()
        inventory.setdefault(row['history_id'], []).append(row['query_id'])
    if set(inventory) != set(audits) or costs.get('history_count') != len(inventory):
        reject()
    model_hash = costs.get('coordinate_model_sha256')
    if (type(model_hash) is not str or len(model_hash) != 64 or
            any(c not in '0123456789abcdef' for c in model_hash) or
            model_numeric_sha256 is not None and model_hash != model_numeric_sha256):
        reject()
    diagnostics = []
    for history, query_ids in inventory.items():
        d = audits[history].get('coordinate_diagnostic')
        if (type(d) is not dict or d.get('schema_version') != 2 or d.get('policy') != COORDINATE_POLICY or
                d.get('history_id') != history or d.get('model_numeric_sha256') != model_hash or
                d.get('atol') != 1e-12 or d.get('rtol') != 1e-12 or
                d.get('query_ids') != sorted(query_ids) or len(set(query_ids)) != len(query_ids) or
                d.get('query_count') != len(query_ids) or
                d.get('state_checks') != {'z': True, 'h': True} or
                d.get('mask_checks') != {name: True for name in _COORDINATE_MASKS}):
            reject()
        if any(value is not True for name in ('state_checks', 'mask_checks') for value in d[name].values()):
            reject()
        fields = ('query_count', 'value_dim', 'total_scalar_count', 'evaluated_scalar_count',
                  'strict_prediction_failed_scalars', 'strict_prediction_failed_queries')
        if any(type(d.get(name)) is not int or d[name] < 0 for name in fields):
            reject()
        if (d['value_dim'] < 1 or d['total_scalar_count'] != len(query_ids) * d['value_dim'] or
                not 0 <= d['strict_prediction_failed_scalars'] <= d['evaluated_scalar_count'] <= d['total_scalar_count'] or
                not 0 <= d['strict_prediction_failed_queries'] <= min(len(query_ids), d['strict_prediction_failed_scalars']) or
                d['strict_prediction_failed_scalars'] > d['strict_prediction_failed_queries'] * d['value_dim'] or
                (d['strict_prediction_failed_scalars'] == 0) != (d['strict_prediction_failed_queries'] == 0)):
            reject()
        maxima = ('max_state_absolute_error', 'max_state_scaled_error',
                  'max_prediction_absolute_error', 'max_prediction_scaled_error')
        if any(type(d.get(name)) not in (float, int) or not math.isfinite(d[name]) or d[name] < 0 for name in maxima):
            reject()
        state = d.get('state_errors')
        if (type(state) is not dict or set(state) != {'z', 'h'} or
                any(type(v) is not dict or set(v) != {'absolute', 'scaled'} or
                    any(type(x) not in (float, int) or not math.isfinite(x) or x < 0 for x in v.values())
                    for v in state.values())):
            reject()
        failed = d['strict_prediction_failed_scalars'] > 0
        if (d['max_state_scaled_error'] > 1 or
                any(d['max_state_' + name + '_error'] != max(v[name] for v in state.values())
                    for name in ('absolute', 'scaled')) or
                (d['max_prediction_scaled_error'] > 1) != failed or
                d['strict_prediction_status'] != ('FAILED' if failed else 'PASSED') or
                d['evaluated_scalar_count'] == 0 and d['max_prediction_absolute_error'] != 0):
            reject()
        history_rows = [row for row in rows if row['history_id'] == history]
        if any(type(row.get('raw_prediction')) is not list or
               len(row['raw_prediction']) != d['value_dim'] for row in history_rows):
            reject()
        finite_count = sum(type(value) in (float, int) and math.isfinite(value)
                           for row in history_rows for value in row['raw_prediction'])
        if finite_count != d['evaluated_scalar_count']:
            reject()
        diagnostics.append(d)
    result = {'schema_version': 2, 'policy': COORDINATE_POLICY,
              'status': 'diagnostic_complete', 'state_checks': 'PASSED', 'mask_checks': 'PASSED',
              'atol': 1e-12, 'rtol': 1e-12, 'history_count': len(diagnostics),
              'strict_prediction_failed_histories': sum(d['strict_prediction_status'] == 'FAILED' for d in diagnostics)}
    for name in ('query_count', 'total_scalar_count', 'evaluated_scalar_count',
                 'strict_prediction_failed_scalars', 'strict_prediction_failed_queries'):
        result[name] = sum(d[name] for d in diagnostics)
    for name in ('max_state_absolute_error', 'max_state_scaled_error',
                 'max_prediction_absolute_error', 'max_prediction_scaled_error'):
        result[name] = max(d[name] for d in diagnostics)
    result['strict_prediction_status'] = 'FAILED' if result['strict_prediction_failed_histories'] else 'PASSED'
    if ((require_summary or 'coordinate_diagnostic_summary' in costs) and
            costs.get('coordinate_diagnostic_summary') != result):
        reject()
    return result
