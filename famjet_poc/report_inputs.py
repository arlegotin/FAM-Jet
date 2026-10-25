"""Read and validate immutable E4 artifacts without opening a scientific data source.

The serialized paths remain byte-for-byte frozen. ``ArtifactPaths`` changes only
the I/O location of a reference when a complete run is copied into a clone.
"""

import hashlib
import json
import math
from pathlib import Path
import tempfile

from famjet.provenance import canonical_hash, canonical_json
from .comparators import validate_coordinate_audits, load_coordinate_model
from .contracts import ShapeSpec


_ROOT = Path(__file__).resolve().parent.parent
_MIGRATION_ID = 'run06-report-order-v1'
_MIGRATION_PATH = _ROOT / 'docs/research/e2e-run06-report-migration.json'
_INDEX_PATH = _ROOT / 'docs/research/e2e-run06-execution-record/index.json'
_INDEX_SHA256 = 'f00aac585d16237cc546259df85c69f5f65a9b6ea6d63fcc4b8b65a67f9ad43c'
_OLD_COMMIT = 'f886e3c41517fd935a642cb83233dd72faf083b0'
_OLD_EXECUTABLE = 'b994b3ef7b770fb50db7adba3a9125f75c7c5dc1a4cd3dc3d85843d3177e1260'
_ARCHIVED_IDENTITY_SHA256 = 'e08af6dfbeeb3c31909a180f8d5ca6fb44b78ae14bc2b3293b533b6dbeb70cc8'
_REPORT_LOCK_SHA256 = '132d9a7822f2a2bd502f2deabdef30e7d3190802d9f5df18f1d2d8a3af062cf1'
_RUN_PINS = {
    'freeze/study-freeze-v1.json': 'a0a1a66bc15de891b3bd365008e8ea24be74008d6fdc06bba958c619e6828845',
    'release/release.json': '8b1ed1eec3c3899a4a2d5d8efb38329dbc33545ed88b5ca76e04ddf8dcb9b635',
    'release/real/real-release.json': 'dcc7549f5e1c710e53ba322876af69c51fdb9ab3eae98190e324fdeccded2846',
    'release/inference.json': 'b6f6b0e5353353b6d7bdcebf752a4aada4e2bf7f709a0fe036ca6838e3d5ca7a',
    'run-ledger.json': '9a731a11707b4c903f4806d8ca0767362107d31626a9985212ef2872b305f330',
    'run-policy.json': '175433f8e414bca12fc4e1308e259e1d64e804aba0f65a551a2579b4a5accd24',
    'run-policy-anchor.json': '87019266034d447e6dc7b1359bcce02a3a5117894388a8e7e3a22065fc41285d',
    'report/live-guard-attempt-000.json': '5c4f1f9781fa0d273acbccb14a4b12577f49cd21761504c9da2cc2c0e5f75822',
}
_PREP_PINS = {'stderr.log': '2e7387bd39f3440c036c8fa1694d89aae15a584552f78bc865d53407711c2065',
              'exit-witness.json': '567f5759da13b8d336a2cbe3a8dc9fce90cfff82512c730c386d2130e6261f71'}


def _file_sha(path):
    digest = hashlib.sha256()
    size = 0
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
            size += len(block)
    return digest.hexdigest(), size


def _read_json(path, sha256=None, size=None):
    path = Path(path)
    digest, actual_size = _file_sha(path)
    if (sha256 is not None and digest != sha256) or (size is not None and actual_size != size):
        raise ValueError(f'artifact hash/bytes mismatch: {path.name}')
    return json.loads(path.read_bytes())


def _require_study_run_roster(expected_ids, receipts, *, cells, methods):
    """Require the exact frozen roster while retaining sealed receipt order."""
    if (type(expected_ids) is not list or type(receipts) is not list or
            type(cells) is not list or type(methods) is not list or
            any(type(value) is not str or not value for value in cells + methods) or
            len(set(cells)) != len(cells) or len(set(methods)) != len(methods) or
            expected_ids != [cell + '-' + method for cell in cells for method in methods] or
            len(expected_ids) != len(receipts) or
            any(type(value) is not str or not value for value in expected_ids) or
            len(set(expected_ids)) != len(expected_ids)):
        raise ValueError('protected run ID inventory differs from freeze')
    actual = []
    for receipt in receipts:
        if type(receipt) is not dict:
            raise ValueError('protected run ID receipt malformed')
        run_id, cell, method = (receipt.get(key) for key in ('run_id', 'cell_id', 'method'))
        if (any(type(value) is not str or not value for value in (run_id, cell, method)) or
                run_id != cell + '-' + method):
            raise ValueError('protected run ID cell/method binding differs')
        actual.append(run_id)
    if len(set(actual)) != len(actual) or set(actual) != set(expected_ids):
        raise ValueError('protected run ID inventory differs from freeze')


def _validate_report_transition(manifest, old_files, new_files, observed_pins):
    """Check the one file transition and exact historical artifact anchors."""
    if (type(manifest) is not dict or type(old_files) is not dict or type(new_files) is not dict or
            set(old_files) != set(new_files) or
            set(old_files) != set(manifest.get('old_files', {})) or
            old_files != manifest['old_files'] or new_files != manifest.get('new_files') or
            {name for name in old_files if old_files[name] != new_files[name]} !=
                {'famjet_poc/report_inputs.py'} or
            manifest.get('old_sha256') != canonical_hash(old_files) or
            manifest.get('new_sha256') != canonical_hash(new_files)):
        raise ValueError('report transition executable inventory mismatch')
    if observed_pins != manifest.get('pinned'):
        raise ValueError('report transition pinned artifact/clock mismatch')


def _inventory(root, names):
    """Hash an exact file roster without following links or accepting additions."""
    root = Path(root).resolve(strict=True)
    observed = {}
    for path in root.rglob('*'):
        if path.is_symlink():
            raise ValueError('symlink in report migration inventory')
        if path.is_file():
            name = str(path.relative_to(root))
            if name not in names:
                raise ValueError('extra file in report migration inventory')
            sha, size = _file_sha(path)
            observed[name] = {'sha256': sha, 'bytes': size}
    if observed != names:
        raise ValueError('report migration inventory differs')
    return observed


