"""Write-once study commitments, guarded access, complete runs and sealed release."""
from dataclasses import dataclass
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import subprocess
import time
import numpy as np

from famjet.provenance import canonical_hash, canonical_json
from .contracts import AccessGrant, PopulationSpec, source_sha256
from .inference import source_identity, validate_calibration


_ROOT = Path(__file__).resolve().parent.parent
_SHA = set('0123456789abcdef')
_CALIBRATION_FULL_CACHE = {}
_CALIBRATION_COSTS = []


def calibration_costs():
    return list(_CALIBRATION_COSTS)


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _digest(value):
    return type(value) is str and len(value) == 64 and set(value) <= _SHA


def _write_once(path, body):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = canonical_json(body)
    with path.open('xb') as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    return {'path': str(path), 'sha256': _sha(raw), 'bytes': len(raw)}


def executable_identity():
    """Bind every executable PoC/core byte, including later E5 modules."""
    paths = sorted((_ROOT / 'famjet_poc').glob('*.py')) + sorted((_ROOT / 'famjet').rglob('*.py'))
    paths.append(_ROOT / 'requirements.lock')
    files = {str(path.relative_to(_ROOT)): _sha(path.read_bytes()) for path in paths}
    return {'sha256': canonical_hash(files), 'files': files}


def _git_identity():
    revision = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=_ROOT, check=True,
                              capture_output=True, text=True).stdout.strip()
    diff = subprocess.run(['git', 'diff', '--binary', 'HEAD', '--', 'famjet', 'famjet_poc',
                           'requirements.lock'], cwd=_ROOT, check=True, capture_output=True).stdout
    return {'revision': revision, 'tracked_source_diff_sha256': _sha(diff)}


def _accepted_qualification():
    index_path = _ROOT / 'docs/research/e2e-qualification-01-evidence/index.json'
    index = json.loads(index_path.read_bytes())
    if (index.get('schema_version') != 1 or len(index.get('files', [])) < 16 or
            index.get('status') != 'QUALIFIED_FOR_EXPLICIT_TWO_AGE_FAMILY' or
            index.get('cases') != 8 or index.get('source_model_sha256') != source_sha256()):
        raise ValueError('incomplete reader qualification archive')
    for item in index['files']:
        path = index_path.parent / item['path']
        if path.stat().st_size != item['bytes'] or _sha(path.read_bytes()) != item['sha256']:
            raise ValueError('reader qualification archive hash mismatch')
    report = _ROOT / 'docs/research/e2e-qualification-01-report.md'
    if not report.is_file() or 'All8predeclaredcasespassed' not in report.read_text():
        raise ValueError('reader qualification acceptance missing')
    return {'status': 'reused_accepted', 'index_sha256': _sha(index_path.read_bytes()),
            'report_sha256': _sha(report.read_bytes()), 'file_count': len(index['files'])}


def _verify_bundle_bytes(directory, expected):
    """Check every declared byte and reject added/missing files or unsafe paths."""
    started = time.perf_counter()
    directory = Path(directory)
    if type(expected) is not dict or not expected or not directory.is_dir():
        raise ValueError('calibration bundle inventory missing')
    observed_names = {str(path.relative_to(directory)) for path in directory.rglob('*') if path.is_file()}
    if observed_names != set(expected):
        raise ValueError('calibration bundle file inventory changed')
    total = 0
    for name, digest in expected.items():
        relative = Path(name)
        path = directory / relative
        if (relative.is_absolute() or '..' in relative.parts or path.is_symlink() or
                not _digest(digest) or _sha(path.read_bytes()) != digest):
            raise ValueError('calibration bundle byte hash mismatch')
        total += path.stat().st_size
    inventory = {'sha256': canonical_hash(expected), 'file_count': len(expected),
                 'bytes': total}
    _CALIBRATION_COSTS.append({'kind': 'bundle_digest',
                               'elapsed_seconds': time.perf_counter() - started,
                               'file_count': len(expected), 'bytes': total})
    return inventory


def _calibration_expected_files(evidence, evidence_sha256):
    expected = {'evidence.json': evidence_sha256}
    for fixture in evidence.get('fixtures', {}).values():
        for batch in fixture.get('batches', []):
            name, digest = batch.get('file'), batch.get('sha256')
            if type(name) is not str or '/' in name or name in expected or not _digest(digest):
                raise ValueError('calibration bundle batch inventory invalid')
            expected[name] = digest
    return expected


def _calibration_material():
    path = _ROOT / 'docs/research/e2e-inference-qualification.json'
    acceptance_raw = path.read_bytes()
    accepted = json.loads(acceptance_raw)
    if (accepted.get('status') != 'pass' or accepted.get('attempt') != 2 or
            accepted.get('per_cell') != 256 or accepted.get('all_32_guards') is not True or
            accepted.get('inference_source') != source_identity()):
        raise ValueError('accepted calibration source/attempt mismatch')
    evidence_path = _ROOT / accepted['evidence_path']
    raw = evidence_path.read_bytes()
    if _sha(raw) != accepted['evidence_sha256']:
        raise ValueError('calibration evidence bytes changed')
    evidence = json.loads(raw)
    validation_path = _ROOT / accepted['validation_path']
    validation_raw = validation_path.read_bytes()
    if json.loads(validation_raw).get('status') != 'pass':
        raise ValueError('accepted calibration validation receipt missing')
    admission_path = _ROOT / accepted['admission_path']
    admission_raw = admission_path.read_bytes()
    admission = json.loads(admission_raw)
    if (admission.get('work_deadline') != accepted['deadline_monotonic'] or
            not admission.get('start_monotonic') <= evidence['resource']['start_monotonic'] < accepted['deadline_monotonic']):
        raise ValueError('original calibration deadline admission mismatch')
    bundle = _verify_bundle_bytes(evidence_path.parent,
                                  _calibration_expected_files(evidence, accepted['evidence_sha256']))
    attestation = {'status': 'reused_accepted', 'acceptance_sha256': _sha(acceptance_raw),
                   'evidence_sha256': _sha(raw), 'validation_sha256': _sha(validation_raw),
                   'admission_sha256': _sha(admission_raw), 'bundle': bundle,
                   'attempt': 2, 'per_cell': 256,
                   'source_sha256': source_identity()['sha256'],
                   'deadline_monotonic': accepted['deadline_monotonic']}
    return evidence, accepted, attestation


