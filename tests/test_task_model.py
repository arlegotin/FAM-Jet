"""Complete predictor checks: causal ownership, units, gradients and controls."""
from dataclasses import replace
import importlib
import math
from pathlib import Path
import pytest
import torch
from jet_fixtures import events, queries, kernel_case
from famjet.config import load_config
from famjet.memory.jet import JetMemory
from famjet.memory.expbank import ExpBankMemory, BoundedRates
from famjet.memory.coordinates import to_laguerre, from_laguerre
from famjet.memory.jet import JetState
from famjet.types import Episode


def configuration(family='jet', kind='structured', learned=False, dtype=torch.float64):
    cfg = load_config(Path('configs/smoke.yaml'))
    cfg = replace(cfg, data=replace(cfg.data, key_dim=3, value_dim=2), model=replace(cfg.model,
        method=family, K=3, J=2, precision=str(dtype).split('.')[-1], writer='learned' if learned else 'fixed',
        rates=replace(cfg.model.rates, mode='learned' if learned else 'fixed'),
        reader=replace(cfg.model.reader, kind=kind, width=16)))
    return cfg


def model(family='jet', kind='structured', learned=False, dtype=torch.float64, device='cpu'):
    assert importlib.util.find_spec('famjet.models.task_model') is not None, 'TaskModel is missing'
    from famjet.models.task_model import TaskModel
    from famjet.readers.structured import make_reader
    cfg = configuration(family, kind, learned, dtype)
    rates = BoundedRates(2, math.log(.1), math.log(1.)).to(device=device, dtype=dtype) if learned else torch.tensor([[.1, 1.]], device=device, dtype=dtype)
    kernel = (JetMemory if family == 'jet' else ExpBankMemory)(rates, 3, 2,
        eps=cfg.model.epsilon, support_floor=cfg.model.numerical_support_floor, t_ref=2.)
    reader = make_reader(kind, dict(family=family, anchors=2, key_dim=3, value_dim=2),
                         dict(key_dim=3), dict(width=16, hidden_layers=2)).to(device=device, dtype=dtype)
    return TaskModel(kernel, reader, cfg).to(device=device, dtype=dtype)


@pytest.mark.parametrize('family', ['jet', 'bank'])
def test_terminal_and_stream_model_match(family, kernel_case):
    dtype, device, tol = kernel_case
    m = model(family, learned=True, dtype=dtype, device=device)
    e = events(dtype, device); q = queries(e, [[8, 12], [7, 14]])
    a = m(e, q, encode_mode='stream'); b = m(e, q, encode_mode='terminal')
    torch.testing.assert_close(a.prediction, b.prediction, rtol=tol[0], atol=tol[1])
    (b.prediction.square().sum() + b.diagnostics['support_logit'].square().sum()).backward()
    for name, p in m.named_parameters():
        assert p.grad is not None and torch.isfinite(p.grad).all(), name
        # The support head is trained by its own objective.
    assert m.kernel.rates.shape == (1, 2)


@pytest.mark.parametrize('kind', ['structured', 'generic_contracted', 'generic_full', 'fixed_scale', 'query_only'])
def test_dimensionless_predictor_units(kind):
    m = model(kind=kind); e = events(); q = queries(e, [[8, 12], [7, 14]])
    a = m(e, q, encode_mode='terminal').prediction
    n = model(kind=kind); n.load_state_dict(m.state_dict())
    n.kernel.rates.div_(1000); n.kernel.t_ref *= 1000
    ee = replace(e, timestamps=e.timestamps*1000, time_unit='milliseconds')
    qq = replace(q, T=q.T*1000, age_start=q.age_start*1000, age_end=q.age_end*1000)
    b = n(ee, qq, encode_mode='terminal').prediction
    torch.testing.assert_close(a, b, atol=1e-12, rtol=1e-12)


def test_generic_inputs_include_all_state():
    m = model(kind='generic_full'); e = events(); q = queries(e, [[8], [7]])
    s = m.encode(e, mode='terminal'); f = m.features(s, q)
    raw = torch.cat([s.payload[k].flatten(1) for k in ('z', 'h')], -1)
    torch.testing.assert_close(f.values[:, 0, :36], raw)
    assert f.values.shape[-1] == m.reader.input_dim


