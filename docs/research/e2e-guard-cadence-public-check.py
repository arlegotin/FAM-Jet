#!/usr/bin/env python3
"""Bounded, public-only 16 x 2048 guard-cadence qualification.

This command evaluates archived development histories; it never opens a
protected grant, factory, row or score. Root runs it only after source review.
"""
import argparse
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import sys
import time
import traceback


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
DEFAULT_PUBLIC_ROOT = ROOT / 'artifacts/e2e-core-run-04'
REGIMES = ('piecewise_stationary', 'trend_reset', 'periodic_impulses', 'irregular_revisions')
METHODS = ('jet', 'bank', 'exact', 'recent', 'latest_lru', 'reservoir', 'buckets', 'laguerre')
PUBLIC_JOURNAL_SHA256 = 'ef5f2c6e4d32934df3ff22397906cd9dd1664dd4b3c54e216b2fc26471a05309'
PUBLIC_CACHE_SHA256 = '90673f30d722c262c18363fd3482b3b35f40d17c78659e66992b1a92483b7ec1'
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


def _project(row, method):
    if type(row) is not dict or not set(PROJECTION_FIELDS) <= set(row):
        raise ValueError('scientific row projection incomplete')
    return {key: method if key == 'method' else row[key] for key in PROJECTION_FIELDS}


def compare_scientific_rows(expected, observed, history_ids, method, *, source_method=None):
    """Compare exact numerical rows while omitting policy/path/cost commitments."""
    if (type(history_ids) not in (list, tuple) or not history_ids or
            any(type(history_id) is not str or not history_id for history_id in history_ids) or
            len(set(history_ids)) != len(history_ids)):
        raise ValueError('declared scientific history inventory malformed')
    ids = set(history_ids)
    def indexed(rows, stored_method, *, archived_subset):
        selected = {}
        for row in rows:
            if row.get('history_id') not in ids:
                if archived_subset:
                    continue
                raise ValueError('observed scientific row coverage exceeds declared histories')
            if row.get('method') != stored_method:
                raise ValueError('scientific method coverage mismatch')
            key = (row['history_id'], row['query_id'])
            if key in selected:
                raise ValueError('duplicate scientific row coverage')
            selected[key] = _project(row, method)
        return selected
    left = indexed(expected, source_method or method, archived_subset=True)
    right = indexed(observed, method, archived_subset=False)
    keys = {(history_id, query_id) for history_id in history_ids for query_id in range(8)}
    if set(left) != keys or set(right) != keys:
        raise ValueError('scientific row coverage incomplete')
    for key in sorted(keys):
        if left[key] != right[key]:
            raise ValueError(f'scientific row mismatch: {method} {key}')
    return {'method': method, 'row_count': len(keys), 'history_count': len(ids),
            'projection_sha256': _projection_sha(right)}


def _projection_sha(rows):
    from famjet.provenance import canonical_hash, canonical_json
    from famjet_poc.pipeline import _run_output_bytes
    if type(rows) is dict:
        rows = [rows[key] for key in sorted(rows)]
    return canonical_hash(rows)


def _public_file(old_public_root, relative, *, kind):
    root = Path(old_public_root).absolute()
    relative = Path(relative)
    parts = relative.parts
    if (relative.is_absolute() or len(parts) < 3 or '..' in parts or
            '..' in Path(old_public_root).parts or
            parts[:2] != ('development_k16', 'study')):
        raise ValueError('file outside exact public development subtree')
    allowed = {
        'journal': parts == ('development_k16', 'study', 'development.json'),
        'cache_manifest': parts == ('development_k16', 'study', 'development-cache',
                                    'cache-manifest.json'),
        'row': len(parts) == 4 and parts[2] == 'rows' and parts[3].endswith('.json'),
        'episode': len(parts) == 4 and parts[2] == 'development-cache' and
                   re.fullmatch(r'episode-[0-9]{6}\.json', parts[3]) is not None,
    }
    if not allowed.get(kind, False):
        raise ValueError('file outside committed public file class')
    if any(path.is_symlink() for path in (root, *root.parents)):
        raise ValueError('symlink in public development root')
    path = root
    for part in parts:
        path = path / part
        if path.is_symlink():
            raise ValueError('symlink in public development path')
    if (not path.is_file() or
            not path.resolve(strict=True).is_relative_to(
                (root / 'development_k16/study').resolve(strict=True))):
        raise ValueError('public development file missing or escaped')
    return path


def _rebase_ref(ref, old_public_root):
    source = Path(ref['path'])
    canonical = Path('artifacts/e2e-core-run-04')
    try:
        relative = source.relative_to(canonical)
    except ValueError:
        raise ValueError('reference outside old public run') from None
    path = _public_file(old_public_root, relative, kind='row')
    return {**ref, 'path': str(path)}


