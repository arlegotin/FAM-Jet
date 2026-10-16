import numpy as np
import pytest
import torch
from jet_fixtures import events, kernel_case


def test_jet_direct_sum(kernel_case):
    from famjet.memory.jet import JetMemory, jet_terminal
    from famjet.memory.oracle import direct_moments
    dtype, device, (rtol, atol) = kernel_case
    e = events(dtype, device); rates = torch.tensor([[.01, .1, 1.]], dtype=dtype, device=device)
    m = JetMemory(rates, 3, 2)
    streamed = m.encode(e)
    for c in (1, 2, 4, 6, 20):
        terminal = jet_terminal(e, rates, c)
        for row, length in enumerate(e.lengths.tolist()):
            keys = e.key_features[row, :length].cpu().double().numpy()
            vals = e.values[row, :length].cpu().double().numpy()
            aug = np.concatenate([vals, np.ones((length, 1))], -1)
            gates = e.auxiliary['gate'][row, :length].cpu().double().numpy()
            gates *= e.observed[row, :length].all(-1).cpu().numpy()
            writes = keys[:, :, None] * aug[:, None, :] * gates[:, None, None]
            z, h = direct_moments(e.timestamps[row, :length].numpy(), writes, rates[0].cpu().double().numpy(), e.timestamps[row, length-1].item())
            np.testing.assert_allclose(terminal.z[row, 0].cpu().double().numpy(), z, rtol=rtol, atol=atol)
            np.testing.assert_allclose(terminal.h[row, 0].cpu().double().numpy(), h, rtol=rtol, atol=atol)
            np.testing.assert_allclose(streamed.payload['z'][row, 0].cpu().double().numpy(), z, rtol=rtol, atol=atol)
            np.testing.assert_allclose(streamed.payload['h'][row, 0].cpu().double().numpy(), h, rtol=rtol, atol=atol)


def test_old_z_used_for_h(kernel_case):
    from famjet.memory.jet import JetState, jet_step
    dtype, device, tol = kernel_case
    zeros = torch.zeros(1, 2, 2, 1, 2, dtype=dtype, device=device)
    state = JetState(zeros, zeros.clone())
    rates = torch.tensor([[.5, 1.], [2., 3.]], dtype=dtype, device=device)
    key = torch.ones(1, 2, 1, dtype=dtype, device=device)
    value = torch.tensor([[[2.], [4.]]], dtype=dtype, device=device)
    gate = torch.ones(1, 2, dtype=dtype, device=device)
    first = jet_step(state, key, value, gate, torch.zeros(1, dtype=dtype, device=device), rates, torch.ones(1, dtype=torch.bool, device=device))
    assert not first.h.any()  # new impulses have exactly zero age
    second = jet_step(first, key, value, gate, torch.ones(1, dtype=dtype, device=device), rates, torch.ones(1, dtype=torch.bool, device=device))
    expected = first.z * (rates * torch.exp(-rates))[None, :, :, None, None]
    torch.testing.assert_close(second.h, expected, rtol=tol[0], atol=tol[1])
    wrong_new_z = second.z * (rates * torch.exp(-rates))[None, :, :, None, None]
    assert not torch.allclose(expected, wrong_new_z)
    assert not torch.allclose(second.h, -expected)  # wrong-sign control


def test_zero_gap_is_additive_and_gap_without_write(kernel_case):
    from famjet.memory.jet import JetState, jet_step
    dtype, device, tol = kernel_case
    z = torch.ones(1, 1, 1, 1, 2, dtype=dtype, device=device)
    state = JetState(z, z*2)
    key = torch.ones(1, 1, 1, dtype=dtype, device=device)
    value = key*3; gate = key[..., 0]; rates = gate
    active = torch.ones(1, device=device, dtype=torch.bool)
    zero = jet_step(state, key, value, gate, gate[:, 0]*0, rates, active)
    torch.testing.assert_close(zero.z, torch.tensor([[[[[4., 2.]]]]], dtype=dtype, device=device))
    assert torch.equal(zero.h, state.h)
    gap = jet_step(state, key, value, gate*0, gate[:, 0]*2, rates, active)
    torch.testing.assert_close(gap.z, z*np.exp(-2), rtol=tol[0], atol=tol[1])
    torch.testing.assert_close(gap.h, z*4*np.exp(-2), rtol=tol[0], atol=tol[1])
    padding = jet_step(state, key, value, gate, gate[:, 0]*2, rates, ~active)
    assert torch.equal(padding.z, state.z) and torch.equal(padding.h, state.h)


