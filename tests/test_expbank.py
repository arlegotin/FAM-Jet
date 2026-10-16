"""Distinct-pole controls: independent sums, bytes, rates and stream ownership."""
from dataclasses import replace
import math

import pytest
import torch

from jet_fixtures import events, queries, chunk, kernel_case


def bank_rates(dtype=torch.float64, device='cpu'):
    return torch.logspace(-2, 0, 8, dtype=torch.float64).to(device=device, dtype=dtype)[None]


def direct(e, rates):
    """Independent differentiable CPU FP64 event sum, not a bank helper."""
    out = []
    for b, n in enumerate(e.lengths.tolist()):
        writes = []
        for j in range(n):
            age = int(e.timestamps[b, n-1]) - int(e.timestamps[b, j])
            weight = torch.exp(-rates[0] * age)
            aug = torch.cat((e.values[b, j], e.values.new_ones(1)))
            impulse = e.key_features[b, j, :, None] * aug[None] * e.auxiliary['gate'][b, j]
            writes.append(weight[:, None, None] * impulse[None] * e.observed[b, j].all())
        out.append(torch.stack(writes).sum(0))
    return torch.stack(out)[:, None]


def test_equal_payload_and_metadata():
    from famjet.memory.expbank import ExpBankMemory
    from famjet.memory.jet import JetMemory
    jet = JetMemory(torch.ones(1, 4), 16, 8)
    bank = ExpBankMemory(bank_rates(torch.float32), 16, 8)
    js = jet.init_state(1, device='cpu', dtype='float32')
    bs = bank.init_state(1, device='cpu', dtype='float32')
    assert sum(js.payload[k].numel()*js.payload[k].element_size() for k in ('z', 'h')) == 4608
    assert bs.payload['z'].numel()*bs.payload['z'].element_size() == 4608
    assert bank.persistent_nbytes(bs) == jet.persistent_nbytes(js)
    for k in ('history_hash', 'time_unit_hash', 'last_event_id'):
        assert torch.equal(bs.payload[k], js.payload[k])
    assert bank.persistent_nbytes(bs) == 4737


def test_direct_stream_terminal_states_and_gradients(kernel_case):
    from famjet.memory.expbank import exp_terminal, ExpBankMemory
    dtype, device, tol = kernel_case
    e = events(dtype, device)
    e.key_features.requires_grad_(); e.values.requires_grad_(); e.auxiliary['gate'].requires_grad_()
    rates = bank_rates(dtype, device).requires_grad_()
    args = (rates, e.auxiliary['gate'], e.key_features, e.values)
    cr, cg, ck, cv = [x.detach().cpu().double().requires_grad_() for x in args]
    ce = replace(e, key_features=ck, values=cv, auxiliary={'gate': cg}, present=e.present.cpu(), observed=e.observed.cpu())
    reference = direct(ce, cr)
    refgrad = torch.autograd.grad(reference.square().sum()*.03, (cr, cg, ck, cv), retain_graph=True)
    outputs = [ExpBankMemory(rates, 3, 2).encode(e).payload['z']]
    outputs += [exp_terminal(e, rates, size) for size in (1, 2, 4, 6, 12)]
    for out in outputs:
        torch.testing.assert_close(out.cpu().double(), reference, rtol=tol[0], atol=tol[1])
        for actual, want in zip(torch.autograd.grad(out.square().sum()*.03, args, retain_graph=True), refgrad):
            torch.testing.assert_close(actual.cpu().double(), want, rtol=tol[0], atol=tol[1])