def _accepted_calibration():
    evidence, accepted, attestation = _calibration_material()
    cache_key = canonical_hash(attestation)
    if cache_key in _CALIBRATION_FULL_CACHE:
        return _CALIBRATION_FULL_CACHE[cache_key]
    started = time.perf_counter()
    evidence_path = _ROOT / accepted['evidence_path']
    verdict = validate_calibration(evidence, {'out': str(evidence_path.parent),
                                               'deadline_monotonic': accepted['deadline_monotonic']})
    if verdict.get('status') != 'pass' or not all(all(v.values()) for v in verdict['guards'].values()):
        raise ValueError('calibration raw campaign not accepted')
    _CALIBRATION_COSTS.append({'kind': 'full_validation',
                               'elapsed_seconds': time.perf_counter() - started,
                               'file_count': attestation['bundle']['file_count'],
                               'bytes': attestation['bundle']['bytes']})
    _CALIBRATION_FULL_CACHE[cache_key] = attestation
    return attestation


def _verify_calibration_attestation(attestation):
    _, _, current = _calibration_material()
    if current != attestation:
        raise ValueError('calibration attested bundle/source/deadline changed')
    if canonical_hash(current) not in _CALIBRATION_FULL_CACHE:
        if _accepted_calibration() != attestation:
            raise ValueError('calibration resumed full validation changed')
    return current


def validate_scientific_plan(populations):
    """Reject altered protected roots, strata, shape or panel size before grant."""
    from .inference import STRATA
    if type(populations) is not list or len(populations) != 36:
        raise ValueError('scientific plan needs 36 frozen cells')
    expected = {('pilot', label): (2026102401902, 16) for label in STRATA}
    expected.update({('confirmation', label): (2026102401904, 256) for label in STRATA})
    expected.update({('replication', label): (2026102401905, 256) for label in STRATA})
    seen = set()
    history_ids = set()
    for item in populations:
        if type(item) is not dict or not {'phase', 'split', 'spec', 'episode_ids', 'cell_id'} <= set(item):
            raise ValueError('scientific cell incomplete')
        spec = PopulationSpec.from_json(item['spec'])
        if len(spec.lengths) != 1 or len(spec.regimes) != 1:
            raise ValueError('scientific cell must use one stratum')
        label = f'{spec.lengths[0]}:{spec.regimes[0]}'
        key = (item['phase'], label)
        if key not in expected or key in seen or item['split'] != item['phase'] or spec.namespace != item['phase']:
            raise ValueError('scientific phase/stratum mismatch')
        seen.add(key)
        seed, count = expected[key]
        if spec.seed != seed:
            raise ValueError('protected root mismatch')
        if (spec.version != 'poc_numeric_v1' or spec.shape.to_json() != {'key_dim': 16, 'value_dim': 8} or
                spec.queries_per_history != 8 or spec.max_query_attempts != 4096):
            raise ValueError('protected shape/generator/query plan mismatch')
        ids = item['episode_ids']
        if (type(ids) is not list or len(ids) != count or len(ids) != len(set(ids)) or
                any(type(h) is not str or not h for h in ids) or history_ids.intersection(ids)):
            raise ValueError('protected panel history inventory mismatch')
        history_ids.update(ids)
    if seen != set(expected):
        raise ValueError('scientific 12-stratum inventory incomplete')
    return {'cell_count': len(seen), 'history_count': len(history_ids),
            'history_inventory_sha256': canonical_hash(populations)}


def validate_model_commitments(inputs):
    """Verify selected model weights and both prefreeze real transfer modes."""
    from .models import load_model
    from .contracts import ShapeSpec
    from .transfer import (verify_prefreeze_cache_entries,
                           verify_transfer_probe, verify_selected_reference)
    from . import transfer as transfer_module
    from .cache import e3_source_sha256
    selected = inputs.get('selected_models')
    selected12 = inputs.get('selected_k12_models')
    if type(selected) is not dict or set(selected) != {'jet', 'bank'} or type(selected12) is not dict or set(selected12) != {'jet', 'bank'}:
        raise ValueError('both shape-specific model pairs required')
    if canonical_hash({name: selected[name]['sha256'] for name in ('jet', 'bank')}) != inputs.get('model_pair_sha256'):
        raise ValueError('frozen model pair commitment mismatch')
    for refs, shape in ((selected, ShapeSpec(16, 8)), (selected12, ShapeSpec(12, 1))):
        for family, ref in refs.items():
            if type(ref) is not dict or set(ref) != {'path', 'sha256'} or not _digest(ref['sha256']):
                raise ValueError('model reference schema mismatch')
            model = load_model(Path(ref['path']), ref['sha256'])
            if model.shape != shape or model.spec.family != family:
                raise ValueError('model shape/family mismatch')
    mode_path = inputs.get('transfer_modes_path')
    mode_sha = inputs.get('transfer_modes_sha256')
    if not isinstance(mode_path, str) or not _digest(mode_sha) or _sha(Path(mode_path).read_bytes()) != mode_sha:
        raise ValueError('prefreeze transfer mode bytes mismatch')
    modes = json.loads(Path(mode_path).read_bytes())
    if (modes.get('prefreeze') is not True or modes.get('shape') != ShapeSpec(12, 1).to_json() or
            modes.get('beijing_manifest_sha256') != inputs.get('beijing_manifest_sha256') or
            modes.get('e3_source_sha256') != e3_source_sha256() or
            modes.get('transfer_source_sha256') != _sha(Path(transfer_module.__file__).read_bytes()) or
            modes.get('synthetic_frozen') != selected12 or
            set(modes.get('task_adapted', {})) != {'jet', 'bank'}):
        raise ValueError('transfer mode/model commitment mismatch')
    commitments = {name: canonical_hash(modes[name]) for name in ('synthetic_frozen', 'task_adapted')}
    if inputs.get('real_model_commitments') != commitments:
        raise ValueError('real mode pair commitment mismatch')
    if modes.get('real_probe_ref') != inputs.get('transfer_probe_ref'):
        raise ValueError('frozen real transfer probe reference mismatch')
    probe = verify_transfer_probe(inputs['transfer_probe_ref'],
                                  inputs['beijing_manifest_sha256'],
                                  inputs['worker_limits'])
    allocation = inputs.get('transfer_fit_allocation')
    if (type(allocation) is not dict or
            allocation.get('max_wall_seconds') != probe['recommended_wall_seconds'] or
            allocation.get('max_disk_bytes') != probe['recommended_disk_bytes'] or
            allocation.get('max_rss_bytes') != probe['recommended_rss_bytes']):
        raise ValueError('frozen real fit allocation not bound to measured probe')
    guard = _read_bound_file(inputs.get('transfer_fit_guard_ref'))
    if (guard.get('kind') != 'famjet_e4_live_stage_guard' or
            guard.get('status') != 'completed' or guard.get('violation') is not None or
            guard.get('allocation') != allocation):
        raise ValueError('real fit live resource guard incomplete')
    verify_selected_reference(modes)
    verify_prefreeze_cache_entries(modes['training_cache'])
    verify_prefreeze_cache_entries(modes['development_cache'])
    for family, ref in modes['task_adapted'].items():
        model = load_model(Path(ref['path']), ref['sha256'])
        if model.shape != ShapeSpec(12, 1) or model.spec.family != family:
            raise ValueError('task-adapted model shape/family mismatch')
    return {'selected_pair_sha256': inputs['model_pair_sha256'],
            'transfer_modes_sha256': mode_sha, 'real_model_commitments': commitments}


