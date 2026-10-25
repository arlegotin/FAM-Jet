#!/usr/bin/env python3
"""Bounded, public-only 16 x 2048 guard-cadence qualification.

This command evaluates archived development histories; it never opens a
protected grant, factory, row or score. Root runs it only after source review.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import signal
import sys
import time
import traceback


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
DEFAULT_PUBLIC_ROOT = ROOT / 'artifacts/e2e-core-run-04'
REGIMES = ('piecewise_stationary', 'trend_reset', 'periodic_impulses', 'irregular_revisions')
METHODS = ('jet', 'bank', 'exact', 'recent', 'latest_lru', 'reservoir', 'buckets', 'laguerre')
PROJECTION_FIELDS = ('history_id', 'query_id', 'method', 'task', 'regime', 'event_count',
                     'target', 'prediction', 'raw_prediction', 'factual_supported',
                     'numeric_supported', 'prediction_valid', 'eligible', 'accepted',
                     'abstained', 'failure', 'fallback', 'fallback_reasons', 'quarantined',
                     'quarantine_trigger', 'nonfinite', 'infinite_loss', 'loss_status',
                     'loss', 'normalized_error', 'native_mae', 'native_mse',
                     'native_mae_infinite', 'native_mse_infinite',
                     'constant_absolute_error', 'score_scope', 'target_semantics',
                     'time_unit', 'support_calibration_status')


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _write(path, body):
    from famjet.provenance import canonical_json
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as stream:
        stream.write(canonical_json(body))
        stream.flush()
        os.fsync(stream.fileno())


def select_history_ids(entries):
    present = {entry['history_id'] for entry in entries}
    ids = [f'development_fit-2048-{regime}-{index:03d}'
           for index in range(4) for regime in REGIMES]
    if len(present) != len(entries) or not set(ids) <= present:
        raise ValueError('public 2048-history cache coverage missing/duplicate')
    return ids


def _project(row):
    if type(row) is not dict or not set(PROJECTION_FIELDS) <= set(row):
        raise ValueError('scientific row projection incomplete')
    return {key: row[key] for key in PROJECTION_FIELDS}


def compare_scientific_rows(expected, observed, history_ids, method):
    """Compare exact numerical rows while omitting policy/path/cost commitments."""
    ids = set(history_ids)
    def indexed(rows):
        selected = {}
        for row in rows:
            if row.get('history_id') not in ids:
                continue
            if row.get('method') != method:
                raise ValueError('scientific method coverage mismatch')
            key = (row['history_id'], row['query_id'])
            if key in selected:
                raise ValueError('duplicate scientific row coverage')
            selected[key] = _project(row)
        return selected
    left, right = indexed(expected), indexed(observed)
    keys = {(history_id, query_id) for history_id in history_ids for query_id in range(8)}
    if set(left) != keys or set(right) != keys:
        raise ValueError('scientific row coverage incomplete')
    for key in sorted(keys):
        if left[key] != right[key]:
            raise ValueError(f'scientific row mismatch: {method} {key}')
    return {'method': method, 'row_count': len(keys), 'history_count': len(ids),
            'projection_sha256': _projection_sha(right)}


def _projection_sha(rows):
    from famjet.provenance import canonical_hash
    if type(rows) is dict:
        rows = [rows[key] for key in sorted(rows)]
    return canonical_hash(rows)


def _rebase_ref(ref, old_public_root):
    source = Path(ref['path'])
    canonical = Path('artifacts/e2e-core-run-04')
    try:
        relative = source.relative_to(canonical)
    except ValueError:
        raise ValueError('reference outside old public run') from None
    path = old_public_root / relative
    if not path.resolve(strict=True).is_relative_to(old_public_root.resolve(strict=True)):
        raise ValueError('unsafe old public reference')
    return {**ref, 'path': str(path)}


def _old_public_sources(old_public_root):
    from famjet_poc.cache import load_episode_cache
    from famjet_poc.execution_policy import BASELINE_PATH, BASELINE_SHA256
    from famjet_poc.study import load_score_rows
    if _sha(BASELINE_PATH) != BASELINE_SHA256:
        raise ValueError('public model baseline changed')
    baseline = json.loads(BASELINE_PATH.read_bytes())
    study_root = old_public_root / 'development_k16/study'
    journal_path = study_root / 'development.json'
    journal = json.loads(journal_path.read_bytes())
    if journal.get('status') != 'complete' or set(journal.get('selected', {})) != {'jet', 'bank'}:
        raise ValueError('old public development journal incomplete')
    cache = load_episode_cache(study_root / 'development-cache', journal['development_cache_sha256'])
    ids = select_history_ids(cache.entries)
    row_refs = {}
    for family in ('jet', 'bank'):
        chosen = journal['selected'][family]
        role = baseline['roles']['k16_' + family]
        if chosen['fit_ref'] != role['source_model_ref']:
            raise ValueError('old public selected reference changed')
        entry, = [item for item in journal['candidate_ledger']
                  if item['config_hash'] == chosen['config_hash']]
        if entry['status'] != 'qualified' or entry['fit_ref'] != chosen['fit_ref']:
            raise ValueError('old public selected row ledger changed')
        row_refs[family] = entry['rows_ref']
    for method in METHODS[2:]:
        if journal['controls'][method]['status'] != 'measured':
            raise ValueError('old public control incomplete')
        row_refs[method] = journal['controls'][method]['rows_ref']
    rows = {method: load_score_rows(_rebase_ref(ref, old_public_root))
            for method, ref in row_refs.items()}
    return baseline, journal, cache, ids, row_refs, rows, {'path': str(journal_path),
           'sha256': _sha(journal_path)}


def run(out, old_public_root):
    work_started = time.monotonic()
    import torch
    from famjet_poc.cache import episode_factory
    from famjet_poc.comparators import build_controls, validate_coordinate_audits
    from famjet_poc.contracts import ShapeSpec
    from famjet_poc.models import load_model
    from famjet_poc.resources import LiveStageGuard
    from famjet_poc.study import evaluate_panel, freeze_score_policy, load_score_rows
    from famjet_poc.transfer import evaluate_equivalent_control
    from famjet_poc.execution_policy import BASELINE_SHA256
    from famjet.provenance import canonical_hash

    out = Path(out)
    old_public_root = Path(old_public_root)
    out.mkdir(parents=True, exist_ok=False)
    torch.set_num_threads(1)
    baseline, journal, cache, ids, old_refs, old_rows, journal_ref = _old_public_sources(old_public_root)
    selected = {family: load_model(ROOT / baseline['roles']['k16_' + family]['archived_model_ref']['path'],
                                   baseline['roles']['k16_' + family]['archived_model_ref']['sha256'])
                for family in ('jet', 'bank')}
    controls = build_controls(ShapeSpec(16, 8), 9345, selected['jet'].target_statistics,
                              2026102401906)
    worker_limits = json.loads((ROOT / 'docs/research/e2e-study-config.json').read_bytes())['worker_limits']
    if worker_limits != {'max_frame_bytes': 33554432,
                         'max_array_bytes': 16777216, 'max_histories': 64}:
        raise ValueError('public CPU64 worker limits changed')
    methods = {**selected, **{name: item['method'] for name, item in controls.items()},
               'laguerre': selected['jet']}
    remaining_work = 180 - (time.monotonic() - work_started)
    if remaining_work <= 0:
        raise RuntimeError('public qualification work ceiling exhausted before evaluation')
    allocation = {'schema_version': 1, 'phase': 'development',
                  'manifest_sha256': journal['manifest_sha256'],
                  'allocation_id': 'e2e-public-guard-cadence-v2',
                  'max_wall_seconds': remaining_work, 'max_disk_bytes': 128 * 2**20,
                  'max_rss_bytes': 1610612736}
    guard = LiveStageGuard(out, allocation, out / 'live-guard.json', sample_interval=.1)
    results = {}
    with guard:
        def factory():
            for episode in episode_factory(cache, ids)():
                guard.check()
                yield episode
        policy = freeze_score_policy(factory(), manifest_hash=journal['manifest_sha256'])
        for method in METHODS:
            guard.check()
            directory = out / method
            statistics = (selected[method].target_statistics if method in ('jet', 'bank')
                          else selected['jet'].target_statistics)
            if method == 'laguerre':
                evaluated = evaluate_equivalent_control(methods[method], factory,
                            policy, statistics, directory, allocation,
                            worker_limits)
            else:
                evaluated = evaluate_panel(methods[method], factory, policy, statistics,
                            method, directory, allocation,
                            worker_limits)
            current_rows = load_score_rows(evaluated['rows_ref'])
            matched = compare_scientific_rows(old_rows[method], current_rows, ids, method)
            if method == 'laguerre':
                validate_coordinate_audits(evaluated['costs'], current_rows,
                                           expected_model=selected['jet'])
                matched['coordinate_diagnostic_summary'] = evaluated['costs']['coordinate_diagnostic_summary']
            matched['rows_ref'] = evaluated['rows_ref']
            matched['old_public_rows_ref'] = old_refs[method]
            matched['evaluation_seconds'] = evaluated['costs']['evaluation_seconds']
            matched['maximum_state_bytes'] = evaluated['costs']['maximum_state_bytes']
            results[method] = matched
            guard.check()
    guard_receipt = json.loads((out / 'live-guard.json').read_bytes())
    body = {'schema_version': 1, 'kind': 'famjet_public_guard_cadence_qualification',
            'status': 'matched', 'boundary': 'public_development_only_no_protected_access',
            'history_ids': ids, 'history_count': 16, 'event_count_per_history': 2048,
            'methods': results, 'baseline_sha256': BASELINE_SHA256,
            'old_public_journal_ref': journal_ref,
            'old_public_cache_manifest_sha256': cache.manifest_sha256,
            'old_public_cache_entries': [entry for entry in cache.entries
                                         if entry['history_id'] in set(ids)],
            'old_public_policy_ref': journal['policy_ref'],
            'old_public_row_refs_sha256': canonical_hash(old_refs),
            'e3_source_sha256': cache.e3_sha256,
            'study_config_sha256': _sha(ROOT / 'docs/research/e2e-study-config.json'),
            'source_sha256': _sha(__file__),
            'guard_ref': guard.receipt_ref,
            'guard_cadence': {key: guard_receipt[key] for key in
                              ('reuse_count', 'forced_count', 'background_count',
                               'maximum_sample_age_seconds', 'observer_seconds',
                               'sample_count', 'status')},
            'peak_sampled_tree_rss_bytes': max(sample.get('tree_rss_bytes', 0)
                                               for sample in guard_receipt['samples']),
            'elapsed_seconds': time.monotonic() - work_started,
            'failing_inputs': []}
    _write(out / 'qualification.json', body)
    return body


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', required=True, type=Path)
    parser.add_argument('--old-public-root', type=Path, default=DEFAULT_PUBLIC_ROOT)
    args = parser.parse_args(argv)
    for name in ('OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'OPENBLAS_NUM_THREADS'):
        os.environ[name] = '1'
    def timeout(_signum, _frame):
        raise TimeoutError('public qualification 200-second total shutdown deadline exceeded')
    signal.signal(signal.SIGALRM, timeout)
    signal.setitimer(signal.ITIMER_REAL, 200)
    new_output = not args.out.exists()
    try:
        run(args.out, args.old_public_root)
    except BaseException as exc:
        if new_output and args.out.is_dir():
            try:
                _write(args.out / 'failure.json', {'schema_version': 1,
                       'kind': 'famjet_public_guard_cadence_failure',
                       'status': 'failed', 'boundary': 'public_development_only',
                       'failing_inputs': {'out': str(args.out),
                                          'old_public_root': str(args.old_public_root)},
                       'error': f'{type(exc).__name__}: {exc}',
                       'traceback': traceback.format_exc()})
            except OSError:
                pass
        raise
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)


if __name__ == '__main__':
    main()