def test_bank_all_anchors_visible(kernel_case):
    from famjet.memory.expbank import ExpBankMemory
    dtype, device, tol = kernel_case
    e = events(dtype, device); rates = bank_rates(dtype, device)
    m = ExpBankMemory(rates, 3, 2)
    s = m.encode(e); q = queries(e, [[9, 20], [10, 30]])
    f = m.features(s, q)
    assert f.values.shape == (2, 2, 8*(2+3))
    assert f.diagnostics['u'].shape == (2, 2, 1, 8, 2)
    assert f.diagnostics['z'].shape == (2, 2, 1, 8)
    assert f.diagnostics['r'].shape == (2, 2, 1, 8, 2)
    refm = ExpBankMemory(rates.cpu().double(), 3, 2)
    refe = events()
    ref = refm.features(refm.encode(refe), queries(refe, [[9, 20], [10, 30]]))
    torch.testing.assert_close(f.values.cpu().double(), ref.values, rtol=tol[0], atol=tol[1])
    for j in range(8):
        torch.testing.assert_close(f.values.reshape(2, 2, 1, 8, 5)[:, :, :, j, :2], f.diagnostics['r'][:, :, :, j])
    assert f.supported.all()


def test_no_decay_is_explicit_and_retains_total_writes(kernel_case):
    from famjet.memory.expbank import ExpBankMemory, exp_terminal, contract_bank
    from famjet.memory.jet import JetMemory
    dtype, device, tol = kernel_case
    e = events(dtype, device); rates = torch.tensor([[0., .3]], dtype=dtype, device=device)
    with pytest.raises(ValueError): ExpBankMemory(rates, 3, 2)
    with pytest.raises(ValueError): exp_terminal(e, rates, 2)
    with pytest.raises(ValueError): JetMemory(rates, 3, 2)
    m = ExpBankMemory(rates, 3, 2, no_decay=True)
    s = m.encode(e); future = m.advance_copy(s, 10000)
    torch.testing.assert_close(s.payload['z'][:, :, 0], future.payload['z'][:, :, 0])
    expected = direct(e, torch.zeros_like(rates))[:, :, 0]
    torch.testing.assert_close(s.payload['z'][:, :, 0], expected, rtol=tol[0], atol=tol[1])
    f = contract_bank(s.payload['z'], queries(e, [[8], [7]]).key_features, rates, 1e-8, 1e-12, 1., no_decay=True)
    assert torch.isfinite(f.values).all()
    assert f.diagnostics['no_decay'][..., 0].all()
    assert not f.diagnostics['no_decay'][..., 1].any()
    for mode in ('stream', 'terminal'):
        torch.testing.assert_close(m.encode(e, mode=mode).payload['z'], exp_terminal(e, rates, 2, no_decay=True), rtol=tol[0], atol=tol[1])


def test_core_false_mask_decays_padding_preserves_and_has_no_scalar_ops(kernel_case):
    from famjet.memory.expbank import exp_step, validate_exp_step
    dtype, device, tol = kernel_case
    z = torch.ones(1, 1, 2, 1, 2, dtype=dtype, device=device)
    key = torch.ones(1, 1, 1, dtype=dtype, device=device)
    value = key.clone(); gate = key[..., 0]; rates = torch.ones(1, 2, dtype=dtype, device=device)
    mask = torch.zeros(1, dtype=torch.bool, device=device)
    for gap in (0., 2.):
        delta = torch.full((1,), gap, dtype=dtype, device=device)
        validate_exp_step(z, key, value, gate, delta, rates, mask)
        with torch.profiler.profile(activities=[torch.profiler.ProfilerActivity.CPU]) as prof:
            actual = exp_step(z, key, value, gate, delta, rates, mask)
        assert not {'aten::item', 'aten::is_nonzero', 'aten::_local_scalar_dense'} & {x.key for x in prof.key_averages()}
        torch.testing.assert_close(actual, z*math.exp(-gap), rtol=tol[0], atol=tol[1])


@pytest.mark.parametrize('bad', ['key', 'value', 'gate', 'delta', 'rates', 'state'])
def test_direct_validation_rejects_masked_nonfinite(bad):
    from famjet.memory.expbank import validate_exp_step
    args = [torch.ones(1, 1, 2, 1, 2, dtype=torch.float64), torch.ones(1, 1, 1, dtype=torch.float64),
            torch.ones(1, 1, 1, dtype=torch.float64), torch.ones(1, 1, dtype=torch.float64),
            torch.zeros(1, dtype=torch.float64), torch.ones(1, 2, dtype=torch.float64), torch.zeros(1, dtype=torch.bool)]
    args[{'state': 0, 'key': 1, 'value': 2, 'gate': 3, 'delta': 4, 'rates': 5}[bad]].fill_(float('nan'))
    with pytest.raises(ValueError): validate_exp_step(*args)