@dataclass(frozen=True)
class FrozenStudyRef:
    path: Path
    sha256: str
    source_sha256: str
    executable_sha256: str

    def read(self):
        raw = self.path.read_bytes()
        if _sha(raw) != self.sha256:
            raise ValueError('freeze hash mismatch')
        body = json.loads(raw)
        if (body.get('schema_version') != 1 or body.get('kind') != 'famjet_e4_study_freeze' or
                body.get('source_sha256') != source_sha256() or
                body.get('source_sha256') != self.source_sha256 or
                body.get('executable', {}).get('sha256') != executable_identity()['sha256'] or
                body['executable']['sha256'] != self.executable_sha256):
            raise ValueError('frozen source/executable mismatch')
        return body


def freeze_study(inputs, out) -> FrozenStudyRef:
    """Freeze public selections and complete protected allocation, never mutate it."""
    if type(inputs) is not dict or inputs.get('profile') not in {'unit_test', 'study'} or not _digest(inputs.get('model_pair_sha256')):
        raise ValueError('complete model-pair commitment required')
    populations = inputs.get('populations')
    if type(populations) is not list or not populations:
        raise ValueError('complete population inventory required')
    identities = set()
    for item in populations:
        if type(item) is not dict or not {'phase', 'split', 'spec', 'episode_ids'} <= set(item):
            raise ValueError('population record incomplete')
        spec = PopulationSpec.from_json(item['spec'])
        ids = item['episode_ids']
        if (type(ids) is not list or not ids or any(type(h) is not str or not h for h in ids) or
                len(ids) != len(set(ids)) or any(h in identities for h in ids)):
            raise ValueError('duplicate/empty episode inventory')
        identities.update(ids)
        if inputs['profile'] == 'unit_test':
            if (item['phase'], item['split'], spec.namespace) != ('unit_test', 'pilot', 'unit_test'):
                raise ValueError('unit test requires isolated population')
        elif item['phase'] not in {'pilot', 'confirmation', 'replication'} or item['split'] != item['phase'] or spec.namespace != item['phase']:
            raise ValueError('scientific population phase mismatch')
    if inputs['profile'] == 'unit_test':
        if inputs.get('unit_test_admission') != {'schema_version': 1,
                'kind': 'famjet_e4_unit_test_admission', 'status': 'accepted'} or inputs.get('calibration') is not None:
            raise ValueError('test-only admission schema mismatch')
        acceptance = {'status': 'unit_test_only'}
        if 'unit_test_bundle' in inputs:
            bundle = inputs['unit_test_bundle']
            if (type(bundle) is not dict or set(bundle) != {'schema_version', 'kind', 'directory', 'files'} or
                    bundle['schema_version'] != 1 or bundle['kind'] != 'famjet_e4_unit_test_bundle'):
                raise ValueError('unit test bundle schema mismatch')
            _verify_bundle_bytes(bundle['directory'], bundle['files'])
    else:
        validate_scientific_plan(populations)
        validate_model_commitments(inputs)
        methods = ('jet', 'bank', 'exact', 'recent', 'latest_lru',
                   'reservoir', 'buckets', 'laguerre')
        if (inputs.get('expected_methods') != list(methods) or
                inputs.get('expected_query_ids') != list(range(8)) or
                inputs.get('expected_protected_run_ids') != [
                    item['cell_id'] + '-' + method for item in populations for method in methods] or
                type(inputs.get('protected_cell_allocation_template')) is not dict or
                type(inputs.get('real_method_allocation_template')) is not dict or
                type(inputs.get('worker_limits')) is not dict):
            raise ValueError('frozen method/query/resource run inventory incomplete')
        qualification = _accepted_qualification()
        calibration = _accepted_calibration()
        if inputs.get('calibration') != calibration:
            raise ValueError('actual accepted calibration commitment required')
        acceptance = {'reader': qualification, 'inference': calibration}
    if 'beijing_manifest_sha256' in inputs:
        if (not _digest(inputs['beijing_manifest_sha256']) or
                type(inputs.get('beijing_test_ids')) is not list or
                not inputs['beijing_test_ids'] or
                len(inputs['beijing_test_ids']) != len(set(inputs['beijing_test_ids'])) or
                type(inputs.get('real_model_commitments')) is not dict or
                not all(_digest(value) for value in inputs['real_model_commitments'].values())):
            raise ValueError('Beijing frozen manifest/model inventory invalid')
        if inputs['profile'] == 'study' and len(inputs['beijing_test_ids']) != 56:
            raise ValueError('Beijing needs all 56 test blocks')
    body = {'schema_version': 1, 'kind': 'famjet_e4_study_freeze', 'inputs': inputs,
            'source_sha256': source_sha256(), 'inference_source': source_identity(),
            'executable': executable_identity(), 'python': platform.python_version(),
            'git': _git_identity(), 'acceptance': acceptance}
    path = Path(out) / 'study-freeze-v1.json'
    ref = _write_once(path, body)
    _write_once(path.with_name('study-freeze-v1.receipt.json'), ref)
    return FrozenStudyRef(path, ref['sha256'], body['source_sha256'], body['executable']['sha256'])


