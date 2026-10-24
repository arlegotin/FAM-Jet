"""Frozen E3 development inventories, finite allocations and honest v2 scoring."""
from dataclasses import replace
import hashlib
import itertools
import json
import math
import os
from pathlib import Path
import tempfile
import time

import torch

from famjet.data._processes import REGIMES
from famjet.data.schema import validate_events, validate_queries
from famjet.data.synthetic import batch_hash
from famjet.eval.budgets import state_ledger
from famjet.eval.state_io import inference_snapshot, snapshot_hash
from famjet.eval.metrics import aggregate_scores, score_predictions
from famjet.provenance import canonical_hash, canonical_json
from famjet.types import PredictionBatch
from .cache import (attach_training_cache, e3_source_sha256, episode_factory,
                    load_episode_cache, prepare_episode_cache)
from .comparators import (build_controls, laguerre_control, coordinate_model_sha256,
                          validate_coordinate_audits, load_coordinate_model)
from .contracts import PopulationSpec, ReaderSpec, ShapeSpec, source_sha256
from .models import (RidgeMemoryModel, build_model, fit_reader, fit_training_metadata,
                     load_model, make_fit_manifest, save_model)
from .wire import export_statics, isolated_read_batch

_LENGTHS = (128, 512, 2048)
_Q = 8
_FIT_COUNT = 40