def test_identical_recovered_coordinates_same_reader():
    m = model(); e = events(); q = queries(e, [[8, 13], [7, 10]])
    s = m.encode(e, mode='terminal')
    recovered = from_laguerre(*to_laguerre(JetState(s.payload['z'], s.payload['h'])))
    ss = replace(s, payload={**s.payload, 'z': recovered.z, 'h': recovered.h})
    torch.testing.assert_close(m.read(s, q).prediction, m.read(ss, q).prediction, atol=1e-12, rtol=1e-12)


def test_reader_updates_reuse_state_writer_updates_reject():
    m = model(learned=True); e = events(); q = queries(e, [[8], [7]])
    s = m.encode(e)
    with torch.no_grad():
        m.reader.output.bias.add_(1)
        m.query_map.bias.add_(.1)
    assert torch.isfinite(m.read(s, q).prediction).all()
    with torch.no_grad(): m.writer.value.bias.add_(.1)
    with pytest.raises(ValueError, match='hash'): m.read(s, q)


def test_absent_key_presence_prediction_valid():
    m = model(); e = events(); q = queries(e, [[8], [7]])
    q = replace(q, key_features=torch.zeros_like(q.key_features), tasks=(('presence',), ('presence',)))
    out = m(e, q, encode_mode='terminal')
    assert not out.diagnostics['numeric_supported'].any()
    assert out.diagnostics['prediction_valid'].all() and not out.failure.any()
    assert out.prediction.shape == (2, 1, 1)
    assert torch.isfinite(out.diagnostics['support_logit']).all()


@pytest.mark.parametrize('family', ['jet', 'bank'])
def test_tiny_sufficient_statistic_overfit(family):
    torch.manual_seed(41)
    m = model(family); e = events(); q = queries(e, [[8], [7]])
    target = torch.tensor([[[.2, -.5]], [[.8, .1]]], dtype=torch.float64)
    opt = torch.optim.Adam(m.parameters(), lr=.03)
    for _ in range(160):
        out = m(e, q, encode_mode='terminal')
        loss = (out.prediction-target).square().mean()
        opt.zero_grad(); loss.backward(); opt.step()
    assert loss.item() < 1e-6


def test_training_statistics_reject_development_and_require_reference():
    m = model(); e = events(); q = queries(e, [[8], [7]])
    ep = Episode(e, q, torch.tensor([[[1., 2.]], [[3., 4.]]]), torch.ones(2, 1, dtype=torch.bool), {'split': 'development'})
    with pytest.raises(ValueError, match='training'): m.fit_statistics([ep])
    e0 = replace(e, timestamps=torch.zeros_like(e.timestamps))
    ep0 = replace(ep, events=e0, queries=replace(q, T=torch.ones_like(q.T)), metadata={'split': 'training'})
    with pytest.raises(ValueError, match='reference'): m.fit_statistics([ep0])
    m.fit_statistics([ep0], reference_duration=2.)
    assert m.kernel.t_ref == 2. and m.fit_provenance['split'] == 'training'
    assert m.target_statistics['tasks']['mean']['mean'] == [2., 3.]
    assert torch.isfinite(m.reader.feature_scale).all()


def test_isolated_task_read_and_complete_inventory():
    from famjet.eval.isolation import isolated_read, model_identity
    from famjet.eval.budgets import model_ledger
    m = model('bank', learned=True); e = events(); q = queries(e, [[8], [7]])
    s = m.encode(e, mode='terminal'); local = m.read(s, q)
    remote = isolated_read(m, s, q)
    torch.testing.assert_close(local.prediction, remote.prediction)
    ledger = model_ledger(m)
    assert ledger['parameter_bytes'] == sum(p.numel()*p.element_size() for p in m.parameters())
    before = model_identity(m)
    with torch.no_grad(): m.reader.output.bias.add_(1)
    assert model_identity(m) != before
    m.hidden_history = e.values
    with pytest.raises(ValueError, match='hidden'): model_identity(m)


def test_sign_is_derived_from_contrast_and_training_requires_continuous_labels():
    m = model(); e = events(); q = queries(e, [[8], [7]])
    contrast = replace(q, tasks=(('contrast',), ('contrast',)))
    sign = replace(q, tasks=(('change_sign',), ('change_sign',)))
    c = m(e, contrast, encode_mode='terminal'); s = m(e, sign, encode_mode='terminal')
    torch.testing.assert_close(s.prediction, c.prediction.sign())
    torch.testing.assert_close(s.diagnostics['continuous_prediction'], c.prediction)
    ep = Episode(e, sign, torch.ones_like(s.prediction), torch.ones(2, 1, dtype=torch.bool))
    with pytest.raises(ValueError, match='contrast'): m.loss(s, ep)