def test_stream_ownership_exact_time_padding_and_revalidation():
    from famjet.memory.expbank import ExpBankMemory
    e = events(); m = ExpBankMemory(bank_rates(), 3, 2)
    first = m.encode(chunk(e, 0, 3)); before = {k: v.clone() for k, v in first.payload.items()}
    m.features(first, queries(e, [[20, 3], [30, 7]])); m.advance_copy(first, 40)
    for mode in ('stream', 'terminal'):
        continued = m.encode(chunk(e, 3, 6), first, mode=mode)
        torch.testing.assert_close(continued.payload['z'], m.encode(e).payload['z'], rtol=1e-12, atol=1e-12)
        assert continued.last_time.tolist() == [8, 7] and continued.event_offset.tolist() == [6, 4]
    assert all(torch.equal(before[k], first.payload[k]) for k in before)
    with pytest.raises(ValueError, match='before'): m.advance_copy(m.encode(e), 1)
    shifted = replace(e, timestamps=e.timestamps+2**60)
    torch.testing.assert_close(m.encode(e).payload['z'], m.encode(shifted).payload['z'], rtol=1e-12, atol=1e-12)
    e.values[1, 5] = float('nan')
    with pytest.raises(ValueError, match='finite'): m.encode(e)


def test_empty_features_failure_and_safe_backward(kernel_case):
    from famjet.memory.expbank import ExpBankMemory, contract_bank
    dtype, device, _ = kernel_case
    m = ExpBankMemory(bank_rates(dtype, device), 3, 2)
    e = events(dtype, device); s = m.init_state(2, device=device, dtype=str(dtype).removeprefix('torch.'))
    f = m.features(s, queries(e, [[-1], [0]]))
    assert not f.supported.any() and torch.isfinite(f.values).all()
    empty = m.features(s, queries(e, torch.empty(2, 0, dtype=torch.int64)))
    assert empty.values.shape == (2, 0, 40)
    z = s.payload['z'].requires_grad_(); rates = m.rates.detach().requires_grad_()
    p = torch.zeros(2, 1, 3, dtype=dtype, device=device, requires_grad=True)
    f = contract_bank(z, p, rates, 1e-8, 1e-12, 1.)
    for grad in torch.autograd.grad(f.values.sum(), (z, p, rates)):
        assert torch.isfinite(grad).all()
    overflow = torch.full_like(z, torch.finfo(dtype).max)
    f = contract_bank(overflow, torch.ones_like(p)*2, rates, 1e-8, 1e-12, 1.)
    assert f.diagnostics['failure'].all() and not f.supported.any() and not f.values.any()
    with pytest.raises(ValueError, match='eps'): contract_bank(z.float(), p.float(), rates.float(), 1e-300, 0., 1.)


def test_bounded_rates_learned_handoff_and_collapsed_grid():
    from famjet.memory.expbank import BoundedRates, ExpBankMemory, log_rate_grid
    source = BoundedRates(8, -5., 1.).double()
    assert source().shape == (1, 8)
    assert ((source().log() > -5) & (source().log() < 1)).all()
    m = ExpBankMemory(source, 3, 2)
    e = events(); s = m.encode(e)
    assert any(p is source.logits for p in m.parameters())
    m.features(s, queries(e, [[9], [10]])).values.square().sum().backward()
    assert source.logits.grad is not None and torch.isfinite(source.logits.grad).all() and source.logits.grad.abs().sum() > 0
    assert m.parameter_nbytes() == source.logits.numel()*8
    with torch.no_grad(): source.logits.zero_()
    assert torch.unique(source()).numel() == 1  # coincidence permitted
    with pytest.raises(ValueError, match='parameter'): m.advance_copy(s, 40)
    collapsed = ExpBankMemory(source, 3, 2).encode(e).payload['z']
    torch.testing.assert_close(collapsed[:, :, 0], collapsed[:, :, 7])
    torch.testing.assert_close(log_rate_grid(3, -2., 0., dtype=torch.float64), torch.tensor([[math.exp(-2), math.exp(-1), 1.]], dtype=torch.float64))
    for args in [(0, -2., 1.), (2, 1., -2.), (2, float('nan'), 1.)]:
        with pytest.raises(ValueError): BoundedRates(*args)