def _admit_report_migration(run, compatibility_id, archived_source):
    """Read only the one committed run06 authorization before any score access."""
    from .protected import executable_identity
    from .contracts import source_sha256
    run = Path(run).resolve(strict=True)
    if compatibility_id != _MIGRATION_ID or archived_source is None:
        raise ValueError('unregistered report compatibility ID or missing archived source')
    manifest_sha, _ = _file_sha(_MIGRATION_PATH)
    manifest = _read_json(_MIGRATION_PATH)
    index = _read_json(_INDEX_PATH, _INDEX_SHA256)
    if (manifest.get('schema_version') != 1 or manifest.get('compatibility_id') != _MIGRATION_ID or
            manifest.get('scope') != 'artifact_validation_and_reporting_only' or
            manifest.get('old_commit') != _OLD_COMMIT or
            manifest.get('old_sha256') != _OLD_EXECUTABLE or
            manifest.get('old_report_inputs_sha256') !=
                index.get('frozen_executable', {}).get('files', {}).get('famjet_poc/report_inputs.py') or
            manifest.get('new_report_inputs_sha256') !=
                manifest.get('new_files', {}).get('famjet_poc/report_inputs.py') or
            manifest.get('launcher_path') != 'scripts/report_run06_recovery.py' or
            manifest.get('original_exit_code') != 1 or
            manifest.get('original_report_status') != 'failed' or
            manifest.get('archive_index_sha256') != _INDEX_SHA256 or
            manifest.get('archived_identity_sha256') != _ARCHIVED_IDENTITY_SHA256 or
            index.get('source_revision') != _OLD_COMMIT or
            index.get('frozen_executable') !=
                {'files': manifest.get('old_files'), 'sha256': _OLD_EXECUTABLE} or
            index.get('file_count') != 4813 or index.get('bytes') != 2062164087 or
            index.get('prep_bytes') != 10158074 or
            index.get('actual_returncode') != 1 or
            any(index['files'].get(name, {}).get('sha256') != sha for name, sha in _RUN_PINS.items()) or
            any(index['prep_files'].get(name, {}).get('sha256') != sha for name, sha in _PREP_PINS.items()) or
            manifest.get('pinned') != _RUN_PINS or manifest.get('prep_pinned') != _PREP_PINS or
            manifest.get('report_lock_sha256') !=
                _REPORT_LOCK_SHA256 or
            _file_sha(_ROOT / 'docs/reporting-requirements.lock')[0] !=
                _REPORT_LOCK_SHA256 or
            manifest.get('launcher_sha256') !=
                _file_sha(_ROOT / 'scripts/report_run06_recovery.py')[0]):
        raise ValueError('run06 report migration authorization mismatch')
    archive = Path(archived_source).resolve(strict=True)
    if (_file_sha(archive / 'identity.json')[0] != _ARCHIVED_IDENTITY_SHA256 or
            _read_json(archive / 'identity.json') != index['frozen_executable']):
        raise ValueError('archived original execution identity mismatch')
    old_files = {name: _file_sha(archive / name)[0] for name in manifest['old_files']}
    # Include additions, omissions, and links in the archived source inventory.
    archived_inventory = {name: {'sha256': sha, 'bytes': (archive / name).stat().st_size}
                          for name, sha in manifest['old_files'].items()}
    archived_inventory['identity.json'] = {'sha256': _ARCHIVED_IDENTITY_SHA256,
                                           'bytes': (archive / 'identity.json').stat().st_size}
    _inventory(archive, archived_inventory)
    current = executable_identity()
    _validate_report_transition(manifest, old_files, current['files'], _RUN_PINS)
    if (source_sha256() != _read_json(run / 'freeze/study-freeze-v1.json',
                                     _RUN_PINS['freeze/study-freeze-v1.json'])['source_sha256'] or
            current['sha256'] != manifest['new_sha256']):
        raise ValueError('run06 report transition source mismatch')
    _inventory(run, index['files'])
    prep = run.with_name('prep' if run.name == 'run' else run.name + '-prep')
    _inventory(prep, index['prep_files'])
    return {'compatibility_id': _MIGRATION_ID,
            'manifest_sha256': manifest_sha,
            'launcher_sha256': manifest['launcher_sha256'],
            'execution_sha256': _OLD_EXECUTABLE,
            'reporter_sha256': current['sha256'],
            'archive_index_sha256': _INDEX_SHA256,
            'original_exit_code': 1,
            'original_report_status': 'failed',
            'original_report_error': 'protected run ID inventory differs from freeze'}


def _verify_historical_run_policy(paths, inputs):
    """Apply normal dated policy semantics to the pinned historical source."""
    from .execution_policy import load_execution_policy, POLICY_PATH, BASELINE_PATH
    master_path = paths.root / 'run-policy.json'
    anchor_path = paths.root / 'run-policy-anchor.json'
    master = _read_json(master_path, _RUN_PINS['run-policy.json'])
    anchor = _read_json(anchor_path, _RUN_PINS['run-policy-anchor.json'])
    policy = load_execution_policy()
    start = master.get('start_epoch_seconds')
    if type(start) not in (int, float) or not math.isfinite(start) or start <= 0:
        raise ValueError('original report run policy clock invalid')
    expected = {**policy,
                'execution_policy_sha256': _file_sha(POLICY_PATH)[0],
                'execution_source_sha256': _OLD_EXECUTABLE,
                'public_selection_baseline_sha256': _file_sha(BASELINE_PATH)[0],
                'study_manifest_sha256': inputs['resource_policy']['study_manifest_sha256'],
                'start_epoch_seconds': start,
                'global_deadline_epoch_seconds': start + policy['global_wall_seconds'],
                'work_deadline_epoch_seconds': start + policy['global_wall_seconds'] -
                                               policy['completion_reserve_seconds'],
                'profile': 'scientific_study'}
    if (set(master) != set(expected) or
            any(type(master[key]) is not type(value) or master[key] != value
                for key, value in expected.items()) or
            master != inputs['resource_policy'] or
            inputs.get('execution_policy_sha256') != master['execution_policy_sha256'] or
            _file_sha(POLICY_PATH)[0] != '05b81ec4ca8f4a02ca2f5e02a859f58c62d0fc67418b7094500e0dfd0d8db0c1' or
            _file_sha(BASELINE_PATH)[0] != 'dd49488b03f78fb7b0818ed837fd53b6272304c0f8497030b4a239c78c5abe43'):
        raise ValueError('historical run policy semantics differ')
    anchor_expected = {'schema_version': 1, 'kind': 'famjet_run_policy_anchor_v2',
                       'run_policy_sha256': _RUN_PINS['run-policy.json'],
                       'execution_source_sha256': _OLD_EXECUTABLE,
                       'original_start_epoch_seconds': start,
                       'global_deadline_epoch_seconds': expected['global_deadline_epoch_seconds'],
                       'work_deadline_epoch_seconds': expected['work_deadline_epoch_seconds']}
    ref = inputs.get('run_policy_anchor_ref')
    if (anchor != anchor_expected or type(ref) is not dict or
            ref.get('path') != str(paths.original_root / 'run-policy-anchor.json') or
            ref.get('sha256') != _RUN_PINS['run-policy-anchor.json']):
        raise ValueError('historical run policy clock anchor differs')
    return master


class ArtifactPaths:
    """Resolve frozen absolute paths against one original run and repository root."""

    def __init__(self, supplied_root, recorded_freeze_path, *, recorded_project_root=None):
        self.root = Path(supplied_root).resolve(strict=True)
        original = Path(recorded_freeze_path)
        if ('..' in original.parts or
                original.parts[-2:] != ('freeze', 'study-freeze-v1.json')):
            raise ValueError('frozen original run root path malformed')
        self.original_root = original.parent.parent
        self.original_project = Path(recorded_project_root) if recorded_project_root else None

    def resolve(self, recorded):
        path = Path(recorded)
        if '..' in path.parts:
            raise ValueError('traversing frozen path rejected')
        try:
            relative = path.relative_to(self.original_root)
            base = self.root
        except ValueError:
            allowed = (Path('configs/manifests/beijing_v2_targets.json'),)
            if self.original_project is None:
                raise ValueError('artifact path outside frozen run root') from None
            try:
                relative = path.relative_to(self.original_project)
            except ValueError:
                relative = path
            if relative not in allowed:
                raise ValueError('non-whitelisted project artifact path')
            base = _ROOT
        candidate = base / relative
        if not candidate.is_file():
            raise ValueError(f'referenced artifact missing: {relative}')
        current = base
        for part in relative.parts:
            current = current / part
            if current.is_symlink():
                raise ValueError('symlink in frozen artifact path')
        if not candidate.resolve(strict=True).is_relative_to(base):
            raise ValueError('artifact path escapes resolved root')
        return candidate

    def ref(self, original):
        if type(original) is not dict or set(original) != {'path', 'sha256', 'bytes'}:
            raise ValueError('bound artifact reference schema mismatch')
        path = self.resolve(original['path'])
        if _file_sha(path) != (original['sha256'], original['bytes']):
            raise ValueError('bound artifact hash/bytes mismatch')
        return {**original, 'path': str(path)}


