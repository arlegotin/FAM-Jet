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
    ResourceGuard, fixture_target_stats, new_campaign_progress, run_arm_inventory,
)
from validation.reader_adequacy_v1.check_run import _launch_threads, THREAD_ENV, _publish_start
from famjet.artifacts import atomic_json
import json


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


def test_fixture_task_scales_are_distinct_pooled_population_scalars():
    labels = torch.empty(4, 64, 8, dtype=torch.float64)
    labels[:, :32] = torch.tensor([-1., 1., -1., 1.])[:, None, None]
    labels[:, 32:] = torch.tensor([-2., 2., -2., 2.])[:, None, None]
    coordinate_offsets = 10*torch.arange(8, dtype=torch.float64)
    labels += coordinate_offsets
    means, scales = fixture_target_stats(labels)
    assert means.shape == (2, 8) and torch.equal(means, coordinate_offsets[None].expand(2, -1))
    assert scales.shape == (2, 1) and torch.equal(scales, torch.tensor([[1.], [2.]], dtype=torch.float64))
    losses = group_losses(labels+1., labels)
    assert all(losses[f'mean:{key:02d}'] == 1. for key in range(16))
    assert all(losses[f'contrast:{key:02d}'] == .25 for key in range(16))


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
                   'reader.target_scale', 'fixture_scale[task[index]]',
                   'run_arm_inventory(execute, budget)', 'on_checkpoint=checkpoint',
                   '_attempt_optimizer_step(optimizer, arm, n)'):
        assert phrase in source


def test_raising_optimizer_call_is_charged_before_completion():
    module = __import__('validation.reader_adequacy_v1.checks', fromlist=['_attempt_optimizer_step'])
    class RaisingOptimizer:
        def step(self):
            raise RuntimeError('partial optimizer call')
    arm = {'optimizer_steps_attempted': 0, 'optimizer_steps_completed': 0}
    with pytest.raises(RuntimeError, match='partial optimizer call'):
        module._attempt_optimizer_step(RaisingOptimizer(), arm, 1)
    assert arm == {'optimizer_steps_attempted': 1, 'optimizer_steps_completed': 0}


def test_initial_status_and_closed_inventory_are_durable(tmp_path):
    progress = new_campaign_progress('numerical_then_tiny_fit')
    _publish_start(tmp_path, {'status': 'RUNNING', 'phase': 'admission'}, progress)
    assert json.loads((tmp_path/'status.json').read_text())['phase'] == 'admission'
    saved = json.loads((tmp_path/'progress.json').read_text())
    assert len(saved['tiny_fit']['arms']) == 6
    assert all(arm['status'] == 'NOT_RUN' for arm in saved['tiny_fit']['arms'])
    assert len(saved['numerical']['terminal_cells']) == 12


def test_completed_cell_is_durable_before_numerical_return(tmp_path):
    module = __import__('validation.reader_adequacy_v1.checks', fromlist=['_record_terminal_cell'])
    path = tmp_path/'progress.json'
    budget = ResourceGuard(tmp_path, start=0., deadline=20., baseline_rss=0,
                           sample=lambda: (0, 0), clock=lambda: 1.,
                           publish=lambda value: atomic_json(path, value))
    budget.progress = new_campaign_progress('numerical_then_tiny_fit')
    completed = {'length': 128, 'regime': 'piecewise_stationary',
                 'episode_id': 't18ra1-check-128-piecewise_stationary',
                 'status': 'PASS', 'families': {'jet': {'errors': {'z': 0.}}}}
    module._record_terminal_cell(budget, 0, completed)
    saved = json.loads(path.read_text())
    assert saved['numerical']['terminal_cells'][0] == completed
    assert saved['numerical']['terminal_cells'][1]['status'] == 'NOT_RUN'


def test_setup_failure_preserves_full_inventory_and_unavailable_fields(tmp_path):
    progress_path = tmp_path/'progress.json'
    budget = ResourceGuard(tmp_path, start=0., deadline=20., baseline_rss=0,
                           sample=lambda: (0, 0), clock=lambda: 1.,
                           publish=lambda value: atomic_json(progress_path, value))
    budget.progress = new_campaign_progress('numerical_then_tiny_fit')
    def executor(arm, _):
        if arm['family'] == 'jet' and arm['access'] == 'C' and arm['width'] == 128:
            raise ValueError('setup failed')
        arm['status'] = 'PASS'
    run_arm_inventory(executor, budget)
    arms = json.loads(progress_path.read_text())['tiny_fit']['arms']
    assert len(arms) == 6 and arms[0]['status'] == 'FAIL'
    assert arms[0]['optimizer_steps_completed'] == 0
    assert arms[0]['feature_sha256'] is None and arms[0]['static_hash'] is None
    assert arms[0]['unavailable']['feature_sha256']
    assert all(arm['status'] == 'PASS' for arm in arms[1:])