def _atomic_json(path, body):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = canonical_json(body)
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix='.e3-', delete=False) as stream:
        temp = Path(stream.name)
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    try:
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)
    return {'path': str(path), 'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw)}


def persist_score_rows(rows, out, *, max_bytes=None):
    """Store each core scoring policy once; rows retain exact policy hashes."""
    if type(rows) is not list or not rows or max_bytes is not None and (type(max_bytes) is not int or max_bytes <= 0):
        raise ValueError('nonempty score rows and positive optional byte ceiling required')
    policies, compact, identities = {}, [], set()
    for row in rows:
        if type(row) is not dict or 'policy' not in row or 'policy_hash' not in row:
            raise ValueError('core scoring policy record required')
        digest = canonical_hash(row['policy'])
        if digest != row['policy_hash']:
            raise ValueError('scoring policy hash mismatch')
        identity = (row['method'], row['history_id'], row['replicate'], row['task'], row['query_id'])
        if identity in identities:
            raise ValueError('duplicate score row identity')
        identities.add(identity)
        policies.setdefault(digest, row['policy'])
        compact.append({k: v for k, v in row.items() if k != 'policy'} | {'policy_ref': digest})
    body = {'schema_version': 1, 'kind': 'famjet_e3_normalized_rows',
            'policies': policies, 'rows': compact}
    body['normalized_hash'] = canonical_hash(body)
    raw = canonical_json(body)
    if max_bytes is not None and len(raw) > max_bytes:
        raise MemoryError('normalized score rows exceed disk admission')
    return _atomic_json(out, body)


def load_score_rows(ref):
    if type(ref) is not dict or set(ref) != {'path', 'sha256', 'bytes'}:
        raise ValueError('score row file reference schema mismatch')
    raw = Path(ref['path']).read_bytes()
    if (len(raw) != ref['bytes'] or hashlib.sha256(raw).hexdigest() != ref['sha256']):
        raise ValueError('score row file hash mismatch')
    body = json.loads(raw)
    if (type(body) is not dict or set(body) != {'schema_version', 'kind', 'policies', 'rows', 'normalized_hash'} or
            body['schema_version'] != 1 or body['kind'] != 'famjet_e3_normalized_rows' or
            body['normalized_hash'] != canonical_hash({k: v for k, v in body.items() if k != 'normalized_hash'}) or
            type(body['policies']) is not dict or type(body['rows']) is not list):
        raise ValueError('normalized score row schema/hash mismatch')
    for digest, policy in body['policies'].items():
        if digest != canonical_hash(policy):
            raise ValueError('normalized policy hash mismatch')
    rows = []
    for row in body['rows']:
        if (type(row) is not dict or 'policy' in row or 'policy_ref' not in row or
                row['policy_ref'] != row.get('policy_hash') or row['policy_ref'] not in body['policies']):
            raise ValueError('normalized row policy reference mismatch')
        restored = {k: v for k, v in row.items() if k != 'policy_ref'}
        restored['policy'] = body['policies'][row['policy_ref']]
        rows.append(restored)
    return rows


def _config(config):
    required = {'profile', 'shape', 'training_seed', 'development_seed', 'max_query_attempts',
                'cache_limits', 'worker_limits'}
    if type(config) is not dict or set(config) != required or config['profile'] not in {'study', 'unit_test'}:
        raise ValueError('complete frozen study config required')
    shape = ShapeSpec.from_json(config['shape'])
    for name in ('training_seed', 'development_seed'):
        if type(config[name]) is not int or not 0 <= config[name] < 2**63:
            raise ValueError('finite frozen study seed required')
    if type(config['max_query_attempts']) is not int or config['max_query_attempts'] <= 0:
        raise ValueError('positive frozen query attempt count required')
    c = config['cache_limits']
    w = config['worker_limits']
    if (type(c) is not dict or set(c) != {'disk_bytes', 'lru_bytes'} or
            any(type(v) is not int or v <= 0 for v in c.values()) or
            type(w) is not dict or set(w) != {'max_frame_bytes', 'max_array_bytes', 'max_histories'} or
            any(type(v) is not int or v <= 0 for v in w.values()) or w['max_histories'] > 64):
        raise ValueError('finite cache/worker limits required')
    return shape


def _inventory(shape, namespace, seed, attempts, lengths, regimes, count):
    specs = [PopulationSpec('poc_numeric_v1', shape, namespace, seed, (length,), (regime,), _Q, attempts)
             for length in lengths for regime in regimes]
    records = [{'history_id': f'{namespace}-{length}-{regime}-{i:03d}', 'spec': spec.to_json()}
               for i in range(count) for spec in specs
               for length, regime in [(spec.lengths[0], spec.regimes[0])]]
    return [s.to_json() for s in specs], records


def study_manifest(config) -> dict:
    shape = _config(config)
    study = config['profile'] == 'study'
    lengths = _LENGTHS if study else (128,)
    regimes = REGIMES if study else ('piecewise_stationary',)
    count_train, count_dev = (64, 16) if study else (2, 1)
    namespace_train, namespace_dev = ('training', 'development_fit') if study else ('training', 'unit_test')
    train_specs, train = _inventory(shape, namespace_train, config['training_seed'],
                                    config['max_query_attempts'], lengths, regimes, count_train)
    dev_specs, dev = _inventory(shape, namespace_dev, config['development_seed'],
                                config['max_query_attempts'], lengths, regimes, count_dev)
    if config['profile'] == 'unit_test':
        for item in dev:
            item['history_id'] = item['history_id'].replace('unit_test-', 'unit_test-development-', 1)
    candidates = []
    for family, width, ridge, alpha_max in itertools.product(
            ('jet', 'bank'), (8, 16), (1e-10, 1e-6, 1e-2), (.5, 1., 2.)):
        reader = ReaderSpec('ridge_v1', family, width, ridge, 1 / 5224, alpha_max, 1e-6, 1e-12).to_json()
        candidates.append({'family': family, 'reader': reader, 'config_hash': canonical_hash(reader)})
    body = {'schema_version': 1, 'kind': 'famjet_e3_study', 'config': config,
            'source_sha256': source_sha256(), 'e3_source_sha256': e3_source_sha256(),
            'training_specs': train_specs, 'development_specs': dev_specs,
            'training_inventory': train, 'development_inventory': dev,
            'training_inventory_hash': canonical_hash(train), 'development_inventory_hash': canonical_hash(dev),
            'candidates': candidates, 'expected_fit_count': _FIT_COUNT if study else 36,
            'prefixes': [192, 384, 768] if study else [len(train)],
            'query_count': _Q, 'lengths': list(lengths), 'regimes': list(regimes),
            'stream_chunk_size': 128, 'stream_mode': 'stream',
            'numerical_replay_policy': 'checkpoint_then_single_event_to_first_bad'}
    body['manifest_sha256'] = canonical_hash(body)
    return body


def _validate_manifest(manifest):
    if type(manifest) is not dict or manifest.get('kind') != 'famjet_e3_study' or manifest.get('schema_version') != 1:
        raise ValueError('study manifest schema mismatch')
    expected = study_manifest(manifest['config'])
    if manifest != expected:
        raise ValueError('study manifest/source/inventory changed')
    return ShapeSpec.from_json(manifest['config']['shape'])


def _allocation(allocation, phase, manifest):
    required = {'schema_version', 'phase', 'manifest_sha256', 'allocation_id',
                'max_wall_seconds', 'max_disk_bytes', 'max_rss_bytes'}
    if phase == 'development':
        if type(allocation) is not dict or 'probe_ref' not in allocation:
            raise ValueError('successful probe reference required before development')
        required.add('probe_ref')
    if (type(allocation) is not dict or set(allocation) != required or allocation['schema_version'] != 1 or
            allocation['phase'] != phase or allocation['manifest_sha256'] != manifest['manifest_sha256'] or
            type(allocation['allocation_id']) is not str or not allocation['allocation_id'] or
            type(allocation['max_wall_seconds']) not in (int, float) or
            not math.isfinite(allocation['max_wall_seconds']) or allocation['max_wall_seconds'] <= 0 or
            any(type(allocation[k]) is not int or allocation[k] <= 0
                for k in ('max_disk_bytes', 'max_rss_bytes'))):
        raise ValueError('explicit finite phase allocation required')
    if phase == 'development':
        ref = allocation['probe_ref']
        if type(ref) is not dict or set(ref) != {'path', 'sha256'}:
            raise ValueError('successful content-bound probe reference required')
        raw = Path(ref['path']).read_bytes()
        if hashlib.sha256(raw).hexdigest() != ref['sha256']:
            raise ValueError('probe reference hash mismatch')
        probe = json.loads(raw)
        if probe.get('phase') != 'probe' or probe.get('manifest_sha256') != manifest['manifest_sha256'] or probe.get('status') != 'measured' or probe.get('feasible') is not True:
            raise ValueError('successful matching probe admission required')


def _rss_bytes():
    import resource
    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return int(value if os.uname().sysname == 'Darwin' else value * 1024)


def _admit(started, allocation, disk_bytes=0, *, directory=None):
    elapsed = time.monotonic() - started
    rss = _rss_bytes()
    if directory is not None:
        disk_bytes = sum(path.stat().st_size for path in Path(directory).rglob('*') if path.is_file())
    if elapsed > allocation['max_wall_seconds'] or disk_bytes > allocation['max_disk_bytes'] or rss > allocation['max_rss_bytes']:
        raise RuntimeError('phase allocation exhausted')
    return {'elapsed_seconds': elapsed, 'rss_bytes': rss, 'disk_bytes': disk_bytes,
            'remaining_wall_seconds': allocation['max_wall_seconds'] - elapsed,
            'remaining_disk_bytes': allocation['max_disk_bytes'] - disk_bytes,
            'remaining_rss_bytes': allocation['max_rss_bytes'] - rss}


def _resume_allocation_started(journal):
    """Rebase a finite allocation clock without granting time on resume."""
    stamp = journal.get('allocation_started_epoch_seconds')
    if type(stamp) not in (int, float) or not math.isfinite(stamp) or stamp <= 0:
        raise ValueError('resumed allocation lacks a durable start time')
    age = time.time() - stamp
    if not math.isfinite(age) or age < 0:
        raise ValueError('allocation wall clock moved before durable start')
    prior = journal.get('admission', {}).get('elapsed_seconds', 0.)
    if type(prior) not in (int, float) or not math.isfinite(prior) or prior < 0:
        raise ValueError('invalid previous allocation admission')
    return time.monotonic() - max(age, prior)


def _regime(ep):
    value = ep.metadata.get('regime')
    if value is None and ep.metadata.get('preparation_version') == 'beijing_observed_v2_targets' and ep.metadata.get('normalization') == 'training_standardized':
        return 'beijing_observed'
    if type(value) is not str or not value:
        raise ValueError('explicit evaluation regime required')
    return value


def freeze_score_policy(episodes, *, tasks=('mean', 'contrast'), task_weights=None, manifest_hash=None):
    """Bind full queries and common label-only eligible numeric inventory."""
    if type(tasks) is not tuple or not tasks or len(set(tasks)) != len(tasks) or not set(tasks) <= {'mean', 'contrast'}:
        raise ValueError('declared numeric primary tasks required')
    if task_weights is None:
        task_weights = {task: 1 / len(tasks) for task in tasks}
    if set(task_weights) != set(tasks) or any(not math.isfinite(w) or w <= 0 for w in task_weights.values()) or not math.isclose(sum(task_weights.values()), 1., abs_tol=1e-12):
        raise ValueError('positive normalized task weights required')
    full, eligible, counts, seen, regimes = [], [], {}, set(), set()
    for ep in episodes:
        validate_events(ep.events)
        validate_queries(ep.queries)
        regime = _regime(ep)
        regimes.add(regime)
        for b, h in enumerate(ep.queries.history_ids):
            if h in seen:
                raise ValueError('duplicate scoring history')
            seen.add(h)
            declared = {task: [] for task in tasks}
            all_queries = {}
            for j in range(int(ep.queries.lengths[b])):
                if not bool(ep.queries.present[b, j]):
                    continue
                task = ep.queries.tasks[b][j]
                if task not in {'mean', 'contrast'}:
                    raise ValueError('E3 supports numeric mean/contrast queries only')
                qid = int(ep.queries.query_ids[b, j])
                all_queries.setdefault(task, []).append(qid)
                if task in declared and bool(ep.metadata['target_valid'][b][j]):
                    if not bool(ep.supported[b, j]) or not bool(torch.isfinite(ep.labels[b, j]).all()):
                        raise ValueError('eligible target/support mismatch')
                    declared[task].append(qid)
            if any(not declared[task] for task in tasks):
                raise ValueError('primary history lacks eligible task')
            full.append({'history_id': h, 'replicate': 0, 'regime': regime, 'tasks': all_queries})
            eligible.append({'history_id': h, 'replicate': 0, 'regime': regime, 'tasks': declared})
            counts[h] = {task: len(declared[task]) for task in tasks}
    if not full:
        raise ValueError('empty scoring inventory')
    weights = {regime: 1 / len(regimes) for regime in sorted(regimes)}
    full_hash = canonical_hash(full)
    if manifest_hash is None:
        manifest_hash = full_hash
    if type(manifest_hash) is not str or len(manifest_hash) != 64 or any(ch not in '0123456789abcdef' for ch in manifest_hash):
        raise ValueError('content-bound manifest hash required')
    return {'version': 2, 'primary_tasks': list(tasks), 'support_calibration': None,
            'expected_inventory': eligible, 'task_weights': task_weights, 'regime_weights': weights,
            'full_inventory': full, 'full_inventory_hash': full_hash,
            'eligible_inventory_hash': canonical_hash(eligible), 'eligible_counts': counts,
            'manifest_hash': manifest_hash}


def _diagnostic_score_policy(policy):
    tasks = {task for item in policy['full_inventory'] for task in item['tasks']}
    return {'version': 2, 'primary_tasks': [], 'support_calibration': None,
            'expected_inventory': policy['full_inventory'],
            'task_weights': {task: 1 / len(tasks) for task in tasks},
            'regime_weights': policy['regime_weights']}


def score_results(episodes, results, statistics, policy, method, *, _allow_partial=False) -> list[dict]:
    if type(method) is not str or not method or type(policy) is not dict or not {'full_inventory', 'full_inventory_hash', 'eligible_inventory_hash', 'eligible_counts', 'manifest_hash'} <= set(policy):
        raise ValueError('frozen scoring policy and method required')
    if policy['full_inventory_hash'] != canonical_hash(policy['full_inventory']) or policy['eligible_inventory_hash'] != canonical_hash(policy['expected_inventory']):
        raise ValueError('scoring inventory hash mismatch')
    full_by_h = {item['history_id']: item for item in policy['full_inventory']}
    eligible_by_h = {item['history_id']: item for item in policy['expected_inventory']}
    diagnostic_policy = _diagnostic_score_policy(policy)
    rows = []
    seen = set()
    for ep, envelope in itertools.zip_longest(episodes, results, fillvalue=None):
        if ep is None or envelope is None or type(envelope) is not dict or set(envelope) != {'result', 'trigger', 'state_bytes'}:
            raise ValueError('incomplete result/episode inventory')
        if ep.metadata.get('target_semantics') != 'observed_event_targets_v2':
            raise ValueError('legacy targets cannot be scored')
        if len(ep.events.history_ids) != 1:
            raise ValueError('E3 score_results expects singleton episode histories')
        h = ep.events.history_ids[0]
        if h in seen or h not in full_by_h or h not in eligible_by_h:
            raise ValueError('unknown scoring history')
        seen.add(h)
        expected_full, expected_eligible = full_by_h[h], eligible_by_h[h]
        if expected_full['regime'] != _regime(ep):
            raise ValueError('scoring regime mismatch')
        actual_full = {}
        actual_eligible = {task: [] for task in policy['task_weights']}
        for j in range(int(ep.queries.lengths[0])):
            if not bool(ep.queries.present[0, j]):
                continue
            task, qid = ep.queries.tasks[0][j], int(ep.queries.query_ids[0, j])
            actual_full.setdefault(task, []).append(qid)
            if task in actual_eligible and bool(ep.metadata['target_valid'][0][j]):
                actual_eligible[task].append(qid)
        if expected_full['tasks'] != actual_full or expected_eligible['tasks'] != actual_eligible:
            raise ValueError('scoring full/eligible query inventory mismatch')
        trigger = envelope['trigger']
        result = envelope['result']
        if result is None and trigger is None:
            raise ValueError('infrastructure failure cannot masquerade as quarantine')
        qshape = ep.queries.T.shape
        if result is None:
            raw = torch.full((*qshape, ep.events.values.shape[-1]), float('nan'), dtype=torch.float64)
            valid = torch.zeros(qshape, dtype=torch.bool)
            numeric = valid
            failure = torch.ones(qshape, dtype=torch.bool)
        else:
            raw = result.prediction.detach().cpu()
            if raw.shape != ep.labels.shape:
                raise ValueError('result prediction shape mismatch')
            valid = result.diagnostics.get('prediction_valid', result.support).detach().cpu()
            numeric = result.diagnostics.get('numeric_supported', valid).detach().cpu()
            failure = result.failure.detach().cpu()
        eligible_mask = ep.queries.present.cpu().clone()
        for j in range(eligible_mask.shape[1]):
            eligible_mask[0, j] &= bool(ep.metadata['target_valid'][0][j]) and ep.queries.tasks[0][j] in policy['task_weights']
        for scope, mask, scoring_policy in (('primary', eligible_mask, policy),
                                            ('ineligible_diagnostic', ep.queries.present.cpu() & ~eligible_mask, diagnostic_policy)):
            if not bool(mask.any()):
                continue
            context = {'version': 2, 'present': mask.tolist(), 'tasks': ep.queries.tasks,
                       'target_valid': ep.metadata['target_valid'], 'numeric_supported': numeric.tolist(),
                       'prediction_valid': valid.tolist(), 'quarantined': torch.full(qshape, trigger is not None).tolist(),
                       'quarantine_trigger': trigger, 'method': method, 'replicate': 0, 'regime': _regime(ep),
                       'target_semantics': 'observed_event_targets_v2',
                       'manifest_hash': policy['manifest_hash'],
                       'statistics_hash': canonical_hash(statistics), 'output_convention': 'numeric'}
            batch = PredictionBatch(ep.queries.history_ids, ep.queries.query_ids.cpu(), raw, ep.labels.cpu(),
                                    ep.supported.cpu(), failure, torch.zeros(qshape, dtype=torch.bool),
                                    {'scoring_v2': context})
            for row in score_predictions(batch, statistics, scoring_policy):
                row.update(score_scope=scope, full_inventory_hash=policy['full_inventory_hash'],
                           eligible_inventory_hash=policy['eligible_inventory_hash'],
                           payload_bytes=envelope['state_bytes'],
                           evaluation_boundary='causal_stream_with_host_state_inspection',
                           event_count=int(ep.events.lengths[0]), time_unit=ep.events.time_unit)
                rows.append(row)
    rows.sort(key=lambda r: (r['history_id'], r['query_id']))
    if not _allow_partial and seen != set(full_by_h):
        raise ValueError('incomplete expected scoring inventory')
    return rows


def select_candidate(ledger):
    qualified = [item for item in ledger if item.get('status') == 'qualified' and
                 type(item.get('loss')) in (int, float) and math.isfinite(item['loss']) and
                 type(item.get('active_static_bytes')) is int and item['active_static_bytes'] > 0]
    if not qualified:
        raise ValueError('no qualified finite development candidate')
    minimum = min(item['loss'] for item in qualified)
    tied = [item for item in qualified if item['loss'] <= minimum + 1e-12]
    return min(tied, key=lambda item: (item['active_static_bytes'], item['config_hash']))


def _stream_snapshot(model, ep, *, chunk_size=128, return_audit=False):
    """Use stream chunks, replaying a bad chunk to the first bad event."""
    if type(chunk_size) is not int or not 1 <= chunk_size <= 128:
        raise ValueError('stream chunk_size must be 1..128')
    validate_events(ep.events)
    validate_queries(ep.queries)
    if ep.events.history_ids != ep.queries.history_ids or len(ep.events.history_ids) != 1:
        raise ValueError('singleton causal history/query pair required')
    events, queries = ep.events, ep.queries
    last = events.timestamps[0, int(events.lengths[0]) - 1]
    if bool((queries.T[queries.present] < last).any()):
        raise ValueError('deferred queries required')
    state = None
    trigger = None
    chunk_hashes = []
    copy_bytes = replayed = replay_count = 0
    copy_seconds = replay_seconds = 0.

    def sliced(start, stop):
        return replace(events, **{name: getattr(events, name)[:, start:stop] for name in
                                  ('event_ids', 'timestamps', 'key_ids', 'key_features', 'values', 'present', 'observed')},
                       lengths=torch.tensor([stop - start], dtype=torch.int64),
                       auxiliary={k: v[:, start:stop] for k, v in events.auxiliary.items()})

    def bad_fields(snapshot):
        return [name for name, value in {**snapshot.payload, 'last_time': snapshot.last_time}.items()
                if value.is_floating_point() and not bool(torch.isfinite(value).all())]

    def numeric_exception(exc):
        return isinstance(exc, ArithmeticError) or (
            isinstance(exc, ValueError) and
            any(word in str(exc).lower() for word in ('nonfinite', 'overflow')))

    with torch.no_grad():
        for start in range(0, int(events.lengths[0]), chunk_size):
            stop = min(start + chunk_size, int(events.lengths[0]))
            chunk = sliced(start, stop)
            chunk_hashes.append(batch_hash(chunk))
            copy_started = time.perf_counter()
            checkpoint = inference_snapshot(state) if state is not None else None
            checkpoint_hash = snapshot_hash(checkpoint) if checkpoint is not None else None
            copy_seconds += time.perf_counter() - copy_started
            if checkpoint is not None:
                copy_bytes += state_ledger(checkpoint)['logical_bytes']
            chunk_error = None
            try:
                advanced = model.encode(chunk, state, mode='stream')
            except Exception as exc:
                if not numeric_exception(exc):
                    raise
                advanced = None
                chunk_error = exc
            if state is not None and snapshot_hash(state) != checkpoint_hash:
                raise ValueError('stream encode mutated its input checkpoint')
            if chunk_error is None and not bad_fields(advanced):
                state = advanced
                continue
            replay_count += 1
            replay_started = time.perf_counter()
            replay_state = checkpoint
            for i in range(start, stop):
                event = sliced(i, i + 1)
                replayed += 1
                try:
                    next_state = model.encode(event, replay_state, mode='stream')
                except Exception as exc:
                    if not numeric_exception(exc):
                        raise
                    trigger = {'reason': 'numerical_encode_exception', 'error': f'{type(exc).__name__}: {exc}',
                               'fields': [], 'event_offset': i + 1,
                               'parameter_hash': model.writer_hash if type(model) is RidgeMemoryModel else model._parameter_hash(),
                               'input_hash': batch_hash(event), 'history_id': events.history_ids[0],
                               'checkpoint_hash': checkpoint_hash}
                    state = replay_state
                    break
                bad = bad_fields(next_state)
                if bad:
                    trigger = {'reason': 'nonfinite_stored_state', 'fields': bad, 'event_offset': i + 1,
                               'parameter_hash': next_state.parameter_hash, 'input_hash': batch_hash(event),
                               'state_hash': snapshot_hash(next_state), 'history_id': events.history_ids[0],
                               'checkpoint_hash': checkpoint_hash}
                    state = next_state
                    break
                replay_state = next_state
            replay_seconds += time.perf_counter() - replay_started
            if trigger is None:
                raise RuntimeError('bad stream chunk did not reproduce under one-event replay')
            if state is None:
                state = model.init_state(1, device='cpu', dtype='float64')
            break
    if trigger is None:
        measured_bytes = model.persistent_nbytes(state)
        if measured_bytes != state_ledger(state)['logical_bytes']:
            raise ValueError('stream method/state byte ledger mismatch')
    audit = {'stream_chunk_size': chunk_size, 'chunk_count': len(chunk_hashes),
             'chunk_input_digest': canonical_hash(chunk_hashes),
             'final_snapshot_hash': snapshot_hash(state),
             'history_id': events.history_ids[0], 'time_unit': events.time_unit,
             'checkpoint_copy_bytes': copy_bytes, 'checkpoint_copy_seconds': copy_seconds,
             'replay_count': replay_count, 'replayed_events': replayed,
             'replay_seconds': replay_seconds}
    result = (state, trigger, state_ledger(state)['logical_bytes'])
    return (*result, audit) if return_audit else result


def _evaluate(model, factory, policy, statistics, method_name, worker_limits, out, started, allocation, *, equivalent=False):
    if (type(method_name) is not str or not method_name or
            any(ch not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-' for ch in method_name) or
            method_name in {'.', '..'}):
        raise ValueError('safe method identifier required')
    evaluation_started = time.perf_counter()
    statics = export_statics(model)
    episodes, envelopes, rows = [], [], []
    maximum = 0
    batches = 0
    stream_seconds = worker_seconds = score_seconds = 0.
    event_count = history_count = 0
    audits = {}
    def flush():
        nonlocal batches, worker_seconds, score_seconds
        if not episodes:
            return
        _admit(started, allocation, directory=out)
        positions = [i for i, item in enumerate(envelopes) if item['trigger'] is None]
        if positions:
            pairs = [{'snapshot': envelopes[i].pop('snapshot'), 'queries': episodes[i].queries,
                      'time_unit': episodes[i].events.time_unit} for i in positions]
            journal_path = Path(out) / 'worker-attempts' / f'{method_name}-{batches:05d}-{time.time_ns()}.json'
            worker_started = time.perf_counter()
            results = isolated_read_batch(statics, pairs,
                {'limits': worker_limits, 'timeout_seconds': min(120., allocation['max_wall_seconds']),
                 'journal_path': str(journal_path)})
            worker_seconds += time.perf_counter() - worker_started
            for i, result in zip(positions, results):
                envelopes[i]['result'] = result
        for item in envelopes:
            item.pop('snapshot', None)
        score_started = time.perf_counter()
        rows.extend(score_results(episodes, envelopes, statistics, policy, method_name, _allow_partial=True))
        score_seconds += time.perf_counter() - score_started
        episodes.clear(); envelopes.clear(); batches += 1
        _admit(started, allocation, directory=out)
    for ep in factory():
        _admit(started, allocation, directory=out)
        stream_started = time.perf_counter()
        if equivalent:
            measured = laguerre_control(model, ep.events, ep.queries, diagnostic_mode=True)
            state = measured['recovered_state']
            trigger = None
            bytes_used = model.persistent_nbytes(state)
            audit = {'stream_chunk_size': 1, 'chunk_count': int(ep.events.lengths[0]),
                     'chunk_input_digest': batch_hash(ep.events), 'checkpoint_copy_bytes': 0,
                     'checkpoint_copy_seconds': 0., 'replay_count': 0,
                     'replayed_events': 0, 'replay_seconds': 0.,
                     'coordinate_diagnostic': measured['coordinate_diagnostics'][ep.events.history_ids[0]],
                     'coordinate_seconds': measured['coordinate_seconds'],
                     'conversion_seconds': measured['conversion_seconds'],
                     'diagnostic_seconds': measured['diagnostic_seconds'],
                     'equivalent_state_bytes': measured['equivalent_state_bytes'],
                     'equivalent_metadata_bytes': measured['equivalent_metadata_bytes']}
        else:
            state, trigger, bytes_used, audit = _stream_snapshot(model, ep, return_audit=True)
        if equivalent and ep.events.history_ids[0] in audits:
            raise ValueError('duplicate evaluation history audit')
        audits[ep.events.history_ids[0]] = audit
        stream_seconds += time.perf_counter() - stream_started
        event_count += int(ep.events.lengths[0])
        history_count += 1
        maximum = max(maximum, bytes_used)
        episodes.append(ep)
        envelopes.append({'snapshot': state, 'result': None, 'trigger': trigger, 'state_bytes': bytes_used})
        if len(episodes) == min(64, worker_limits['max_histories']):
            flush()
    flush()
    primary = [row for row in rows if row['score_scope'] == 'primary']
    summary = aggregate_scores(primary)
    costs = {'maximum_state_bytes': maximum, 'worker_batches': batches,
                           'statics_bytes': len(canonical_json(statics)),
                           'event_count': event_count, 'history_count': history_count,
                           'stream_seconds': stream_seconds, 'worker_seconds': worker_seconds,
                           'score_seconds': score_seconds,
                           'stream_chunk_size': 1 if equivalent else 128,
                           'stream_audits': audits,
                           'stream_audits_sha256': canonical_hash(audits),
                           'checkpoint_copy_bytes': sum(item['checkpoint_copy_bytes'] for item in audits.values()),
                           'checkpoint_copy_seconds': sum(item['checkpoint_copy_seconds'] for item in audits.values()),
                           'replay_count': sum(item['replay_count'] for item in audits.values()),
                           'replayed_events': sum(item['replayed_events'] for item in audits.values()),
                           'replay_seconds': sum(item['replay_seconds'] for item in audits.values()),
                           'evaluation_seconds': time.perf_counter() - evaluation_started}
    if equivalent:
        costs['coordinate_model_sha256'] = coordinate_model_sha256(model)
        costs['coordinate_diagnostic_summary'] = validate_coordinate_audits(costs, rows, expected_model=model, require_summary=False)
        costs['evaluation_seconds'] = time.perf_counter() - evaluation_started
    return rows, summary, costs


def evaluate_panel(model, factory, policy, statistics, method, out, allocation, worker_limits) -> dict:
    """Generic public real/synthetic panel evaluator for E4 callers.

    The caller freezes policy and allocation first, and supplies a replayable
    Episode factory. Every snapshot advances all events through the stream
    recurrence in chunks of at most 128; each worker batch sees only statics,
    snapshots and queries.
    """
    required = {'schema_version', 'phase', 'manifest_sha256', 'allocation_id',
                'max_wall_seconds', 'max_disk_bytes', 'max_rss_bytes'}
    if (type(policy) is not dict or type(allocation) is not dict or set(allocation) != required or allocation['schema_version'] != 1 or
            allocation['phase'] not in {'unit_test', 'development', 'pilot', 'confirmation', 'replication', 'test'} or
            type(allocation['allocation_id']) is not str or not allocation['allocation_id'] or
            type(allocation['manifest_sha256']) is not str or len(allocation['manifest_sha256']) != 64 or
            any(ch not in '0123456789abcdef' for ch in allocation['manifest_sha256']) or
            allocation['manifest_sha256'] != policy.get('manifest_hash') or
            type(allocation['max_wall_seconds']) not in (int, float) or
            not math.isfinite(allocation['max_wall_seconds']) or allocation['max_wall_seconds'] <= 0 or
            any(type(allocation[k]) is not int or allocation[k] <= 0
                for k in ('max_disk_bytes', 'max_rss_bytes'))):
        raise ValueError('finite panel allocation required')
    if not callable(factory):
        raise ValueError('replayable episode factory required')
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    rows, summary, costs = _evaluate(model, factory, policy, statistics, method,
                                      worker_limits, out, started, allocation)
    ref = persist_score_rows(rows, out / f'{method}-rows.json',
                             max_bytes=int(_admit(started, allocation, directory=out)['remaining_disk_bytes']))
    return {'schema_version': 1, 'method': method, 'rows_ref': ref, 'summary': summary,
            'costs': costs, 'full_inventory_hash': policy['full_inventory_hash'],
            'eligible_inventory_hash': policy['eligible_inventory_hash'],
            'statistics_sha256': canonical_hash(statistics),
            'admission': _admit(started, allocation, directory=out)}


def _probe_forecast(manifest, probe_training, probe_development, cache_seconds, fit_seconds, costs):
    study = manifest['config']['profile'] == 'study'
    training = manifest['training_inventory']
    development = manifest['development_inventory']
    train_events = sum(item['spec']['lengths'][0] for item in training)
    dev_events = sum(item['spec']['lengths'][0] for item in development)
    probe_train_events = sum(item['spec']['lengths'][0] for item in probe_training)
    probe_dev_events = sum(item['spec']['lengths'][0] for item in probe_development)
    prefix_events = sum(sum(item['spec']['lengths'][0] for item in training[:prefix])
                        for prefix in (192, 384)) * 2 if study else 0
    passes = 36 + (4 if study else 0) + 6  # exact, four bounded, Laguerre
    fits = 40 if study else 36
    worker_batches = passes * math.ceil(len(development) / manifest['config']['worker_limits']['max_histories'])
    training_steps = 36 * train_events + prefix_events
    development_steps = passes * dev_events
    return {'status': 'linear_extrapolation_with_unmeasured_solver_and_cache_variance',
            'expected_fit_attempts': fits, 'candidate_fit_attempts': 36,
            'prefix_fit_attempts': 4 if study else 0,
            'training_event_steps': training_steps,
            'training_episode_replay_event_steps': 4 * training_steps,
            'training_metadata_scan_event_steps': 2 * training_steps,
            'training_terminal_writer_event_steps_range': [training_steps, 2 * training_steps],
            'development_history_passes': passes * len(development),
            'development_event_steps': development_steps,
            'worker_batches': worker_batches,
            'probe_training_event_steps': probe_train_events,
            'probe_development_event_steps': probe_dev_events,
            'estimated_training_fit_seconds': fit_seconds * training_steps / probe_train_events,
            'estimated_development_stream_seconds': costs['stream_seconds'] * development_steps / probe_dev_events,
            'estimated_cold_worker_seconds': costs['worker_seconds'] * worker_batches / max(1, costs['worker_batches']),
            'estimated_cache_construction_seconds': cache_seconds *
                (len(training) + len(development)) / max(1, len(probe_training) + len(probe_development)),
            'solver_workspace_bytes': None, 'rss_growth_status': 'not_extrapolatable_from_small_probe',
            'method_variance_status': 'controls_and_q16_solver_not_measured_by_probe',
            'development_admission_status': 'requires_separate_finite_allocation'}


def _fit_one(reader, shape, train_cache, train_ids, out, allocation, started, workspace):
    _admit(started, allocation, directory=workspace)
    factory = episode_factory(train_cache, train_ids)
    meta = fit_training_metadata(factory)
    model = attach_training_cache(build_model(shape, ReaderSpec.from_json(reader), meta['t_ref'],
                                              meta['target_statistics']), train_cache,
                                  {'lru_bytes': train_cache.lru_bytes})
    fit_manifest = make_fit_manifest(model, meta)
    fit = fit_reader(model, factory, fit_manifest, chunk_rows=1024)
    ref = save_model(model, Path(out))
    loaded = load_model(ref.path, ref.sha256)
    if type(loaded) is not RidgeMemoryModel:
        raise ValueError('inference must use exact base E1 class')
    admission = _admit(started, allocation, directory=workspace)
    return loaded, meta, fit, ref, model.cache_stats, admission


def _cache_for(specs, inventory, root, limits, *, incremental_disk_bytes=None):
    if (type(limits) is not dict or set(limits) != {'disk_bytes', 'lru_bytes'} or
            any(type(value) is not int or value <= 0 for value in limits.values()) or
            incremental_disk_bytes is not None and
            (type(incremental_disk_bytes) is not int or incremental_disk_bytes < 0)):
        raise ValueError('invalid cache total/incremental disk admission')
    path = Path(root) / 'cache-manifest.json'
    if path.exists():
        raw = path.read_bytes()
        cache = load_episode_cache(root, hashlib.sha256(raw).hexdigest())
        requested_specs = {canonical_hash(s) for s in specs}
        requested = [(item['history_id'], canonical_hash(item['spec'])) for item in inventory]
        saved = [(entry['history_id'], entry['spec_sha256']) for entry in cache.entries]
        if requested != saved or any(spec_hash not in requested_specs for _, spec_hash in requested):
            raise ValueError('resumed cache history/spec inventory mismatch')
        if (limits['disk_bytes'] < cache.disk_bytes or limits['lru_bytes'] != cache.lru_bytes):
            raise ValueError('resumed cache ceiling/admission mismatch')
        return cache
    disk_ceiling = limits['disk_bytes'] if incremental_disk_bytes is None else min(limits['disk_bytes'], incremental_disk_bytes)
    if disk_ceiling <= 0:
        raise RuntimeError('new episode cache has no incremental disk admission')
    return prepare_episode_cache([PopulationSpec.from_json(s) for s in specs], inventory, root,
                                 {**limits, 'disk_bytes': disk_ceiling})


def probe_feasibility(manifest, out, allocation) -> dict:
    shape = _validate_manifest(manifest)
    _allocation(allocation, 'probe', manifest)
    started = time.monotonic()
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    prior_probe = out / 'probe.json'
    if prior_probe.exists():
        existing = json.loads(prior_probe.read_bytes())
        if (existing.get('manifest_sha256') != manifest['manifest_sha256'] or
                'allocation' in existing and existing['allocation'] != allocation):
            raise ValueError('probe output directory belongs to a different manifest/allocation')
    record = {'schema_version': 1, 'phase': 'probe', 'manifest_sha256': manifest['manifest_sha256'],
              'allocation': allocation, 'status': 'incomplete'}
    try:
        train = manifest['training_inventory'][:min(2, len(manifest['training_inventory']))]
        dev = manifest['development_inventory'][:1]
        limits = manifest['config']['cache_limits']
        train_incremental = int(_admit(started, allocation, directory=out)['remaining_disk_bytes'])
        cache_started = time.perf_counter()
        cache = _cache_for(manifest['training_specs'], train, out / 'probe-training-cache',
                           limits, incremental_disk_bytes=train_incremental)
        dev_total_ceiling = limits['disk_bytes'] - cache.disk_bytes
        if dev_total_ceiling <= 0:
            raise RuntimeError('probe development cache configured ceiling exhausted')
        dev_incremental = int(_admit(started, allocation, directory=out)['remaining_disk_bytes'])
        dev_cache = _cache_for(manifest['development_specs'], dev, out / 'probe-development-cache',
                               {'disk_bytes': dev_total_ceiling, 'lru_bytes': limits['lru_bytes']},
                               incremental_disk_bytes=dev_incremental)
        cache_seconds = time.perf_counter() - cache_started
        _admit(started, allocation, directory=out)
        candidate = manifest['candidates'][0]
        fit_started = time.perf_counter()
        model, meta, fit, ref, cache_stats, admission = _fit_one(candidate['reader'], shape, cache,
            [item['history_id'] for item in train], out / 'probe-model.json', allocation, started, out)
        fit_seconds = time.perf_counter() - fit_started
        policy = freeze_score_policy(episode_factory(dev_cache, [item['history_id'] for item in dev])(),
                                     manifest_hash=manifest['manifest_sha256'])
        rows, summary, costs = _evaluate(model, episode_factory(dev_cache, [item['history_id'] for item in dev]),
            policy, meta['target_statistics'], 'probe', manifest['config']['worker_limits'], out,
            started, allocation)
        row_budget = int(_admit(started, allocation, directory=out)['remaining_disk_bytes'])
        row_ref = persist_score_rows(rows, out / 'probe-rows.json', max_bytes=row_budget)
        record.update(status='measured', fit_ref={'path': str(ref.path), 'sha256': ref.sha256},
                      fit_rows=fit.row_count, cache_stats=cache_stats, admission=admission,
                      score=summary, costs=costs, row_ref=row_ref,
                      train_cache_sha256=cache.manifest_sha256, development_cache_sha256=dev_cache.manifest_sha256,
                      feasible=summary['status'] == 'ok',
                      forecast=_probe_forecast(manifest, train, dev, cache_seconds, fit_seconds, costs))
    except Exception as exc:
        record.update(status='failed', error=f'{type(exc).__name__}: {exc}')
    record['final_admission'] = _admit(started, allocation, directory=out) if record['status'] == 'measured' else None
    record.setdefault('feasible', False)
    _atomic_json(out / 'probe.json', record)
    _admit(started, allocation, directory=out)
    return record


def _audit_terminal_entries(journal, policy, out):
    """Revalidate persisted model and normalized score evidence before resume skips it."""
    root = Path(out).resolve()
    policy_hash = canonical_hash(policy)
    diagnostic = _diagnostic_score_policy(policy)
    diagnostic_hash = canonical_hash(diagnostic)
    full = {(item['history_id'], task, query_id) for item in policy['full_inventory']
            for task, query_ids in item['tasks'].items() for query_id in query_ids}
    eligible = {(item['history_id'], task, query_id) for item in policy['expected_inventory']
                for task, query_ids in item['tasks'].items() for query_id in query_ids}
    def local_ref(ref):
        path = Path(ref['path']).resolve()
        if not path.is_relative_to(root):
            raise ValueError('resumed artifact path escapes development allocation')
        return path
    def score_entry(entry, method):
        ref = entry['rows_ref']
        local_ref(ref)
        rows = load_score_rows(ref)
        observed = set()
        for row in rows:
            identity = (row['history_id'], row['task'], row['query_id'])
            primary = identity in eligible
            expected_policy = policy if primary else diagnostic
            expected_hash = policy_hash if primary else diagnostic_hash
            if (identity not in full or identity in observed or row['method'] != method or
                    row['score_scope'] != ('primary' if primary else 'ineligible_diagnostic') or
                    row['policy_hash'] != expected_hash or row['policy'] != expected_policy or
                    row['full_inventory_hash'] != policy['full_inventory_hash'] or
                    row['eligible_inventory_hash'] != policy['eligible_inventory_hash']):
                raise ValueError('resumed score row method/policy/inventory mismatch')
            observed.add(identity)
        if observed != full:
            raise ValueError('resumed full scoring query inventory mismatch')
        summary = aggregate_scores([row for row in rows if row['score_scope'] == 'primary'])
        if canonical_hash(summary) != canonical_hash(entry['score']):
            raise ValueError('resumed score aggregate mismatch')
        if method == 'laguerre':
            winner = select_candidate([item for item in journal['candidate_ledger'] if item['family'] == 'jet'])
            selected_ref = winner['fit_ref']
            if journal['selected']['jet']['fit_ref'] != selected_ref:
                raise ValueError('coordinate resumed selected checkpoint mismatch')
            local_ref(selected_ref)
            selected_model = load_coordinate_model(selected_ref)
            validate_coordinate_audits(entry.get('costs'), rows, expected_model=selected_model)
        return summary
    for entry in journal['candidate_ledger']:
        if entry['status'] == 'qualified':
            ref = entry['fit_ref']
            load_model(local_ref(ref), ref['sha256'])
            summary = score_entry(entry, entry['config_hash'])
            if entry['loss'] != summary['loss']:
                raise ValueError('resumed candidate loss mismatch')
        elif entry['status'] == 'failed' and 'rows_ref' in entry:
            score_entry(entry, entry['config_hash'])
    for entry in journal['prefix_ledger']:
        if entry['status'] == 'measured':
            ref = entry['fit_ref']
            load_model(local_ref(ref), ref['sha256'])
            score_entry(entry, f"{entry['family']}-prefix-{entry['prefix']}")
    for name, entry in journal['controls'].items():
        if entry['status'] == 'measured':
            score_entry(entry, name)


def run_development(manifest, out, allocation) -> dict:
    shape = _validate_manifest(manifest)
    _allocation(allocation, 'development', manifest)
    invocation_started = time.monotonic()
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    journal_path = out / 'development.json'
    resuming = journal_path.exists()
    if resuming:
        journal = json.loads(journal_path.read_bytes())
        if journal.get('manifest_sha256') != manifest['manifest_sha256'] or journal.get('allocation') != allocation:
            raise ValueError('development resume allocation/manifest mismatch')
        started = _resume_allocation_started(journal)
    else:
        started = invocation_started
        journal = {'schema_version': 1, 'status': 'incomplete', 'manifest_sha256': manifest['manifest_sha256'],
                   'allocation': allocation, 'candidate_ledger': [], 'prefix_ledger': [], 'controls': {},
                   'expected_fit_count': manifest['expected_fit_count'], 'completed_fit_count': 0,
                   'allocation_started_epoch_seconds': time.time(),
                   'allocation_clock_kind': 'continuous_wall_since_first_development_invocation'}
        _atomic_json(journal_path, journal)
    _admit(started, allocation, directory=out)
    limits = manifest['config']['cache_limits']
    train_incremental = int(_admit(started, allocation, directory=out)['remaining_disk_bytes'])
    train_cache_started = time.perf_counter()
    train_cache = _cache_for(manifest['training_specs'], manifest['training_inventory'], out / 'training-cache',
                             limits, incremental_disk_bytes=train_incremental)
    train_cache_seconds = time.perf_counter() - train_cache_started
    dev_total_ceiling = limits['disk_bytes'] - train_cache.disk_bytes
    if dev_total_ceiling <= 0:
        raise RuntimeError('development cache configured ceiling exhausted')
    dev_incremental = int(_admit(started, allocation, directory=out)['remaining_disk_bytes'])
    dev_cache_started = time.perf_counter()
    dev_cache = _cache_for(manifest['development_specs'], manifest['development_inventory'],
                           out / 'development-cache',
                           {'disk_bytes': dev_total_ceiling, 'lru_bytes': limits['lru_bytes']},
                           incremental_disk_bytes=dev_incremental)
    dev_cache_seconds = time.perf_counter() - dev_cache_started
    _admit(started, allocation, directory=out)
    train_ids = [item['history_id'] for item in manifest['training_inventory']]
    dev_ids = [item['history_id'] for item in manifest['development_inventory']]
    dev_factory = episode_factory(dev_cache, dev_ids)
    policy = freeze_score_policy(dev_factory(), manifest_hash=manifest['manifest_sha256'])
    policy_ref = _atomic_json(out / 'development-policy.json', policy)
    if resuming and 'shared_costs' in journal:
        shared = journal['shared_costs']
        shared['resume_training_cache_open_seconds'] = shared.get('resume_training_cache_open_seconds', 0.) + train_cache_seconds
        shared['resume_development_cache_open_seconds'] = shared.get('resume_development_cache_open_seconds', 0.) + dev_cache_seconds
        shared['amortized_training_cache_seconds_per_fit'] = (shared['training_cache_seconds'] +
            shared['resume_training_cache_open_seconds']) / (40 if manifest['config']['profile'] == 'study' else 36)
        shared['amortized_development_cache_seconds_per_panel'] = (shared['development_cache_seconds'] +
            shared['resume_development_cache_open_seconds']) / (
            46 if manifest['config']['profile'] == 'study' else 42)
    else:
        shared = {'training_cache_seconds': train_cache_seconds,
                  'development_cache_seconds': dev_cache_seconds,
                  'resume_training_cache_open_seconds': 0.,
                  'resume_development_cache_open_seconds': 0.,
                  'training_cache_bytes': train_cache.disk_bytes,
                  'development_cache_bytes': dev_cache.disk_bytes,
                  'amortized_training_cache_seconds_per_fit': train_cache_seconds / (
                      40 if manifest['config']['profile'] == 'study' else 36),
                  'amortized_development_cache_seconds_per_panel': dev_cache_seconds / (
                      46 if manifest['config']['profile'] == 'study' else 42)}
    journal.update(training_cache_sha256=train_cache.manifest_sha256,
                   development_cache_sha256=dev_cache.manifest_sha256, policy_ref=policy_ref,
                   full_inventory_hash=policy['full_inventory_hash'],
                   eligible_inventory_hash=policy['eligible_inventory_hash'],
                   shared_costs=shared)
    if resuming:
        _audit_terminal_entries(journal, policy, out)
    _atomic_json(journal_path, journal)
    done = {item['config_hash'] for item in journal['candidate_ledger']
            if item['status'] in {'qualified', 'failed'}}
    for candidate in manifest['candidates']:
        if candidate['config_hash'] in done:
            continue
        item = {'family': candidate['family'], 'config_hash': candidate['config_hash'],
                'reader': candidate['reader'], 'status': 'incomplete'}
        journal['candidate_ledger'].append(item)
        journal['fit_attempt_count'] = journal.get('fit_attempt_count', 0) + 1
        _atomic_json(journal_path, journal)
        try:
            fit_started = time.perf_counter()
            model, meta, fit, ref, cache_stats, admission = _fit_one(candidate['reader'], shape,
                train_cache, train_ids, out / 'models' / (candidate['config_hash'] + '.json'), allocation, started, out)
            fit_wall = time.perf_counter() - fit_started
            journal['completed_fit_count'] += 1
        except ArithmeticError as exc:
            item.update(status='failed', loss=None, error=f'{type(exc).__name__}: {exc}',
                        failure_stage='numerical_fit')
            _atomic_json(journal_path, journal)
            continue
        except Exception as exc:
            item.update(status='incomplete', error=f'{type(exc).__name__}: {exc}',
                        failure_stage='fit_infrastructure_or_data')
            journal['status'] = 'incomplete'
            _atomic_json(journal_path, journal)
            raise
        try:
            rows, summary, costs = _evaluate(model, dev_factory, policy, meta['target_statistics'],
                candidate['config_hash'], manifest['config']['worker_limits'], out, started, allocation)
            row_started = time.perf_counter()
            row_ref = persist_score_rows(rows, out / 'rows' / (candidate['config_hash'] + '.json'),
                max_bytes=int(_admit(started, allocation, directory=out)['remaining_disk_bytes']))
            row_seconds = time.perf_counter() - row_started
            item.update(status='qualified' if summary['status'] == 'ok' else 'failed',
                        loss=summary['loss'], score=summary,
                        active_static_bytes=model.parameter_nbytes(),
                        wire_static_bytes=costs['statics_bytes'],
                        numeric_parameter_bytes=model.parameter_nbytes(),
                        fit_ref={'path': str(ref.path), 'sha256': ref.sha256},
                        statistics_sha256=canonical_hash(meta['target_statistics']),
                        training_data_sha256=meta['data_sha256'], fit_rows=fit.row_count,
                        fit_objective=fit.objective, cache_stats=cache_stats, admission=admission,
                        costs={**costs, 'fit_wall_seconds': fit_wall, 'row_persistence_seconds': row_seconds,
                               'standalone_seconds': fit_wall + costs['evaluation_seconds'] + row_seconds +
                                   shared['training_cache_seconds'] + shared['development_cache_seconds'] +
                                   shared['resume_training_cache_open_seconds'] +
                                   shared['resume_development_cache_open_seconds'],
                               'amortized_seconds': fit_wall + costs['evaluation_seconds'] + row_seconds +
                                   journal['shared_costs']['amortized_training_cache_seconds_per_fit'] +
                                   journal['shared_costs']['amortized_development_cache_seconds_per_panel']},
                        rows_ref=row_ref)
        except Exception as exc:
            item.update(status='incomplete', error=f'{type(exc).__name__}: {exc}',
                        failure_stage='evaluation_or_persistence')
            journal['status'] = 'incomplete'
            _atomic_json(journal_path, journal)
            raise
        journal['admission'] = _admit(started, allocation, directory=out)
        _atomic_json(journal_path, journal)
    selected = {}
    for family in ('jet', 'bank'):
        winner = select_candidate([item for item in journal['candidate_ledger'] if item['family'] == family])
        selected[family] = {'config_hash': winner['config_hash'], 'reader': winner['reader'],
                            'fit_ref': winner['fit_ref'], 'loss': winner['loss']}
    journal['selected'] = selected
    _atomic_json(journal_path, journal)
    done_prefix = {(item['family'], item['prefix']) for item in journal['prefix_ledger']
                   if item['status'] in {'measured', 'failed'}}
    for family, winner in selected.items():
        for prefix in (192, 384) if manifest['config']['profile'] == 'study' else ():
            if (family, prefix) in done_prefix:
                continue
            item = {'family': family, 'prefix': prefix, 'status': 'incomplete'}
            journal['prefix_ledger'].append(item)
            journal['fit_attempt_count'] = journal.get('fit_attempt_count', 0) + 1
            _atomic_json(journal_path, journal)
            try:
                fit_started = time.perf_counter()
                model, meta, fit, ref, cache_stats, admission = _fit_one(winner['reader'], shape, train_cache,
                    train_ids[:prefix], out / 'models' / f'{family}-prefix-{prefix}.json', allocation, started, out)
                fit_wall = time.perf_counter() - fit_started
                journal['completed_fit_count'] += 1
            except ArithmeticError as exc:
                item.update(status='failed', error=f'{type(exc).__name__}: {exc}', failure_stage='numerical_fit')
                _atomic_json(journal_path, journal)
                continue
            except Exception as exc:
                item.update(status='incomplete', error=f'{type(exc).__name__}: {exc}',
                            failure_stage='fit_infrastructure_or_data')
                journal['status'] = 'incomplete'
                _atomic_json(journal_path, journal)
                raise
            try:
                rows, summary, costs = _evaluate(model, dev_factory, policy, meta['target_statistics'],
                    f'{family}-prefix-{prefix}', manifest['config']['worker_limits'], out, started, allocation)
                row_started = time.perf_counter()
                row_ref = persist_score_rows(rows, out / 'rows' / f'{family}-prefix-{prefix}.json',
                    max_bytes=int(_admit(started, allocation, directory=out)['remaining_disk_bytes']))
                row_seconds = time.perf_counter() - row_started
                item.update(status='measured', fit_ref={'path': str(ref.path), 'sha256': ref.sha256},
                            training_data_sha256=meta['data_sha256'], statistics_sha256=canonical_hash(meta['target_statistics']),
                            score=summary, rows_ref=row_ref,
                            costs={**costs, 'fit_wall_seconds': fit_wall,
                                   'row_persistence_seconds': row_seconds,
                                   'standalone_seconds': fit_wall + costs['evaluation_seconds'] + row_seconds +
                                       shared['training_cache_seconds'] + shared['development_cache_seconds'] +
                                       shared['resume_training_cache_open_seconds'] +
                                       shared['resume_development_cache_open_seconds'],
                                   'amortized_seconds': fit_wall + costs['evaluation_seconds'] + row_seconds +
                                       shared['amortized_training_cache_seconds_per_fit'] +
                                       shared['amortized_development_cache_seconds_per_panel']},
                            cache_stats=cache_stats, admission=admission)
            except Exception as exc:
                item.update(status='incomplete', error=f'{type(exc).__name__}: {exc}',
                            failure_stage='evaluation_or_persistence')
                journal['status'] = 'incomplete'
                _atomic_json(journal_path, journal)
                raise
            _atomic_json(journal_path, journal)
    selected_jet = selected['jet']['fit_ref']
    base = load_model(Path(selected_jet['path']), selected_jet['sha256'])
    if type(base) is not RidgeMemoryModel:
        raise ValueError('selected inference reader subclass rejected')
    controls = build_controls(shape, 9345 if shape == ShapeSpec(16, 8) else 1665,
                              base.target_statistics, manifest['config']['training_seed'])
    for name, info in controls.items():
        if name in journal['controls'] and journal['controls'][name]['status'] == 'measured':
            continue
        entry = {'status': 'incomplete', 'capacity': info['capacity'],
                 'static_bytes': info['static_bytes'], 'state_budget': info['state_budget']}
        journal['controls'][name] = entry
        _atomic_json(journal_path, journal)
        try:
            rows, summary, costs = _evaluate(info['method'], dev_factory, policy, base.target_statistics,
                name, manifest['config']['worker_limits'], out, started, allocation)
            if info['bounded'] and costs['maximum_state_bytes'] > info['state_budget']:
                raise ValueError('occupied bounded control exceeded persistent state budget')
            row_ref = persist_score_rows(rows, out / 'rows' / f'control-{name}.json',
                max_bytes=int(_admit(started, allocation, directory=out)['remaining_disk_bytes']))
            entry.update(status='measured', score=summary, costs=costs,
                         unused_bytes=info.get('unused_bytes'),
                         rows_ref=row_ref)
        except Exception as exc:
            entry.update(status='incomplete', error=f'{type(exc).__name__}: {exc}')
            journal['status'] = 'incomplete'
            _atomic_json(journal_path, journal)
            raise
        _atomic_json(journal_path, journal)
    if journal['controls'].get('laguerre', {}).get('status') != 'measured':
        entry = {'status': 'incomplete', 'equivalent_to': selected['jet']['config_hash']}
        journal['controls']['laguerre'] = entry
        _atomic_json(journal_path, journal)
        try:
            rows, summary, costs = _evaluate(base, dev_factory, policy, base.target_statistics,
                'laguerre', manifest['config']['worker_limits'], out, started, allocation, equivalent=True)
            row_ref = persist_score_rows(rows, out / 'rows' / 'control-laguerre.json',
                max_bytes=int(_admit(started, allocation, directory=out)['remaining_disk_bytes']))
            entry.update(status='measured', score=summary, costs=costs, rows_ref=row_ref)
        except Exception as exc:
            entry.update(status='incomplete', error=f'{type(exc).__name__}: {exc}')
            journal['status'] = 'incomplete'
            _atomic_json(journal_path, journal)
            raise
    terminal_candidates = {item['config_hash'] for item in journal['candidate_ledger']
                           if item['status'] in {'qualified', 'failed'}}
    measured_prefix = {(item['family'], item['prefix']) for item in journal['prefix_ledger']
                       if item['status'] == 'measured'}
    required_prefix = {(family, prefix) for family in ('jet', 'bank')
                       for prefix in ((192, 384) if manifest['config']['profile'] == 'study' else ())}
    journal['status'] = ('complete' if len(terminal_candidates) == 36 and
                         journal.get('fit_attempt_count', 0) >= manifest['expected_fit_count'] and
                         measured_prefix == required_prefix and
                         set(journal['controls']) == {'exact', 'recent', 'latest_lru', 'reservoir', 'buckets', 'laguerre'} and
                         all(item['status'] == 'measured' for item in journal['controls'].values()) else 'incomplete')
    journal['admission'] = _admit(started, allocation, directory=out)
    _atomic_json(journal_path, journal)
    _admit(started, allocation, directory=out)
    return journal