def _stage_records(run):
    from .pipeline import StageLedger
    path = run / 'run-ledger.json'
    if not path.is_file():
        raise ValueError('run stage ledger missing')
    generations = StageLedger(run)._read()['generations']
    latest = {}
    for record in generations:
        if record['stage'] != 'report':
            latest[record['stage']] = record
    for name, item in latest.items():
        if item['status'] != 'completed':
            raise ValueError(f'incomplete run stage: {name}')
        directory = run / name
        expected = item['output_files']
        if type(expected) is not dict:
            raise ValueError('stage file inventory missing')
        found = {}
        for path in sorted(directory.rglob('*')):
            if not path.is_file():
                continue
            if path.is_symlink():
                raise ValueError('symlink in stage artifact inventory')
            sha, size = _file_sha(path)
            found[str(path.relative_to(directory))] = {'sha256': sha, 'bytes': size}
        if found != expected:
            raise ValueError(f'stage output hash/inventory mismatch: {name}')
    return latest


def require_scientific_stages(stages, inputs):
    """Reject an opened or selectively omitted production phase."""
    core = {'preflight', 'probe_k16', 'development_k16', 'timing_k16',
            'probe_k12', 'development_k12', 'probe_beijing_fit',
            'transfer_fit', 'public_selection_gate', 'freeze', 'stress', 'release'}
    cells = {'cell-' + item['cell_id'] for item in inputs['populations']}
    real = {'beijing-' + mode + '-' + method
            for mode in ('synthetic_frozen', 'task_adapted')
            for method in inputs['expected_methods']}
    expected = core | cells | real
    if set(stages) != expected:
        raise ValueError('scientific stage inventory missing/unknown real or protected stage')
    return expected


def verify_beijing_inventory(frozen_inventory, manifest):
    """Verify the sealed array SHA inventory without reopening external arrays."""
    if set(frozen_inventory) != {'training', 'development_fit',
                                 'development_calibration', 'test'}:
        raise ValueError('Beijing four-split source inventory incomplete')
    for split, expected in frozen_inventory.items():
        observed = [{'history_id': item['history_id'], 'sha256': item['sha256']}
                    for item in manifest['splits'][split]['blocks']]
        if expected != observed:
            raise ValueError('frozen Beijing source array inventory mismatch')
    return 'verified_inventory_not_rehashed'


def require_shared_cell_counts(paths, receipts):
    """Keep one observed-label/count commitment across all methods in a cell."""
    by_cell = {}
    for receipt in receipts:
        ref = receipt.get('counts_ref')
        if ref is None:
            raise ValueError('cell observed-count sidecar missing')
        paths.ref(ref)
        by_cell.setdefault((receipt.get('phase'), receipt.get('cell_id')), set()).add(ref['sha256'])
    if any(len(hashes) != 1 for hashes in by_cell.values()):
        raise ValueError('method observed-count sidecars differ within cell')


def require_real_method_rows(method, rows):
    if any(row.get('method') != method for row in rows):
        raise ValueError('real row method differs from receipt method')


def verify_selected_reference_rebased(paths, modes):
    """Run E4's complete reference validator against I/O-resolved refs."""
    from .transfer import verify_selected_reference
    adapted = dict(modes)
    original = modes['selected_reference']
    adapted['selected_reference'] = {**original,
        'rows_ref': paths.ref(original['rows_ref'])}
    selected = modes['task_adapted']['jet']
    adapted['task_adapted'] = {**modes['task_adapted'],
        'jet': {**selected, 'path': str(paths.resolve(selected['path']))}}
    verify_selected_reference(adapted)
    return original


def verify_transfer_probe_rebased(paths, ref, manifest_sha256, worker_limits):
    """Check original bytes, then use a temporary resolved copy for E4's validator."""
    from .transfer import verify_transfer_probe
    original_ref = paths.ref(ref)
    probe = _read_json(original_ref['path'], original_ref['sha256'], original_ref['bytes'])
    adjusted = {**probe,
                'guard_ref': paths.ref(probe['guard_ref']),
                'score_rows_ref': paths.ref(probe['score_rows_ref'])}
    with tempfile.TemporaryDirectory(prefix='famjet-e5-probe-') as directory:
        path = Path(directory) / 'resolved-probe.json'
        raw = canonical_json(adjusted)
        path.write_bytes(raw)
        runtime_ref = {'path': str(path), 'sha256': hashlib.sha256(raw).hexdigest(),
                       'bytes': len(raw)}
        verify_transfer_probe(runtime_ref, manifest_sha256, worker_limits)
    return probe