def _repository_public_file(relative):
    relative = Path(relative)
    fixed = {Path('docs/research/e2e-evaluation-v2-selection-baseline.json'),
             Path('docs/research/e2e-study-config.json')}
    archive = Path('docs/research/e2e-evaluation-v2-public-model-baseline')
    if (relative.is_absolute() or '..' in relative.parts or
            relative not in fixed and not (
                len(relative.parts) == len(archive.parts) + 2 and
                relative.parts[:len(archive.parts)] == archive.parts and
                relative.suffix in {'.json', '.npz'})):
        raise ValueError('file outside committed public repository allowlist')
    path = ROOT
    for part in relative.parts:
        path = path / part
        if path.is_symlink():
            raise ValueError('symlink in committed public repository file')
    if not path.is_file() or not path.resolve(strict=True).is_relative_to(ROOT.resolve(strict=True)):
        raise ValueError('committed public repository file missing or escaped')
    return path


def _old_public_sources(old_public_root):
    from famjet_poc.cache import load_episode_cache
    from famjet_poc.execution_policy import BASELINE_SHA256
    from famjet_poc.study import load_score_rows
    baseline_path = _repository_public_file(
        'docs/research/e2e-evaluation-v2-selection-baseline.json')
    baseline_raw = baseline_path.read_bytes()
    if hashlib.sha256(baseline_raw).hexdigest() != BASELINE_SHA256:
        raise ValueError('public model baseline changed')
    baseline = json.loads(baseline_raw)
    journal_path = _public_file(old_public_root, 'development_k16/study/development.json',
                                kind='journal')
    journal_raw = journal_path.read_bytes()
    if hashlib.sha256(journal_raw).hexdigest() != PUBLIC_JOURNAL_SHA256:
        raise ValueError('committed public development journal changed')
    journal = json.loads(journal_raw)
    if journal.get('status') != 'complete' or set(journal.get('selected', {})) != {'jet', 'bank'}:
        raise ValueError('old public development journal incomplete')
    cache_manifest = _public_file(old_public_root,
        'development_k16/study/development-cache/cache-manifest.json', kind='cache_manifest')
    if journal['development_cache_sha256'] != PUBLIC_CACHE_SHA256:
        raise ValueError('committed public development cache changed')
    cache = load_episode_cache(cache_manifest.parent, PUBLIC_CACHE_SHA256)
    ids = select_history_ids(cache.entries)
    for entry in cache.entries:
        if entry['history_id'] in ids:
            _public_file(old_public_root,
                Path('development_k16/study/development-cache') / entry['file'], kind='episode')
    row_refs = {}
    for family in ('jet', 'bank'):
        chosen = journal['selected'][family]
        role = baseline['roles']['k16_' + family]
        if (chosen['fit_ref'] != role['source_model_ref'] or
                chosen['reader'] != role['reader']):
            raise ValueError('old public selected reference changed')
        entry, = [item for item in journal['candidate_ledger']
                  if item['config_hash'] == chosen['config_hash']]
        if (entry['status'] != 'qualified' or entry['fit_ref'] != chosen['fit_ref'] or
                entry['family'] != family):
            raise ValueError('old public selected row ledger changed')
        row_refs[family] = entry['rows_ref']
    for method in METHODS[2:]:
        if journal['controls'][method]['status'] != 'measured':
            raise ValueError('old public control incomplete')
        row_refs[method] = journal['controls'][method]['rows_ref']
    rows = {method: load_score_rows(_rebase_ref(ref, old_public_root))
            for method, ref in row_refs.items()}
    return baseline, journal, cache, ids, row_refs, rows, {'path': str(journal_path),
           'sha256': PUBLIC_JOURNAL_SHA256}


def _archived_model_file(ref, family):
    relative = Path(ref['path'])
    prefix = Path('docs/research/e2e-evaluation-v2-public-model-baseline') / ('k16_' + family)
    if (relative.is_absolute() or '..' in relative.parts or
            relative.parent != prefix or relative.suffix != '.json'):
        raise ValueError('model outside committed public archive')
    for candidate in (relative, relative.with_suffix('.npz')):
        _repository_public_file(candidate)
    return ROOT / relative


@contextmanager
def public_guard_pair(out, allocation, *, observer=None, sample_interval=.1):
    """Match the stage-root and nested run-root guard topology of protected cells."""
    from famjet_poc.resources import LiveStageGuard
    out = Path(out)
    outer = LiveStageGuard(out, allocation, out / 'outer-live-guard.json',
                           observer=observer, sample_interval=sample_interval)
    with outer:
        inner_root = out / 'runs'
        inner_root.mkdir(exist_ok=False)
        inner = LiveStageGuard(inner_root, allocation, inner_root / 'live-guard.json',
                               observer=observer, sample_interval=sample_interval)
        with inner:
            yield outer, inner