def test_binary_loss_uses_zero_labels_even_without_numeric_mass():
    m = model(); e = events(); q = queries(e, [[8], [7]])
    q = replace(q, key_features=torch.zeros_like(q.key_features), tasks=(('presence',), ('presence',)))
    out = m(e, q, encode_mode='terminal')
    ep = Episode(e, q, torch.zeros(2, 1, 1), torch.zeros(2, 1, dtype=torch.bool))
    loss = m.loss(out, ep)
    expected = torch.nn.functional.softplus(out.diagnostics['support_logit']).mean()
    torch.testing.assert_close(loss, expected)
    loss.backward()
    assert m.reader.support.bias.grad.abs().sum() > 0


def test_categorical_v32_logits_cross_entropy():
    from famjet.models.task_model import TaskModel
    from famjet.readers.structured import make_reader
    cfg = load_config(Path('configs/smoke.yaml'))
    cfg = replace(cfg, data=replace(cfg.data, key_dim=3, value_dim=32),
                  model=replace(cfg.model, K=3, J=2, precision='float64'))
    k = JetMemory(torch.tensor([[.1, 1.]], dtype=torch.float64), 3, 32, eps=cfg.model.epsilon,
                  support_floor=cfg.model.numerical_support_floor)
    r = make_reader('structured', dict(family='jet', anchors=2, key_dim=3, value_dim=32),
                    dict(key_dim=3), dict(width=128, hidden_layers=2)).double()
    m = TaskModel(k, r, cfg)
    e = events(); e = replace(e, values=e.values[..., :1].expand(-1, -1, 32).clone(),
                             observed=e.observed[..., :1].expand(-1, -1, 32).clone())
    q = replace(queries(e, [[8], [7]]), tasks=(('corrected_categorical',), ('random_binding',)))
    out = m(e, q, encode_mode='terminal')
    assert out.prediction is None and out.logits.shape == (2, 1, 32)
    ep = Episode(e, q, torch.tensor([[0], [31]]), torch.ones(2, 1, dtype=torch.bool))
    torch.testing.assert_close(m.loss(out, ep), torch.nn.functional.cross_entropy(out.logits[:, 0], ep.labels[:, 0]))
    from famjet.eval.isolation import isolated_read
    m.fit_statistics([replace(ep, metadata={'split': 'training'})])
    assert len(m.target_statistics['tasks']['corrected_categorical']['class_distribution']) == 32
    state = m.encode(e)
    torch.testing.assert_close(m.read(state, q).logits, isolated_read(m, state, q).logits)


@pytest.mark.parametrize('family', ['jet', 'bank'])
def test_fitted_prediction_units_and_shift(family):
    m = model(family, learned=True); n = model(family, learned=True); n.load_state_dict(m.state_dict())
    e = events(); q = queries(e, [[8, 12], [7, 14]])
    ep = Episode(e, q, torch.randn(2, 2, 2, dtype=torch.float64), torch.ones(2, 2, dtype=torch.bool), {'split': 'training'})
    # Identical represented dimensionless rates for the learned bank are obtained
    # by translating both log bounds; logits stay identical.
    n.kernel.rate_source.log_min -= math.log(1000)
    n.kernel.rate_source.log_max -= math.log(1000)
    ee = replace(e, timestamps=e.timestamps*1000 + 1234567, time_unit='ms')
    qq = replace(q, T=q.T*1000 + 1234567, age_start=q.age_start*1000, age_end=q.age_end*1000)
    m.fit_statistics([ep]); n.fit_statistics([replace(ep, events=ee, queries=qq)])
    torch.testing.assert_close(m(e, q, encode_mode='terminal').prediction,
                               n(ee, qq, encode_mode='terminal').prediction, atol=1e-10, rtol=1e-10)


@pytest.mark.parametrize('family', ['jet', 'bank'])
def test_native_task_isolation_preserves_learned_rate_bits(kernel_case, family):
    from famjet.eval.isolation import isolated_read
    dtype, device, tol = kernel_case
    m = model(family, learned=True, dtype=dtype, device=device)
    e = events(dtype, device); q = queries(e, [[8], [7]])
    s = m.encode(e, mode='terminal')
    remote = isolated_read(m, s, q)
    torch.testing.assert_close(m.read(s, q).prediction.cpu(), remote.prediction, rtol=tol[0], atol=tol[1])


