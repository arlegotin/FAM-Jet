"""HOLD: external public-only qualification, run only after root accepts source.

Reads old public JSON as hash-committed diagnostic inputs. This is not cache
adoption: no E3 cache loader, migration, fitting, scoring, or protected data access.
An independent parent witness must enforce the 300 s / 1.5 GiB / 32 MiB limits.
"""
import time
START_MONOTONIC = time.monotonic()
START_EPOCH = time.time()
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import resource
import signal
import subprocess
import sys
import traceback

ROOT = Path(__file__).resolve().parents[3]
E1 = 'f78761891876540011e577293e31a89c7661ef66adbb522d2cbcd36c331d8475'
OLD_E3 = 'bbd4772c341de2b1b25d63dae195b3a2a3f2456dbe3f79af76ed31726dada39e'
SELECTED = '78d5f023a56f7eb040976507012ae80a9edbed16bfeeb8da26a43a6321c467f0'
BASE = ROOT/'artifacts/e2e-core-run-01/development_k16'
PINS = {
    'manifest.json': (274991, '979c622e64405d781983120f90d36821c15f2070448a2709d556317cc502a030'),
    'study/development.json': (4916199, '3d0cb35773bfd779877fb510f0c045c7eca0ec5da60521501f7fb7d1253b6652'),
    'study/development-cache/cache-manifest.json': (102901, '43f504530406d86ffcaae953823a6ab175e1e2281d09ef0c6fe26febf544ae7f'),
    f'study/models/{SELECTED}.json': (157750, '8d65aa42d217e957950eae2becfa5e326d88f9e692815f3fff37337ad8ba1d2b'),
    f'study/models/{SELECTED}.npz': (6548, '5b97fb880daffaece3136b25e4665e3498fabd07f77eb4b553ccc8f4794adb63'),
}
THREAD_ENV = {name: '1' for name in ('OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'VECLIB_MAXIMUM_THREADS')}
os.environ.update(THREAD_ENV)
sys.path.insert(0, str(ROOT))
MAX_OUTPUT = 32*1024**2
MAX_RSS = 1536*1024**2
OUT = None
INPUTS = {}
RECORD = {'schema_version': 1, 'scope': 'external_old_public_JSON_coordinate_diagnostic_only',
          'status': 'INCOMPLETE', 'strict_prediction_status': 'NOT_EVALUATED',
          'start_epoch_seconds': START_EPOCH, 'start_monotonic_seconds': START_MONOTONIC,
          'argv': [sys.executable, *sys.argv], 'environment_overrides': THREAD_ENV,
          'budget': {'inner_wall_seconds': 270, 'external_wall_seconds': 300,
                     'max_rss_bytes': MAX_RSS, 'max_output_bytes': MAX_OUTPUT},
          'history_count_completed': 0, 'strict_prediction_failed_histories': 0,
          'strict_prediction_failed_queries': 0, 'strict_prediction_failed_scalars': 0,
          'query_count': 0, 'total_scalar_count': 0, 'evaluated_scalar_count': 0,
          'max_state_absolute_error': 0., 'max_state_scaled_error': 0.,
          'max_prediction_absolute_error': 0., 'max_prediction_scaled_error': 0.}


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT, text=True).strip()


def peak_rss():
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return int(peak if sys.platform == 'darwin' else peak*1024)


def admit():
    if time.monotonic()-START_MONOTONIC >= 270:
        raise TimeoutError('Original 270-second preflight deadline exhausted')
    if peak_rss() > MAX_RSS:
        raise MemoryError('Observed process peak RSS exceeded 1.5 GiB')
    if OUT and sum(p.stat().st_size for p in OUT.iterdir() if p.is_file()) >= MAX_OUTPUT-1024**2:
        raise MemoryError('Output ceiling reserve exhausted')


def write_json(name, value):
    with (OUT/name).open('x') as stream:
        json.dump(value, stream, sort_keys=True, indent=2, allow_nan=False)
        stream.write('\n')


def read_committed(path, expected_bytes, expected_sha):
    raw = path.read_bytes()
    if len(raw) != expected_bytes or sha(raw) != expected_sha:
        raise ValueError(f'Immutable public input bytes changed: {path}')
    INPUTS[str(path.relative_to(ROOT))] = {'bytes': len(raw), 'sha256': sha(raw)}
    return raw


def decode_public_json(raw):
    # Standalone record decoding, deliberately NOT a changed-E3 cache-loader bypass.
    from famjet.eval.state_io import tensor_from_record
    from famjet.types import Episode, EventBatch, QueryBatch
    record = json.loads(raw)
    if set(record) != {'schema_version', 'events', 'queries', 'labels', 'supported', 'metadata'} or record['schema_version'] != 1:
        raise ValueError('Old public diagnostic JSON schema changed')
    e, q = record['events'], record['queries']
    enames = ('event_ids', 'timestamps', 'key_ids', 'key_features', 'values', 'lengths', 'present', 'observed')
    qnames = ('query_ids', 'T', 'key_ids', 'key_features', 'age_start', 'age_end', 'present', 'lengths')
    if set(e) != {*enames, 'history_ids', 'time_unit', 'normalization', 'auxiliary'} or set(q) != {*qnames, 'history_ids', 'tasks'}:
        raise ValueError('Old public tensor schema changed')
    events = EventBatch(tuple(e['history_ids']), **{k: tensor_from_record(e[k]) for k in enames},
                        time_unit=e['time_unit'], normalization=e['normalization'],
                        auxiliary={k: tensor_from_record(v) for k, v in e['auxiliary'].items()})
    queries = QueryBatch(tuple(q['history_ids']), **{k: tensor_from_record(q[k]) for k in qnames},
                         tasks=tuple(tuple(row) for row in q['tasks']))
    return Episode(events, queries, tensor_from_record(record['labels']), tensor_from_record(record['supported']), record['metadata'])


def failure_locals(exc, comparator):
    import torch
    trace, local = exc.__traceback__, {}
    while trace:
        if trace.tb_frame.f_code is comparator.__code__:
            local = trace.tb_frame.f_locals
        trace = trace.tb_next
    summary = {'local_names': sorted(local), 'state': {}, 'masks': {}}
    for name in ('prediction_error', 'state_error', 'strict_pass', 'j', 'n'):
        value = local.get(name)
        if type(value) in (int, float, bool, str) and not (type(value) is float and not math.isfinite(value)):
            summary[name] = value
    direct, recovered = local.get('direct'), local.get('recovered')
    if direct is not None and recovered is not None:
        for key in ('z', 'h'):
            a, b = direct.payload[key], recovered.payload[key]
            finite = torch.isfinite(a) & torch.isfinite(b)
            delta = torch.abs(a[finite]-b[finite])
            ratio = delta/(1e-12+1e-12*torch.abs(b[finite]))
            summary['state'][key] = {'shape': list(a.shape), 'all_finite_direct': bool(torch.isfinite(a).all()),
                'all_finite_recovered': bool(torch.isfinite(b).all()),
                'strict_allclose': bool(torch.allclose(a, b, atol=1e-12, rtol=1e-12)),
                'finite_max_absolute': float(delta.max()) if delta.numel() else None,
                'finite_max_scaled': float(ratio.max()) if ratio.numel() else None}
    left, right = local.get('left'), local.get('right')
    if left is not None and right is not None:
        pairs = {'finite': (torch.isfinite(left.prediction), torch.isfinite(right.prediction)),
                 'support': (left.support, right.support), 'failure': (left.failure, right.failure),
                 **{k: (left.diagnostics[k], right.diagnostics[k]) for k in ('prediction_valid', 'numeric_supported')}}
        for name, (a, b) in pairs.items():
            mismatch = a != b
            summary['masks'][name] = {'equal': bool(torch.equal(a, b)), 'mismatch_count': int(mismatch.sum()),
                                      'first_16_mismatch_indices': torch.nonzero(mismatch)[:16].tolist()}
    return summary


def main(args):
    import torch
    from famjet_poc.cache import e3_source_sha256
    from famjet_poc.comparators import laguerre_control, coordinate_model_sha256, COORDINATE_POLICY
    from famjet_poc.contracts import source_sha256
    from famjet_poc.models import load_model, _episode_digest
    from famjet_poc.study import select_candidate
    torch.set_num_threads(1)
    torch.set_num_interop_threads(1)
    assert source_sha256() == E1, 'Unchanged E1 source identity required'
    RECORD.update(e1_source_sha256=source_sha256(), e3_source_sha256=e3_source_sha256(),
                  old_public_input_e3_sha256=OLD_E3, coordinate_policy=COORDINATE_POLICY,
                  python=sys.version, torch_version=torch.__version__, torch_threads=torch.get_num_threads())
    RECORD['tracked_python_sha256'] = {name: sha((ROOT/name).read_bytes()) for name in git('ls-files', '*.py').splitlines()}
    data = {name: read_committed(BASE/name, size, digest) for name, (size, digest) in PINS.items()}
    manifest = json.loads(data['manifest.json'])
    journal = json.loads(data['study/development.json'])
    cache = json.loads(data['study/development-cache/cache-manifest.json'])
    assert cache['source_sha256'] == E1 and cache['e3_sha256'] == OLD_E3
    winner = select_candidate([item for item in journal['candidate_ledger'] if item['family'] == 'jet'])
    assert winner['config_hash'] == journal['selected']['jet']['config_hash'] == journal['controls']['laguerre']['equivalent_to'] == SELECTED
    model_path = BASE/f'study/models/{SELECTED}.json'
    model = load_model(model_path, PINS[f'study/models/{SELECTED}.json'][1])
    ids = [item['history_id'] for item in manifest['development_inventory']]
    assert len(ids) == len(set(ids)) == 192
    assert all(h.startswith('development_fit-') for h in ids)
    entries = {item['history_id']: item for item in cache['entries']}
    assert set(entries) == set(ids)
    RECORD.update(expected_history_count=192, chronological_history_ids=ids,
                  chronological_ids_sha256=sha(json.dumps(ids, separators=(',', ':')).encode()),
                  selected_config_hash=SELECTED, selected_model_manifest_sha256=PINS[f'study/models/{SELECTED}.json'][1],
                  model_numeric_sha256=coordinate_model_sha256(model),
                  original_development_started_epoch_seconds=journal['allocation_started_epoch_seconds'],
                  original_allocation_clock_kind=journal['allocation_clock_kind'])
    write_json('admission.json', RECORD)
    with (OUT/'histories.jsonl').open('x') as history_log:
        for index, history in enumerate(ids):
            admit()
            RECORD['active_history'] = {'index': index, 'history_id': history}
            entry = entries[history]
            assert entry['file'].startswith('episode-') and Path(entry['file']).name == entry['file']
            path = BASE/'study/development-cache'/entry['file']
            episode = decode_public_json(read_committed(path, entry['bytes'], entry['sha256']))
            assert episode.events.history_ids == episode.queries.history_ids == (history,)
            assert _episode_digest(episode) == entry['episode_digest']
            before = time.monotonic()
            try:
                result = laguerre_control(model, episode.events, episode.queries, diagnostic_mode=True)
            except ArithmeticError as exc:
                write_json('hard-failure.json', {'history_index': index, 'history_id': history,
                    'exception': repr(exc), 'traceback': traceback.format_exc(),
                    'comparator_locals_summary': failure_locals(exc, laguerre_control)})
                RECORD['status'] = 'HARD_FAILURE'
                raise
            diagnostics = result['coordinate_diagnostics']
            assert set(diagnostics) == {history}
            d = diagnostics[history]
            assert d['model_numeric_sha256'] == RECORD['model_numeric_sha256']
            assert d['atol'] == d['rtol'] == 1e-12
            assert d['query_ids'] == episode.queries.query_ids[0][episode.queries.present[0]].tolist()
            assert d['state_checks'] == {'z': True, 'h': True}
            assert d['mask_checks'] == {k: True for k in ('finite', 'support', 'failure', 'prediction_valid', 'numeric_supported')}
            assert d['max_state_scaled_error'] <= 1
            assert (d['strict_prediction_status'] == 'FAILED') == (d['strict_prediction_failed_scalars'] > 0)
            line = {'history_index': index, 'history_id': history, 'input_sha256': entry['sha256'],
                    'elapsed_seconds': time.monotonic()-before, 'event_count': int(episode.events.lengths[0]),
                    'coordinate_diagnostic': d}
            history_log.write(json.dumps(line, sort_keys=True, allow_nan=False)+'\n')
            history_log.flush()
            RECORD['history_count_completed'] += 1
            RECORD['strict_prediction_failed_histories'] += int(d['strict_prediction_status'] == 'FAILED')
            for name in ('query_count', 'total_scalar_count', 'evaluated_scalar_count', 'strict_prediction_failed_queries', 'strict_prediction_failed_scalars'):
                RECORD[name] += d[name]
            for name in ('max_state_absolute_error', 'max_state_scaled_error', 'max_prediction_absolute_error', 'max_prediction_scaled_error'):
                RECORD[name] = max(RECORD[name], d[name])
            RECORD['strict_prediction_status'] = 'FAILED' if RECORD['strict_prediction_failed_histories'] else 'PASSED'
            print(json.dumps({'index': index, 'history': history, 'strict_prediction': d['strict_prediction_status'],
                              'state_scaled': d['max_state_scaled_error'], 'prediction_scaled': d['max_prediction_scaled_error']}), flush=True)
            del episode, result, diagnostics
    assert RECORD['history_count_completed'] == 192
    # Preserve source/input immutability across this diagnostic, without adopting old caches.
    for path, commitment in list(INPUTS.items()):
        read_committed(ROOT/path, commitment['bytes'], commitment['sha256'])
    assert git('rev-parse', 'HEAD') == args.expected_head
    assert git('status', '--porcelain', '--untracked-files=normal') == ''
    assert source_sha256() == E1 and e3_source_sha256() == RECORD['e3_source_sha256']
    assert all(sha((ROOT/name).read_bytes()) == digest for name, digest in RECORD['tracked_python_sha256'].items())
    admit()
    RECORD['status'] = 'PUBLIC_STATE_AND_MASK_QUALIFICATION_COMPLETE'
    return 0


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', required=True, type=Path)
    parser.add_argument('--expected-head', required=True)
    args = parser.parse_args()
    assert len(args.expected_head) == 40 and all(c in '0123456789abcdef' for c in args.expected_head)
    assert git('rev-parse', 'HEAD') == args.expected_head, 'Reviewed exact HEAD required'
    assert git('status', '--porcelain', '--untracked-files=normal') == '', 'Clean tree required (ignored runtime outputs allowed)'
    OUT = args.out.resolve()
    assert not OUT.is_relative_to(BASE), 'Never write into original run inputs'
    OUT.mkdir(parents=False, exist_ok=False)
    RECORD.update(expected_head=args.expected_head, cwd=str(Path.cwd()), output_directory=str(OUT),
                  script_sha256=sha(Path(__file__).read_bytes()))
    def deadline(*_):
        raise TimeoutError('270-second original wall deadline')
    signal.signal(signal.SIGALRM, deadline)
    signal.setitimer(signal.ITIMER_REAL, max(.001, 270-(time.monotonic()-START_MONOTONIC)))
    code = 1
    try:
        code = main(args)
    except BaseException as exc:
        RECORD['error'] = repr(exc)
        if RECORD['status'] != 'HARD_FAILURE':
            RECORD['status'] = 'INCOMPLETE_ERROR'
        trace = traceback.format_exc()
        (OUT/'failure.log').write_text(trace)
        print(trace, file=sys.stderr, flush=True)
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        RECORD.update(exit_code=code, end_epoch_seconds=time.time(), end_monotonic_seconds=time.monotonic(),
                      elapsed_seconds=time.monotonic()-START_MONOTONIC, observed_peak_rss_bytes=peak_rss(),
                      immutable_input_refs=INPUTS,
                      files={p.name: {'bytes': p.stat().st_size, 'sha256': sha(p.read_bytes())} for p in OUT.iterdir() if p.is_file()})
        RECORD['output_bytes_before_summary'] = sum(p.stat().st_size for p in OUT.iterdir() if p.is_file())
        write_json('result.json', RECORD)
    raise SystemExit(code)