def grant_for(freeze, phase, split, population, model_pair) -> AccessGrant:
    body = freeze.read()
    if body['inputs']['profile'] == 'study':
        if (body['acceptance']['reader'] != _accepted_qualification() or
                body['acceptance']['inference'] != _verify_calibration_attestation(body['acceptance']['inference'])):
            raise ValueError('frozen accepted qualification/calibration changed')
    elif 'unit_test_bundle' in body['inputs']:
        bundle = body['inputs']['unit_test_bundle']
        _verify_bundle_bytes(bundle['directory'], bundle['files'])
    if isinstance(population, PopulationSpec):
        if model_pair != body['inputs']['model_pair_sha256']:
            raise ValueError('frozen model pair mismatch')
        matches = [i for i in body['inputs']['populations'] if i['phase'] == phase and
                   i['split'] == split and i['spec'] == population.to_json()]
        if len(matches) != 1:
            raise ValueError('frozen population inventory mismatch')
        data_hash = canonical_hash(population.to_json())
        population_record = population.to_json()
        episode_ids = matches[0]['episode_ids']
    else:
        path = Path(population)
        data_hash = _sha(path.read_bytes())
        if data_hash != body['inputs'].get('beijing_manifest_sha256'):
            raise ValueError('Beijing manifest bytes changed')
        if (phase, split) != (('unit_test', 'test') if body['inputs']['profile'] == 'unit_test' else ('test', 'test')):
            raise ValueError('Beijing grant phase/split mismatch')
        if model_pair not in body['inputs'].get('real_model_commitments', {}).values():
            raise ValueError('real transfer model commitment mismatch')
        population_record = None
        episode_ids = body['inputs']['beijing_test_ids']
    grant = {'schema_version': 1, 'kind': 'famjet_poc_access', 'phase': phase,
             'split': split, 'source_sha256': freeze.source_sha256,
             'model_sha256': model_pair, 'data_sha256': data_hash,
             'population': population_record, 'episode_ids': episode_ids}
    path = freeze.path.parent.parent / 'grants' / (phase + '-' + data_hash + '-' + model_pair + '.json')
    if path.exists():
        if path.read_bytes() != canonical_json(grant):
            raise ValueError('existing grant bytes differ')
        ref = {'sha256': _sha(path.read_bytes())}
    else:
        ref = _write_once(path, grant)
    return AccessGrant(path, ref['sha256'], phase, split)


def admit_cell(out, allocation, started, *, tree_rss_bytes=None):
    if (type(allocation) is not dict or
            type(allocation.get('max_wall_seconds')) not in (int, float) or
            type(allocation.get('max_disk_bytes')) is not int):
        raise ValueError('finite protected cell allocation required')
    elapsed = time.monotonic() - started
    output_bytes = sum(path.stat().st_size for path in Path(out).rglob('*') if path.is_file())
    if elapsed >= allocation['max_wall_seconds']:
        raise RuntimeError('protected cell deadline exhausted')
    if output_bytes > allocation['max_disk_bytes']:
        raise RuntimeError('protected cell output allocation exhausted')
    if tree_rss_bytes is not None and tree_rss_bytes > allocation['max_rss_bytes']:
        raise RuntimeError('protected cell whole-tree RSS allocation exhausted')
    return {'elapsed_seconds': elapsed, 'output_bytes': output_bytes,
            'tree_rss_bytes': tree_rss_bytes}


def episode_count_records(episode):
    """Capture oracle support counts while the authorized Episode is in hand."""
    if episode.metadata.get('target_semantics') != 'observed_event_targets_v2':
        raise ValueError('counts require current observed-event targets')
    counts = np.asarray(episode.metadata['observed_counts'])
    queries = episode.queries
    regime = episode.metadata.get('regime')
    if regime is None and episode.metadata.get('preparation_version') == 'beijing_observed_v2_targets':
        regime = 'beijing_observed'
    if type(regime) is not str or not regime:
        raise ValueError('observed-count scoring regime missing')
    if len(queries.history_ids) != 1 or counts.shape[:2] != queries.T.shape:
        raise ValueError('per-query observed count layout mismatch')
    records = []
    for j in range(int(queries.lengths[0])):
        if not bool(queries.present[0, j]):
            continue
        observed = counts[0, j]
        if not np.issubdtype(observed.dtype, np.integer) or np.any(observed < 0):
            raise ValueError('observed counts must be nonnegative integers')
        records.append({'history_id': queries.history_ids[0],
                        'query_id': int(queries.query_ids[0, j]),
                        'task': queries.tasks[0][j],
                        'regime': regime,
                        'target_valid': bool(episode.metadata['target_valid'][0][j]),
                        'factual_supported': bool(episode.supported[0, j]),
                        'target': (episode.labels[0, j].tolist()
                                   if bool(episode.metadata['target_valid'][0][j]) else None),
                        'observed_counts': observed.tolist()})
    return records


def write_count_sidecar(records, manifest_hash, out):
    """One immutable history/query-keyed label-diagnostic inventory."""
    if not records or not _digest(manifest_hash):
        raise ValueError('nonempty bound observed-count inventory required')
    keys = [(item['history_id'], item['query_id']) for item in records]
    if len(keys) != len(set(keys)):
        raise ValueError('duplicate observed-count query')
    return _write_once(Path(out) / 'observed-counts.json',
                       {'schema_version': 1, 'kind': 'famjet_e4_observed_counts',
                        'manifest_hash': manifest_hash,
                        'target_semantics': 'observed_event_targets_v2',
                        'records': records})