def test_fixed_writer_has_no_projection_and_ignores_future_queries():
    m = model(); e = events(); s = m.encode(e, mode='terminal')
    direct = m.kernel.encode(e, mode='terminal')
    assert m.writer is None and m.query_map is None
    for key in ('z', 'h'): torch.testing.assert_close(s.payload[key], direct.payload[key])
    q = queries(e, [[9, 40], [8, 200]])
    m.read(s, q)
    for key in ('z', 'h'): torch.testing.assert_close(s.payload[key], direct.payload[key])


def test_configuration_dtype_and_rate_mismatch_rejected():
    from famjet.models.task_model import TaskModel
    m = model()
    cfg = configuration()
    with pytest.raises(ValueError, match='precision'):
        TaskModel(m.kernel, m.reader, replace(cfg, model=replace(cfg.model, precision='float32')))


def test_identity_and_isolation_do_not_consume_training_rng():
    from famjet.eval.isolation import model_identity, isolated_read
    m = model('bank', learned=True); e = events(); q = queries(e, [[8], [7]])
    s = m.encode(e)
    before = torch.random.get_rng_state().clone()
    model_identity(m)
    assert torch.equal(before, torch.random.get_rng_state())
    isolated_read(m, s, q)
    assert torch.equal(before, torch.random.get_rng_state())


def test_learned_query_map_rejects_invalid_raw_features():
    m = model(learned=True); e = events(); q = queries(e, [[8], [7]])
    q = replace(q, key_features=-q.key_features)
    with pytest.raises(ValueError, match='nonnegative'):
        m.read(m.encode(e), q)


def test_failed_fit_preserves_existing_reference_and_statistics():
    m = model(); e = events(); q = queries(e, [[8], [7]])
    ep = Episode(e, q, torch.randn(2, 1, 2, dtype=torch.float64), torch.ones(2, 1, dtype=torch.bool), {'split': 'training'})
    m.fit_statistics([ep])
    previous = m.kernel.t_ref
    # Legal empty query batch cannot fit preprocessing and must not partially refit.
    empty = queries(e, torch.empty(2, 0, dtype=torch.int64))
    ep0 = replace(ep, queries=empty, labels=torch.empty(2, 0, 2), supported=torch.empty(2, 0, dtype=torch.bool),
                  events=replace(e, timestamps=e.timestamps*100))
    with pytest.raises(ValueError, match='queries'): m.fit_statistics([ep0])
    assert m.kernel.t_ref == previous


def test_terminal_keeps_early_write_gradients_and_matches_stream():
    m = model('bank', learned=True); e = events(); q = queries(e, [[8], [7]])
    e.values.requires_grad_()
    terminal = m(e, q, encode_mode='terminal')
    terminal_loss = terminal.prediction.square().sum() + terminal.support.sum()
    params = [e.values, *m.parameters()]
    grads = torch.autograd.grad(terminal_loss, params)
    stream = m(e, q, encode_mode='stream')
    other = torch.autograd.grad(stream.prediction.square().sum() + stream.support.sum(), params)
    for a, b in zip(grads, other):
        assert torch.isfinite(a).all() and a.abs().sum() > 0
        torch.testing.assert_close(a, b, atol=1e-12, rtol=1e-12)
    assert grads[0][0, 0].abs().sum() > 0 and grads[0][0, 4].abs().sum() > 0
    assert grads[0][0, 5].abs().sum() == 0  # genuine no-write event


def test_uint64_ids_never_become_reader_features():
    m = model(learned=True); e = events(); q = queries(e, [[8], [7]])
    s = m.encode(e)
    before = m.read(s, q)
    changed = replace(q, key_ids=torch.full((2, 1), 2**64-1, dtype=torch.uint64))
    torch.testing.assert_close(m.read(s, changed).prediction, before.prediction, atol=0, rtol=0)


def test_fitted_static_statistics_survive_isolated_read():
    from famjet.eval.isolation import isolated_read
    m = model(); e = events(); q = queries(e, [[8], [7]])
    ep = Episode(e, q, torch.tensor([[[1., -2.]], [[3., 4.]]], dtype=torch.float64),
                 torch.ones(2, 1, dtype=torch.bool), {'split': 'training'})
    m.fit_statistics([ep]); state = m.encode(e)
    torch.testing.assert_close(m.read(state, q).prediction, isolated_read(m, state, q).prediction)