def test_update_failure_retains_exact_completed_steps_and_durable_checkpoints(tmp_path):
    progress_path = tmp_path/'progress.json'
    budget = ResourceGuard(tmp_path, start=0., deadline=20., baseline_rss=0,
                           sample=lambda: (0, 0), clock=lambda: 1.,
                           publish=lambda value: atomic_json(progress_path, value))
    budget.progress = new_campaign_progress('numerical_then_tiny_fit')
    def executor(arm, guard):
        if arm['family'] == 'jet' and arm['access'] == 'C' and arm['width'] == 128:
            arm['writer_hash'] = 'a'*64
            arm['feature_sha256'] = 'b'*64
            arm['parameter_count'] = 29448
            arm['first_weight_count'] = 11776
            arm['last_weight_count'] = 1024
            arm['static_hash'] = 'c'*64
            guard.persist_progress()
            for n in range(1, 8):
                arm['optimizer_steps_completed'] = n
            raise FloatingPointError('update failed')
        arm['status'] = 'PASS'
    run_arm_inventory(executor, budget)
    saved = json.loads(progress_path.read_text())['tiny_fit']['arms']
    assert saved[0]['optimizer_steps_completed'] == 7
    assert saved[0]['writer_hash'] == 'a'*64 and saved[0]['static_hash'] == 'c'*64
    assert saved[0]['parameter_count'] == 29448
    assert len(saved) == 6


def test_resource_abort_blocks_remaining_arms_and_active_state_survives_hard_stop(tmp_path):
    progress_path = tmp_path/'progress.json'
    budget = ResourceGuard(tmp_path, start=0., deadline=20., baseline_rss=0,
                           sample=lambda: (0, 0), clock=lambda: 1.,
                           publish=lambda value: atomic_json(progress_path, value))
    budget.progress = new_campaign_progress('numerical_then_tiny_fit')
    def hard_stop(arm, _):
        assert json.loads(progress_path.read_text())['tiny_fit']['arms'][0]['status'] == 'ACTIVE'
        raise KeyboardInterrupt
    with pytest.raises(KeyboardInterrupt):
        run_arm_inventory(hard_stop, budget)
    interrupted = json.loads(progress_path.read_text())['tiny_fit']['arms']
    assert interrupted[0]['status'] == 'ACTIVE'
    assert interrupted[0]['interrupted_unknown_range'] == [0, 128]
    assert all(arm['status'] == 'NOT_RUN' for arm in interrupted[1:])
    abort_path = tmp_path/'abort-progress.json'
    aborted_budget = ResourceGuard(tmp_path, start=0., deadline=20., baseline_rss=0,
                                   sample=lambda: (0, 0), clock=lambda: 1.,
                                   publish=lambda value: atomic_json(abort_path, value))
    aborted_budget.progress = new_campaign_progress('numerical_then_tiny_fit')
    aborted_budget.check = lambda: (_ for _ in ()).throw(RuntimeError('campaign deadline reached'))
    run_arm_inventory(lambda *_: None, aborted_budget)
    aborted = json.loads(abort_path.read_text())['tiny_fit']['arms']
    assert aborted[0]['status'] == 'FAIL'
    assert all(arm['status'] == 'BLOCKED' for arm in aborted[1:])


def test_checkpoint_observation_is_durable_before_hard_stop(tmp_path):
    progress_path = tmp_path/'progress.json'
    budget = ResourceGuard(tmp_path, start=0., deadline=20., baseline_rss=0,
                           sample=lambda: (0, 0), clock=lambda: 1.,
                           publish=lambda value: atomic_json(progress_path, value))
    budget.progress = new_campaign_progress('numerical_then_tiny_fit')
    arm = budget.progress['tiny_fit']['arms'][0]
    arm['status'] = 'ACTIVE'
    budget.persist_progress()
    def step(n):
        if n == 130:
            raise KeyboardInterrupt
    def evaluate(n):
        return {'maximum': 1., 'passed': False}
    def checkpoint(n, _):
        arm['optimizer_steps_completed'] = n
        arm['last_durable_step'] = n
        arm['interrupted_unknown_range'] = [n, min(n+128, 4096)]
        budget.persist_progress()
    with pytest.raises(KeyboardInterrupt):
        run_bounded_steps(step, evaluate, lambda: None, records=arm['observations'],
                          on_step=lambda n: arm.__setitem__('optimizer_steps_completed', n),
                          on_checkpoint=checkpoint)
    saved = json.loads(progress_path.read_text())['tiny_fit']['arms'][0]
    assert [row['step'] for row in saved['observations']] == [0, 128]
    assert saved['optimizer_steps_completed'] == 128
    assert saved['interrupted_unknown_range'] == [128, 256]


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
