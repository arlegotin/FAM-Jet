import numpy as np

from famjet.eval.metrics import fit_target_statistics
from famjet_poc.contracts import PopulationSpec, ReaderSpec, ShapeSpec
from famjet_poc.data import generate_episode
from famjet_poc.models import build_model


def _episode():
    spec = PopulationSpec('poc_numeric_v1', ShapeSpec(12, 1), 'unit_test', 318,
                          (128,), ('piecewise_stationary',), 8, 512)
    ep = generate_episode(spec, 'unit-comparator-0')
    ep.metadata['split'] = 'training'
    return ep


def test_controls_take_largest_capacity_within_total_state_budget():
    from famjet_poc.comparators import build_controls

    ep = _episode()
    controls = build_controls(ShapeSpec(12, 1), 1665, fit_target_statistics([ep]), 77)
    assert controls['exact']['capacity'] is None
    for key in ('recent', 'latest_lru', 'reservoir', 'buckets'):
        item = controls[key]
        assert item['capacity'] > 0
        assert item['max_state_bytes'] <= 1665
        assert item['unused_bytes'] == 1665 - item['max_state_bytes']
        method = item['method']
        larger = type(method)(item['capacity'] + 1, 1, **item['constructor_tail'])
        if key == 'latest_lru':
            assert item['capacity'] == ep.events.key_features.shape[-1]
        else:
            assert larger.persistent_nbytes(larger.init_state(1, device='cpu', dtype='float64')) > 1665


def test_laguerre_control_streams_independently_with_reader_parity():
    from famjet_poc.comparators import laguerre_control

    ep = _episode()
    stats = fit_target_statistics([ep])
    spec = ReaderSpec('ridge_v1', 'jet', 8, 1e-6, 1 / 5224, 1., 1e-6, 1e-12)
    model = build_model(ShapeSpec(12, 1), spec, 1., stats)
    model.coefficients = np.linspace(-0.01, 0.02, 33 * spec.query_width)
    result = laguerre_control(model, ep.events, ep.queries)
    assert result['event_count'] == 128
    assert result['max_state_absolute_error'] < 1e-10
    assert result['max_prediction_absolute_error'] < 1e-10
