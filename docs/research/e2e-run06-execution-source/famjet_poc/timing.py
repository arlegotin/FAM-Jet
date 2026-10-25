"""Paired CPU64 timing with explicit boundaries and finite timing allocation."""
from dataclasses import replace
import json
import math
import os
from pathlib import Path
import random
import resource
import statistics
import subprocess
import sys
import time

import torch

from famjet.data.schema import validate_events, validate_queries
from famjet.eval.state_io import tensor_record
from famjet.provenance import canonical_hash, canonical_json
from .cache import e3_source_sha256
from .contracts import source_sha256
from .models import RidgeMemoryModel
from .study import _admit, _atomic_json, _stream_snapshot
from .wire import encode_request, export_statics, isolated_read_batch


def timed_pipeline(preprocess, ingest, read, *, clock=time.perf_counter):
    """Measure adjacent, nonoverlapping real work intervals."""
    start = clock()
    preprocess()
    preprocessed = clock()
    ingest()
    ingested = clock()
    read()
    finished = clock()
    values = [preprocessed - start, ingested - preprocessed, finished - ingested, finished - start]
    if any(not math.isfinite(v) or v < 0 for v in values):
        raise ValueError('nonmonotone timing clock')
    return dict(zip(('preprocessing_seconds', 'ingest_seconds', 'read_output_seconds', 'complete_seconds'), values))


def measure_one_event(encode, *, clock=time.perf_counter):
    started = clock()
    encode()
    elapsed = clock() - started
    if not math.isfinite(elapsed) or elapsed < 0:
        raise ValueError('nonmonotone single-event timing clock')
    return elapsed


def break_even_queries(extra_ingest_seconds, baseline_query_seconds, candidate_query_seconds, *, accuracy_satisfied):
    values = (extra_ingest_seconds, baseline_query_seconds, candidate_query_seconds)
    if any(type(v) not in (int, float) or not math.isfinite(v) or v < 0 for v in values) or type(accuracy_satisfied) is not bool:
        raise ValueError('finite nonnegative timing inputs and explicit accuracy flag required')
    saving = baseline_query_seconds - candidate_query_seconds
    if not accuracy_satisfied or saving <= 0:
        return None
    return math.ceil(extra_ingest_seconds / saving)


def _quantiles(values):
    data = sorted(values)
    if not data:
        raise ValueError('empty timing blocks')
    def quantile(p):
        position = (len(data) - 1) * p
        low = math.floor(position)
        high = math.ceil(position)
        return data[low] + (data[high] - data[low]) * (position - low)
    rng = random.Random(0)
    bootstrap_medians = sorted(statistics.median(rng.choices(data, k=len(data))) for _ in range(1000))
    return {'p50': quantile(.5), 'p95': quantile(.95), 'min': data[0], 'max': data[-1],
            'median_bootstrap_95': [bootstrap_medians[24], bootstrap_medians[974]],
            'blocks': data, 'uncertainty_unit': 'separated_block'}


def _query_count(queries, count):
    if len(queries.history_ids) != 1 or int(queries.lengths[0]) <= 0:
        raise ValueError('singleton nonempty query workload required')
    source = int(queries.lengths[0])
    indices = torch.tensor([j % source for j in range(count)], dtype=torch.int64)
    fields = {name: getattr(queries, name).index_select(1, indices).clone() for name in
              ('T', 'key_ids', 'key_features', 'age_start', 'age_end', 'present')}
    fields['query_ids'] = torch.arange(count, dtype=torch.int64)[None]
    return replace(queries, tasks=(tuple(queries.tasks[0][j % source] for j in range(count)),),
                   lengths=torch.tensor([count], dtype=torch.int64), **fields)


def _cold_start_seconds():
    root = Path(__file__).resolve().parents[1]
    command = [sys.executable, '-I', '-c', 'import sys; sys.path.insert(0, '+repr(str(root))+
               '); import famjet_poc.worker']
    env = {k: v for k, v in os.environ.items() if k in {'SYSTEMROOT', 'WINDIR'}}
    env.update(OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1',
               VECLIB_MAXIMUM_THREADS='1', NUMEXPR_NUM_THREADS='1')
    start = time.perf_counter()
    completed = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env, timeout=60)
    if completed.returncode:
        raise RuntimeError('cold worker startup failed: '+completed.stderr.decode(errors='replace')[-500:])
    return time.perf_counter() - start


def _rss_bytes():
    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return int(value if os.uname().sysname == 'Darwin' else value * 1024)