def _release_rows(paths, release, freeze):
    """Validate release closure then read one method/cell at a time."""
    from .contracts import PopulationSpec
    from .protected import validate_scored_receipt
    from .study import load_score_rows
    from .contracts import AccessGrant

    methods = release.get('expected_methods')
    populations = freeze['inputs']['populations']
    if (release.get('kind') != 'famjet_e4_complete_release' or
            release.get('status') != 'complete' or type(methods) is not list or
            not methods or len(set(methods)) != len(methods)):
        raise ValueError('complete synthetic release required')
    if (freeze['inputs']['profile'] == 'study' and
            methods != freeze['inputs']['expected_methods']):
        raise ValueError('released method roster differs from frozen study')
    expected = {(item['phase'], item.get('cell_id', canonical_hash(item['spec'])), method): item
                for item in populations for method in methods}
    receipts = release.get('receipts')
    if (type(receipts) is not list or len(receipts) != len(expected) or
            release.get('expected_cells') != len(expected)):
        raise ValueError('incomplete release cell/method pair inventory')
    if freeze['inputs']['profile'] == 'study':
        _require_study_run_roster(freeze['inputs']['expected_protected_run_ids'], receipts,
                                  cells=[item['cell_id'] for item in populations], methods=methods)
        require_shared_cell_counts(paths, receipts)
    seen = set()
    grouped = {}
    aggregates = {}
    total = 0
    for receipt in receipts:
        phase, method = receipt.get('phase'), receipt.get('method')
        cell = receipt.get('cell_id')
        if cell is None:
            candidates = [key for key, item in expected.items()
                          if key[0] == phase and key[2] == method and
                          item['episode_ids'] == receipt.get('history_ids')]
            if len(candidates) != 1:
                raise ValueError('release cell inventory mismatch')
            key = candidates[0]
        else:
            key = (phase, cell, method)
        if key not in expected or key in seen or receipt.get('status') != 'completed':
            raise ValueError('duplicate/incomplete release cell or method')
        seen.add(key)
        item = expected[key]
        if (receipt.get('freeze_sha256') != release['freeze_sha256'] or
                receipt.get('history_ids') != item['episode_ids']):
            raise ValueError('release history/freeze commitment mismatch')
        if 'rows_ref' in receipt:
            resolved = paths.ref(receipt['rows_ref'])
            if receipt.get('rows_sha256') != resolved['sha256']:
                raise ValueError('receipt row hash mismatch')
            rows = load_score_rows(resolved)
        else:
            path = paths.resolve(receipt['rows_path'])
            rows = _read_json(path, receipt['rows_sha256'])
        if ({row['history_id'] for row in rows} != set(item['episode_ids']) or
                any(row['method'] != method for row in rows)):
            raise ValueError('release scored history/method inventory mismatch')
        if freeze['inputs']['profile'] == 'study':
            spec = PopulationSpec.from_json(item['spec'])
            if (receipt.get('source_sha256') != freeze['source_sha256'] or
                    receipt.get('model_sha256') != freeze['inputs']['model_pair_sha256'] or
                    receipt.get('data_sha256') != canonical_hash(spec.to_json()) or
                    receipt.get('expected_query_ids') != list(range(spec.queries_per_history)) or
                    receipt.get('score_contract', {}).get('statistics_sha256') !=
                        freeze['_expected_statistics_sha256'] or
                    receipt.get('resource_receipt_sha256') != canonical_hash(receipt.get('resource_receipt')) or
                    receipt.get('cell_admission_sha256') != canonical_hash(receipt.get('cell_admission')) or
                    type(receipt.get('costs')) is not dict or not receipt['costs']):
                raise ValueError('protected source/model/data/query/resource receipt mismatch')
            grant_path = paths.resolve(receipt['grant_path'])
            grant = AccessGrant(grant_path, receipt['grant_sha256'], phase, phase)
            grant.verify(source_sha256=freeze['source_sha256'],
                         data_sha256=canonical_hash(spec.to_json()),
                         model_sha256=freeze['inputs']['model_pair_sha256'], population=spec)
            for hid in item['episode_ids']:
                grant.verify(source_sha256=freeze['source_sha256'],
                             data_sha256=canonical_hash(spec.to_json()),
                             model_sha256=freeze['inputs']['model_pair_sha256'],
                             population=spec, episode_id=hid)
            adjusted = dict(receipt)
            adjusted['score_contract'] = {**receipt['score_contract'],
                                          'policy_ref': paths.ref(receipt['score_contract']['policy_ref'])}
            adjusted['counts_ref'] = paths.ref(receipt['counts_ref'])
            live = _read_json(paths.resolve(receipt['live_guard_ref']['path']),
                              receipt['live_guard_ref']['sha256'],
                              receipt['live_guard_ref']['bytes'])
            if (live.get('kind') != 'famjet_e4_live_stage_guard' or
                    live.get('status') != 'completed' or live.get('violation') is not None or
                    live.get('allocation', {}).get('manifest_sha256') !=
                        freeze['_freeze_sha256'] or
                    live.get('allocation', {}).get('allocation_id') != 'e4-' + key[1] or
                    any(live['allocation'].get(field) != value for field, value in
                        freeze['inputs']['protected_cell_allocation_template'].items())):
                raise ValueError('protected live resource guard failed')
            validate_scored_receipt(adjusted, rows, release['freeze_sha256'],
                                    item['episode_ids'], receipt['expected_query_ids'],
                                    coordinate_model=load_coordinate_model(freeze['inputs']['selected_models']['jet'],
                                        spec.shape, resolve=paths.resolve) if method == 'laguerre' else None)
        identities = {(row['history_id'], row.get('query_id')) for row in rows}
        if len(identities) != len(rows):
            raise ValueError('duplicate query row identity')
        total += len(rows)
        key_text = phase + '/' + method
        summary = aggregates.setdefault(key_text, {'rows': 0, 'primary_rows': 0,
                          'ineligible_rows': 0, 'fallback_rows': 0, 'loss_sum': 0.,
                          'loss_count': 0, 'costs': []})
        summary['rows'] += len(rows)
        if 'costs' in receipt:
            summary['costs'].append(receipt['costs'])
        for row in rows:
            if row.get('score_scope') == 'primary':
                summary['primary_rows'] += 1
                loss = row.get('loss')
                if type(loss) not in (float, int) or not math.isfinite(loss):
                    raise ValueError('nonfinite released primary loss')
                summary['loss_sum'] += float(loss)
                summary['loss_count'] += 1
            else:
                summary['ineligible_rows'] += 1
            if row.get('fallback') or row.get('fallback_reason'):
                summary['fallback_rows'] += 1
            if method in {'jet', 'bank'} and row.get('score_scope') == 'primary':
                pair_key = (phase, row['history_id'], row['task'])
                grouped.setdefault(pair_key, {}).setdefault(method, []).append(float(row['loss']))
    if seen != set(expected):
        raise ValueError('missing released pair/cell')
    for key, values in grouped.items():
        if set(values) != {'jet', 'bank'}:
            raise ValueError('incomplete paired primary history')
    for summary in aggregates.values():
        count = summary.pop('loss_count')
        total_loss = summary.pop('loss_sum')
        summary['mean_normalized_loss'] = total_loss / count if count else None
    paired_panels = {}
    if freeze['inputs']['profile'] == 'study':
        from .inference import STRATA, conditional_interval, validate_history_pairs
        for phase in ('confirmation', 'replication'):
            populations = [item for item in freeze['inputs']['populations'] if item['phase'] == phase]
            by_stratum = {f"{item['spec']['lengths'][0]}:{item['spec']['regimes'][0]}": item
                          for item in populations}
            if set(by_stratum) != set(STRATA):
                raise ValueError('paired stratum inventory incomplete')
            ids_by_stratum = {str(i): by_stratum[stratum]['episode_ids']
                              for i, stratum in enumerate(STRATA)}
            paired = []
            for stratum, ids in ids_by_stratum.items():
                for hid in ids:
                    means = {}
                    for method in ('jet', 'bank'):
                        tasks = []
                        for task in ('mean', 'contrast'):
                            losses = grouped.get((phase, hid, task), {}).get(method)
                            if not losses:
                                raise ValueError('missing paired primary task')
                            tasks.append(sum(losses) / len(losses))
                        means[method] = sum(tasks) / 2
                    paired.append({'history_id': hid, 'stratum': int(stratum),
                                   'jet_loss': means['jet'], 'bank_loss': means['bank'],
                                   'units': 'history'})
            calibration = freeze['acceptance']['inference']
            manifest = {'panel': phase, 'units': 'history',
                        'history_ids_by_stratum': ids_by_stratum,
                        'weights': [1 / 12] * 12, 'strata': list(STRATA),
                        'attempt': calibration['attempt'],
                        'per_cell': calibration['per_cell'],
                        'source_sha256': calibration['source_sha256'],
                        'calibration_evidence_sha256': calibration['evidence_sha256']}
            differences, strata = validate_history_pairs(paired, manifest)
            interval = conditional_interval(differences, strata, weights=manifest['weights'])
            paired_panels[phase] = {**interval, 'panel': phase,
                                   'paired_history_count': len(paired),
                                   'release_sha256': release['_release_sha256'],
                                   'manifest': manifest}
    return {'methods': methods, 'query_rows': total, 'by_phase_method': aggregates,
            'paired_task_histories': len(grouped), 'paired_panels': paired_panels}


def _stage_json(paths, stage, path_field, hash_field):
    result = stage['result']
    return _read_json(paths.resolve(result[path_field]), result[hash_field])