def _read_bound_file(ref):
    if (type(ref) is not dict or set(ref) != {'path', 'sha256', 'bytes'} or
            not _digest(ref['sha256']) or type(ref['bytes']) is not int):
        raise ValueError('bound artifact reference schema mismatch')
    raw = Path(ref['path']).read_bytes()
    if len(raw) != ref['bytes'] or _sha(raw) != ref['sha256']:
        raise ValueError('bound artifact hash mismatch')
    return json.loads(raw)


def validate_scored_receipt(receipt, rows, manifest_hash, histories, query_ids):
    """Validate E3 score contract and all primary tasks against captured labels."""
    from .study import _diagnostic_score_policy
    contract = receipt.get('score_contract')
    if type(contract) is not dict or set(contract) != {'policy_ref', 'statistics_sha256'}:
        raise ValueError('score contract missing')
    policy = _read_bound_file(contract['policy_ref'])
    counts = _read_bound_file(receipt.get('counts_ref'))
    if (policy.get('manifest_hash') != manifest_hash or
            policy.get('version') != 2 or
            policy.get('primary_tasks') != ['mean', 'contrast'] or
            policy.get('task_weights') != {'mean': .5, 'contrast': .5} or
            policy.get('support_calibration') is not None or
            policy.get('full_inventory_hash') != canonical_hash(policy.get('full_inventory')) or
            policy.get('eligible_inventory_hash') != canonical_hash(policy.get('expected_inventory')) or
            counts.get('kind') != 'famjet_e4_observed_counts' or
            counts.get('manifest_hash') != manifest_hash or
            counts.get('target_semantics') != 'observed_event_targets_v2'):
        raise ValueError('frozen scoring/counts contract mismatch')
    records = counts.get('records')
    if type(records) is not list:
        raise ValueError('observed-count records missing')
    by_key = {(r['history_id'], r['query_id']): r for r in records}
    expected_keys = {(hid, qid) for hid in histories for qid in query_ids}
    if len(by_key) != len(records) or set(by_key) != expected_keys:
        raise ValueError('observed-count history/query inventory mismatch')
    full = {item['history_id']: item for item in policy['full_inventory']}
    eligible = {item['history_id']: item for item in policy['expected_inventory']}
    if set(full) != set(histories) or set(eligible) != set(histories):
        raise ValueError('score policy history inventory mismatch')
    regimes = {item['regime'] for item in records}
    if len(regimes) != 1 or policy.get('regime_weights') != {next(iter(regimes)): 1.}:
        raise ValueError('cell-local scoring regime weight mismatch')
    for hid in histories:
        collected = {task: [] for task in ('mean', 'contrast')}
        accepted = {task: [] for task in ('mean', 'contrast')}
        for qid in query_ids:
            item = by_key[(hid, qid)]
            if ((item['history_id'], item['query_id']) != (hid, qid) or
                    item['task'] not in collected or type(item['target_valid']) is not bool or
                    type(item['factual_supported']) is not bool or
                    not isinstance(item['observed_counts'], list) or
                    any(type(value) is not int or value < 0 for value in
                        np.asarray(item['observed_counts']).ravel().tolist())):
                raise ValueError('observed-count label diagnostics invalid')
            collected[item['task']].append(qid)
            if item['target_valid']:
                accepted[item['task']].append(qid)
        if any(not accepted[task] for task in accepted):
            raise ValueError('missing eligible primary task before release')
        if (full[hid]['tasks'] != collected or eligible[hid]['tasks'] != accepted or
                full[hid]['regime'] != eligible[hid]['regime'] or
                policy.get('eligible_counts', {}).get(hid) !=
                    {task: len(ids) for task, ids in accepted.items()} or
                any(by_key[(hid, qid)]['regime'] != full[hid]['regime'] for qid in query_ids)):
            raise ValueError('score policy/count sidecar inventory mismatch')
    diagnostic = _diagnostic_score_policy(policy)
    policies = {'primary': policy, 'ineligible_diagnostic': diagnostic}
    policy_hashes = {scope: canonical_hash(value) for scope, value in policies.items()}
    seen = set()
    primary = {(hid, task): 0 for hid in histories for task in ('mean', 'contrast')}
    for row in rows:
        key = (row['history_id'], row['query_id'])
        if key in seen or key not in by_key:
            raise ValueError('scored query identity duplicate/outside inventory')
        seen.add(key)
        captured = by_key[key]
        scope = 'primary' if captured['target_valid'] else 'ineligible_diagnostic'
        if (row.get('schema_version') != 2 or row.get('score_scope') != scope or
                row.get('replicate') != 0 or
                row.get('task') != captured['task'] or row.get('regime') != captured['regime'] or
                row.get('eligible') != captured['target_valid'] or
                row.get('factual_supported') != captured['factual_supported'] or
                row.get('target') != captured['target'] or
                row.get('target_semantics') != 'observed_event_targets_v2' or
                row.get('manifest_hash') != manifest_hash or
                row.get('statistics_hash') != contract['statistics_sha256'] or
                row.get('full_inventory_hash') != policy['full_inventory_hash'] or
                row.get('eligible_inventory_hash') != policy['eligible_inventory_hash'] or
                row.get('policy_hash') != policy_hashes[scope]):
            raise ValueError('scored row contract mismatch')
        if scope == 'primary':
            if type(row.get('loss')) not in (int, float) or not math.isfinite(row['loss']):
                raise ValueError('nonfinite primary loss before release')
            primary[(key[0], row['task'])] += 1
    if seen != expected_keys or any(value == 0 for value in primary.values()):
        raise ValueError('scored primary task/query inventory incomplete')
    if receipt.get('method') == 'laguerre' or any(row.get('method') == 'laguerre' for row in rows):
        from .comparators import validate_coordinate_audits
        validate_coordinate_audits(receipt.get('costs'), rows)
    return {'query_count': len(seen), 'history_count': len(histories),
            'counts_sha256': receipt['counts_ref']['sha256'],
            'policy_sha256': contract['policy_ref']['sha256']}


