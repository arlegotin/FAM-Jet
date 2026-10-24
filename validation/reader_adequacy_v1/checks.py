"""Independent FP64 diagnostics and a closed, fixture-only reader fit.

Numerical values here are diagnostic. Nothing in this module fits production
statistics or promotes a fixture to a development population.
"""
from dataclasses import replace
import hashlib
import math
from pathlib import Path
import time
from types import SimpleNamespace

import torch

from famjet.data.schema import validate_events
from famjet.data.synthetic import generate_episode
from famjet.eval.oracle import exact_time_difference
from famjet.eval.state_io import tensor_from_record
from famjet.provenance import derive_seed
from famjet.train import move_episode
from famjet.types import EventBatch, QueryBatch
from .contract import ROOT, ReaderSpec, load_pinned_kernel
from .fixtures import make_two_age_fixture
from .reader import PrimaryReader, features

ATOL = RTOL = 1e-12
REGIMES = ('piecewise_stationary', 'trend_reset', 'periodic_impulses', 'irregular_revisions')
LENGTHS = (128, 512, 2048)
ARMS = (('C', 128), ('C', 558), ('F', 256))


def _close(actual, expected, label):
    if actual.shape != expected.shape or not torch.allclose(actual, expected, atol=ATOL, rtol=RTOL):
        error = float(torch.max(torch.abs(actual-expected))) if actual.shape == expected.shape else float('inf')
        raise ArithmeticError(f'{label}: maximum error {error}')
    return float(torch.max(torch.abs(actual-expected))) if actual.numel() else 0.


def direct_state(events, rates, query_times, *, family):
    """Event-by-event analytical sums; no live propagation or contraction call."""
    if family not in ('jet', 'bank') or rates.dtype != torch.float64 or rates.device.type != 'cpu':
        raise ValueError('fixed CPU FP64 family/rates required')
    validate_events(events)  # Shared partial observations fail before any arithmetic.
    if events.normalization != 'shared' or events.values.dtype != torch.float64 or events.values.device.type != 'cpu':
        raise ValueError('shared CPU FP64 events required')
    bsz, _, width = events.values.shape
    if query_times.shape[0] != bsz or query_times.dtype not in (torch.int64, torch.float64):
        raise ValueError('query time shape/dtype mismatch')
    qcount = query_times.shape[1]
    shape = (bsz, qcount, 1, rates.shape[1], events.key_features.shape[-1], width+1)
    z, h = torch.zeros(shape, dtype=torch.float64), torch.zeros(shape, dtype=torch.float64)
    gate = events.auxiliary.get('gate', events.auxiliary.get('gates'))
    for b in range(bsz):
        for q in range(qcount):
            target = query_times[b, q].item()
            for e in range(int(events.lengths[b])):
                if not bool(events.validation.write_mask[b, e]):
                    continue
                age = float(exact_time_difference(target, events.timestamps[b, e].item()))
                if age < 0:
                    raise ValueError('query predates event')
                weight = 1. if gate is None else float(gate[b, e].item())
                if weight == 0:
                    continue
                impulse = torch.outer(events.key_features[b, e],
                                      torch.cat((events.values[b, e], events.values.new_ones(1))))*weight
                for j, rate in enumerate(rates[0].tolist()):
                    damp = math.exp(-rate*age)
                    z[b, q, 0, j] += damp*impulse
                    if family == 'jet':
                        h[b, q, 0, j] += rate*age*damp*impulse
    return z, (h if family == 'jet' else None)


def direct_features(events, queries, rates, *, family, access, t_ref=1.):
    """Independent feature vector from explicit event sums at every query."""
    z, h = direct_state(events, rates, queries.T, family=family)
    bsz, qcount = queries.T.shape
    rows = []
    for b in range(bsz):
        line = []
        for q in range(qcount):
            p = queries.key_features[b, q]
            if access == 'F':
                memory = torch.cat((z[b, q].reshape(-1), h[b, q].reshape(-1))) if family == 'jet' else z[b, q].reshape(-1)
            elif access == 'C':
                parts = []
                for j in range(rates.shape[1]):
                    cz = (p[:, None]*z[b, q, 0, j]).sum(0)
                    if family == 'jet':
                        ch = (p[:, None]*h[b, q, 0, j]).sum(0)
                        parts.extend((cz[:-1], ch[:-1], cz[-1:], ch[-1:]))
                    else:
                        parts.extend((cz[:-1], cz[-1:]))
                memory = torch.cat(parts)
            else:
                raise ValueError('access must be C or F')
            task = queries.tasks[b][q]
            if task not in ('mean', 'contrast'):
                raise ValueError('primary task required')
            tail = torch.tensor([float(task == 'mean'), float(task == 'contrast'),
                                 float(queries.age_start[b, q])/t_ref,
                                 float(queries.age_end[b, q])/t_ref], dtype=torch.float64)
            line.append(torch.cat((memory, p, tail)))
        rows.append(torch.stack(line) if line else torch.empty(0, 92 if access == 'C' else 1172, dtype=torch.float64))
    return torch.stack(rows)