@pytest.mark.parametrize('kind', ['structured', 'generic_full', 'generic_contracted', 'fixed_scale', 'query_only'])
def test_no_queries_and_unknown_task_contract(kind):
    m = model(kind=kind); e = events(); s = m.encode(e)
    empty = queries(e, torch.empty(2, 0, dtype=torch.int64))
    assert m.read(s, empty).prediction.shape == (2, 0, 2)
    q = replace(queries(e, [[8], [7]]), tasks=(('invented',), ('mean',)))
    with pytest.raises(ValueError, match='unknown task'): m.read(s, q)


@pytest.mark.parametrize('family', ['jet', 'bank'])
def test_learned_rates_train_and_invalidate_snapshots(family):
    m = model(family, learned=True); e = events(); q = queries(e, [[8], [7]])
    s = m.encode(e, mode='terminal')
    m.read(s, q).prediction.square().sum().backward()
    gradient = m.kernel.rate_source.logits.grad
    assert torch.isfinite(gradient).all() and gradient.abs().sum() > 0
    with torch.no_grad(): m.kernel.rate_source.logits.add_(.01)
    with pytest.raises(ValueError, match='hash'): m.read(s, q)


@pytest.mark.parametrize('family', ['jet', 'bank'])
def test_frozen_inference_rates_cannot_masquerade_as_training(family):
    from famjet.eval.isolation import export_method, _reconstruct
    from famjet.models.task_model import TaskModel
    m = model(family, learned=True)
    frozen = _reconstruct(export_method(m), freeze_rates=True)
    assert frozen._frozen_rates and not hasattr(frozen.kernel, 'rate_source')
    assert frozen._parameter_hash() == m._parameter_hash()
    with pytest.raises(ValueError, match='rate mode'):
        TaskModel(frozen.kernel, frozen.reader, configuration(family, learned=True))
    with pytest.raises(ValueError, match='inference'):
        frozen.encode(events())


@pytest.mark.parametrize('field', ['fit_provenance', 'target_statistics'])
@pytest.mark.parametrize('operation', ['export', 'identity', 'ledger'])
def test_metadata_inventory_rejects_raw_history(field, operation):
    from famjet.eval.isolation import export_method, model_identity
    from famjet.eval.budgets import model_ledger
    m = model()
    setattr(m, field, {'raw_history': events().values.tolist()})
    call = {'export': export_method, 'identity': model_identity, 'ledger': model_ledger}[operation]
    with pytest.raises(ValueError, match='metadata|provenance|statistics'):
        call(m)


def test_full_run_config_is_not_retained_in_inference_model():
    from famjet.models.task_model import TaskModel
    from famjet.eval.isolation import export_method, _reconstruct
    m = model()
    # The input RunConfig may contain scientific Any fields, but its unrestricted
    # payload belongs to external RunContext and must not survive projection.
    cfg = configuration()
    cfg = replace(cfg, confirmation=replace(cfg.confirmation,
        metrics={'raw_history': events().values.tolist()}))
    n = TaskModel(m.kernel, m.reader, cfg)
    assert not hasattr(n, 'config')
    wire = export_method(n)
    assert 'confirmation' not in wire['schema']['inference_config']
    assert 'raw_history' not in str(wire)
    assert not hasattr(_reconstruct(wire), 'config')


def fitted_model():
    m = model(); e = events(); q = queries(e, [[8], [7]])
    ep = Episode(e, q, torch.tensor([[[1., -2.]], [[3., 4.]]], dtype=torch.float64),
                 torch.ones(2, 1, dtype=torch.bool), {'split': 'training'})
    m.fit_statistics([ep])
    return m


@pytest.mark.parametrize('field,key,value', [
    ('fit_provenance', 'history_count', True),
    ('fit_provenance', 'history_count', 2**1000),
    ('fit_provenance', 'history_identity_hash', 'a'*10000),
    ('fit_provenance', 't_ref', float('inf')),
    ('fit_provenance', 'reference_source', {'raw_history': [1, 2, 3]}),
    ('fit_provenance', 'writer_hash', 'not-a-digest'),
    ('target_statistics', 'schema_version', True),
    ('target_statistics', 'pooling', 'raw_history'*10000),
])
def test_closed_metadata_rejects_bad_scalars(field, key, value):
    from famjet.eval.isolation import export_method
    m = fitted_model()
    getattr(m, field)[key] = value
    with pytest.raises(ValueError, match='metadata|provenance|statistics'): export_method(m)