def evaluate_cell(freeze, cell, grant, out):
    """Run one frozen cell under a live whole-stage host resource guard."""
    if freeze.read()['inputs']['profile'] != 'study':
        return _evaluate_cell_body(freeze, cell, grant, out, None)
    from .resources import LiveStageGuard
    out = Path(out)
    out.mkdir(parents=True, exist_ok=False)
    live = LiveStageGuard(out, cell['allocation'], Path(out) / 'live-guard.json')
    with live:
        receipts = _evaluate_cell_body(freeze, cell, grant, out, live)
    for receipt in receipts:
        receipt['live_guard_ref'] = live.receipt_ref
    return receipts


def _evaluate_cell_body(freeze, cell, grant, out, live):
    """Use E3's complete evaluator after exact model and grant admission."""
    from .data import generate_episode
    from .models import load_model
    from .study import evaluate_panel, freeze_score_policy
    from .comparators import build_controls
    from .transfer import evaluate_equivalent_control
    cell_started = time.monotonic()
    body = freeze.read()
    if body['inputs']['profile'] == 'study':
        resource_policy = body['inputs']['resource_policy']
        if time.time() >= resource_policy['start_epoch_seconds'] + resource_policy['global_wall_seconds']:
            raise RuntimeError('frozen whole-study deadline expired')
        template = body['inputs']['protected_cell_allocation_template']
        allocation = cell['allocation']
        if (cell['worker_limits'] != body['inputs']['worker_limits'] or
                allocation.get('phase') != cell['phase'] or
                allocation.get('manifest_sha256') != freeze.sha256 or
                allocation.get('allocation_id') != 'e4-' + cell['cell_id'] or
                any(allocation.get(key) != value for key, value in template.items())):
            raise ValueError('protected cell resource/worker allocation differs from freeze')
    spec = PopulationSpec.from_json(cell['spec'])
    if cell['episode_ids'] not in [i['episode_ids'] for i in body['inputs']['populations'] if i['spec'] == cell['spec']]:
        raise ValueError('cell history inventory mismatch')
    if type(cell.get('models')) is not dict or set(cell['models']) != {'jet', 'bank'}:
        raise ValueError('frozen Jet/Bank checkpoint pair required')
    if (body['inputs']['profile'] == 'study' and
            cell['models'] != body['inputs']['selected_models']):
        raise ValueError('cell model references differ from frozen selected pair')
    verified_pair = canonical_hash({name: cell['models'][name]['sha256']
                                    for name in ('jet', 'bank')})
    if verified_pair != body['inputs']['model_pair_sha256']:
        raise ValueError('actual cell model pair differs from frozen commitment')
    selected = {name: load_model(Path(ref['path']), ref['sha256'])
                for name, ref in cell['models'].items()}
    if any(model.shape != spec.shape or model.spec.family != name
           for name, model in selected.items()):
        raise ValueError('protected model checkpoint shape/family mismatch')
    grant.verify(source_sha256=freeze.source_sha256, data_sha256=canonical_hash(spec.to_json()),
                 model_sha256=verified_pair, population=spec)
    captured_counts = []
    def factory(capture=False):
        for history_id in cell['episode_ids']:
            if live is not None:
                live.check()
            freeze.read()
            grant.verify(source_sha256=freeze.source_sha256, data_sha256=canonical_hash(spec.to_json()),
                         model_sha256=verified_pair, population=spec,
                         episode_id=history_id)
            episode = generate_episode(spec, history_id,
                                       grant=None if spec.namespace == 'unit_test' else grant)
            if capture:
                captured_counts.extend(episode_count_records(episode))
            yield episode
    policy = freeze_score_policy(factory(capture=True), manifest_hash=freeze.sha256)
    policy_ref = _write_once(Path(out) / 'score-policy.json', policy)
    counts_ref = write_count_sidecar(captured_counts, freeze.sha256, out)
    from .pipeline import observe_resources
    def tree_rss():
        return (observe_resources(freeze.path.parent.parent)['tree_rss_bytes']
                if body['inputs']['profile'] == 'study' else None)
    admit_cell(out, cell['allocation'], cell_started,
               tree_rss_bytes=tree_rss())
    budget = 9345 if spec.shape.to_json() == {'key_dim': 16, 'value_dim': 8} else 1665
    controls = build_controls(spec.shape, budget, selected['jet'].target_statistics,
                              body['inputs'].get('control_seed', 2026102401906))
    methods = {**selected, **{name: item['method'] for name, item in controls.items()},
               'laguerre': selected['jet']}
    receipts = []
    for method, model in methods.items():
        if live is not None:
            live.check()
        admit_cell(out, cell['allocation'], cell_started,
                   tree_rss_bytes=tree_rss())
        statistics = selected['jet'].target_statistics
        if method == 'laguerre':
            result = evaluate_equivalent_control(model, factory, policy,
                       statistics, Path(out) / method, cell['allocation'],
                       cell['worker_limits'])
        else:
            result = evaluate_panel(model, factory, policy, statistics, method,
                                    Path(out) / method, cell['allocation'], cell['worker_limits'])
        cell_admission = admit_cell(out, cell['allocation'], cell_started,
                   tree_rss_bytes=tree_rss())
        if live is not None:
            live.check()
        receipts.append({'run_id': cell['cell_id'] + '-' + method, 'phase': cell['phase'],
                         'cell_id': cell['cell_id'], 'method': method,
                         'history_ids': cell['episode_ids'], 'rows_ref': result['rows_ref'],
                         'rows_sha256': result['rows_ref']['sha256'],
                         'status': 'completed', 'freeze_sha256': freeze.sha256,
                         'grant_path': str(grant.manifest_path),
                         'grant_sha256': grant.manifest_sha256,
                         'source_sha256': freeze.source_sha256,
                         'model_sha256': verified_pair,
                         'data_sha256': canonical_hash(spec.to_json()),
                         'expected_query_ids': list(range(spec.queries_per_history)),
                         'score_contract': {'policy_ref': policy_ref,
                                            'statistics_sha256': canonical_hash(statistics)},
                         'counts_ref': counts_ref,
                         'resource_receipt': result['admission'],
                         'resource_receipt_sha256': canonical_hash(result['admission']),
                         'cell_admission': cell_admission,
                         'cell_admission_sha256': canonical_hash(cell_admission),
                         'summary': result['summary'], 'costs': result['costs']})
    return receipts