def recover_two_ages(first, second, old_coefficient_first, old_coefficient_second):
    """Solve [a,1; b,1] [old,recent] = [first,second]."""
    gap = old_coefficient_second-old_coefficient_first
    if not math.isfinite(gap) or abs(gap) < 1e-14:
        raise ValueError('two-age coefficients are singular')
    old = (second-first)/gap
    return old, first-old_coefficient_first*old


def analytic_ratio(u, h, mass, moment, eps):
    """Contracted ratio and rate-log derivative from direct-sum moments."""
    denominator = mass+eps
    if not math.isfinite(float(denominator)) or denominator <= 0:
        raise ValueError('invalid normalization')
    ratio = u/denominator
    return ratio, (ratio*moment-h)/denominator


def explicit_network(x, layers, output_grad=None):
    """Independent SiLU chain and sum-output gradients for input/three weights."""
    first, middle, output = layers
    original_shape = x.shape[:-1]
    flat_x = x.reshape(-1, x.shape[-1])
    a = flat_x@first.weight.T+first.bias
    s = torch.sigmoid(a)
    v = a*s
    b = v@middle.weight.T+middle.bias
    t = torch.sigmoid(b)
    w = b*t
    y = w@output.weight.T+output.bias
    gy = torch.ones_like(y) if output_grad is None else output_grad.reshape(-1, y.shape[-1])
    gwout = gy.T@w
    gb = (gy@output.weight)*(t+b*t*(1-t))
    gwmiddle = gb.T@v
    ga = (gb@middle.weight)*(s+a*s*(1-s))
    gwfirst = ga.T@flat_x
    gx = ga@first.weight
    return y.reshape(*original_shape, -1), gx.reshape(*original_shape, -1), gwfirst, gwout, gwmiddle


def fixture_target_stats(targets):
    if targets.shape != (4, 64, 8) or not bool(torch.isfinite(targets).all()):
        raise ValueError('complete finite fixture targets required')
    means = torch.stack((targets[:, :32].reshape(-1, 8).mean(0),
                         targets[:, 32:].reshape(-1, 8).mean(0)))
    centered = torch.stack((targets[:, :32].reshape(-1, 8)-means[0],
                            targets[:, 32:].reshape(-1, 8)-means[1]))
    scale = torch.sqrt(torch.mean(centered.square(), dim=(1, 2)))[:, None]
    if not bool((scale > 0).all()) or not bool(torch.isfinite(scale).all()):
        raise ValueError('degenerate fixture target scale')
    return means, scale


def group_losses(prediction, target):
    _, scale = fixture_target_stats(target)
    if prediction.shape != target.shape or not bool(torch.isfinite(prediction).all()):
        raise ValueError('finite matching predictions required')
    losses = {}
    for task in range(2):
        for key in range(16):
            indices = (key, key+16) if task == 0 else (key+32, key+48)
            delta = (prediction[:, indices]-target[:, indices])/scale[task]
            losses[f'{("mean", "contrast")[task]}:{key:02d}'] = float(delta.square().mean())
    return losses


def checkpoint_schedule():
    return tuple(range(0, 4097, 128))


def run_bounded_steps(step, evaluate, resource_check, *, records=None,
                      on_step=None, on_checkpoint=None):
    """Evaluate zero and complete 128-update boundaries; no retry/sweep."""
    observations = [] if records is None else records
    for n in range(4097):
        if n == 0 or n % 128 == 0:
            resource_check()
            observation = dict(evaluate(n), step=n)
            observations.append(observation)
            if on_checkpoint is not None:
                on_checkpoint(n, observation)
            if observation['passed']:
                break
        if n == 4096:
            break
        if n % 16 == 0:
            resource_check()
        step(n+1)
        if on_step is not None:
            on_step(n+1)
    return observations


def admission(free_plus_spec_bytes, disk_free_bytes):
    return (free_plus_spec_bytes >= 2*2**30 and disk_free_bytes >= 4*2**30
            and 2**30 <= .75*free_plus_spec_bytes)


class ResourceGuard:
    """Incremental process RSS, monotonic lifetime and output bound."""
    def __init__(self, root, *, start, deadline, baseline_rss, sample,
                 clock=time.monotonic, publish=None):
        self.root = Path(root)
        self.start, self.deadline, self.baseline_rss = start, deadline, baseline_rss
        self.sample, self.clock = sample, clock
        self.publish = publish
        self.samples = []

    def persist_progress(self):
        if self.publish is not None:
            self.publish(self.progress)

    def check(self):
        now = self.clock()
        current, highwater = self.sample()
        size = sum(p.stat().st_size for p in self.root.rglob('*') if p.is_file()) if self.root.exists() else 0
        row = dict(monotonic=now, current_rss=current, lifetime_highwater=highwater,
                   incremental_rss=max(0, current-self.baseline_rss), output_bytes=size)
        self.samples.append(row)
        if now >= self.deadline:
            raise RuntimeError('campaign deadline reached')
        if row['incremental_rss'] > 2**30:
            raise RuntimeError('incremental RSS cap exceeded')
        if size > 2*2**30:
            raise RuntimeError('output byte cap exceeded')
        return row


