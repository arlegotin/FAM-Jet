"""Small arithmetic and policy checks; no numerical panel or optimizer campaign."""
from dataclasses import replace
from pathlib import Path
import inspect

import pytest
import torch

from famjet.types import EventBatch, QueryBatch
from validation.reader_adequacy_v1.contract import ReaderSpec, load_pinned_kernel
from validation.reader_adequacy_v1.reader import PrimaryReader, features
from validation.reader_adequacy_v1.checks import (
    direct_state, direct_features, recover_two_ages, explicit_network,
    analytic_ratio, group_losses, checkpoint_schedule, run_bounded_steps, admission,
    ResourceGuard,
)
from validation.reader_adequacy_v1.check_run import _launch_threads, THREAD_ENV


def small_case():
    key = torch.nn.functional.one_hot(torch.tensor([[3, 3, 3, 0]]), 16).to(torch.float64)
    values = torch.zeros(1, 4, 8, dtype=torch.float64)
    values[0, 0, 0], values[0, 1, 0], values[0, 2, 0] = 2., -1., 17.
    present = torch.tensor([[True, True, True, False]])
    observed = present[..., None].expand(1, 4, 8).clone()
    observed[0, 2] = False
    events = EventBatch(('small',), torch.arange(4)[None],
                        torch.tensor([[0., 1., 2., 2.]], dtype=torch.float64),
                        torch.tensor([[3, 3, 3, 0]]), key, values,
                        torch.tensor([3]), present, observed, 's')
    queries = QueryBatch(('small',), torch.arange(3)[None],
                         torch.tensor([[2., 3., 3.]], dtype=torch.float64),
                         torch.tensor([[3, 3, 0]]), key[:, [0, 0, 3]],
                         (('mean', 'contrast', 'mean'),),
                         torch.tensor([[0., 0., 0.]], dtype=torch.float64),
                         torch.tensor([[1., 2., 1.]], dtype=torch.float64),
                         torch.tensor([[True, True, False]]), torch.tensor([2]))
    return events, queries


@pytest.mark.parametrize('family', ('jet', 'bank'))
def test_direct_sum_catches_signed_no_write_and_delay(family):
    events, queries = small_case()
    kernel = load_pinned_kernel(family)
    snapshot = kernel.encode(events)
    z, h = direct_state(events, kernel.rates, queries.T, family=family)
    for j in range(2):
        actual = kernel._advance_payload(snapshot, queries.T[:, j].tolist(), [True])
        assert torch.allclose(z[:, j], actual['z'], atol=1e-12, rtol=1e-12)
        if family == 'jet':
            assert torch.allclose(h[:, j], actual['h'], atol=1e-12, rtol=1e-12)
    raw = direct_features(events, queries, kernel.rates, family=family, access='C')
    adapted = features(kernel, snapshot, queries, ReaderSpec(family, 'C', 128))
    assert torch.allclose(raw[:, :2], adapted.values[:, :2], atol=1e-12, rtol=1e-12)
    actual = PrimaryReader(ReaderSpec(family, 'C', 128)).read(kernel, snapshot, queries)
    assert raw.shape == (1, 3, 92)
    assert actual.diagnostics['prediction_valid'].tolist() == [[True, True, False]]
    assert raw[0, 0, 0] > raw[0, 1, 0]
    assert not torch.allclose(z[:, 0], -z[:, 0], atol=1e-12, rtol=1e-12)


@pytest.mark.parametrize('family', ('jet', 'bank'))
def test_whole_predictor_unit_and_public_shift_spot(family):
    events, queries = small_case()
    kernel = load_pinned_kernel(family)
    reader = PrimaryReader(ReaderSpec(family, 'C', 128))
    canonical = reader.read(kernel, kernel.encode(events), queries).prediction
    unit_events = replace(events, timestamps=events.timestamps*1000)
    unit_queries = replace(queries, T=queries.T*1000,
                           age_start=queries.age_start*1000,
                           age_end=queries.age_end*1000)
    reference = direct_features(unit_events, unit_queries, kernel.rates/1000,
                                family=family, access='C', t_ref=1000.)
    raw = direct_features(events, queries, kernel.rates, family=family, access='C')
    assert torch.allclose(raw, reference, atol=1e-12, rtol=1e-12)
    task = torch.tensor([[0, 1, 0]])
    transformed = reader.network((reference-reader.feature_mean)/reader.feature_scale)
    transformed = transformed*reader.target_scale[task]+reader.target_mean[task]
    assert torch.allclose(canonical[:, :2], transformed[:, :2], atol=1e-12, rtol=1e-12)
    shifted = reader.read(kernel, kernel.encode(replace(events, timestamps=events.timestamps+1024.)),
                          replace(queries, T=queries.T+1024.)).prediction
    assert torch.allclose(canonical, shifted, atol=1e-12, rtol=1e-12)


@pytest.mark.parametrize('family', ('jet', 'bank'))
def test_signed_cancellation_absence_and_padding_spot(family):
    module = __import__('validation.reader_adequacy_v1.checks', fromlist=['_edge_case_numerical'])
    errors = module._edge_case_numerical(load_pinned_kernel(family), family)
    assert errors and max(errors.values()) <= 1e-12


def test_partial_value_mask_rejected_before_encoding():
    events, _ = small_case()
    observed = events.observed.clone()
    observed[0, 0, 1] = False
    with pytest.raises(ValueError, match='partial value observation'):
        direct_state(replace(events, observed=observed), torch.ones(1, 1, dtype=torch.float64),
                     torch.tensor([[3.]], dtype=torch.float64), family='jet')