def test_optional_finite_difference_converges_fp64():
    from famjet.memory.expbank import exp_terminal
    from famjet.memory.jet import jet_terminal
    e = events(); rate = .3
    want = jet_terminal(e, torch.tensor([[rate]], dtype=torch.float64), 2).h[:, :, 0]
    errors = []
    for spacing in (.1, .01, .001):
        rates = torch.tensor([[rate*math.exp(-spacing), rate*math.exp(spacing)]], dtype=torch.float64)
        z = exp_terminal(e, rates, 2)
        estimate = (z[:, :, 0]-z[:, :, 1])/(2*spacing)
        errors.append((estimate-want).abs().max().item())
    assert errors[1] < errors[0]/50 and errors[2] < errors[1]/50 and errors[2] < 1e-6


def test_huge_host_time_and_unit_invariance(kernel_case):
    from famjet.memory.expbank import ExpBankMemory
    dtype, device, tol = kernel_case
    e = events(dtype, device); m = ExpBankMemory(bank_rates(dtype, device), 3, 2, t_ref=2.)
    f = m.features(m.encode(e), queries(e, [[9, 20], [10, 30]]))
    scaled = replace(e, timestamps=e.timestamps*1000, time_unit='scaled')
    other = ExpBankMemory(m.rates/1000, 3, 2, t_ref=2000.)
    torch.testing.assert_close(f.values, other.features(other.encode(scaled), queries(scaled, [[9000, 20000], [10000, 30000]])).values, rtol=tol[0], atol=tol[1])
    tiny = ExpBankMemory(torch.tensor([[1e-30, 0.]], dtype=dtype, device=device), 3, 2, no_decay=True)
    s = tiny.encode(chunk(e, 0, 1)); future = tiny.advance_copy(s, 1e40)
    assert not future.payload['z'][:, :, 0].any()
    torch.testing.assert_close(future.payload['z'][:, :, 1], s.payload['z'][:, :, 1])


def test_native_grid_and_learned_rates(kernel_case):
    from famjet.memory.expbank import BoundedRates, ExpBankMemory, log_rate_grid
    dtype, device, tol = kernel_case
    grid = log_rate_grid(8, -5., 1., device=device, dtype=dtype)
    torch.testing.assert_close(grid.cpu().double(), torch.linspace(-5., 1., 8, dtype=torch.float64).exp()[None], rtol=tol[0], atol=tol[1])
    source = BoundedRates(8, -5., 1.).to(device=device, dtype=dtype)
    m = ExpBankMemory(source, 3, 2); e = events(dtype, device)
    m.encode(e).payload['z'].square().sum().backward()
    assert source.logits.grad is not None and torch.isfinite(source.logits.grad).all()


def test_bank_device_evidence_checker():
    from validation.expbank_checks import run_checks
    result = run_checks(include_mps=False)
    assert result['passed']
    assert {c['case'] for c in result['checks']} == {'cpu64', 'cpu32'}
    assert all(c['passed'] for c in result['checks'])
    assert len(result['finite_difference']) == 2