def _empty_arm(family, access, width, *, status='NOT_RUN'):
    spec = ReaderSpec(family, access, width)
    unknown = ('parameter_count', 'first_weight_count', 'last_weight_count',
               'feature_sha256', 'static_hash', 'writer_hash')
    return {'family': family, 'access': access, 'width': width, 'status': status,
            'failure': None, 'observations': [], 'optimizer_steps_completed': 0,
            'optimizer_steps_attempted': 0,
            'last_durable_step': 0, 'interrupted_unknown_range': None,
            'elapsed_seconds': None, 'frozen_parameter_count': spec.parameter_count,
            'parameter_count': None, 'first_weight_count': None,
            'last_weight_count': None, 'feature_sha256': None, 'static_hash': None,
            'static_hash_step': None, 'writer_hash': None,
            'public_cached_max_error': None,
            'unavailable': {name: 'not yet observed' for name in unknown}}


def new_campaign_progress(mode):
    if mode not in ('numerical', 'numerical_then_tiny_fit'):
        raise ValueError('closed campaign mode required')
    return {'numerical': {'status': 'NOT_RUN', 'fixture': [],
            'terminal_cells': [{'length': length, 'regime': regime,
                                'episode_id': f't18ra1-check-{length}-{regime}',
                                'status': 'NOT_RUN'} for length in LENGTHS for regime in REGIMES]},
            'tiny_fit': {'status': 'NOT_RUN' if mode == 'numerical_then_tiny_fit' else 'NOT_REQUESTED',
                         'arms': [_empty_arm(family, access, width,
                                             status='NOT_RUN' if mode == 'numerical_then_tiny_fit' else 'NOT_REQUESTED')
                                  for family in ('jet', 'bank') for access, width in ARMS]}}


def _resource_abort(exc):
    return isinstance(exc, RuntimeError) and any(
        phrase in str(exc) for phrase in ('cap exceeded', 'deadline reached'))


class CommonInputFailure(RuntimeError):
    """A common fixed source/fixture failure blocks the remaining arms."""


def run_arm_inventory(executor, budget):
    """Durable six-arm orchestration; executor may be a cheap injected step."""
    outcome = budget.progress['tiny_fit']
    arms = outcome['arms']
    if len(arms) != 6 or any(arm['status'] != 'NOT_RUN' for arm in arms):
        raise ValueError('fresh closed six-arm inventory required')
    outcome['status'] = 'ACTIVE'
    budget.persist_progress()
    for index, arm in enumerate(arms):
        arm['status'] = 'ACTIVE'
        arm['interrupted_unknown_range'] = [0, 128]
        budget.persist_progress()  # Survives a hard stop during setup.
        started = time.monotonic()
        try:
            budget.check()
            executor(arm, budget)
            if arm['status'] not in ('PASS', 'FAIL'):
                raise RuntimeError('arm executor did not record terminal outcome')
        except Exception as exc:
            arm['status'] = 'FAIL'
            arm['failure'] = f'{type(exc).__name__}: {exc}'
            arm['elapsed_seconds'] = time.monotonic()-started
            arm['interrupted_unknown_range'] = None
            for name in tuple(arm['unavailable']):
                if arm[name] is not None:
                    del arm['unavailable'][name]
                else:
                    arm['unavailable'][name] = f'unavailable after {type(exc).__name__}: {exc}'
            outcome['status'] = 'FAIL'
            if _resource_abort(exc) or isinstance(exc, CommonInputFailure):
                for remaining in arms[index+1:]:
                    remaining['status'] = 'BLOCKED'
                    remaining['failure'] = f'blocked by {type(exc).__name__} in prior arm'
                    remaining['unavailable'] = {name: 'not attempted after prior-arm failure'
                                                for name in remaining['unavailable']}
                budget.persist_progress()
                break
        else:
            arm['elapsed_seconds'] = time.monotonic()-started
            arm['interrupted_unknown_range'] = None
            if arm['status'] == 'FAIL':
                outcome['status'] = 'FAIL'
        budget.persist_progress()
    if outcome['status'] != 'FAIL':
        outcome['status'] = 'PASS'
    budget.persist_progress()
    return outcome


def _tensor_sha(value):
    return hashlib.sha256(value.detach().contiguous().numpy().tobytes()).hexdigest()


def _snapshot_sha(snapshot):
    return {**{name: _tensor_sha(value) for name, value in snapshot.payload.items()},
            **{name: _tensor_sha(getattr(snapshot, name)) for name in
               ('last_time', 'valid', 'event_offset')}}


def _query_task_index(queries):
    return torch.tensor([[0 if t == 'mean' else 1 for t in row] for row in queries.tasks], dtype=torch.long)


