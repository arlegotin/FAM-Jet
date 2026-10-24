"""Bounded, read-only diagnosis of the actual selected public Jet checkpoint.

Run via run.py. Never fits, generates data, changes a tolerance, or edits artifacts.
The unchanged comparator is called once per visited history; failures are retained.
"""
import os
for _name in ('OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'VECLIB_MAXIMUM_THREADS'):
    assert os.environ.get(_name) == '1'
import sys
import time
START = time.monotonic()
import hashlib
import json
import platform
import resource
import signal
import traceback
from dataclasses import replace
from decimal import Decimal, localcontext
from pathlib import Path
signal.signal(signal.SIGALRM, lambda *_: (_ for _ in ()).throw(TimeoutError('270-second inner deadline')))
signal.alarm(270)
import numpy as np
import torch
from famjet_poc.cache import episode_factory, load_episode_cache, e3_source_sha256
from famjet_poc.comparators import laguerre_control
from famjet_poc.contracts import source_sha256
from famjet_poc.models import load_model, query_basis
from famjet_poc.study import select_candidate

OUT = Path(__file__).resolve().parent
BASE = Path('artifacts/e2e-core-run-01/development_k16')
INPUTS = {}


def fingerprint(path):
    path = Path(path)
    raw = path.read_bytes()
    record = {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}
    INPUTS[str(path)] = record
    return record


def read_json(path):
    fingerprint(path)
    return json.loads(Path(path).read_bytes())


def D(value):
    return Decimal.from_float(float(value))


def difference(left, right):
    left, right = np.asarray(left), np.asarray(right)
    finite = np.isfinite(left) & np.isfinite(right)
    delta = np.where(finite, np.abs(left - right), 0.)
    ratio = delta / (1e-12 + 1e-12 * np.where(finite, np.abs(right), 0.))
    return {'max_absolute_error': float(delta.max()),
            'max_tolerance_ratio': float(ratio.max()),
            'max_ratio_index': list(map(int, np.unravel_index(ratio.argmax(), ratio.shape))),
            'strict_allclose': bool(np.all(ratio <= 1))}


def capture(model, ep):
    local = {}
    def profile(frame, event, arg):
        if event == 'return' and frame.f_code is laguerre_control.__code__:
            local.update(frame.f_locals)
    sys.setprofile(profile)
    try:
        laguerre_control(model, ep.events, ep.queries)
        status, error = 'passed', None
    except ArithmeticError as exc:
        status, error = 'failed', str(exc)
        traceback.print_exc()
        trace = exc.__traceback__
        while trace:
            if trace.tb_frame.f_code is laguerre_control.__code__:
                local.update(trace.tb_frame.f_locals)
            trace = trace.tb_next
    finally:
        sys.setprofile(None)
    left, right = local['left'], local['right']
    summary = {'history_id': ep.events.history_ids[0], 'status': status, 'error': error,
               'event_count': int(ep.events.lengths[0]),
               'state': {k: difference(local['direct'].payload[k], local['recovered'].payload[k]) for k in ('z', 'h')},
               'prediction': difference(left.prediction, right.prediction),
               'finite_mask_equal': bool(torch.equal(torch.isfinite(left.prediction), torch.isfinite(right.prediction))),
               'support_equal': bool(torch.equal(left.support, right.support)),
               'failure_equal': bool(torch.equal(left.failure, right.failure)),
               'diagnostic_masks_equal': {k: bool(torch.equal(left.diagnostics[k], right.diagnostics[k])) for k in ('prediction_valid', 'numeric_supported')}}
    print(json.dumps({'comparator': summary}), flush=True)
    return summary, local


def direct_sums(ep, model, query_index, target):
    """Independent Decimal exp sums from actual binary64 event/key/gate/rate inputs."""
    e, q = ep.events, ep.queries
    key = q.key_features[0, query_index].tolist()
    converted = replace(e, values=e.values.to(torch.float64), key_features=e.key_features.to(torch.float64))
    gates = model.writer._raw(converted)[0].tolist()
    result = [[Decimal(0) for _ in range(model.shape.value_dim + 1)] for _ in range(8)]
    contributing = 0
    for j in range(int(e.lengths[0])):
        if not bool(e.validation.write_mask[0, j]):
            continue
        overlap = sum(D(a) * D(b) for a, b in zip(key, e.key_features[0, j].tolist()))
        if not overlap:
            continue
        contributing += 1
        age = D(target) - D(e.timestamps[0, j])
        impulse = [overlap * D(gates[j]) * D(v) for v in e.values[0, j].tolist() + [1.]]
        for anchor, rate in enumerate(model.writer.rates[0].tolist()):
            scaled_age = D(rate) * age
            decay = (-scaled_age).exp()
            for v, value in enumerate(impulse):
                result[anchor][v] += decay * value
                result[anchor + 4][v] += scaled_age * decay * value
    return result, contributing


def keyed_payload(model, state, ep, qi, advance):
    p = model.writer._advance_payload(state, [ep.queries.T[0, qi].item()], [True]) if advance else state.payload
    key = ep.queries.key_features[:, qi].to(torch.float64)
    return np.concatenate([torch.einsum('bjkv,bk->bjv', p[k][:, 0], key).numpy()[0] for k in ('z', 'h')])


def decimal_readout(joined, model, ep, qi, vi):
    masses = [r[-1] for r in joined]
    u = [r[vi] for r in joined]
    raw = [Decimal(1)] + u + [a / (b + D(model.spec.epsilon)) for a, b in zip(u, masses)]
    raw += [(1 + m).ln() for m in masses] + [Decimal(int(m > D(model.spec.support_floor))) for m in masses]
    f = [Decimal(1)] + [(r - D(m)) / D(s) for r, m, s in zip(raw[1:], model.feature_mean, model.feature_scale)]
    a, b = ep.queries.age_start[0, qi].item(), ep.queries.age_end[0, qi].item()
    task = ep.queries.tasks[0][qi]
    x, y, c = (1 + D(a) / D(model.t_ref)).ln(), (1 + (D(b) - D(a)) / D(model.t_ref)).ln(), Decimal(int(task == 'contrast'))
    basis = [Decimal(1), x, y, x*y, x*x, y*y, c, c*x]
    if model.spec.query_width == 16:
        basis += [c*y, c*x*y, c*x*x, c*y*y, x**3, y**3, x*x*y, x*y*y]
    def evaluate(q):
        qs = [Decimal(1)] + [(r - D(m)) / D(s) for r, m, s in zip(q[1:], model.query_mean, model.query_scale)]
        phi = [a * b for a in qs for b in f]
        return sum(v * D(beta) for v, beta in zip(phi, model.coefficients))
    # Same rounded query-basis isolates the state/readout path; second is mathematical query basis.
    frozen_basis = list(map(D, query_basis(float(a), float(b), task, model.t_ref, model.spec.query_width)))
    return raw, evaluate(frozen_basis), evaluate(basis)


def detail(model, ep, local):
    direct, recovered = local['direct'], local['recovered']
    left, right = local['left'].prediction.numpy(), local['right'].prediction.numpy()
    raw_l = model._raw_features(direct, ep.queries)[0]
    raw_r = model._raw_features(recovered, ep.queries)[0]
    phi_l = model.design(direct, ep.queries)[0]
    phi_r = model.design(recovered, ep.queries)[0]
    ratio = np.where(np.isfinite(left) & np.isfinite(right), np.abs(left-right) / (1e-12 + 1e-12*np.abs(right)), 0.)
    failing = np.argwhere(ratio > 1)
    chosen = [tuple(failing[0]), np.unravel_index(ratio.argmax(), ratio.shape), np.unravel_index(np.abs(left-right).argmax(), ratio.shape)]
    chosen = list(dict.fromkeys(chosen))
    result = {'first_failing_index': list(map(int, failing[0])), 'failing_scalar_count': len(failing),
              'raw_feature_difference': difference(raw_l, raw_r),
              'standardized_design_difference': difference(phi_l, phi_r), 'queries': []}
    for _, qi, vi in chosen:
        qi, vi = int(qi), int(vi)
        with localcontext() as ctx:
            ctx.prec = 70
            terminal_ref, contributors = direct_sums(ep, model, qi, direct.last_time[0].item())
            query_ref, _ = direct_sums(ep, model, qi, ep.queries.T[0, qi].item())
            raw_ref, pred_ref, mathematical_ref = decimal_readout(query_ref, model, ep, qi, vi)
            lphi, rphi = list(map(D, phi_l[0, qi, vi])), list(map(D, phi_r[0, qi, vi]))
            beta = list(map(D, model.coefficients))
            ldot = sum(a*b for a, b in zip(lphi, beta))
            rdot = sum(a*b for a, b in zip(rphi, beta))
            bound = sum(abs((a-b)*c) for a, b, c in zip(lphi, rphi, beta))
            lround, rround = D(left[0, qi, vi])-ldot, D(right[0, qi, vi])-rdot
            terminal_float, query_float = np.asarray(terminal_ref, dtype=float), np.asarray(query_ref, dtype=float)
            task = ep.queries.tasks[0][qi]
            scale = model.target_statistics['tasks'][task]['scale']
            target = float(ep.labels[0, qi, vi])
            delta = float(abs(D(left[0, qi, vi])-D(right[0, qi, vi])))
            row = {'query_index': qi, 'query_id': int(ep.queries.query_ids[0, qi]), 'value_index': vi,
                   'key_id': int(ep.queries.key_ids[0, qi]), 'key_features': ep.queries.key_features[0, qi].tolist(),
                   'T': ep.queries.T[0, qi].item(), 'age_start': ep.queries.age_start[0, qi].item(),
                   'age_end': ep.queries.age_end[0, qi].item(), 'task': task,
                   'contributing_events': contributors, 'direct_prediction': float(left[0, qi, vi]),
                   'laguerre_prediction': float(right[0, qi, vi]), 'absolute_prediction_delta': delta,
                   'strict_tolerance_ratio': float(ratio[0, qi, vi]),
                   'decimal70_prediction_same_binary64_query_basis': str(pred_ref),
                   'decimal70_prediction_mathematical_query_basis': str(mathematical_ref),
                   'direct_error_to_decimal70': str(D(left[0, qi, vi])-pred_ref),
                   'laguerre_error_to_decimal70': str(D(right[0, qi, vi])-pred_ref),
                   'feature_delta_dot_beta_exact_decimal': str(ldot-rdot),
                   'sum_abs_beta_delta_phi_bound': str(bound),
                   'direct_dot_rounding': str(lround), 'laguerre_dot_rounding': str(rround),
                   'total_observed_delta_bound': str(bound+abs(lround)+abs(rround)),
                   'task_training_scale': scale, 'target': target,
                   'prediction_delta_in_training_scale': delta/scale,
                   'normalized_scalar_squared_loss_delta_bound': delta*(abs(float(left[0, qi, vi])-target)+abs(float(right[0, qi, vi])-target))/scale**2,
                   'raw_feature_to_decimal70_direct': difference(raw_l[0, qi, vi], np.asarray(raw_ref, dtype=float)),
                   'raw_feature_to_decimal70_laguerre': difference(raw_r[0, qi, vi], np.asarray(raw_ref, dtype=float)),
                   'terminal_direct_to_decimal70': difference(keyed_payload(model, direct, ep, qi, False), terminal_float),
                   'terminal_laguerre_to_decimal70': difference(keyed_payload(model, recovered, ep, qi, False), terminal_float),
                   'query_direct_to_decimal70': difference(keyed_payload(model, direct, ep, qi, True), query_float),
                   'query_laguerre_to_decimal70': difference(keyed_payload(model, recovered, ep, qi, True), query_float),
                   'decimal70_terminal_key_ZH': [[str(v) for v in row] for row in terminal_ref],
                   'decimal70_query_key_ZH': [[str(v) for v in row] for row in query_ref]}
            result['queries'].append(row)
    np.savez(OUT/'first-failure-arrays.npz', direct_z=direct.payload['z'].numpy(), direct_h=direct.payload['h'].numpy(),
             recovered_z=recovered.payload['z'].numpy(), recovered_h=recovered.payload['h'].numpy(),
             l0=local['l0'].numpy(), l1=local['l1'].numpy(), direct_prediction=left, laguerre_prediction=right,
             direct_raw=raw_l, laguerre_raw=raw_r, direct_phi=phi_l, laguerre_phi=phi_r, coefficients=model.coefficients)
    return result


def main():
    journal = read_json(BASE/'study/development.json')
    manifest = read_json(BASE/'manifest.json')
    selected = select_candidate([r for r in journal['candidate_ledger'] if r['family'] == 'jet'])
    assert selected['config_hash'] == journal['selected']['jet']['config_hash'] == journal['controls']['laguerre']['equivalent_to']
    ref = selected['fit_ref']
    model_record = read_json(ref['path'])
    fingerprint(Path(ref['path']).with_suffix('.npz'))
    model = load_model(Path(ref['path']), ref['sha256'])
    cache_root = BASE/'study/development-cache'
    fingerprint(cache_root/'cache-manifest.json')
    cache = load_episode_cache(cache_root, journal['development_cache_sha256'])
    ids = [r['history_id'] for r in manifest['development_inventory']]
    assert set(ids) == {r['history_id'] for r in cache.entries}
    results = {'purpose': 'diagnosis only; strict failure retained', 'source_sha256': source_sha256(),
               'e3_source_sha256': e3_source_sha256(), 'python': sys.version, 'platform': platform.platform(),
               'numpy_longdouble_mantissa_bits': int(np.finfo(np.longdouble).nmant+1),
               'original_allocation_started_epoch_seconds': journal['allocation_started_epoch_seconds'],
               'original_allocation_clock_kind': journal['allocation_clock_kind'],
               'selected_config_hash': selected['config_hash'], 'selected_fit_ref': ref,
               'reader': selected['reader'], 'development_loss': selected['loss'],
               'coefficient_l2_norm': float(np.linalg.norm(model.coefficients)),
               'coefficient_l1_norm': float(np.linalg.norm(model.coefficients, ord=1)),
               'coefficient_max_abs': float(np.abs(model.coefficients).max()),
               'feature_scale_min': float(model.feature_scale.min()), 'query_scale_min': float(model.query_scale.min()),
               'fit_scaled_normal_residual': model.fit_artifact.scaled_normal_residual,
               'fit_objective': model.fit_artifact.objective,
               'normal_condition': 'unavailable: normal matrix/eigenvalues not persisted; no training rescan or refit authorized here',
               'predeclared_neighbor_policy': 'first failure plus immediately following public history, no additional scan',
               'histories': []}
    failed = False
    for index, ep in enumerate(episode_factory(cache, ids)()):
        entry = next(e for e in cache.entries if e['history_id'] == ids[index])
        fingerprint(cache.root/entry['file'])
        summary, local = capture(model, ep)
        summary['development_sequence_index'] = index
        results['histories'].append(summary)
        if failed:
            break
        if summary['status'] == 'failed':
            results['first_failure'] = detail(model, ep, local)
            failed = True
        if time.monotonic()-START > 240:
            raise TimeoutError('public search deadline; no restart authorized')
    assert failed, 'original failure was not reproduced'
    for path, before in list(INPUTS.items()):
        assert fingerprint(path) == before, f'input changed: {path}'
    results['immutable_inputs'] = INPUTS
    results['elapsed_inside_process_seconds'] = time.monotonic()-START
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    results['observed_process_peak_rss_bytes'] = peak if sys.platform == 'darwin' else peak*1024
    assert results['observed_process_peak_rss_bytes'] <= 1536*1024**2
    (OUT/'result.json').write_text(json.dumps(results, indent=2, sort_keys=True)+'\n')
    print(json.dumps({'status': 'diagnosis_completed_original_failure_retained', 'selected': selected['config_hash'],
                      'histories': len(results['histories']), 'elapsed_seconds': results['elapsed_inside_process_seconds'],
                      'peak_rss_bytes': results['observed_process_peak_rss_bytes']}), flush=True)


if __name__ == '__main__':
    main()