def _verify_frozen_science(paths, freeze, *, recovery=None):
    """Reapply the accepted source, calibration and fitted-model commitments."""
    from .contracts import ShapeSpec
    from .models import load_model
    from .protected import (_accepted_calibration, _accepted_qualification,
                            validate_scientific_plan)
    from .cache import e3_source_sha256

    inputs = freeze['inputs']
    from .execution_policy import verify_run_policy, verify_public_gate_ref, bind_run_policy
    run_policy = _read_json(paths.root / 'run-policy.json')
    if recovery is None:
        verify_run_policy(run_policy, inputs['resource_policy']['study_manifest_sha256'])
    else:
        _verify_historical_run_policy(paths, inputs)
    if run_policy != inputs['resource_policy'] or (
            inputs.get('execution_policy_sha256') != run_policy['execution_policy_sha256']):
        raise ValueError('frozen run execution policy mismatch')
    anchor_ref = inputs.get('run_policy_anchor_ref')
    if (type(anchor_ref) is not dict or
            anchor_ref.get('path') != str(paths.original_root / 'run-policy-anchor.json') or
            _file_sha(paths.resolve(anchor_ref['path']))[0] != anchor_ref.get('sha256') or
            (bind_run_policy(paths.root / 'run-policy.json') != run_policy
             if recovery is None else False)):
        raise ValueError('frozen original run clock anchor mismatch')
    validate_scientific_plan(inputs['populations'])
    if (freeze['acceptance']['reader'] != _accepted_qualification() or
            freeze['acceptance']['inference'] != _accepted_calibration() or
            inputs['calibration'] != freeze['acceptance']['inference']):
        raise ValueError('reader/calibration acceptance changed')
    pairs = {}
    for key, shape in (('selected_models', ShapeSpec(16, 8)),
                       ('selected_k12_models', ShapeSpec(12, 1))):
        refs = inputs[key]
        if set(refs) != {'jet', 'bank'}:
            raise ValueError('frozen selected pair incomplete')
        pairs[key] = {}
        for family, ref in refs.items():
            path = paths.resolve(ref['path'])
            model = load_model(path, ref['sha256'])
            if model.shape != shape or model.spec.family != family:
                raise ValueError('frozen selected model shape/family mismatch')
            pairs[key][family] = {'manifest_sha256': ref['sha256'],
                                  'active_numeric_bytes': model.parameter_nbytes(),
                                  'reader': model.spec.to_json(),
                                  'target_statistics_sha256': canonical_hash(model.target_statistics),
                                  'target_statistics': model.target_statistics}
    if canonical_hash({family: refs['sha256'] for family, refs in
                       inputs['selected_models'].items()}) != inputs['model_pair_sha256']:
        raise ValueError('frozen selected model pair commitment mismatch')
    modes = _read_json(paths.resolve(inputs['transfer_modes_path']),
                       inputs['transfer_modes_sha256'])
    gate = verify_public_gate_ref(inputs.get('public_selection_gate_ref'),
                                  inputs['selected_models'], inputs['selected_k12_models'],
                                  modes, resolve=paths.resolve)
    if (modes.get('prefreeze') is not True or
            modes.get('beijing_manifest_sha256') != inputs['beijing_manifest_sha256'] or
            modes.get('e3_source_sha256') != e3_source_sha256() or
            modes.get('synthetic_frozen') != inputs['selected_k12_models'] or
            inputs['real_model_commitments'] !=
                {mode: canonical_hash(modes[mode]) for mode in ('synthetic_frozen', 'task_adapted')}):
        raise ValueError('frozen real transfer mode commitment mismatch')
    for family, ref in modes['task_adapted'].items():
        model = load_model(paths.resolve(ref['path']), ref['sha256'])
        if model.shape != ShapeSpec(12, 1) or model.spec.family != family:
            raise ValueError('task-adapted model shape/family mismatch')
    from .study import load_score_rows
    from .transfer import verify_prefreeze_cache_entries
    from . import transfer as transfer_module
    if modes.get('transfer_source_sha256') != _file_sha(transfer_module.__file__)[0]:
        raise ValueError('frozen transfer source changed')
    if (modes.get('real_probe_ref') != inputs['transfer_probe_ref'] or
            len(modes.get('real_development_ledger', [])) != 36 or
            set(modes.get('task_adapted', {})) != {'jet', 'bank'}):
        raise ValueError('real fit ledger/probe/model inventory mismatch')
    ledger_hashes = set()
    for entry in modes['real_development_ledger']:
        if entry.get('config_hash') in ledger_hashes or entry.get('family') not in {'jet', 'bank'}:
            raise ValueError('duplicate real fit candidate')
        ledger_hashes.add(entry['config_hash'])
        if entry['status'] not in {'qualified', 'failed'}:
            raise ValueError('real development candidate unfinished')
        if type(entry.get('rows_ref')) is not dict or type(entry.get('fit_ref')) is not dict:
            raise ValueError('real fit candidate model/rows missing')
        load_score_rows(paths.ref(entry['rows_ref']))
        load_model(paths.resolve(entry['fit_ref']['path']), entry['fit_ref']['sha256'])
    for split in ('training_cache', 'development_cache'):
        adjusted_entries = []
        for entry in modes[split]:
            path = paths.resolve(entry['path'])
            sha, size = _file_sha(path)
            if (sha, size) != (entry['sha256'], entry['bytes']):
                raise ValueError('prefreeze real episode cache changed')
            adjusted_entries.append({**entry, 'path': str(path)})
        verify_prefreeze_cache_entries(adjusted_entries)
    selected_reference = verify_selected_reference_rebased(paths, modes)
    probe_ref = inputs['transfer_probe_ref']
    probe = verify_transfer_probe_rebased(paths, probe_ref,
                                          inputs['beijing_manifest_sha256'],
                                          inputs['worker_limits'])
    allocation = inputs['transfer_fit_allocation']
    if (allocation.get('max_wall_seconds') != probe['recommended_wall_seconds'] or
            allocation.get('max_disk_bytes') != probe['recommended_disk_bytes'] or
            allocation.get('max_rss_bytes') != probe['recommended_rss_bytes']):
        raise ValueError('frozen real fit allocation differs from measured probe')
    guard_ref = paths.ref(inputs['transfer_fit_guard_ref'])
    guard = _read_json(guard_ref['path'], guard_ref['sha256'], guard_ref['bytes'])
    if (guard.get('status') != 'completed' or guard.get('violation') is not None or
            guard.get('allocation') != inputs['transfer_fit_allocation']):
        raise ValueError('prefreeze transfer resource guard failed')
    transfer = {'real_development_ledger': modes['real_development_ledger'],
                'selected_task_adapted': modes['task_adapted'],
                'selected_reference': selected_reference,
                'real_probe': {'sha256': probe_ref['sha256'],
                               'measured_profile': probe['measured_profile'],
                               'forecast_seconds': probe['forecast_seconds'],
                               'recommended_wall_seconds': probe['recommended_wall_seconds'],
                               'recommended_disk_bytes': probe['recommended_disk_bytes'],
                               'recommended_rss_bytes': probe['recommended_rss_bytes']},
                'cache_bytes': modes['cache_bytes'],
                'elapsed_seconds': modes['elapsed_seconds'],
                'fit_allocation': allocation}
    return {'pairs': pairs, 'modes': modes, 'gate': gate, 'transfer': transfer,
            'calibration': freeze['acceptance']['inference'],
            'qualification': freeze['acceptance']['reader']}