def test_bank_core_multihead_and_no_forced_sorting(kernel_case):
    from famjet.memory.expbank import exp_step, contract_bank, validate_exp_step
    dtype, device, tol = kernel_case
    # Two heads, deliberately unsorted and coincident poles; literal age-zero writes.
    rates = torch.tensor([[.3, .1, .3], [.2, .5, .1]], dtype=dtype, device=device)
    key = torch.tensor([[[1., 2.], [3., 1.]]], dtype=dtype, device=device)
    value = torch.tensor([[[2.], [-1.]]], dtype=dtype, device=device)
    gate = torch.tensor([[1., 2.]], dtype=dtype, device=device)
    z = torch.zeros(1, 2, 3, 2, 2, dtype=dtype, device=device)
    delta = torch.zeros(1, dtype=dtype, device=device); mask = torch.ones(1, dtype=torch.bool, device=device)
    validate_exp_step(z, key, value, gate, delta, rates, mask)
    z = exp_step(z, key, value, gate, delta, rates, mask)
    want = torch.tensor([[[[2., 1.], [4., 2.]]]*3, [[[-6., 6.], [-2., 2.]]]*3], dtype=dtype, device=device)[None]
    torch.testing.assert_close(z, want)
    q = torch.ones(1, 1, 2, 2, dtype=dtype, device=device)
    f = contract_bank(z, q, rates, 1e-8, 1e-12, 1.)
    assert f.values.shape == (1, 1, 24)
    torch.testing.assert_close(f.diagnostics['r'][0, 0, 0, :, 0], torch.full((3,), 6./(3.+1e-8), dtype=dtype, device=device), rtol=tol[0], atol=tol[1])
    torch.testing.assert_close(f.diagnostics['r'][0, 0, 1, :, 0], torch.full((3,), -8./(8.+1e-8), dtype=dtype, device=device), rtol=tol[0], atol=tol[1])


def test_bank_public_metadata_masks_and_negative_inputs():
    from famjet.memory.expbank import ExpBankMemory, exp_terminal, validate_exp_step
    e = events(); m = ExpBankMemory(bank_rates(), 3, 2)
    first = m.encode(chunk(e, 0, 3)); tail = chunk(e, 3, 6)
    with pytest.raises(ValueError, match='identity'): m.encode(replace(tail, history_ids=('other', 'b')), first)
    with pytest.raises(ValueError, match='time_unit'): m.encode(replace(tail, time_unit='seconds'), first)
    with pytest.raises(ValueError): exp_terminal(e, m.rates, 0)
    e.normalization = 'independent'
    with pytest.raises(ValueError, match='shared'): m.encode(e)
    e = events(); e.auxiliary['gate'][1, -1] = -1
    with pytest.raises(ValueError): m.encode(e)
    e = events(); s = m.encode(e); q = queries(e, [[9, 0], [10, 0]])
    q.present[:, 1] = False; q.lengths[:] = 1
    assert not m.features(s, q).supported[:, 1].any()
    q.key_features[:, 1] = float('nan')
    with pytest.raises(ValueError, match='finite'): m.features(s, q)
    for name in ('key', 'gate', 'delta', 'rates'):
        args = [torch.ones(1, 1, 1, 1, 2, dtype=torch.float64), torch.ones(1, 1, 1, dtype=torch.float64),
                torch.ones(1, 1, 1, dtype=torch.float64), torch.ones(1, 1, dtype=torch.float64),
                torch.zeros(1, dtype=torch.float64), torch.ones(1, 1, dtype=torch.float64), torch.zeros(1, dtype=torch.bool)]
        args[{'key': 1, 'gate': 3, 'delta': 4, 'rates': 5}[name]].fill_(-1)
        with pytest.raises(ValueError): validate_exp_step(*args, no_decay=True)


def test_bank_central_difference_for_every_input():
    from famjet.memory.expbank import exp_terminal
    e = events(); rates = bank_rates().requires_grad_()
    e.key_features.requires_grad_(); e.values.requires_grad_(); e.auxiliary['gate'].requires_grad_()
    args = (rates, e.auxiliary['gate'], e.key_features, e.values)
    def loss():
        return exp_terminal(e, rates, 2).square().sum()*.03
    grads = torch.autograd.grad(loss(), args)
    for x, grad, index in zip(args, grads, [(0, 2), (0, 2), (0, 2, 1), (0, 2, 1)]):
        old = x[index].item(); step = 1e-5; vals = []
        for sign in (-1, 1):
            with torch.no_grad(): x[index] = old + sign*step
            vals.append(loss().item())
        with torch.no_grad(): x[index] = old
        assert (vals[1]-vals[0])/(2*step) == pytest.approx(grad[index].item(), rel=1e-8, abs=1e-8)