def _physical(reader, x, task):
    raw = reader.network((x-reader.feature_mean)/reader.feature_scale)
    return raw*reader.target_scale[task]+reader.target_mean[task]


def _fresh_reader(spec):
    with torch.random.fork_rng(devices=[]):
        torch.manual_seed(2026102402)
        return PrimaryReader(spec)


def _exported_layers(reader):
    records = reader.export_static()['weights']
    return tuple(SimpleNamespace(weight=tensor_from_record(records[f'network.{i}.weight']),
                                 bias=tensor_from_record(records[f'network.{i}.bias']))
                 for i in (0, 2, 4))


def _fixture_numerical(fixture, family, budget):
    from famjet.eval.oracle import exact_targets
    kernel = load_pinned_kernel(family)
    kernel.chunk_size = 32
    snapshot = kernel.encode(fixture.events, mode='stream')
    oracle = exact_targets(fixture.events, fixture.queries, arithmetic_version=2)
    _close(oracle.target, fixture.targets, 'fixture exact oracle')
    if not bool(oracle.supported.all()):
        raise ArithmeticError('fixture oracle unsupported')
    before = _snapshot_sha(snapshot)
    queries_before = {name: _tensor_sha(getattr(fixture.queries, name)) for name in
                      ('query_ids', 'T', 'key_ids', 'key_features', 'age_start',
                       'age_end', 'present', 'lengths')}
    z, h = direct_state(fixture.events, kernel.rates, fixture.queries.T, family=family)
    maximum = 0.
    for q in range(64):
        budget.check() if q % 16 == 0 else None
        actual = kernel._advance_payload(snapshot, fixture.queries.T[:, q].tolist(), [True]*4)
        maximum = max(maximum, _close(actual['z'], z[:, q], f'{family} direct Z query {q}'))
        if family == 'jet':
            maximum = max(maximum, _close(actual['h'], h[:, q], f'{family} direct H query {q}'))
    errors = {}
    contracted = kernel.features(snapshot, fixture.queries).diagnostics
    ratio_error = 0.
    derivative_error = 0.
    for b in range(4):
        for q in range(64):
            p = fixture.queries.key_features[b, q]
            for j in range(kernel.rates.shape[1]):
                cz = (p[:, None]*z[b, q, 0, j]).sum(0)
                if family == 'jet':
                    ch = (p[:, None]*h[b, q, 0, j]).sum(0)
                    ratio, derivative = analytic_ratio(cz[:-1], ch[:-1], cz[-1], ch[-1], kernel.eps)
                    derivative_error = max(derivative_error, _close(
                        derivative, contracted['dlog_rate_r'][b, q, 0, j],
                        f'{family} derivative {b}/{q}/{j}'))
                else:
                    ratio = cz[:-1]/(cz[-1]+kernel.eps)
                ratio_error = max(ratio_error, _close(ratio, contracted['r'][b, q, 0, j],
                                                       f'{family} ratio {b}/{q}/{j}'))
    errors['ratio'] = ratio_error
    if family == 'jet':
        errors['derivative'] = derivative_error
    scaled_events = replace(fixture.events, timestamps=fixture.events.timestamps*1000)
    scaled_queries = replace(fixture.queries, T=fixture.queries.T*1000,
                             age_start=fixture.queries.age_start*1000,
                             age_end=fixture.queries.age_end*1000)
    shifted_events = replace(fixture.events, timestamps=fixture.events.timestamps+1024.)
    shifted_queries = replace(fixture.queries, T=fixture.queries.T+1024.)
    shifted_snapshot = kernel.encode(shifted_events)
    reference_cache = {}
    unit_cache = {}
    for access, width in ARMS:
        budget.check()
        arm = f'{access}{width}'
        spec = ReaderSpec(family, access, width)
        reader = _fresh_reader(spec)
        actual = features(kernel, snapshot, fixture.queries, spec)
        if not bool(actual.supported.all()):
            raise ArithmeticError('fixture features unsupported')
        if access not in reference_cache:
            reference_cache[access] = direct_features(fixture.events, fixture.queries, kernel.rates,
                                                      family=family, access=access)
            unit_cache[access] = direct_features(scaled_events, scaled_queries, kernel.rates/1000,
                                                 family=family, access=access, t_ref=1000.)
        reference = reference_cache[access]
        unit_reference = unit_cache[access]
        errors[f'{arm}_features'] = _close(actual.values, reference, f'{family} {arm} direct features')
        task = _query_task_index(fixture.queries)
        physical = reader.read(kernel, snapshot, fixture.queries)
        layers = _exported_layers(reader)
        manual, *_ = explicit_network((reference-reader.feature_mean)/reader.feature_scale, layers)
        prediction = manual*reader.target_scale[task]+reader.target_mean[task]
        errors[f'{arm}_output'] = _close(physical.prediction, prediction,
                                       f'{family} {arm} physical prediction')
        # Transport all dimensions analytically. Public kernel stays canonical.
        errors[f'{arm}_unit_vector'] = _close(reference, unit_reference, f'{family} {arm} full unit vector')
        transformed, *_ = explicit_network((unit_reference-reader.feature_mean)/reader.feature_scale, layers)
        transformed = transformed*reader.target_scale[task]+reader.target_mean[task]
        errors[f'{arm}_unit_prediction'] = _close(physical.prediction, transformed,
                                                 f'{family} {arm} whole predictor unit transform')
        shifted = reader.read(kernel, shifted_snapshot, shifted_queries)
        errors[f'{arm}_shift_prediction'] = _close(physical.prediction, shifted.prediction,
                                                  f'{family} {arm} public timestamp shift')
        # Check actual gradients of all three exported Linear layers and input.
        input_row = ((reference-reader.feature_mean)/reader.feature_scale)[:1, :1].detach().requires_grad_()
        grad_output = reader.target_scale[task[:1, :1]].expand(1, 1, 8)
        for parameter in reader.parameters():
            parameter.grad = None
        (reader.network(input_row)*grad_output).sum().backward()
        _, dx, dw0, dwlast, dwmiddle = explicit_network(input_row.detach(), layers, grad_output)
        errors[f'{arm}_gradient_input'] = _close(input_row.grad, dx, f'{family} {arm} input gradient')
        for label, actual_grad, expected in (
                ('first', reader.network[0].weight.grad, dw0),
                ('middle', reader.network[2].weight.grad, dwmiddle),
                ('last', reader.network[4].weight.grad, dwlast)):
            errors[f'{arm}_gradient_{label}'] = _close(actual_grad, expected,
                                                      f'{family} {arm} {label} weight gradient')
            if not bool(torch.isfinite(actual_grad).all()) or not bool((actual_grad != 0).any()):
                raise ArithmeticError(f'{family} {arm} {label} gradient inactive')
        if not bool((input_row.grad != 0).any()):
            raise ArithmeticError(f'{family} {arm} input gradient inactive')
    if before != _snapshot_sha(snapshot):
        raise ArithmeticError('snapshot mutated by read')
    if queries_before != {name: _tensor_sha(getattr(fixture.queries, name)) for name in queries_before}:
        raise ArithmeticError('queries mutated by read')
    # Key order permutation is legal because query IDs are unique ordinals.
    permutation = torch.arange(63, -1, -1)
    q = fixture.queries
    reordered = replace(q, query_ids=q.query_ids[:, permutation], T=q.T[:, permutation],
                        key_ids=q.key_ids[:, permutation], key_features=q.key_features[:, permutation],
                        tasks=tuple(tuple(row[i] for i in permutation.tolist()) for row in q.tasks),
                        age_start=q.age_start[:, permutation], age_end=q.age_end[:, permutation],
                        present=q.present[:, permutation])
    reader = _fresh_reader(ReaderSpec(family, 'C', 128))
    original = reader.read(kernel, snapshot, q).prediction
    permuted = reader.read(kernel, snapshot, reordered).prediction
    errors['permutation'] = _close(original[:, permutation], permuted,
                                   f'{family} query permutation')
    # Explicit 2x2 inversion, all four histories and sixteen selectors.
    values = fixture.events.values.reshape(4, 2, 16, 8)
    old, recent = values[:, 0], values[:, 1]
    if family == 'bank':
        rates = kernel.rates[0]
        first, last = math.exp(-2*float(rates[0])), math.exp(-2*float(rates[-1]))
        got_old, got_recent = recover_two_ages(snapshot.payload['z'][:, 0, 0, :, :8],
                                                snapshot.payload['z'][:, 0, -1, :, :8], first, last)
    else:
        rate = float(kernel.rates[0, -1]); a = math.exp(-2*rate)
        got_old = snapshot.payload['h'][:, 0, -1, :, :8]/(2*rate*a)
        got_recent = snapshot.payload['z'][:, 0, -1, :, :8]-a*got_old
        gamma_l1 = snapshot.payload['z']-2*snapshot.payload['h']
        recovered_h = (snapshot.payload['z']-gamma_l1)/2
        errors['gamma_roundoff'] = _close(recovered_h, snapshot.payload['h'],
                                         'gamma H recovery')
        gamma_snapshot = replace(snapshot, payload={**snapshot.payload, 'h': recovered_h})
        gamma_reader = _fresh_reader(ReaderSpec('jet', 'C', 128))
        errors['gamma_read'] = _close(gamma_reader.read(kernel, gamma_snapshot, q).prediction,
                                      gamma_reader.read(kernel, snapshot, q).prediction,
                                      'gamma unchanged reader')
    errors['old_reconstruction'] = _close(got_old, old, f'{family} old all-key values')
    errors['recent_reconstruction'] = _close(got_recent, recent, f'{family} recent all-key values')
    errors.update(_edge_case_numerical(kernel, family))
    return {'family': family, 'state_max_error': maximum, 'errors': errors,
            'snapshot_sha256': {name: _tensor_sha(snapshot.payload[name]) for name in kernel._state_keys},
            'writer_hash': kernel._parameter_hash(),
            'unit_public_transport': 'canonical_only'}