def project_development_journal(journal):
    """Project exact E3 terminal records, preserving unavailable subset metrics."""
    def complete_ref(ref, fields):
        if type(ref) is not dict or set(ref) != fields:
            return False
        if (type(ref['path']) is not str or not ref['path'] or
                type(ref['sha256']) is not str or len(ref['sha256']) != 64 or
                any(char not in '0123456789abcdef' for char in ref['sha256'])):
            return False
        return 'bytes' not in fields or (type(ref['bytes']) is int and ref['bytes'] >= 0)

    if (journal.get('status') != 'complete' or len(journal.get('candidate_ledger', [])) != 36 or
            len(journal.get('prefix_ledger', [])) != 4 or
            set(journal.get('selected', {})) != {'jet', 'bank'} or
            set(journal.get('controls', {})) !=
                {'exact', 'recent', 'latest_lru', 'reservoir', 'buckets', 'laguerre'}):
        raise ValueError('development candidate/subset/control inventory incomplete')
    candidates = []
    seen = set()
    for item in journal['candidate_ledger']:
        identity = (item.get('family'), item.get('config_hash'))
        if (identity in seen or item.get('status') not in {'qualified', 'failed'} or
                identity[0] not in {'jet', 'bank'}):
            raise ValueError('duplicate/incomplete candidate ledger')
        seen.add(identity)
        if item['status'] == 'qualified':
            if (type(item.get('active_static_bytes')) is not int or
                    type(item.get('wire_static_bytes')) is not int or
                    type(item.get('numeric_parameter_bytes')) is not int or
                    any(item[field] < 0 for field in
                        ('active_static_bytes', 'wire_static_bytes', 'numeric_parameter_bytes')) or
                    item.get('wire_static_bytes') != item.get('costs', {}).get('statics_bytes') or
                    type(item.get('loss')) not in (int, float) or
                    not math.isfinite(item['loss'])):
                raise ValueError('qualified candidate storage/loss schema mismatch')
        elif 'fit_ref' not in item and 'rows_ref' not in item:
            if item.get('failure_stage') != 'numerical_fit':
                raise ValueError('candidate model/row evidence incomplete')
            if (type(item.get('error')) is not str or not item['error'] or
                    item.get('loss') is not None or 'score' in item or 'costs' in item):
                raise ValueError('candidate failure is not terminal numerical fit')
        if (item['status'] == 'qualified' or 'fit_ref' in item or 'rows_ref' in item or
                item.get('failure_stage') != 'numerical_fit') and not (
                    complete_ref(item.get('fit_ref'), {'path', 'sha256'}) and
                    complete_ref(item.get('rows_ref'), {'path', 'sha256', 'bytes'})):
            raise ValueError('candidate model/row evidence incomplete')
        candidates.append({key: item.get(key) for key in
            ('family', 'reader', 'config_hash', 'status', 'loss', 'score',
             'active_static_bytes', 'wire_static_bytes', 'numeric_parameter_bytes',
             'fit_rows', 'fit_objective', 'costs', 'error', 'failure_stage')})
    if len({item['config_hash'] for item in candidates}) != 36:
        raise ValueError('candidate configuration inventory incomplete')
    prefixes = []
    prefix_ids = set()
    for item in journal['prefix_ledger']:
        identity = (item.get('family'), item.get('prefix'))
        if identity in prefix_ids or identity[0] not in {'jet', 'bank'} or identity[1] not in {192, 384}:
            raise ValueError('duplicate/unknown subset fit')
        prefix_ids.add(identity)
        if item.get('status') == 'measured':
            if (type(item.get('score')) is not dict or
                    type(item.get('costs')) is not dict or
                    type(item.get('fit_ref')) is not dict or
                    type(item.get('rows_ref')) is not dict):
                raise ValueError('measured subset evidence incomplete')
        elif item.get('status') == 'failed':
            if (item.get('failure_stage') != 'numerical_fit' or
                    type(item.get('error')) is not str or not item['error'] or
                    any(field in item for field in ('score', 'costs', 'fit_ref', 'rows_ref'))):
                raise ValueError('subset failure is not terminal numerical fit')
        else:
            raise ValueError('subset fit incomplete')
        prefixes.append({key: item.get(key) for key in
                         ('family', 'prefix', 'status', 'score', 'costs',
                          'error', 'failure_stage')})
    if prefix_ids != {(family, prefix) for family in ('jet', 'bank') for prefix in (192, 384)}:
        raise ValueError('subset fit inventory incomplete')
    controls = {}
    for name, item in journal['controls'].items():
        if item.get('status') != 'measured' or type(item.get('costs')) is not dict:
            raise ValueError('simple control missing')
        controls[name] = {key: item.get(key) for key in
                          ('status', 'score', 'costs', 'static_bytes',
                           'state_budget', 'unused_bytes', 'capacity')}
    for family in ('jet', 'bank'):
        chosen = journal['selected'][family]
        matches = [item for item in journal['candidate_ledger']
                   if item['family'] == family and item['config_hash'] == chosen.get('config_hash')
                   and item['status'] == 'qualified' and item['reader'] == chosen.get('reader')]
        if len(matches) != 1:
            raise ValueError('selected configuration differs from qualified candidate')
    return {'candidates': candidates, 'prefixes': prefixes,
            'controls': controls, 'selected': journal['selected'],
            'shared_costs': journal['shared_costs'],
            'fit_attempt_count': journal.get('fit_attempt_count'),
            'completed_fit_count': journal.get('completed_fit_count')}


def _verify_development(paths, stages, freeze):
    """Bind every entered candidate, subset fit and control to saved row bytes."""
    from .study import load_score_rows
    from .models import load_model
    output = {}
    for shape, stage_name, hash_field in (('K16/V8', 'development_k16', 'study_k16_sha256'),
                                          ('K12/V1', 'development_k12', 'study_k12_sha256')):
        journal = _stage_json(paths, stages[stage_name], 'journal_path', 'journal_sha256')
        if stages[stage_name]['result']['journal_sha256'] != freeze['inputs'][hash_field]:
            raise ValueError('development journal differs from frozen study')
        projected = project_development_journal(journal)
        for item in journal['candidate_ledger']:
            if item['status'] == 'qualified' or 'fit_ref' in item:
                load_model(paths.resolve(item['fit_ref']['path']), item['fit_ref']['sha256'])
                load_score_rows(paths.ref(item['rows_ref']))
        for item in journal['prefix_ledger']:
            if item['status'] == 'measured':
                load_model(paths.resolve(item['fit_ref']['path']), item['fit_ref']['sha256'])
                load_score_rows(paths.ref(item['rows_ref']))
        for name, item in journal['controls'].items():
            rows = load_score_rows(paths.ref(item['rows_ref']))
            if name == 'laguerre':
                key = 'selected_models' if shape == 'K16/V8' else 'selected_k12_models'
                selected_ref = freeze['inputs'][key]['jet']
                if journal['selected']['jet']['fit_ref'] != selected_ref:
                    raise ValueError('coordinate development selected checkpoint mismatch')
                expected_shape = ShapeSpec(16, 8) if shape == 'K16/V8' else ShapeSpec(12, 1)
                model = load_coordinate_model(selected_ref, expected_shape, resolve=paths.resolve)
                validate_coordinate_audits(item.get('costs'), rows, expected_model=model)
        output[shape] = projected
    return output


def _verify_timing(paths, stage, expected_methods):
    body = _stage_json(paths, stage, 'timing_path', 'timing_sha256')
    timed_methods = set(expected_methods) - {'laguerre'}
    records = body.get('records', [])
    expected_records = {(method, qcount, block) for method in timed_methods
                        for qcount in (1, 8, 64) for block in range(12)}
    if (body.get('schema_version') != 1 or body['policy'].get('warmups') != 3 or
            body['policy'].get('blocks') != 12 or
            body['policy'].get('query_counts') != [1, 8, 64] or
            set(body.get('summaries', {})) != timed_methods or
            any(set(summary) != {'1', '8', '64'} for summary in body['summaries'].values()) or
            len(records) != len(expected_records) or
            any(type(row.get('method')) is not str or type(row.get('query_count')) is not int or
                type(row.get('block')) is not int for row in records) or
            {(row['method'], row['query_count'], row['block']) for row in records} != expected_records):
        raise ValueError('paired timing inventory incomplete')
    unmeasured = {'laguerre': {'status': 'not_measured', 'query_seconds': None,
                             'reason': 'coordinate_reference_validation_not_deployment_timing'}} if 'laguerre' in expected_methods else {}
    return {'policy': body['policy'], 'summaries': body['summaries'],
            'unmeasured_methods': unmeasured,
            'break_even_queries': body['break_even_queries'],
            'rss_scope': body['rss_scope'], 'admission': body['admission']}


def _verify_stress(paths, stage, freeze):
    from .study import load_score_rows
    body = _stage_json(paths, stage, 'results_path', 'results_sha256')
    if body.get('kind') != 'famjet_e4_public_stress' or not body.get('secondary_task_ledger'):
        raise ValueError('stress/secondary inventory incomplete')
    from .pipeline import secondary_ledger, stress_inventory
    if (body.get('inventory_sha256') != canonical_hash(stress_inventory()) or
            body['secondary_task_ledger'] != secondary_ledger(body['results'])):
        raise ValueError('stress inventory/status ledger mismatch')
    for item in body['results']:
        if item['rows_ref'] is not None:
            rows = load_score_rows(paths.ref(item['rows_ref']))
            if item['method'] == 'laguerre':
                model = load_coordinate_model(freeze['inputs']['selected_models']['jet'],
                                              ShapeSpec(16, 8), resolve=paths.resolve)
                validate_coordinate_audits(item.get('costs'), rows, expected_model=model)
    statuses = {'implemented/scored', 'unsupported', 'failed', 'unentered'}
    for item in body['secondary_task_ledger']:
        if item['status'] not in statuses or (item['status'] != 'implemented/scored' and
                                              item['metrics'] is not None):
            raise ValueError('secondary status/metric mismatch')
    return {'secondary_task_ledger': body['secondary_task_ledger'],
            'results': [{key: item.get(key) for key in
                        ('mode', 'method', 'status', 'reason', 'summary', 'costs', 'tasks')}
                        for item in body['results']]}