def benchmark(methods, workloads, policy, out, allocation) -> dict:
    """Run the fixed paired Q1/Q8/Q64 timing design; no training cache is read."""
    required = {'warmups', 'blocks', 'query_counts', 'seed', 'worker_limits',
                'timeout_seconds', 'accuracy_satisfied', 'manifest_sha256', 'baseline_method'}
    if (type(policy) is not dict or set(policy) != required or policy['warmups'] != 3 or
            policy['blocks'] != 12 or policy['query_counts'] != [1, 8, 64] or
            type(policy['seed']) is not int or type(policy['accuracy_satisfied']) is not dict):
        raise ValueError('frozen 3-warmup/12-block Q1/Q8/Q64 policy required')
    if (type(methods) is not dict or len(methods) < 2 or
            set(policy['accuracy_satisfied']) != set(methods) or
            not all(type(value) is bool for value in policy['accuracy_satisfied'].values()) or
            not workloads):
        raise ValueError('paired methods/workloads and accuracy admission required')
    if policy['baseline_method'] not in methods:
        raise ValueError('declared baseline method required')
    if any(isinstance(method, RidgeMemoryModel) and type(method) is not RidgeMemoryModel for method in methods.values()):
        raise ValueError('timing rejects training subclasses')
    if (type(allocation) is not dict or set(allocation) != {'schema_version', 'phase', 'manifest_sha256',
            'allocation_id', 'max_wall_seconds', 'max_disk_bytes', 'max_rss_bytes'} or
            allocation['schema_version'] != 1 or allocation['phase'] != 'timing' or
            allocation['manifest_sha256'] != policy['manifest_sha256'] or
            type(allocation['max_wall_seconds']) not in (int, float) or
            not math.isfinite(allocation['max_wall_seconds']) or allocation['max_wall_seconds'] <= 0 or
            any(type(allocation[k]) is not int or allocation[k] <= 0
                for k in ('max_disk_bytes', 'max_rss_bytes'))):
        raise ValueError('finite timing phase allocation required')
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    rng = random.Random(policy['seed'])
    ordered_names = tuple(sorted(methods))
    statics = {name: export_statics(model) for name, model in methods.items()}
    records = []
    for warm in range(policy['warmups'] + policy['blocks']):
        block = warm - policy['warmups']
        for qcount in policy['query_counts']:
            episode = workloads[(warm * len(policy['query_counts']) + qcount) % len(workloads)]
            if len(episode.events.history_ids) != 1:
                raise ValueError('timing requires singleton real episode workloads')
            query = _query_count(episode.queries, qcount)
            order = list(ordered_names)
            rng.shuffle(order)
            for name in order:
                model = methods[name]
                state_holder = {}
                single_event_seconds = None
                single_event_setup_seconds = None
                if qcount == 1:
                    events = episode.events
                    prefix_length = min(127, int(events.lengths[0]) - 1)
                    if prefix_length <= 0:
                        raise ValueError('one-event latency needs a preceding stream event')
                    prefix = replace(events,
                        **{field: getattr(events, field)[:, :prefix_length] for field in
                           ('event_ids', 'timestamps', 'key_ids', 'key_features', 'values', 'present', 'observed')},
                        lengths=torch.tensor([prefix_length], dtype=torch.int64),
                        auxiliary={k: v[:, :prefix_length] for k, v in events.auxiliary.items()})
                    setup_started = time.perf_counter()
                    prior_state = model.encode(prefix, mode='stream')
                    one = replace(events,
                        **{field: getattr(events, field)[:, prefix_length:prefix_length+1] for field in
                           ('event_ids', 'timestamps', 'key_ids', 'key_features', 'values', 'present', 'observed')},
                        lengths=torch.ones_like(events.lengths),
                        auxiliary={k: v[:, prefix_length:prefix_length+1] for k, v in events.auxiliary.items()})
                    single_event_seconds = measure_one_event(lambda: model.encode(one, prior_state, mode='stream'))
                    single_event_setup_seconds = time.perf_counter() - setup_started - single_event_seconds
                def preprocess():
                    validate_events(episode.events)
                    validate_queries(query)
                def ingest():
                    state, trigger, max_bytes = _stream_snapshot(model, episode)
                    if trigger is not None:
                        raise ArithmeticError('timing workload quarantined')
                    state_holder.update(state=state, max_state_bytes=max_bytes)
                def read():
                    state_holder['result'] = model.read(state_holder['state'], query)
                    state_holder['output_record'] = tensor_record(state_holder['result'].prediction)
                rss_before = _rss_bytes()
                intervals = timed_pipeline(preprocess, ingest, read)
                rss_after = _rss_bytes()
                state = state_holder['state']
                pair = {'snapshot': state, 'queries': query, 'time_unit': episode.events.time_unit}
                expected = [{'history_id': query.history_ids[0], 'query_ids': query.query_ids[0].tolist()}]
                serialization_start = time.perf_counter()
                frame = encode_request(statics[name], [pair], expected, policy['worker_limits'])
                serialization_seconds = time.perf_counter() - serialization_start
                cold_seconds = _cold_start_seconds()
                worker_start = time.perf_counter()
                journal_path = out / 'worker-attempts' / f'{block}-{qcount}-{name}-{time.time_ns()}.json'
                worker_result = isolated_read_batch(statics[name], [pair],
                    {'limits': policy['worker_limits'], 'timeout_seconds': policy['timeout_seconds'],
                     'journal_path': str(journal_path), 'sample_rss': True})
                worker_seconds = time.perf_counter() - worker_start
                worker_journal = json.loads(journal_path.read_bytes())
                rss = worker_journal.get('rss_sampling', {})
                if not torch.equal(torch.isfinite(worker_result[0].prediction),
                                   torch.isfinite(state_holder['result'].prediction)):
                    raise ValueError('timing worker prediction support changed')
                if block >= 0:
                    records.append({'block': block, 'query_count': qcount, 'method': name,
                                    'paired_order': order, **intervals,
                                    'single_event_encode_seconds': single_event_seconds,
                                    'single_event_setup_seconds': single_event_setup_seconds,
                                    'ingest_mode': 'stream', 'ingest_chunk_size': 128,
                                    'cold_worker_startup_seconds': cold_seconds,
                                    'serialization_seconds': serialization_seconds,
                                    'worker_roundtrip_seconds': worker_seconds,
                                    'ipc_residual_seconds': max(0., worker_seconds - cold_seconds -
                                                                serialization_seconds - intervals['read_output_seconds']),
                                    'state_bytes': state_holder['max_state_bytes'],
                                    'static_bytes': model.parameter_nbytes(), 'serialized_bytes': len(frame),
                                    'parent_lifetime_peak_before_bytes': rss_before,
                                    'parent_lifetime_peak_after_bytes': rss_after,
                                    'parent_lifetime_peak_increment_bytes': max(0, rss_after - rss_before),
                                    'parent_lifetime_peak_at_handshake_bytes': rss.get('parent_lifetime_peak_bytes'),
                                    'child_lifetime_peak_at_handshake_bytes': rss.get('child_lifetime_peak_bytes'),
                                    'sum_lifetime_peaks_at_handshake_bytes': rss.get('sum_lifetime_peaks_bytes'),
                                    'parent_handshake_lifetime_peak_increment_bytes': rss.get('parent_lifetime_peak_increment_bytes'),
                                    'rss_sampling_method': rss.get('sampling_method'),
                                    'rss_kind': rss.get('rss_kind'),
                                    'inference_workspace_bytes': None,
                                    'workspace_status': 'not_identified_by_rss_or_logical_state'})
            _admit(started, allocation, directory=out)
    summaries = {}
    for name in ordered_names:
        summaries[name] = {}
        for qcount in policy['query_counts']:
            selected = [record for record in records if record['method'] == name and record['query_count'] == qcount]
            summaries[name][str(qcount)] = {metric: _quantiles([row[metric] for row in selected])
                for metric in ('preprocessing_seconds', 'ingest_seconds', 'read_output_seconds', 'complete_seconds',
                               'cold_worker_startup_seconds', 'serialization_seconds', 'worker_roundtrip_seconds',
                               'ipc_residual_seconds')}
            if qcount == 1:
                summaries[name][str(qcount)]['single_event_encode_seconds'] = _quantiles(
                    [row['single_event_encode_seconds'] for row in selected])
    baseline = policy['baseline_method']
    break_even = {name: break_even_queries(
        max(0., summaries[name]['1']['ingest_seconds']['p50'] - summaries[baseline]['1']['ingest_seconds']['p50']),
        summaries[baseline]['1']['read_output_seconds']['p50'],
        summaries[name]['1']['read_output_seconds']['p50'],
        accuracy_satisfied=policy['accuracy_satisfied'][name]) for name in ordered_names if name != baseline}
    output = {'schema_version': 1, 'policy': policy, 'allocation': allocation,
              'e1_source_sha256': source_sha256(), 'e3_source_sha256': e3_source_sha256(),
              'records': records, 'summaries': summaries, 'break_even_queries': break_even,
              'rss_scope': 'conservative sum of parent/child lifetime peaks at live ACK handshake; not simultaneous physical RSS; workspace unknown',
              'admission': _admit(started, allocation, directory=out)}
    _atomic_json(out / 'timing.json', output)
    _admit(started, allocation, directory=out)
    return output