def test_two_by_two_reconstruction_and_wrong_sign():
    old = torch.tensor([1.2, -0.7], dtype=torch.float64)
    recent = torch.tensor([-0.4, 0.9], dtype=torch.float64)
    a, b = 0.3, 0.8
    first = a*old + recent
    second = b*old + recent
    got_old, got_recent = recover_two_ages(first, second, a, b)
    assert torch.allclose(got_old, old, atol=1e-12, rtol=1e-12)
    assert torch.allclose(got_recent, recent, atol=1e-12, rtol=1e-12)
    with pytest.raises(AssertionError):
        assert torch.allclose(got_old, -old, atol=1e-12, rtol=1e-12)


def test_analytic_ratio_and_derivative_sign():
    u = torch.tensor([3., -1.], dtype=torch.float64)
    h = torch.tensor([2., -4.], dtype=torch.float64)
    r, derivative = analytic_ratio(u, h, 2., 5., 1e-8)
    assert torch.allclose(r, u/(2.+1e-8), atol=1e-12, rtol=1e-12)
    assert torch.allclose(derivative, (r*5.-h)/(2.+1e-8), atol=1e-12, rtol=1e-12)
    with pytest.raises(AssertionError):
        assert torch.allclose(derivative, (h-r*5.)/(2.+1e-8), atol=1e-12, rtol=1e-12)


def test_explicit_silu_chain_matches_autograd():
    with torch.random.fork_rng(devices=[]):
        torch.manual_seed(42)
        reader = PrimaryReader(ReaderSpec('bank', 'C', 128))
    x = torch.linspace(-1., 1., 92, dtype=torch.float64)[None, None].requires_grad_()
    module = __import__('validation.reader_adequacy_v1.checks', fromlist=['_exported_layers'])
    weights = module._exported_layers(reader)
    live_weights = tuple(reader.network[i] for i in (0, 2, 4))
    manual, dx, dw0, dw2, dw1 = explicit_network(x.detach(), weights)
    output = reader.network(x)
    output.sum().backward()
    assert torch.allclose(manual, output, atol=1e-12, rtol=1e-12)
    assert torch.allclose(dx, x.grad, atol=1e-12, rtol=1e-12)
    assert torch.allclose(dw0, live_weights[0].weight.grad, atol=1e-12, rtol=1e-12)
    assert torch.allclose(dw1, live_weights[1].weight.grad, atol=1e-12, rtol=1e-12)
    assert torch.allclose(dw2, live_weights[2].weight.grad, atol=1e-12, rtol=1e-12)
    assert torch.count_nonzero(dw0) and torch.count_nonzero(dw2)


def test_group_loss_requires_all_32_non_degenerate_groups():
    labels = torch.ones(4, 64, 8, dtype=torch.float64)
    with pytest.raises(ValueError, match='degenerate'):
        group_losses(labels, labels)
    labels[0] += 1
    losses = group_losses(labels, labels)
    assert len(losses) == 32 and max(losses.values()) == 0


def test_fixed_checkpoint_and_injected_step_recording():
    assert checkpoint_schedule() == tuple(range(0, 4097, 128))
    calls = []
    def step(n):
        calls.append(n)
    def evaluate(n):
        return {'maximum': 0. if n == 256 else 1., 'passed': n == 256}
    records = run_bounded_steps(step, evaluate, lambda: None)
    assert calls == list(range(1, 257))
    assert [r['step'] for r in records] == [0, 128, 256]
    module = __import__('validation.reader_adequacy_v1.checks', fromlist=['tiny_fit'])
    source = inspect.getsource(module.tiny_fit)+inspect.getsource(module._physical)
    for phrase in ('torch.optim.AdamW(parameters, lr=0.003', 'betas=(0.9, 0.999)',
                   'eps=1e-8, weight_decay=0.', 'clip_grad_norm_(parameters, 1.',
                   '_physical(reader, raw[index], task[index])',
                   'reader.target_scale'):
        assert phrase in source


def test_admission_expiry_and_resource_failure(tmp_path):
    assert admission(3*2**30, 5*2**30)
    assert not admission(2*2**30-1, 5*2**30)
    assert not admission(3*2**30, 4*2**30-1)
    guard = ResourceGuard(tmp_path, start=10., deadline=20., baseline_rss=100,
                          sample=lambda: (110, 120), clock=lambda: 19.)
    guard.check()
    guard.clock = lambda: 20.
    with pytest.raises(RuntimeError, match='deadline'):
        guard.check()
    guard.clock = lambda: 19.
    guard.sample = lambda: (100+2**30+1, 0)
    with pytest.raises(RuntimeError, match='RSS'):
        guard.check()


def test_zero_query_direct_sum_and_features():
    events, queries = small_case()
    empty = replace(queries, query_ids=queries.query_ids[:, :0], T=queries.T[:, :0],
                    key_ids=queries.key_ids[:, :0], key_features=queries.key_features[:, :0],
                    tasks=((),), age_start=queries.age_start[:, :0],
                    age_end=queries.age_end[:, :0], present=queries.present[:, :0],
                    lengths=torch.tensor([0]))
    kernel = load_pinned_kernel('jet')
    z, h = direct_state(events, kernel.rates, empty.T, family='jet')
    assert z.shape == h.shape == (1, 0, 1, 4, 16, 9)
    assert direct_features(events, empty, kernel.rates, family='jet', access='C').shape == (1, 0, 92)


def test_launcher_thread_environment_fails_closed(monkeypatch):
    for name in THREAD_ENV:
        monkeypatch.setenv(name, '1')
    _launch_threads()
    monkeypatch.setenv('MKL_NUM_THREADS', '2')
    with pytest.raises(RuntimeError, match='launcher'):
        _launch_threads()