def _verify_real_release(paths, stage, freeze, modes):
    """Check both complete real modes in method-sized batches, including native units."""
    from .contracts import AccessGrant
    from .protected import validate_scored_receipt
    from .study import load_score_rows
    from .transfer import (block_sensitivity, native_rows,
                           real_scoring_statistics, validate_real_method_inventory)
    from famjet.data import beijing as beijing_core

    result = stage['result']
    body = _read_json(paths.resolve(result['real_release_path']),
                      result['real_release_sha256'])
    if body.get('kind') != 'famjet_e4_real_complete_release' or body.get('status') != 'complete':
        raise ValueError('real release incomplete')
    if body['freeze_sha256'] != freeze['_freeze_sha256']:
        raise ValueError('real release frozen study mismatch')
    if body['freeze_path'] != freeze['_freeze_path']:
        raise ValueError('real release frozen path mismatch')
    if body.get('population_scope') != 'finite_2015_2017_test_period':
        raise ValueError('real release population scope changed')
    manifest_path = paths.resolve(body['beijing_manifest_path'])
    manifest_sha, _ = _file_sha(manifest_path)
    if (manifest_sha != body['beijing_manifest_sha256'] or
            manifest_sha != freeze['inputs']['beijing_manifest_sha256'] or
            body['mode_ref_sha256'] != freeze['inputs']['transfer_modes_sha256'] or
            body['mode_ref_path'] != freeze['inputs']['transfer_modes_path']):
        raise ValueError('real manifest/mode commitment mismatch')
    metadata = beijing_core._verify_manifest(manifest_path)
    blocks = metadata['splits']['test']['blocks']
    histories = [block['history_id'] for block in blocks]
    if (histories != freeze['inputs']['beijing_test_ids'] or len(histories) != 56 or
            len({b['cluster_28d'] for b in blocks}) != 28 or
            len({b['cluster_56d'] for b in blocks}) != 14):
        raise ValueError('real test block/cluster inventory mismatch')
    block_by_id = {block['history_id']: block for block in blocks}
    statistics_hash = canonical_hash(real_scoring_statistics(manifest_path))
    roster = freeze['inputs']['expected_methods']
    inventory = validate_real_method_inventory(body['receipts'],
                                               ('synthetic_frozen', 'task_adapted'), roster)
    if (body['inventory'] != inventory or
            len({r['counts_ref']['sha256'] for r in body['receipts']}) != 1 or
            body['counts_ref']['sha256'] != body['receipts'][0]['counts_ref']['sha256']):
        raise ValueError('real method/count inventory mismatch')
    output = {}
    paired = {}
    validated = []
    for receipt in body['receipts']:
        mode, method = receipt['mode'], receipt['method']
        commitment = canonical_hash(modes[mode])
        if (receipt.get('freeze_sha256') != freeze['_freeze_sha256'] or
                receipt.get('source_sha256') != freeze['source_sha256'] or
                receipt.get('model_pair_sha256') != commitment or
                receipt.get('beijing_manifest_sha256') != manifest_sha or
                receipt.get('expected_history_ids') != histories or
                receipt.get('score_contract', {}).get('statistics_sha256') != statistics_hash or
                receipt.get('status') != 'completed' or
                type(receipt.get('costs')) is not dict or not receipt['costs'] or
                type(receipt.get('output_admission')) is not dict):
            raise ValueError('real method source/model/data/statistics mismatch')
        grant = AccessGrant(paths.resolve(receipt['grant_path']), receipt['grant_sha256'],
                            'test', 'test')
        grant.verify(source_sha256=freeze['source_sha256'], data_sha256=manifest_sha,
                     model_sha256=commitment)
        grant_record = grant.verify(source_sha256=freeze['source_sha256'],
                                    data_sha256=manifest_sha, model_sha256=commitment)
        if grant_record['episode_ids'] != histories:
            raise ValueError('real grant test-block inventory mismatch')
        live_ref = paths.ref(receipt['live_guard_ref'])
        live = _read_json(live_ref['path'], live_ref['sha256'], live_ref['bytes'])
        if (live.get('kind') != 'famjet_e4_live_stage_guard' or
                live.get('status') != 'completed' or live.get('violation') is not None or
                live.get('allocation', {}).get('allocation_id') !=
                    'e4-beijing-' + mode + '-' + method or
                any(live['allocation'].get(field) != value for field, value in
                    freeze['inputs']['real_method_allocation_template'].items())):
            raise ValueError('real live resource guard failed')
        adjusted = {**receipt, 'counts_ref': paths.ref(receipt['counts_ref']),
                    'score_contract': {**receipt['score_contract'],
                        'policy_ref': paths.ref(receipt['score_contract']['policy_ref'])}}
        normalized = load_score_rows(paths.ref(receipt['rows_ref']))
        native = load_score_rows(paths.ref(receipt['native_rows_ref']))
        require_real_method_rows(method, normalized)
        require_real_method_rows(method, native)
        coordinate_model = load_coordinate_model(modes[mode]['jet'], ShapeSpec(12, 1), resolve=paths.resolve) if method == 'laguerre' else None
        validate_scored_receipt(adjusted, normalized, manifest_sha, histories, list(range(120)), coordinate_model=coordinate_model)
        validate_scored_receipt(adjusted, native, manifest_sha, histories, list(range(120)), coordinate_model=coordinate_model)
        if len(normalized) != 56 * 120 or len(native) != len(normalized):
            raise ValueError('real method query inventory incomplete')
        expected_native = native_rows(normalized, modes['normalization'])
        mse_sum = mae_sum = loss_sum = 0.
        primary_count = fallback_count = ineligible_count = 0
        sensitivity_rows = []
        for source, row, expected in zip(normalized, native, expected_native, strict=True):
            block = block_by_id.get(row['history_id'])
            if (block is None or (source['history_id'], source['query_id'], source['task']) !=
                    (row['history_id'], row['query_id'], row['task']) or
                    any(row.get(field) != expected[field] for field in
                        ('native_status', 'native_prediction', 'native_target') ) or
                    any(row.get(field) != block[key] for field, key in
                        (('cluster_28d', 'cluster_28d'), ('cluster_56d', 'cluster_56d'),
                         ('block_start', 'start'), ('block_end', 'end')))):
                raise ValueError('real native row identity/unit/cluster mismatch')
            if row['score_scope'] == 'primary':
                if (row.get('native_status') != 'ok' or
                        type(row.get('native_mse_micrograms2')) not in (int, float) or
                        type(row.get('native_mae_micrograms')) not in (int, float) or
                        row['native_mse_micrograms2'] != expected['native_mse_micrograms2'] or
                        row['native_mae_micrograms'] != expected['native_mae_micrograms']):
                    raise ValueError('real native error values invalid')
                primary_count += 1
                mse_sum += row['native_mse_micrograms2']
                mae_sum += row['native_mae_micrograms']
                loss_sum += row['loss']
                sensitivity_rows.append(row)
            else:
                ineligible_count += 1
            if row.get('fallback') or row.get('fallback_reason'):
                fallback_count += 1
        if primary_count == 0:
            raise ValueError('real primary rows unavailable')
        sensitivity = block_sensitivity(sensitivity_rows, {'28d': 28, '56d': 14})
        if sensitivity != receipt['block_sensitivity']:
            raise ValueError('real descriptive cluster sensitivity mismatch')
        output.setdefault(mode, {})[method] = {
            'native_rmse_micrograms': math.sqrt(mse_sum / primary_count),
            'native_mae_micrograms': mae_sum / primary_count,
            'mean_normalized_loss': loss_sum / primary_count,
            'primary_rows': primary_count, 'ineligible_rows': ineligible_count,
            'fallback_rows': fallback_count, 'block_sensitivity': sensitivity,
            'costs': receipt['costs'], 'summary': receipt['summary'],
            'output_admission': receipt['output_admission']}
        if method in {'jet', 'bank'}:
            paired[(mode, method)] = [
                {'history_id': r['history_id'], 'query_id': r['query_id'],
                 'task': r['task'], 'score_scope': r['score_scope'],
                 'loss': r['loss'], 'cluster_28d': r['cluster_28d'],
                 'cluster_56d': r['cluster_56d']} for r in native]
        validated.append({'mode': mode, 'method': method,
                          'normalized_rows_sha256': receipt['rows_ref']['sha256'],
                          'native_rows_sha256': receipt['native_rows_ref']['sha256'],
                          'query_count': len(normalized), 'history_count': len(histories),
                          'grant_sha256': receipt['grant_sha256']})
    if body.get('validated_runs') != validated:
        raise ValueError('real release validated-run receipt differs')
    paired_sensitivity = {}
    for mode in ('synthetic_frozen', 'task_adapted'):
        jet = paired[(mode, 'jet')]
        bank = paired[(mode, 'bank')]
        bank_by_key = {(r['history_id'], r['query_id']): r for r in bank}
        differences = []
        for row in jet:
            other = bank_by_key.pop((row['history_id'], row['query_id']), None)
            if other is None or row['task'] != other['task'] or row['score_scope'] != other['score_scope']:
                raise ValueError('real paired query inventory differs')
            if row['score_scope'] == 'primary':
                differences.append({'history_id': row['history_id'],
                    'cluster_28d': row['cluster_28d'], 'cluster_56d': row['cluster_56d'],
                    'loss': other['loss'] - row['loss']})
        if bank_by_key:
            raise ValueError('real bank has unmatched query rows')
        paired_sensitivity[mode] = block_sensitivity(differences, {'28d': 28, '56d': 14})
    if paired_sensitivity != body['paired_block_sensitivity']:
        raise ValueError('real paired sensitivity receipt mismatch')
    return {'modes': output, 'paired_block_sensitivity': paired_sensitivity,
            'test_blocks': 56, 'queries_per_block': 120,
            'cluster_counts': {'28d': 28, '56d': 14},
            'population_scope': body['population_scope'],
            'beijing_manifest_sha256': manifest_sha}