def test_extreme_positive_product_decays_finitely(kernel_case):
    from famjet.memory.jet import JetState, jet_step
    dtype, device, _ = kernel_case
    limit = torch.finfo(dtype).max
    z = torch.ones(1, 1, 1, 1, 2, dtype=dtype, device=device)
    key = torch.ones(1, 1, 1, dtype=dtype, device=device)
    out = jet_step(JetState(z, z), key, key, key[..., 0]*0,
        torch.tensor([limit], device=device, dtype=dtype), torch.tensor([[limit]], device=device, dtype=dtype), torch.ones(1, dtype=torch.bool, device=device))
    assert torch.isfinite(out.z).all() and torch.isfinite(out.h).all()
    assert not out.z.any() and not out.h.any()


def test_laguerre_independent_recurrence(kernel_case):
    from famjet.memory.jet import JetState, jet_step, contract_jet
    from famjet.memory.coordinates import laguerre_step, to_laguerre, from_laguerre
    dtype, device, tol = kernel_case
    e = events(dtype, device); rates = torch.tensor([[.01, .1, 1.]], dtype=dtype, device=device)
    zero = torch.zeros(2, 1, 3, 3, 3, dtype=dtype, device=device)
    state = JetState(zero, zero.clone()); l0, l1 = to_laguerre(state)
    for t in range(6):
        delta = torch.zeros(2, dtype=dtype, device=device) if not t else (e.timestamps[:, t] - e.timestamps[:, t-1]).clamp_min(0).to(device, dtype)
        args = (e.key_features[:, t, None], e.values[:, t, None], (e.auxiliary['gate'][:, t]*e.observed[:, t].all(-1))[:, None], delta, rates, e.present[:, t])
        state = jet_step(state, *args)
        l0, l1 = laguerre_step(l0, l1, *args)
    recovered = from_laguerre(l0, l1)
    torch.testing.assert_close(recovered.z, state.z, rtol=tol[0], atol=tol[1])
    torch.testing.assert_close(recovered.h, state.h, rtol=tol[0], atol=tol[1])
    p = torch.ones(2, 2, 3, device=device, dtype=dtype)
    for field in ('values', 'supported'):
        a = getattr(contract_jet(state, p, rates, 1e-8, 1e-12, 2.), field)
        b = getattr(contract_jet(recovered, p, rates, 1e-8, 1e-12, 2.), field)
        torch.testing.assert_close(a, b, rtol=tol[0], atol=tol[1])


def test_simultaneous_permutations_and_epsilon_mass_scaling():
    from famjet.memory.jet import JetMemory, contract_jet, JetState
    e = events(); e.timestamps.zero_(); e.observed[:] = e.present[:, :, None]
    m = JetMemory(torch.tensor([[.1, 1.]], dtype=torch.float64), 3, 2)
    a = m.encode(e)
    for name in ('key_features', 'values', 'observed'):
        getattr(e, name)[0] = getattr(e, name)[0].flip(0)
    e.auxiliary['gate'][0] = e.auxiliary['gate'][0].flip(0)
    b = m.encode(e)
    torch.testing.assert_close(a.payload['z'], b.payload['z'], rtol=1e-12, atol=1e-12)
    assert not a.payload['h'].any()
    state = JetState(a.payload['z'], a.payload['h'])
    p = torch.ones(2, 1, 3, dtype=torch.float64)
    base = contract_jet(state, p, m.rates, .1, 1e-12, 2.)
    scaled = contract_jet(JetState(state.z*7, state.h*7), p, m.rates, .7, 7e-12, 2.)
    for name in ('r', 'dlog_rate_r', 'smoothed_age', 'dimensionless_age', 'mean_age'):
        torch.testing.assert_close(base.diagnostics[name], scaled.diagnostics[name], rtol=1e-12, atol=1e-12)


def test_signed_cancellation_and_supported_exact_ages(kernel_case):
    from famjet.memory.jet import JetMemory
    from jet_fixtures import queries, chunk
    dtype, device, tol = kernel_case
    e = chunk(events(dtype, device), 0, 2)
    e.timestamps[:] = torch.tensor([0, 1]); e.key_features[:] = 1
    e.values[:, 0] = 1; e.values[:, 1] = -np.exp(-1)
    e.auxiliary['gate'][:] = 1
    m = JetMemory(torch.ones(1, 1, dtype=dtype, device=device), 3, 2, support_floor=.01)
    f = m.features(m.encode(e), queries(e, [[1], [1]]))
    torch.testing.assert_close(f.diagnostics['r'], torch.zeros_like(f.diagnostics['r']), rtol=tol[0], atol=tol[1])
    assert f.supported.all()
    expected_age = 1/(1+np.e)
    torch.testing.assert_close(f.diagnostics['dimensionless_age'], torch.full_like(f.diagnostics['z'], expected_age), rtol=tol[0], atol=tol[1])
    assert (f.diagnostics['dlog_rate_r'] < 0).all()