def _edge_case_numerical(kernel, family):
    """Signed writes, real no-write delay, absent key, padding and immutability."""
    keys = torch.nn.functional.one_hot(torch.tensor([[3, 3, 3, 0]]), 16).to(torch.float64)
    values = torch.zeros(1, 4, 8, dtype=torch.float64)
    values[0, 0] = 2.; values[0, 1] = -2.; values[0, 2] = 100.
    present = torch.tensor([[True, True, True, False]])
    observed = present[..., None].expand(1, 4, 8).clone()
    observed[0, 2] = False
    events = EventBatch(('edge',), torch.arange(4)[None],
                        torch.tensor([[0., 0., 2., 2.]], dtype=torch.float64),
                        torch.tensor([[3, 3, 3, 0]]), keys, values,
                        torch.tensor([3]), present, observed, 's')
    qkeys = torch.nn.functional.one_hot(torch.tensor([[3, 3, 4, 0]]), 16).to(torch.float64)
    queries = QueryBatch(('edge',), torch.arange(4)[None],
                         torch.tensor([[2., 3., 3., 3.]], dtype=torch.float64),
                         torch.tensor([[3, 3, 4, 0]]), qkeys,
                         (('mean', 'contrast', 'mean', 'mean'),),
                         torch.zeros(1, 4, dtype=torch.float64),
                         torch.ones(1, 4, dtype=torch.float64),
                         torch.tensor([[True, True, True, False]]), torch.tensor([3]))
    snapshot = kernel.encode(events)
    before = _snapshot_sha(snapshot)
    direct_z, direct_h = direct_state(events, kernel.rates, queries.T, family=family)
    errors = {}
    for j in range(3):
        advanced = kernel._advance_payload(snapshot, queries.T[:, j].tolist(), [True])
        errors[f'edge_z_{j}'] = _close(advanced['z'], direct_z[:, j], f'{family} edge Z {j}')
        if family == 'jet':
            errors[f'edge_h_{j}'] = _close(advanced['h'], direct_h[:, j], f'{family} edge H {j}')
    batch = features(kernel, snapshot, queries, ReaderSpec(family, 'C', 128))
    if batch.supported.tolist() != [[True, True, False, False]]:
        raise ArithmeticError('absence/padding support mismatch')
    expected = direct_features(events, queries, kernel.rates, family=family, access='C')
    errors['edge_feature'] = _close(batch.values[:, :2], expected[:, :2],
                                    f'{family} edge raw features')
    if not bool((expected[0, :2, :8] == 0).all()):
        raise ArithmeticError('signed cancellation did not zero raw numerator')
    if before != _snapshot_sha(snapshot):
        raise ArithmeticError('edge snapshot mutated')
    invalid_observed = observed.clone(); invalid_observed[0, 0, 0] = False
    try:
        kernel.encode(replace(events, observed=invalid_observed))
    except ValueError as exc:
        if 'partial value observation' not in str(exc):
            raise
    else:
        raise ArithmeticError('partial shared value mask accepted')
    return errors