@dataclass(frozen=True)
class ReleaseRef:
    path: Path
    sha256: str


def _receipt_rows(receipt):
    if 'rows_ref' in receipt:
        from .study import load_score_rows
        return load_score_rows(receipt['rows_ref'])
    raw = Path(receipt['rows_path']).read_bytes()
    if _sha(raw) != receipt['rows_sha256']:
        raise ValueError('row hash mismatch')
    return json.loads(raw)


def _verify_receipt_bytes(receipt):
    if 'rows_ref' in receipt:
        ref = receipt['rows_ref']
        raw = Path(ref['path']).read_bytes()
        if len(raw) != ref['bytes'] or _sha(raw) != ref['sha256']:
            raise ValueError('row hash mismatch')
    else:
        raw = Path(receipt['rows_path']).read_bytes()
        if _sha(raw) != receipt['rows_sha256']:
            raise ValueError('row hash mismatch')
    if 'score_contract' in receipt or 'counts_ref' in receipt:
        _read_bound_file(receipt['score_contract']['policy_ref'])
        _read_bound_file(receipt['counts_ref'])
    if 'live_guard_ref' in receipt:
        live = _read_bound_file(receipt['live_guard_ref'])
        if live.get('status') != 'completed' or live.get('violation') is not None:
            raise ValueError('released live resource guard failed')


def seal_release(freeze, receipts, out, *, expected_methods=('jet', 'bank')) -> ReleaseRef:
    body = freeze.read()
    if type(receipts) is not list or not receipts or not expected_methods or len(set(expected_methods)) != len(expected_methods):
        raise ValueError('complete release methods required')
    if (body['inputs']['profile'] == 'study' and
            tuple(body['inputs'].get('expected_methods', ())) != tuple(expected_methods)):
        raise ValueError('scientific release method inventory differs from freeze')
    planned = {(i['phase'], i.get('cell_id', canonical_hash(i['spec'])), method): set(i['episode_ids'])
               for i in body['inputs']['populations'] for method in expected_methods}
    declared = []
    for receipt in receipts:
        phase, cell, method = receipt.get('phase'), receipt.get('cell_id'), receipt.get('method')
        if cell is None:
            matching = [key for key, ids in planned.items()
                        if key[0] == phase and key[2] == method and
                        ids == set(receipt.get('history_ids', []))]
            if len(matching) != 1:
                raise ValueError('release declared cell inventory mismatch')
            declared.append(matching[0])
        else:
            declared.append((phase, cell, method))
    if len(declared) != len(planned) or len(set(declared)) != len(declared) or set(declared) != set(planned):
        raise ValueError('complete cell/method declaration required before scoring release')
    expected_statistics_sha256 = None
    if body['inputs']['profile'] == 'study':
        from .models import load_model
        selected_jet = body['inputs']['selected_models']['jet']
        expected_statistics_sha256 = canonical_hash(
            load_model(Path(selected_jet['path']), selected_jet['sha256']).target_statistics)
    actual = {}
    for receipt in receipts:
        if receipt.get('status') != 'completed' or receipt.get('freeze_sha256') != freeze.sha256:
            raise ValueError('incomplete or mismatched run receipt')
        phase = receipt['phase']
        cell = receipt.get('cell_id')
        if cell is None:
            matching = [k for k, ids in planned.items() if k[0] == phase and k[2] == receipt['method'] and ids == set(receipt['history_ids'])]
            if len(matching) != 1:
                raise ValueError('run cell inventory mismatch')
            key = matching[0]
        else:
            key = (phase, cell, receipt['method'])
        if key in actual or key not in planned or set(receipt['history_ids']) != planned[key]:
            raise ValueError('duplicate/missing run inventory')
        if body['inputs']['profile'] == 'study':
            spec_record = next(item for item in body['inputs']['populations']
                               if (item['phase'], item['cell_id']) == key[:2])
            spec = PopulationSpec.from_json(spec_record['spec'])
            if (receipt.get('source_sha256') != freeze.source_sha256 or
                    receipt.get('model_sha256') != body['inputs']['model_pair_sha256'] or
                    receipt.get('data_sha256') != canonical_hash(spec.to_json()) or
                    receipt.get('expected_query_ids') != list(range(spec.queries_per_history)) or
                    receipt.get('rows_sha256') != receipt.get('rows_ref', {}).get('sha256') or
                    receipt.get('resource_receipt_sha256') != canonical_hash(receipt.get('resource_receipt')) or
                    receipt.get('cell_admission_sha256') != canonical_hash(receipt.get('cell_admission'))):
                raise ValueError('scientific run source/model/data/query/resource commitment mismatch')
            if receipt.get('score_contract', {}).get('statistics_sha256') != expected_statistics_sha256:
                raise ValueError('scientific score statistics differ from frozen selected Jet')
            bound_grant = AccessGrant(Path(receipt['grant_path']), receipt['grant_sha256'],
                                      phase, phase)
            bound_grant.verify(source_sha256=freeze.source_sha256,
                               data_sha256=canonical_hash(spec.to_json()),
                               model_sha256=body['inputs']['model_pair_sha256'],
                               population=spec)
            live = _read_bound_file(receipt.get('live_guard_ref'))
            if (live.get('kind') != 'famjet_e4_live_stage_guard' or
                    live.get('status') != 'completed' or live.get('violation') is not None or
                    live.get('allocation', {}).get('manifest_sha256') != freeze.sha256 or
                    live['allocation'].get('allocation_id') != 'e4-' + key[1] or
                    any(live['allocation'].get(name) != value for name, value in
                        body['inputs']['protected_cell_allocation_template'].items())):
                raise ValueError('protected live resource guard incomplete')
        rows = _receipt_rows(receipt)
        if {r['history_id'] for r in rows} != planned[key] or any(r['method'] != receipt['method'] for r in rows):
            raise ValueError('incomplete scored history/method inventory')
        if body['inputs']['profile'] == 'study' or 'score_contract' in receipt or 'counts_ref' in receipt:
            spec_record = next(item for item in body['inputs']['populations']
                               if (item['phase'], item.get('cell_id', canonical_hash(item['spec']))) == key[:2])
            spec = PopulationSpec.from_json(spec_record['spec'])
            validate_scored_receipt(receipt, rows, freeze.sha256,
                                    spec_record['episode_ids'],
                                    list(range(spec.queries_per_history)))
        if body['inputs']['profile'] == 'study':
            for hid in planned[key]:
                if sorted(r['query_id'] for r in rows if r['history_id'] == hid) != receipt['expected_query_ids']:
                    raise ValueError('incomplete scientific query inventory')
        actual[key] = receipt
    if actual.keys() != planned.keys():
        raise ValueError('missing method or cell in release')
    if body['inputs']['profile'] == 'study' or any('counts_ref' in item for item in receipts):
        by_cell = {}
        for key, receipt in actual.items():
            by_cell.setdefault(key[:2], set()).add(receipt['counts_ref']['sha256'])
        if any(len(hashes) != 1 for hashes in by_cell.values()):
            raise ValueError('method observed-count sidecars differ within cell')
    release = {'schema_version': 1, 'kind': 'famjet_e4_complete_release',
               'freeze_path': str(freeze.path), 'freeze_sha256': freeze.sha256,
               'expected_methods': list(expected_methods), 'receipts': receipts,
               'expected_cells': len(planned), 'status': 'complete'}
    path = Path(out) / 'release.json'
    ref = _write_once(path, release)
    return ReleaseRef(path, ref['sha256'])