@pytest.mark.parametrize('key,value', [
    ('raw_history', [[1, 2]]*20),
    ('mean', [1.]*10000),
    ('mean', [[1.], [2.]]),
    ('mean', [1., float('nan')]),
    ('mean', [True, 2.]),
    ('coordinate_variance', [-1., 1.]),
    ('constant_coordinates', [0, 1]),
    ('class_distribution', [0.5, 0.5]),
    ('scale', float('inf')),
    ('count', 2**1000),
])
def test_closed_task_summaries_reject_unknown_or_oversized_nested_payloads(key, value):
    from famjet.eval.isolation import export_method
    m = fitted_model()
    m.target_statistics['tasks']['mean'][key] = value
    from famjet.provenance import canonical_hash
    try:
        m.fit_provenance['target_hash'] = canonical_hash(m.target_statistics)
    except ValueError:  # NaN/inf cannot have a valid canonical hash.
        pass
    with pytest.raises(ValueError, match='metadata|provenance|statistics'): export_method(m)


@pytest.mark.parametrize('location', ['provenance', 'statistics', 'task', 'inference', 'oversized_mean'])
def test_numeric_wire_reconstruction_rejects_hidden_metadata(location):
    from famjet.eval.isolation import export_method, _reconstruct
    m = fitted_model(); wire = export_method(m)
    if location == 'provenance':
        wire['schema']['fit_provenance']['raw_history'] = events().values.tolist()
    elif location == 'statistics':
        wire['schema']['target_statistics']['raw_history'] = events().values.tolist()
    elif location == 'task':
        wire['schema']['target_statistics']['tasks']['invented'] = {'raw_history': [1.]}
    elif location == 'oversized_mean':
        wire['schema']['target_statistics']['tasks']['mean']['mean'] = [1.]*10000
    else:
        wire['schema'].setdefault('inference_config', {})['confirmation'] = {'metrics': [1.]*10000}
    from famjet.provenance import canonical_hash
    wire['schema']['fit_provenance']['target_hash'] = canonical_hash(wire['schema']['target_statistics'])
    with pytest.raises(ValueError, match='schema|metadata|provenance|statistics|inference'):
        _reconstruct(wire)


@pytest.mark.parametrize('payload', [
    {'raw_history': [[1., 2.]]*100},
    {'schema_version': True, 'writer': 'fixed', 'rate_mode': 'fixed'},
    {'schema_version': 1, 'writer': 'fixed', 'rate_mode': {'history': [1.]}},
])
@pytest.mark.parametrize('operation', ['export', 'reconstruct', 'ledger'])
def test_inference_config_is_closed_at_every_boundary(payload, operation):
    from famjet.eval.isolation import export_method, _reconstruct
    from famjet.eval.budgets import model_ledger
    m = model()
    if operation == 'reconstruct':
        wire = export_method(m); wire['schema']['inference_config'] = payload
        call = lambda: _reconstruct(wire)
    else:
        m.inference_config = payload
        call = lambda: (export_method(m) if operation == 'export' else model_ledger(m))
    with pytest.raises(ValueError, match='schema|metadata|inference'): call()


@pytest.mark.parametrize('status', ['constant_numeric', 'unsupported_numeric', 'binary'])
def test_closed_fitted_metadata_roundtrips_all_training_statuses(status):
    from famjet.eval.isolation import export_method, _reconstruct, isolated_read
    m = model(); e = events(); q = queries(e, [[8], [7]])
    labels = torch.ones(2, 1, 2, dtype=torch.float64)
    supported = torch.zeros(2, 1, dtype=torch.bool) if status == 'unsupported_numeric' else torch.ones(2, 1, dtype=torch.bool)
    if status == 'binary':
        q = replace(q, tasks=(('presence',), ('presence',)))
        labels = torch.tensor([[[0.]], [[1.]]], dtype=torch.float64)
        supported = torch.zeros(2, 1, dtype=torch.bool)
    m.fit_statistics([Episode(e, q, labels, supported, {'split': 'training'})])
    wire = export_method(m); restored = _reconstruct(wire)
    assert restored.target_statistics == m.target_statistics
    assert restored.fit_provenance == m.fit_provenance
    state = m.encode(e)
    torch.testing.assert_close(m.read(state, q).prediction, isolated_read(m, state, q).prediction)
    # Validated wire metadata owns its copies rather than mutating fitted state.
    wire['schema']['fit_provenance']['history_count'] += 1
    assert m.fit_provenance['history_count'] == 2


def test_reader_budget_cannot_hide_oversized_scalar_history_from_ledger():
    from famjet.eval.budgets import model_ledger
    m = model()
    m.reader.schema['budget']['max_parameters'] = 2**1000
    with pytest.raises(ValueError, match='budget|schema|metadata'): model_ledger(m)