def load_report_inputs(run, *, compatibility_id=None, archived_source=None):
    """Return small validated summaries; never fit, select, or generate rows."""
    from .protected import FrozenStudyRef
    run = Path(run).resolve(strict=True)
    if compatibility_id is None:
        if archived_source is not None:
            raise ValueError('archived source requires registered report compatibility ID')
        recovery = None
    else:
        recovery = _admit_report_migration(run, compatibility_id, archived_source)
    stages = _stage_records(run)
    if not {'freeze', 'release'} <= set(stages):
        raise ValueError('freeze and release stages required')
    freeze_result = stages['freeze']['result']
    release_result = stages['release']['result']
    recorded_freeze = freeze_result['path']
    paths = ArtifactPaths(run, recorded_freeze)
    freeze_path = paths.resolve(recorded_freeze)
    frozen = _read_json(freeze_path, freeze_result['sha256'])
    if frozen.get('kind') != 'famjet_e4_study_freeze':
        raise ValueError('study freeze schema mismatch')
    if recovery is None:
        FrozenStudyRef(freeze_path, freeze_result['sha256'], frozen['source_sha256'],
                       frozen['executable']['sha256']).read()
    elif (frozen.get('schema_version') != 1 or
          frozen.get('executable') !=
              {'sha256': recovery['execution_sha256'],
               'files': _read_json(_MIGRATION_PATH)['old_files']} or
          frozen.get('git', {}).get('revision') != _OLD_COMMIT):
        raise ValueError('historical freeze execution identity mismatch')
    recorded_release = release_result['release_path']
    release_path = paths.resolve(recorded_release)
    release = _read_json(release_path, release_result['release_sha256'])
    if (release.get('freeze_path') != recorded_freeze or
            release.get('freeze_sha256') != freeze_result['sha256']):
        raise ValueError('release frozen source mismatch')
    release['_release_sha256'] = release_result['release_sha256']
    frozen['_freeze_sha256'] = freeze_result['sha256']
    frozen['_freeze_path'] = recorded_freeze
    profile = frozen['inputs']['profile']
    if profile == 'unit_test':
        synthetic = _release_rows(paths, release, frozen)
        status = 'non_scientific_smoke'
    elif profile == 'study':
        require_scientific_stages(stages, frozen['inputs'])
        if stages['public_selection_gate']['result']['gate_ref'] != frozen['inputs']['public_selection_gate_ref']:
            raise ValueError('public selection gate stage/freeze reference mismatch')
        scientific = _verify_frozen_science(paths, frozen, recovery=recovery)
        frozen['_expected_statistics_sha256'] = scientific['pairs']['selected_models']['jet'][
            'target_statistics_sha256']
        development = _verify_development(paths, stages, frozen)
        timing = _verify_timing(paths, stages['timing_k16'], release['expected_methods'])
        stress = _verify_stress(paths, stages['stress'], frozen)
        synthetic = _release_rows(paths, release, frozen)
        real_release_path = _read_json(paths.resolve(release_result['real_release_path']),
                                       release_result['real_release_sha256'])
        recorded_beijing = real_release_path['beijing_manifest_path']
        if not Path(recorded_beijing).is_absolute():
            raise ValueError('original Beijing manifest path invalid')
        paths.original_project = Path(recorded_beijing).parents[2]
        real = _verify_real_release(paths, stages['release'], frozen, scientific['modes'])
        inference = _read_json(run / 'release' / 'inference.json',
                               release_result['inference_sha256'])
        if inference != synthetic['paired_panels']:
            raise ValueError('stored primary/replication inference differs from raw rows')
        beijing_manifest = _read_json(paths.resolve(recorded_beijing),
                                      frozen['inputs']['beijing_manifest_sha256'])
        inventory = frozen['inputs']['beijing_array_inventory']
        array_status = verify_beijing_inventory(inventory, beijing_manifest)
        source = {'archive': beijing_manifest['archive'],
                  'attribution': beijing_manifest['attribution'],
                  'preparation_version': beijing_manifest['preparation_version'],
                  'query_grid_version': beijing_manifest['query_grid_version'],
                  'target_semantics': beijing_manifest['target_semantics'],
                  'normalization': beijing_manifest['normalization']}
        status = 'scientific_artifacts_validated'
    else:
        raise ValueError('unknown study profile')
    output = {'status': status, 'freeze_sha256': freeze_result['sha256'],
            'release_sha256': release_result['release_sha256'],
            'source_sha256': frozen['source_sha256'],
            'executable_sha256': frozen['executable']['sha256'],
            'synthetic': synthetic, 'freeze': frozen,
            'stage_names': sorted(stages)}
    if profile == 'study':
        output.update(scientific={key: value for key, value in scientific.items()
                                  if key not in {'modes', 'transfer'}},
                      development=development, timing=timing, stress=stress,
                      real=real, beijing_source_inventory=inventory,
                      beijing_source=source,
                      beijing_source_array_status=array_status,
                      transfer=scientific['transfer'])
    if recovery is not None:
        output['report_recovery'] = recovery
    return output
