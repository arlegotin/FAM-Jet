"""One bounded diagnostic for the historical two-history unit-fit parity failure."""
import json
import sys

import numpy as np
import torch

from famjet_poc.comparators import laguerre_control
from famjet_poc.contracts import PopulationSpec, ReaderSpec, ShapeSpec
from famjet_poc.data import generate_episode
from famjet_poc.models import (build_model, fit_reader, fit_training_metadata,
                               make_fit_manifest, _training_rows)


def scaled_ratio(left, right):
    difference = torch.abs(left - right)
    tolerance = 1e-12 + 1e-12 * torch.abs(right)
    return float(torch.max(difference / tolerance)) if difference.numel() else 0.0


def normal_condition(model, episodes, metadata):
    inventory = {item['history_id']: item for item in metadata['history_inventory']}
    counts = {item['regime']: sum(x['regime'] == item['regime']
                                 for x in metadata['history_inventory'])
              for item in metadata['history_inventory']}
    p = 33 * model.spec.query_width
    gram = np.zeros((p, p), dtype=np.float64)
    total_weight = 0.0
    for episode in episodes:
        for history, task, features, basis, _ in _training_rows(model, episode):
            item = inventory[history]
            fs = np.r_[1., (features[1:] - model.feature_mean) / model.feature_scale]
            qs = np.r_[1., (basis[1:] - model.query_mean) / model.query_scale]
            phi = np.outer(qs, fs).ravel()
            task_scale = model.target_statistics['tasks'][task]['scale']
            weight = (1.0 / counts[item['regime']] / 2.0 /
                      item['eligible'][task] / model.shape.value_dim / task_scale**2)
            gram += weight * np.outer(phi, phi)
            total_weight += weight
    normal = gram / total_weight + model.spec.ridge * np.eye(p)
    eigenvalues = np.linalg.eigvalsh(normal)
    return {'normal_condition_2': float(eigenvalues[-1] / eigenvalues[0]),
            'normal_min_eigenvalue': float(eigenvalues[0]),
            'normal_max_eigenvalue': float(eigenvalues[-1]),
            'coefficient_l2_norm': float(np.linalg.norm(model.coefficients)),
            'coefficient_max_abs': float(np.max(np.abs(model.coefficients))),
            'fit_scaled_normal_residual': model.fit_artifact.scaled_normal_residual,
            'fit_objective': model.fit_artifact.objective,
            'fit_row_count': model.fit_artifact.row_count}


def frame_report(local, history, status, error):
    direct, recovered = local['direct'], local['recovered']
    left, right = local['left'], local['right']
    finite = local['finite']
    state = {key: {'max_abs_error': float(torch.max(torch.abs(
                      direct.payload[key] - recovered.payload[key]))),
                   'max_scaled_tolerance_ratio': scaled_ratio(
                      direct.payload[key], recovered.payload[key]),
                   'allclose_1e12': bool(torch.allclose(direct.payload[key],
                      recovered.payload[key], rtol=1e-12, atol=1e-12))}
             for key in ('z', 'h')}
    prediction_left, prediction_right = left.prediction[finite], right.prediction[finite]
    return {'history_id': history, 'status': status, 'error': error,
            'max_state_absolute_error': local['state_error'],
            'max_prediction_absolute_error': local['prediction_error'],
            'state': state,
            'prediction': {'finite_count': int(finite.sum()),
                           'max_scaled_tolerance_ratio': scaled_ratio(prediction_left,
                                                                        prediction_right),
                           'allclose_1e12': bool(torch.allclose(prediction_left,
                                                                prediction_right,
                                                                rtol=1e-12, atol=1e-12))},
            'finite_mask_equal': bool(torch.equal(torch.isfinite(left.prediction),
                                                   torch.isfinite(right.prediction))),
            'support_equal': bool(torch.equal(left.support, right.support)),
            'failure_equal': bool(torch.equal(left.failure, right.failure)),
            'prediction_valid_equal': bool(torch.equal(
                left.diagnostics['prediction_valid'], right.diagnostics['prediction_valid'])),
            'numeric_supported_equal': bool(torch.equal(
                left.diagnostics['numeric_supported'], right.diagnostics['numeric_supported']))}


def inspect_control(model, episode):
    captured = {}
    def profile(frame, event, arg):
        if (event == 'return' and frame.f_code.co_name == 'laguerre_control' and
                frame.f_globals.get('__name__') == 'famjet_poc.comparators'):
            captured.update(frame.f_locals)
    try:
        sys.setprofile(profile)
        laguerre_control(model, episode.events, episode.queries)
        return frame_report(captured, episode.events.history_ids[0], 'passed', None)
    except ArithmeticError as exc:
        trace = exc.__traceback__
        while trace is not None and trace.tb_frame.f_code.co_name != 'laguerre_control':
            trace = trace.tb_next
        if trace is None:
            raise
        return frame_report(trace.tb_frame.f_locals, episode.events.history_ids[0],
                            'failed', str(exc))
    finally:
        sys.setprofile(None)


def main():
    spec = PopulationSpec('poc_numeric_v1', ShapeSpec(16, 8), 'unit_test', 17,
                          (128,), ('piecewise_stationary',), 8, 64)
    episodes = [generate_episode(spec, history) for history in ('tiny-0', 'tiny-1')]
    for episode in episodes:
        episode.metadata['split'] = 'training'
    factory = lambda: iter(episodes)
    metadata = fit_training_metadata(factory)
    results = []
    for ridge in (1e-6, 1e-2):
        reader = ReaderSpec('ridge_v1', 'jet', 8, ridge, 1 / 5224,
                            1., 1e-6, 1e-12)
        model = build_model(spec.shape, reader, metadata['t_ref'],
                            metadata['target_statistics'])
        fit_reader(model, factory, make_fit_manifest(model, metadata))
        results.append({'ridge': ridge,
                        'fit': normal_condition(model, episodes, metadata),
                        'histories': [inspect_control(model, episode)
                                      for episode in episodes]})
    print(json.dumps({'scope': 'two-history K16/V8 unit_test Jet-only diagnostic',
                      'original_comparator_rtol_atol': 1e-12,
                      'cases': results}, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