def build_public_controls(selected_jet, expected_manifest_sha256):
    """Use the exact K16 development builder and training seed, not timing seed."""
    from famjet_poc.comparators import build_controls
    from famjet_poc.contracts import ShapeSpec
    from famjet_poc.study import study_manifest
    config = json.loads(_repository_public_file(
        'docs/research/e2e-study-config.json').read_bytes())
    if (study_manifest(config)['manifest_sha256'] != expected_manifest_sha256 or
            config['shape'] != ShapeSpec(16, 8).to_json() or
            config['training_seed'] != 2026102401801):
        raise ValueError('committed K16 public development config/seed changed')
    worker_limits = config['worker_limits']
    if worker_limits != {'max_frame_bytes': 33554432,
                         'max_array_bytes': 16777216, 'max_histories': 64}:
        raise ValueError('public CPU64 worker limits changed')
    return (build_controls(ShapeSpec(16, 8), 9345, selected_jet.target_statistics,
                           config['training_seed']), worker_limits)


def write_qualification_receipt(out, body, max_disk_bytes):
    from famjet.provenance import canonical_json
    from famjet_poc.pipeline import _run_output_bytes
    if _run_output_bytes(out) + len(canonical_json(body)) > max_disk_bytes:
        raise RuntimeError('public qualification output including final receipt exceeded')
    _write(Path(out) / 'qualification.json', body)


def run(out, old_public_root):
    work_started = time.monotonic()
    import torch
    from famjet_poc.cache import episode_factory
    from famjet_poc.comparators import validate_coordinate_audits
    from famjet_poc.models import load_model
    from famjet_poc.study import evaluate_panel, freeze_score_policy, load_score_rows
    from famjet_poc.transfer import evaluate_equivalent_control
    from famjet_poc.execution_policy import BASELINE_SHA256
    from famjet.provenance import canonical_hash

    out = Path(out)
    old_public_root = Path(old_public_root)
    out.mkdir(parents=True, exist_ok=False)
    torch.set_num_threads(1)
    baseline, journal, cache, ids, old_refs, old_rows, journal_ref = _old_public_sources(old_public_root)
    selected = {family: load_model(_archived_model_file(
                                   baseline['roles']['k16_' + family]['archived_model_ref'], family),
                                   baseline['roles']['k16_' + family]['archived_model_ref']['sha256'])
                for family in ('jet', 'bank')}
    controls, worker_limits = build_public_controls(selected['jet'],
                                                   journal['manifest_sha256'])
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
    results = {}
    with public_guard_pair(out, allocation) as (outer_guard, inner_guard):
        def factory():
            for episode in episode_factory(cache, ids)():
                inner_guard.check()
                yield episode
        policy = freeze_score_policy(factory(), manifest_hash=journal['manifest_sha256'])
        for method in METHODS:
            inner_guard.check()
            directory = out / 'runs' / method
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
            source_method = (journal['selected'][method]['config_hash']
                             if method in ('jet', 'bank') else method)
            matched = compare_scientific_rows(old_rows[method], current_rows, ids,
                                              method, source_method=source_method)
            if method == 'laguerre':
                validate_coordinate_audits(evaluated['costs'], current_rows,
                                           expected_model=selected['jet'])
                matched['coordinate_diagnostic_summary'] = evaluated['costs']['coordinate_diagnostic_summary']
            matched['rows_ref'] = evaluated['rows_ref']
            matched['old_public_rows_ref'] = old_refs[method]
            matched['evaluation_seconds'] = evaluated['costs']['evaluation_seconds']
            matched['maximum_state_bytes'] = evaluated['costs']['maximum_state_bytes']
            results[method] = matched
            inner_guard.check()
    guard_receipts = {name: json.loads(path.read_bytes()) for name, path in (
        ('outer', out / 'outer-live-guard.json'),
        ('inner', out / 'runs/live-guard.json'))}
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
            'outer_guard_ref': outer_guard.receipt_ref,
            'inner_guard_ref': inner_guard.receipt_ref,
            'guard_cadence': {name: {key: receipt[key] for key in
                              ('reuse_count', 'forced_count', 'background_count',
                               'maximum_sample_age_seconds', 'observer_seconds',
                               'sample_count', 'status')}
                              for name, receipt in guard_receipts.items()},
            'peak_sampled_tree_rss_bytes': max(sample.get('tree_rss_bytes', 0)
                for receipt in guard_receipts.values() for sample in receipt['samples']),
            'elapsed_seconds': time.monotonic() - work_started,
            'failing_inputs': []}
    write_qualification_receipt(out, body, allocation['max_disk_bytes'])
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