@pytest.mark.parametrize('name,bad', [('rate', 0.), ('rate', -1.), ('rate', float('nan')), ('rate', float('inf')), ('gap', -1.), ('gap', float('nan')), ('gap', float('inf')), ('key', -1.), ('gate', -1.), ('value', float('nan'))])
def test_core_rejects_invalid_inputs_before_multiplication(name, bad):
    from famjet.memory.jet import JetState, jet_step
    z = torch.zeros(1, 1, 1, 1, 2, dtype=torch.float64)
    args = {'rate': torch.ones(1, 1, dtype=torch.float64), 'gap': torch.zeros(1, dtype=torch.float64),
            'key': torch.ones(1, 1, 1, dtype=torch.float64), 'value': torch.ones(1, 1, 1, dtype=torch.float64),
            'gate': torch.zeros(1, 1, dtype=torch.float64)}
    args[name].fill_(bad)
    with pytest.raises(ValueError):
        jet_step(JetState(z, z), args['key'], args['value'], args['gate'], args['gap'], args['rate'], torch.zeros(1, dtype=torch.bool))


def test_jet_device_evidence_checker():
    from validation.jet_checks import run_checks
    result = run_checks(include_mps=False)
    from famjet.provenance import canonical_json
    canonical_json(result)
    assert result['seed'] == 20261016
    for row in result['checks']:
        assert row['passed']
        assert row['max_tolerance_ratio'] <= 1


def test_nonfinite_read_has_failure_flag_and_zero_structured_output():
    from famjet.memory.jet import JetState, contract_jet
    z = torch.full((1, 1, 1, 1, 2), torch.finfo(torch.float32).max)
    f = contract_jet(JetState(z, z*0), torch.ones(1, 1, 1), torch.ones(1, 1), torch.finfo(torch.float32).max, 0., 1.)
    assert f.diagnostics['failure'].item() and not f.supported.item()
    assert not f.values.any()


def test_direct_moments_fixture():
    from famjet.memory.oracle import direct_moments
    z,h=direct_moments(np.array([0,1]),np.array([[[2.,1.]],[[6.,1.]]]),np.array([1.]),2.)
    np.testing.assert_allclose(z,[[[2*np.exp(-2)+6*np.exp(-1),np.exp(-2)+np.exp(-1)]]],rtol=1e-14)
    np.testing.assert_allclose(h,[[[4*np.exp(-2)+6*np.exp(-1),2*np.exp(-2)+np.exp(-1)]]],rtol=1e-14)
    assert z.dtype==h.dtype==np.float64


def test_direct_empty_and_invalid():
    from famjet.memory.oracle import direct_moments
    assert direct_moments(np.array([]),np.empty((0,2,3)),np.array([1.]),2)[0].shape==(1,2,3)
    for times,writes,rates,T in [([3],[[1]],[1],2),([0],[[np.nan]],[1],2),([0],[[1]],[0],2)]:
        with pytest.raises(ValueError):
            direct_moments(np.array(times),np.array(writes),np.array(rates),T)


def test_relative_error():
    from famjet.eval.metrics import relative_error
    assert relative_error(np.array([3.,4.]),np.array([0.,0.])) == float('inf')
    assert relative_error(np.zeros(2),np.zeros(2)) == 0
    assert relative_error(np.array([3.,4.]),np.array([0.,5.])) == pytest.approx(np.sqrt(10)/5)


def test_standalone_numerical_diagnostics():
    from validation.numerical_checks import run_checks
    r=run_checks()
    assert r['seed']==20261013
    assert r['direct_recurrent']['z'] < 1e-12
    assert r['direct_recurrent']['h'] < 1e-12
    assert r['equivalent_coordinates']['h'] < 1e-12
    assert r['normalized_log_derivative_error'] < 1e-8
    assert len(r['finite_difference_spacings'])==6
    assert r['hermite']['minimum']==pytest.approx(-.135026,abs=1e-5)