def _record_terminal_cell(budget, index, cell):
    budget.progress['numerical']['terminal_cells'][index] = cell
    budget.persist_progress()


def _terminal_cells(budget):
    from famjet.config import load_config
    from famjet.data.synthetic import batch_hash
    base = load_config(ROOT/'configs/development/jet_finite_raw_32768.yaml')
    seed = derive_seed(20261024, 'task18_reader_adequacy_v1', 'numerical')
    rows = budget.progress['numerical']['terminal_cells']
    for index, (length, regime) in enumerate((length, regime) for length in LENGTHS for regime in REGIMES):
        _record_terminal_cell(budget, index, {**rows[index], 'status': 'ACTIVE'})
        budget.check()
        identifier = f't18ra1-check-{length}-{regime}'
        config = replace(base, data=replace(base.data, length=length,
                         generator=replace(base.data.generator, namespace='training', regime=regime)))
        episode = generate_episode(config, seed, identifier)
        if episode.metadata['target_semantics'] != 'observed_event_targets_v2' or not all(
                bool(value) for row in episode.metadata['target_valid'] for value in row):
            raise ArithmeticError(f'invalid primary targets in {identifier}; no redraw')
        episode = move_episode(episode, 'cpu', dtype=torch.float64)
        cell = {'length': length, 'regime': regime, 'episode_id': identifier,
                'status': 'PASS', 'seed': seed, 'source_hashes': episode.metadata['hashes'],
                'promoted_hashes': {'events': batch_hash(episode.events),
                                    'queries': batch_hash(episode.queries)},
                'families': {}}
        for family in ('jet', 'bank'):
            budget.check()
            kernel = load_pinned_kernel(family)
            kernel.chunk_size = 32
            terminal = kernel.encode(episode.events, mode='terminal')
            stream = kernel.encode(episode.events, mode='stream')
            errors = {name: _close(terminal.payload[name], stream.payload[name],
                                   f'{identifier} {family} {name}') for name in kernel._state_keys}
            for access, width in (('C', 128), ('F', 256)):
                spec = ReaderSpec(family, access, width)
                t = features(kernel, terminal, episode.queries, spec)
                s = features(kernel, stream, episode.queries, spec)
                errors[f'{access}_input'] = _close(t.values, s.values,
                                                   f'{identifier} {family} {access} inputs')
                if not torch.equal(t.supported, s.supported):
                    raise ArithmeticError('terminal/stream support mismatch')
            cell['families'][family] = {'errors': errors,
                'terminal_sha256': {name: _tensor_sha(terminal.payload[name]) for name in kernel._state_keys},
                'stream_sha256': {name: _tensor_sha(stream.payload[name]) for name in kernel._state_keys}}
        _record_terminal_cell(budget, index, cell)
    return rows, seed