def read_released_rows(release, *, methods=None):
    """Yield verified row files one at a time after sealed inventory closure."""
    raw = release.path.read_bytes()
    if _sha(raw) != release.sha256:
        raise ValueError('release hash mismatch')
    body = json.loads(raw)
    freeze_raw = Path(body['freeze_path']).read_bytes()
    if _sha(freeze_raw) != body['freeze_sha256']:
        raise ValueError('release freeze hash mismatch')
    frozen = json.loads(freeze_raw)
    freeze = FrozenStudyRef(Path(body['freeze_path']), body['freeze_sha256'],
                            frozen['source_sha256'], frozen['executable']['sha256'])
    freeze.read()
    if body.get('kind') != 'famjet_e4_complete_release' or body.get('status') != 'complete':
        raise ValueError('release schema/status mismatch')
    if len(body['receipts']) != body['expected_cells']:
        raise ValueError('release cell count mismatch')
    if methods is not None and (type(methods) not in (tuple, list, set) or
                                not set(methods) <= set(body['expected_methods'])):
        raise ValueError('unknown released method filter')
    for receipt in body['receipts']:
        _verify_receipt_bytes(receipt)
    def verified_rows():
        emitted = False
        for receipt in body['receipts']:
            if methods is not None and receipt['method'] not in methods:
                continue
            for row in _receipt_rows(receipt):
                emitted = True
                yield row
        if not emitted:
            raise ValueError('release has empty rows')
    return verified_rows()


def read_released_counts(release):
    """Stream each cell's hash-verified per-query oracle count sidecar once."""
    read_released_rows(release)
    body = json.loads(release.path.read_bytes())
    def records():
        seen = set()
        for receipt in body['receipts']:
            ref = receipt.get('counts_ref')
            if ref is None or ref['sha256'] in seen:
                continue
            seen.add(ref['sha256'])
            for record in _read_bound_file(ref)['records']:
                yield record
    return records()


def infer_release(freeze, release, phase):
    """Unblind complete paired history means only after a sealed release."""
    from .inference import STRATA, conditional_interval, validate_history_pairs
    if phase not in {'unit_test', 'confirmation', 'replication'}:
        raise ValueError('only complete scientific panels admit inference')
    frozen = freeze.read()
    rows = read_released_rows(release, methods=('jet', 'bank'))
    populations = [item for item in frozen['inputs']['populations'] if item['phase'] == phase]
    if not populations:
        raise ValueError('panel missing from freeze')
    if phase != 'unit_test':
        by_stratum = {f"{item['spec']['lengths'][0]}:{item['spec']['regimes'][0]}": item
                      for item in populations}
        if set(by_stratum) != set(STRATA):
            raise ValueError('scientific stratum inventory mismatch')
        populations = [by_stratum[name] for name in STRATA]
    ids_by_stratum = {str(i): item['episode_ids'] for i, item in enumerate(populations)}
    expected = {hid: stratum for stratum, ids in ids_by_stratum.items() for hid in ids}
    grouped = {}
    for row in rows:
        hid = row.get('history_id')
        if hid not in expected or row.get('method') not in {'jet', 'bank'} or row.get('score_scope') != 'primary':
            continue
        task = row.get('task')
        loss = row.get('loss')
        if task not in {'mean', 'contrast'} or type(loss) not in (float, int) or not math.isfinite(loss):
            raise ValueError('primary paired loss incomplete/nonfinite')
        grouped.setdefault((hid, row['method'], task), []).append(float(loss))
    paired = []
    for stratum, ids in ids_by_stratum.items():
        for hid in ids:
            values = {}
            for method in ('jet', 'bank'):
                tasks = []
                for task in ('mean', 'contrast'):
                    losses = grouped.get((hid, method, task))
                    if not losses:
                        raise ValueError('missing paired primary task')
                    tasks.append(sum(losses) / len(losses))
                values[method] = sum(tasks) / 2
            paired.append({'history_id': hid, 'stratum': int(stratum),
                           'jet_loss': values['jet'], 'bank_loss': values['bank'],
                           'units': 'history'})
    manifest = {'panel': phase, 'units': 'history',
                'history_ids_by_stratum': ids_by_stratum,
                'weights': [1 / len(ids_by_stratum)] * len(ids_by_stratum)}
    if phase != 'unit_test':
        calibration = frozen['acceptance']['inference']
        manifest.update(strata=list(STRATA), attempt=calibration['attempt'],
                        per_cell=calibration['per_cell'],
                        source_sha256=calibration['source_sha256'],
                        calibration_evidence_sha256=calibration['evidence_sha256'])
    differences, strata = validate_history_pairs(paired, manifest)
    result = conditional_interval(differences, strata, weights=manifest['weights'])
    return {**result, 'panel': phase, 'paired_history_count': len(paired),
            'release_sha256': release.sha256, 'manifest': manifest}
