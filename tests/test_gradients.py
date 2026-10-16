"""Independent derivative checks; wrong log-rate signs cannot pass these tests."""
import numpy as np
import pytest
import torch
from jet_fixtures import events, kernel_case


def test_normalized_derivative():
    from famjet.memory.jet import jet_terminal, contract_jet
    e = events(); rates = torch.tensor([[.07, .4]], dtype=torch.float64, requires_grad=True)
    p = torch.tensor([[[.2, .5, .3]], [[.4, .1, .5]]], dtype=torch.float64)
    f = contract_jet(jet_terminal(e, rates, 2), p, rates, 1e-8, 1e-12, 2.)
    for j in range(2):
        grad = torch.autograd.grad(f.diagnostics['r'][:, :, :, j].sum(), rates, retain_graph=True)[0][0, j]*rates[0, j]
        expected = f.diagnostics['dlog_rate_r'][:, :, :, j].sum()
        torch.testing.assert_close(grad, expected, rtol=1e-12, atol=1e-12)
        step = 1e-5
        vals = []
        for sign in (-1, 1):
            changed = rates.detach().clone(); changed[0, j] *= np.exp(sign*step)
            vals.append(contract_jet(jet_terminal(e, changed, 2), p, changed, 1e-8, 1e-12, 2.).diagnostics['r'][:, :, :, j].sum())
        torch.testing.assert_close((vals[1]-vals[0])/(2*step), expected, rtol=1e-8, atol=1e-8)


def test_direct_terminal_stream_gradients_and_central_difference(kernel_case):
    from famjet.memory.jet import JetMemory, jet_terminal
    from dataclasses import replace
    dtype, device, tol = kernel_case
    e = events(dtype, device); e.key_features.requires_grad_(); e.values.requires_grad_(); e.auxiliary['gate'].requires_grad_()
    rates = torch.tensor([[.07, .4]], dtype=dtype, device=device, requires_grad=True)
    args = (rates, e.auxiliary['gate'], e.key_features, e.values)
    def loss(z, h):
        return z.square().sum()*.03 + h.square().sum()*.07
    terminal = jet_terminal(e, rates, 2)
    # CPU FP64 reference consumes the exact represented candidate inputs.
    cpu_args = tuple(a.detach().cpu().double().requires_grad_() for a in args)
    cr, cg, ck, cv = cpu_args
    ce = replace(e, key_features=ck, values=cv, auxiliary={'gate': cg}, observed=e.observed.cpu(), present=e.present.cpu())
    reference_z = []; reference_h = []
    # Independent direct expression: scalar event sums, no candidate helpers.
    for row, n in enumerate(ce.lengths.tolist()):
        aug = torch.cat([cv[row, :n], torch.ones(n, 1, dtype=torch.float64)], -1)
        writes = ck[row, :n, :, None]*aug[:, None, :]*(cg[row, :n]*ce.observed[row, :n].all(-1))[:, None, None]
        d = cr[0, :, None]*(ce.timestamps[row, n-1]-ce.timestamps[row, :n]).double()[None]
        reference_z.append(torch.einsum('jn,nkv->jkv', torch.exp(-d), writes))
        reference_h.append(torch.einsum('jn,nkv->jkv', d*torch.exp(-d), writes))
    direct_loss = loss(torch.stack(reference_z)[:, None], torch.stack(reference_h)[:, None])
    ref = torch.autograd.grad(direct_loss, cpu_args, retain_graph=True)
    streamed = JetMemory(rates, 3, 2).encode(e)
    for scalar in (loss(terminal.z, terminal.h), loss(streamed.payload['z'], streamed.payload['h'])):
        actual = torch.autograd.grad(scalar, args, retain_graph=True)
        for a, b in zip(actual, ref):
            torch.testing.assert_close(a.cpu().double(), b, rtol=tol[0], atol=tol[1])
    # Probe one active entry of each input against central differences.
    if dtype != torch.float64:
        return  # FP64 central differences below; ordinary FP32 gradients above.
    for arg, grad, index in zip(args, ref, [(0, 0), (0, 2), (0, 2, 1), (0, 2, 1)]):
        step = 1e-5; original = arg[index].item(); vals = []
        for sign in (-1, 1):
            with torch.no_grad(): arg[index] = original + sign*step
            out = jet_terminal(e, rates, 2); vals.append(loss(out.z, out.h).item())
        with torch.no_grad(): arg[index] = original
        assert (vals[1]-vals[0])/(2*step) == pytest.approx(grad[index].item(), rel=1e-8, abs=1e-8)


def test_empty_unsupported_read_backward_is_finite(kernel_case):
    from famjet.memory.jet import JetState, contract_jet
    dtype, device, _ = kernel_case
    z = torch.zeros(1, 1, 2, 3, 3, dtype=dtype, device=device, requires_grad=True)
    h = torch.zeros_like(z, requires_grad=True)
    rates = torch.tensor([[.1, 1.]], dtype=dtype, device=device, requires_grad=True)
    p = torch.zeros(1, 1, 3, dtype=dtype, device=device, requires_grad=True)
    f = contract_jet(JetState(z, h), p, rates, 1e-8, 1e-12, 2.)
    assert not f.supported.any()
    total = f.values.sum() + f.diagnostics['mean_age'].sum() + f.diagnostics['dimensionless_age'].sum()
    for grad in torch.autograd.grad(total, (z, h, rates, p)):
        assert torch.isfinite(grad).all()


def test_epsilon_must_survive_state_dtype_conversion():
    from famjet.memory.jet import JetState, contract_jet
    z = torch.zeros(1, 1, 1, 1, 2)
    with pytest.raises(ValueError, match='eps'):
        contract_jet(JetState(z, z), torch.ones(1, 1, 1), torch.ones(1, 1), 1e-300, 0., 1.)