def numerical_checks(*, budget):
    """Full diagnostic campaign. Source tests never call this function."""
    torch.set_num_threads(1)
    report = budget.progress['numerical']
    report.update(status='ACTIVE', tolerance={'atol': ATOL, 'rtol': RTOL},
                  fixture_seed=2026102401, unit_public_transport='canonical_only',
                  diagnostic_only=True)
    budget.persist_progress()
    fixture = make_two_age_fixture()
    for family in ('jet', 'bank'):
        budget.check()
        report['fixture'].append(_fixture_numerical(fixture, family, budget))
        budget.persist_progress()
    report['terminal_cells'], report['terminal_seed'] = _terminal_cells(budget)
    report['status'] = 'PASS'
    budget.persist_progress()
    return report


def _key_sensitive(prediction, labels):
    # Same history/task/window, two keys with different oracle values.
    for task_start in (0, 32):
        found = False
        for key in range(15):
            unequal = bool((labels[:, task_start+key]-labels[:, task_start+key+1]).abs().max() > 1e-8)
            changed = bool((prediction[:, task_start+key]-prediction[:, task_start+key+1]).abs().max() > 1e-12)
            if unequal and changed:
                found = True
                break
        if not found:
            return False
    return True


def tiny_fit(*, budget):
    """Six independent fixed-feature fixture fits; no data or hyperparameter sweep.

    Production inverse target buffers remain frozen. Fixture-only task means
    and pooled scales normalize physical prediction errors in the loss only.
    """
    torch.set_num_threads(1)
    outcome = budget.progress['tiny_fit']
    outcome.update(status='ACTIVE', fixture_seed=2026102401, init_seed=2026102402,
                   rows=256, fixture_target_mean=None, fixture_target_scale=None,
                   optimizer={'lr': 0.003, 'betas': [0.9, 0.999],
                              'eps': 1e-8, 'weight_decay': 0., 'clip_global_norm': 1.,
                              'batch': 64, 'maximum_updates': 4096},
                   loss_parameterization='physical predictions via frozen production inverse; fixture-only per-task population scale in loss; no development statistic')
    budget.persist_progress()
    try:
        budget.check()
        fixture = make_two_age_fixture()
        fixture_mean, fixture_scale = fixture_target_stats(fixture.targets)
    except Exception as exc:
        outcome['status'] = 'FAIL'
        outcome['failure'] = f'common fixture setup: {type(exc).__name__}: {exc}'
        for arm in outcome['arms']:
            arm['status'] = 'BLOCKED'
            arm['failure'] = outcome['failure']
            arm['unavailable'] = {name: 'not attempted after common fixture setup failure'
                                  for name in arm['unavailable']}
        budget.persist_progress()
        return outcome
    outcome['fixture_target_mean'] = fixture_mean.tolist()
    outcome['fixture_target_scale'] = fixture_scale.tolist()
    budget.persist_progress()
    from famjet.provenance import canonical_hash
    kernels = {}
    cached_features = {}
    task = _query_task_index(fixture.queries).reshape(-1)
    labels = fixture.targets.reshape(256, 8)

    def execute(arm, guard):
        family, access, width = arm['family'], arm['access'], arm['width']
        spec = ReaderSpec(family, access, width)
        if family not in kernels:
            try:
                kernel = load_pinned_kernel(family)
                kernel.chunk_size = 32
                kernels[family] = (kernel, kernel.encode(fixture.events, mode='stream'))
            except Exception as exc:
                raise CommonInputFailure(f'{family} fixed fixture/source setup: {exc}') from exc
        kernel, snapshot = kernels[family]
        arm['writer_hash'] = kernel._parameter_hash()
        arm['unavailable'].pop('writer_hash', None)
        reader = _fresh_reader(spec)
        parameters = tuple(reader.parameters())
        arm.update(parameter_count=sum(p.numel() for p in parameters),
                   first_weight_count=reader.network[0].weight.numel(),
                   last_weight_count=reader.network[4].weight.numel(),
                   static_hash=canonical_hash(reader.export_static()), static_hash_step=0)
        for name in ('parameter_count', 'first_weight_count', 'last_weight_count', 'static_hash'):
            arm['unavailable'].pop(name, None)
        guard.persist_progress()
        key = (family, access)
        if key not in cached_features:
            try:
                batch = features(kernel, snapshot, fixture.queries, spec)
                if not bool(batch.supported.all()) or bool(batch.diagnostics['failure'].any()):
                    raise ArithmeticError('fixture reader input unsupported')
                cached_features[key] = batch.values.reshape(256, spec.input_dim)
            except Exception as exc:
                raise CommonInputFailure(f'{family} {access} fixed fixture features: {exc}') from exc
        raw = cached_features[key]
        arm['feature_sha256'] = _tensor_sha(raw)
        arm['unavailable'].pop('feature_sha256', None)
        reader.fit_feature_statistics(({'split': 'training', 'values': raw,
                                        'supported': torch.ones(256, dtype=torch.bool)},),
                                      provenance={'scope': 'fixture_only',
                                                  'fixture_id': 'task18-reader-adequacy-v1-two-age-2026102401'})
        arm['static_hash'] = canonical_hash(reader.export_static())
        guard.persist_progress()
        optimizer = torch.optim.AdamW(parameters, lr=0.003, betas=(0.9, 0.999),
                                      eps=1e-8, weight_decay=0.)
        gradient_activity = {'input': False, 'output': False}
        arm_start = time.monotonic()

        def train_step(n):
            start = ((n-1)*64) % 256
            index = torch.arange(start, start+64) % 256
            optimizer.zero_grad(set_to_none=True)
            physical = _physical(reader, raw[index], task[index])
            center = fixture_mean[task[index]]
            scale = fixture_scale[task[index]]
            loss = (((physical-center)/scale-(labels[index]-center)/scale)**2).mean()
            if not bool(torch.isfinite(loss)):
                raise FloatingPointError('nonfinite fixture loss')
            loss.backward()
            for name, parameter in (('input', reader.network[0].weight),
                                    ('output', reader.network[4].weight)):
                grad = parameter.grad
                if grad is None or not bool(torch.isfinite(grad).all()):
                    raise FloatingPointError(f'nonfinite {name} gradient')
                gradient_activity[name] |= bool((grad != 0).any())
            torch.nn.utils.clip_grad_norm_(parameters, 1., error_if_nonfinite=True)
            optimizer.step()
            arm['optimizer_steps_attempted'] = n
            if not all(bool(torch.isfinite(p).all()) for p in parameters):
                raise FloatingPointError('nonfinite fixture weights')

        def evaluate(n):
            with torch.no_grad():
                prediction = _physical(reader, raw, task).reshape(4, 64, 8)
                losses = group_losses(prediction, fixture.targets)
                maximum = max(losses.values())
                selection = _key_sensitive(prediction, fixture.targets)
                active = all(gradient_activity.values())
                return {'losses': losses, 'maximum': maximum,
                        'gradient_activity': dict(gradient_activity),
                        'key_selection_changed': selection,
                        'passed': maximum <= 1e-4 and active and selection,
                        'elapsed_seconds': time.monotonic()-arm_start}

        def checkpoint(n, _):
            arm['optimizer_steps_completed'] = n
            arm['last_durable_step'] = n
            arm['interrupted_unknown_range'] = [n, min(n+128, 4096)]
            arm['static_hash'] = canonical_hash(reader.export_static())
            arm['static_hash_step'] = n
            guard.persist_progress()

        try:
            run_bounded_steps(train_step, evaluate, guard.check, records=arm['observations'],
                              on_step=lambda n: arm.__setitem__('optimizer_steps_completed', n),
                              on_checkpoint=checkpoint)
        except Exception as exc:
            if not _resource_abort(exc):
                try:
                    arm['static_hash'] = canonical_hash(reader.export_static())
                    arm['static_hash_step'] = arm['optimizer_steps_completed']
                except Exception as static_exc:
                    arm['static_hash'] = None
                    arm['unavailable']['static_hash'] = f'failure-state export unavailable: {static_exc}'
            raise
        with torch.no_grad():
            public = reader.read(kernel, snapshot, fixture.queries)
            cached = _physical(reader, raw, task).reshape(4, 64, 8)
            arm['public_cached_max_error'] = _close(public.prediction, cached,
                                                     'fixture public/cached read')
        arm['static_hash'] = canonical_hash(reader.export_static())
        arm['static_hash_step'] = arm['optimizer_steps_completed']
        arm['status'] = 'PASS' if arm['observations'][-1]['passed'] else 'FAIL'
        if arm['status'] == 'FAIL':
            arm['failure'] = 'finite 4096-update stopping criterion not met'

    return run_arm_inventory(execute, budget)
