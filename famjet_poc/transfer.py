"""Shape-matched Beijing transfer with training-only fit and native-unit audit."""
from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
import time

import numpy as np

from famjet.provenance import canonical_hash, canonical_json
from .contracts import ShapeSpec, ReaderSpec
from .data import invert_normalized_prediction, iter_beijing
from .protected import _write_once


def native_rows(rows, normalization):
    """Preserve standardized scoring rows and add correctly inverted native values."""
    converted = []
    for row in rows:
        if row.get('task') not in {'mean', 'contrast', 'latest'}:
            converted.append({**row, 'native_status': 'unsupported_task',
                              'native_prediction': None, 'native_target': None})
            continue
        if row.get('prediction') is None or row.get('target') is None:
            converted.append({**row, 'native_status': 'undefined_target_or_prediction',
                              'native_prediction': None, 'native_target': None})
            continue
        prediction = invert_normalized_prediction(row['prediction'], row['task'], normalization)
        target = invert_normalized_prediction(row['target'], row['task'], normalization)
        error = prediction - target
        converted.append({**row, 'native_status': 'ok',
                          'native_prediction': prediction.tolist(), 'native_target': target.tolist(),
                          'native_unit': 'micrograms_per_cubic_meter',
                          'native_mse_micrograms2': float(np.mean(error * error)),
                          'native_mae_micrograms': float(np.mean(np.abs(error)))})
    return converted


def real_scoring_statistics(manifest):
    """Use the same Beijing training-only priors for both transfer modes."""
    from famjet.data import beijing as beijing_core
    metadata = beijing_core._verify_manifest(Path(manifest))
    statistics = metadata.get('training_target_statistics')
    if (type(statistics) is not dict or statistics.get('schema_version') != 2 or
            statistics.get('split') != 'training' or
            statistics.get('target_semantics') != 'observed_event_targets_v2' or
            set(statistics.get('tasks', {})) != {'mean', 'contrast'}):
        raise ValueError('Beijing training-only score statistics missing')
    return statistics


def block_sensitivity(released_rows, clusters):
    """Descriptive cluster means; every query/station in a block moves together."""
    if not isinstance(released_rows, (list, tuple)) or not released_rows:
        raise ValueError('nonempty released rows required')
    if type(clusters) is not dict or set(clusters) != {'28d', '56d'}:
        raise ValueError('28d and 56d cluster inventory required')
    result = {}
    for window in ('28d', '56d'):
        field = 'cluster_' + window
        by_block = {}
        losses_by_block = {}
        for row in released_rows:
            hid, cluster, loss = row.get('history_id'), row.get(field), row.get('loss')
            if not isinstance(hid, str) or not isinstance(cluster, str) or not cluster or type(loss) not in (int, float) or not math.isfinite(loss):
                raise ValueError('finite block loss and cluster required')
            if hid in by_block and by_block[hid] != cluster:
                raise ValueError('stations in block cannot split across clusters')
            by_block[hid] = cluster
            losses_by_block.setdefault(hid, []).append(float(loss))
        by_cluster = {}
        for hid, values in losses_by_block.items():
            by_cluster.setdefault(by_block[hid], []).append(sum(values) / len(values))
        expected = clusters[window]
        if type(expected) is not int or expected <= 0 or len(by_cluster) != expected:
            raise ValueError('cluster count mismatch')
        keys = sorted(by_cluster)
        rng = np.random.Generator(np.random.PCG64(2026102401911 + int(window[:2])))
        resampled = []
        for _ in range(2048):
            selected = rng.integers(0, len(keys), size=len(keys))
            block_values = [value for index in selected for value in by_cluster[keys[int(index)]]]
            resampled.append(sum(block_values) / len(block_values))
        result[window] = {'scope': 'finite_period_descriptive', 'cluster_count': len(by_cluster),
                          'block_count': len(by_block),
                          'cluster_means': {key: sum(vals) / len(vals) for key, vals in sorted(by_cluster.items())},
                          'cluster_block_counts': {key: len(vals) for key, vals in sorted(by_cluster.items())},
                          'block_resample_draws': len(resampled),
                          'resampled_mean_95pct': [float(np.quantile(resampled, .025)),
                                                   float(np.quantile(resampled, .975))],
                          'population_claim': 'none_finite_period_only'}
    return result


def evaluate_equivalent_control(model, factory, policy, statistics, out, allocation, worker_limits):
    """Pinned E3 Laguerre path; reference validation time is not deployment latency."""
    from .cache import e3_source_sha256
    from .models import RidgeMemoryModel
    from .study import _admit, _evaluate, persist_score_rows
    if type(model) is not RidgeMemoryModel or model.spec.family != 'jet':
        raise ValueError('base frozen Jet reader required for equivalent control')
    if e3_source_sha256() != 'bbd4772c341de2b1b25d63dae195b3a2a3f2456dbe3f79af76ed31726dada39e':
        raise ValueError('pinned E3 equivalent evaluator source changed')
    if (type(policy) is not dict or type(allocation) is not dict or
            allocation.get('manifest_sha256') != policy.get('manifest_hash') or
            allocation.get('phase') not in {'unit_test', 'development', 'pilot', 'confirmation', 'replication', 'test'}):
        raise ValueError('equivalent control allocation/inventory mismatch')
    if not callable(factory):
        raise ValueError('replayable equivalent Episode factory required')
    out = Path(out)
    out.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    rows, summary, costs = _evaluate(model, factory, policy, statistics, 'laguerre',
                                      worker_limits, out, started, allocation,
                                      equivalent=True)
    remaining = int(_admit(started, allocation, directory=out)['remaining_disk_bytes'])
    ref = persist_score_rows(rows, out / 'laguerre-rows.json', max_bytes=remaining)
    reference_seconds = sum(item['coordinate_seconds'] + item['conversion_seconds']
                            for item in costs['stream_audits'].values())
    costs = {**costs, 'diagnostic_reference_validation_seconds': reference_seconds,
             'deployable_ingestion_seconds': None,
             'deployment_latency_status': 'unmeasured_reference_validation_entangled',
             'equivalent_role': 'state_prediction_parity_diagnostic'}
    return {'schema_version': 1, 'method': 'laguerre', 'rows_ref': ref,
            'summary': summary, 'costs': costs,
            'full_inventory_hash': policy['full_inventory_hash'],
            'eligible_inventory_hash': policy['eligible_inventory_hash'],
            'statistics_sha256': canonical_hash(statistics),
            'e3_source_sha256': e3_source_sha256(),
            'admission': _admit(started, allocation, directory=out)}


@dataclass(frozen=True)
class ModeRefs:
    path: Path
    sha256: str

    def read(self):
        raw = self.path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != self.sha256:
            raise ValueError('transfer mode manifest hash mismatch')
        return json.loads(raw)


@dataclass(frozen=True)
class PrefreezeTransferInputs:
    """Public selections and finite resources, created before a study freeze."""
    synthetic_k12_selected: dict
    allocation: dict
    worker_limits: dict
    cache_max_bytes: int
    beijing_manifest_sha256: str

    def __post_init__(self):
        allocation_fields = {'schema_version', 'phase', 'manifest_sha256', 'allocation_id',
                             'max_wall_seconds', 'max_disk_bytes', 'max_rss_bytes'}
        worker_fields = {'max_frame_bytes', 'max_array_bytes', 'max_histories'}
        if (set(self.synthetic_k12_selected) != {'jet', 'bank'} or
                type(self.cache_max_bytes) is not int or self.cache_max_bytes <= 0 or
                type(self.beijing_manifest_sha256) is not str or len(self.beijing_manifest_sha256) != 64 or
                type(self.allocation) is not dict or set(self.allocation) != allocation_fields or
                self.allocation['schema_version'] != 1 or self.allocation['phase'] != 'development' or
                self.allocation['manifest_sha256'] != self.beijing_manifest_sha256 or
                type(self.allocation['max_wall_seconds']) not in (int, float) or
                not math.isfinite(self.allocation['max_wall_seconds']) or
                self.allocation['max_wall_seconds'] <= 0 or
                any(type(self.allocation[key]) is not int or self.allocation[key] <= 0
                    for key in ('max_disk_bytes', 'max_rss_bytes')) or
                type(self.worker_limits) is not dict or set(self.worker_limits) != worker_fields or
                any(type(value) is not int or value <= 0 for value in self.worker_limits.values()) or
                self.worker_limits['max_histories'] > 64):
            raise ValueError('complete pre-freeze transfer inputs/allocation required')


def load_bound_modes(ref: ModeRefs, freeze):
    """Read weights only after the immutable freeze binds the mode artifact."""
    from .cache import e3_source_sha256
    body = freeze.read()
    if body['inputs'].get('transfer_modes_sha256') != ref.sha256:
        raise ValueError('transfer mode SHA absent from freeze')
    modes = ref.read()
    if (modes['beijing_manifest_sha256'] != body['inputs'].get('beijing_manifest_sha256') or
            modes.get('transfer_source_sha256') != hashlib.sha256(Path(__file__).read_bytes()).hexdigest() or
            modes.get('e3_source_sha256') != e3_source_sha256()):
        raise ValueError('Beijing manifest/transfer freeze mismatch')
    verify_prefreeze_cache_entries(modes['training_cache'])
    verify_prefreeze_cache_entries(modes['development_cache'])
    return modes


def _cached_factory(episodes, out, max_bytes):
    """Content-verified Episode records; each iteration restores owned tensor copies."""
    from .cache import _record, _restore
    from .models import _episode_digest
    out = Path(out)
    out.mkdir(parents=True, exist_ok=False)
    entries = []
    total = 0
    for ep in episodes:
        if len(ep.events.history_ids) != 1:
            raise ValueError('Beijing block must contain one history')
        raw = canonical_json(_record(ep))
        total += len(raw)
        if total > max_bytes:
            raise MemoryError('Beijing replay cache allocation exceeded')
        path = out / (str(len(entries)).zfill(3) + '.json')
        path.write_bytes(raw)
        entries.append({'path': str(path), 'sha256': hashlib.sha256(raw).hexdigest(),
                        'bytes': len(raw), 'history_id': ep.events.history_ids[0],
                        'episode_digest': _episode_digest(ep)})
    if not entries:
        raise ValueError('empty Beijing training/development split')
    def factory():
        for item in entries:
            raw = Path(item['path']).read_bytes()
            if len(raw) != item['bytes'] or hashlib.sha256(raw).hexdigest() != item['sha256']:
                raise ValueError('Beijing replay cache hash mismatch')
            ep = _restore(json.loads(raw))
            if _episode_digest(ep) != item['episode_digest']:
                raise ValueError('Beijing replay episode changed')
            yield ep
    return factory, entries, total


def verify_prefreeze_cache_entries(entries):
    if type(entries) is not list or not entries:
        raise ValueError('prefreeze episode cache inventory missing')
    total = 0
    ids = set()
    for item in entries:
        if (type(item) is not dict or set(item) != {'path', 'sha256', 'bytes',
                 'history_id', 'episode_digest'} or type(item['history_id']) is not str or
                item['history_id'] in ids or type(item['bytes']) is not int or item['bytes'] <= 0):
            raise ValueError('prefreeze episode cache entry invalid')
        ids.add(item['history_id'])
        path = Path(item['path'])
        if path.is_symlink() or not path.is_file():
            raise ValueError('prefreeze episode cache path invalid')
        raw = path.read_bytes()
        if len(raw) != item['bytes'] or hashlib.sha256(raw).hexdigest() != item['sha256']:
            raise ValueError('prefreeze episode cache hash mismatch')
        total += len(raw)
    return total


def admit_real_output(out, allocation):
    maximum = allocation.get('max_disk_bytes') if type(allocation) is dict else None
    if type(maximum) is not int or maximum <= 0:
        raise ValueError('finite real output allocation required')
    used = sum(path.stat().st_size for path in Path(out).rglob('*') if path.is_file())
    if used > maximum:
        raise RuntimeError('real mode output allocation exceeded')
    return {'output_bytes': used, 'maximum_output_bytes': maximum}


def fit_transfer_modes(inputs: PrefreezeTransferInputs, beijing_manifest, out) -> ModeRefs:
    """Fit/tune K12/V1 models on public blocks; test is never iterated here."""
    from .models import build_model, fit_reader, fit_training_metadata, load_model, make_fit_manifest, save_model
    from .study import evaluate_panel, freeze_score_policy, select_candidate
    from .cache import e3_source_sha256
    if type(inputs) is not PrefreezeTransferInputs:
        raise ValueError('typed pre-freeze transfer inputs required; frozen studies cannot create weights')
    transfer = {'synthetic_k12_selected': inputs.synthetic_k12_selected,
                'allocation': inputs.allocation, 'worker_limits': inputs.worker_limits,
                'cache_max_bytes': inputs.cache_max_bytes}
    manifest = Path(beijing_manifest)
    raw = manifest.read_bytes()
    manifest_sha = hashlib.sha256(raw).hexdigest()
    if inputs.beijing_manifest_sha256 != manifest_sha:
        raise ValueError('Beijing manifest commitment mismatch')
    out = Path(out)
    out.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    def guard():
        from .pipeline import observe_resources
        elapsed = time.monotonic() - started
        output_bytes = sum(path.stat().st_size for path in out.rglob('*') if path.is_file())
        whole_tree_rss = observe_resources(out)['tree_rss_bytes']
        if (elapsed >= inputs.allocation['max_wall_seconds'] or
                output_bytes > inputs.allocation['max_disk_bytes'] or
                whole_tree_rss > inputs.allocation['max_rss_bytes']):
            raise RuntimeError('real transfer fit allocation exhausted')
        return {'elapsed_seconds': elapsed, 'output_bytes': output_bytes,
                'whole_tree_rss_bytes': whole_tree_rss}
    guard()
    maximum = transfer['cache_max_bytes']
    if type(maximum) is not int or maximum <= 0:
        raise ValueError('positive Beijing replay cache cap required')
    training, train_entries, train_bytes = _cached_factory(iter_beijing(manifest, 'training'), out / 'train-cache', maximum)
    guard()
    development, dev_entries, dev_bytes = _cached_factory(iter_beijing(manifest, 'development_fit'),
                                                            out / 'dev-cache', maximum - train_bytes)
    guard()
    meta = fit_training_metadata(training)
    shape = ShapeSpec(12, 1)
    frozen_refs = {}
    for family, selected in transfer['synthetic_k12_selected'].items():
        if family not in {'jet', 'bank'}:
            raise ValueError('unknown synthetic transfer family')
        model = load_model(Path(selected['path']), selected['sha256'])
        if model.shape != shape or model.spec.family != family:
            raise ValueError('cross-shape synthetic checkpoint rejected')
        frozen_refs[family] = selected
    if set(frozen_refs) != {'jet', 'bank'}:
        raise ValueError('both K12 synthetic families required')
    policy = freeze_score_policy(development(), manifest_hash=manifest_sha)
    ledger = []
    for family in ('jet', 'bank'):
        # The real-data adaptation grid remains fixed to the E3 public 18 candidates.
        from .study import study_manifest
        config = {'profile': 'unit_test', 'shape': shape.to_json(),
                  'training_seed': 1, 'development_seed': 2, 'max_query_attempts': 64,
                  'cache_limits': {'disk_bytes': 1, 'lru_bytes': 1},
                  'worker_limits': transfer['worker_limits']}
        candidates = [c for c in study_manifest(config)['candidates'] if c['family'] == family]
        for candidate in candidates:
            guard()
            spec = ReaderSpec.from_json(candidate['reader'])
            model = build_model(shape, spec, meta['t_ref'], meta['target_statistics'])
            fit = fit_reader(model, training, make_fit_manifest(model, meta))
            ref = save_model(model, out / 'models' / (candidate['config_hash'] + '.json'))
            allocation = dict(transfer['allocation'])
            allocation['manifest_sha256'] = manifest_sha
            item = evaluate_panel(model, development, policy, meta['target_statistics'],
                                  candidate['config_hash'], out / 'development' / candidate['config_hash'],
                                  allocation, transfer['worker_limits'])
            ledger.append({'family': family, 'config_hash': candidate['config_hash'],
                           'reader': candidate['reader'], 'status': 'qualified' if item['summary']['status'] == 'ok' else 'failed',
                           'loss': item['summary']['loss'], 'active_static_bytes': model.parameter_nbytes(),
                           'fit_ref': {'path': str(ref.path), 'sha256': ref.sha256},
                           'fit_objective': fit.objective, 'rows_ref': item['rows_ref'],
                           'costs': item['costs']})
            guard()
    selected_real = {}
    for family in ('jet', 'bank'):
        winner = select_candidate([item for item in ledger if item['family'] == family])
        selected_real[family] = winner['fit_ref']
    body = {'schema_version': 1, 'kind': 'famjet_e4_transfer_modes',
            'prefreeze': True, 'beijing_manifest_sha256': manifest_sha,
            'transfer_source_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'e3_source_sha256': e3_source_sha256(), 'shape': shape.to_json(),
            'normalization': json.loads(raw)['normalization'],
            'synthetic_frozen': frozen_refs, 'task_adapted': selected_real,
            'real_development_ledger': ledger,
            'training_cache': train_entries, 'development_cache': dev_entries,
            'cache_bytes': train_bytes + dev_bytes, 'elapsed_seconds': time.monotonic() - started,
            'test_accessed': False, 'final_allocation': guard()}
    ref = _write_once(out / 'transfer-modes.json', body)
    return ModeRefs(Path(ref['path']), ref['sha256'])


def evaluate_real_mode(mode, grant, out):
    """Open exactly the 56 committed test blocks after exact model-bound grant."""
    from .models import load_model
    from .study import evaluate_panel, freeze_score_policy, load_score_rows, persist_score_rows
    from .comparators import build_controls
    from .protected import FrozenStudyRef
    if type(mode) is not dict or not {'mode_name', 'modes_ref', 'family', 'manifest', 'allocation', 'worker_limits'} <= set(mode):
        raise ValueError('frozen real mode descriptor required')
    method = mode['family']
    allowed = {'jet', 'bank', 'exact', 'recent', 'latest_lru', 'reservoir', 'buckets', 'laguerre'}
    if mode['mode_name'] not in {'synthetic_frozen', 'task_adapted'} or method not in allowed:
        raise ValueError('unknown real transfer mode/method')
    freeze = FrozenStudyRef(Path(mode['freeze_path']), mode['freeze_sha256'],
                            mode['source_sha256'], mode['executable_sha256'])
    frozen = freeze.read()
    if frozen['inputs']['profile'] == 'study':
        template = frozen['inputs']['real_method_allocation_template']
        allocation = mode['allocation']
        master = frozen['inputs']['resource_policy']
        if (time.time() >= master['start_epoch_seconds'] + master['global_wall_seconds'] or
                mode['worker_limits'] != frozen['inputs']['worker_limits'] or
                allocation.get('phase') != 'test' or
                allocation.get('manifest_sha256') != frozen['inputs']['beijing_manifest_sha256'] or
                allocation.get('allocation_id') != 'e4-beijing-' + mode['mode_name'] + '-' + method or
                any(allocation.get(key) != value for key, value in template.items())):
            raise ValueError('real mode resource/worker allocation differs from freeze or deadline expired')
    refs = load_bound_modes(ModeRefs(Path(mode['modes_ref']['path']),
                                    mode['modes_ref']['sha256']), freeze)
    manifest = Path(mode['manifest'])
    raw = manifest.read_bytes()
    if hashlib.sha256(raw).hexdigest() != refs['beijing_manifest_sha256']:
        raise ValueError('Beijing test manifest mismatch')
    scoring_statistics = real_scoring_statistics(manifest)
    selected = refs[mode['mode_name']][method if method in {'jet', 'bank'} else 'jet']
    model = load_model(Path(selected['path']), selected['sha256'])
    if model.shape != ShapeSpec(12, 1):
        raise ValueError('real transfer requires K12/V1 checkpoint')
    commitment = canonical_hash(refs[mode['mode_name']])
    grant.verify(source_sha256=freeze.read()['source_sha256'],
                 data_sha256=refs['beijing_manifest_sha256'], model_sha256=commitment)
    def factory():
        freeze.read()
        grant.verify(source_sha256=mode['source_sha256'], data_sha256=refs['beijing_manifest_sha256'],
                     model_sha256=commitment)
        yield from iter_beijing(manifest, 'test', grant=grant)
    policy = freeze_score_policy(factory(), manifest_hash=refs['beijing_manifest_sha256'])
    if method in {'jet', 'bank'}:
        evaluated = model
    elif method == 'laguerre':
        evaluated = model
    else:
        controls = build_controls(ShapeSpec(12, 1), 1665,
                                  scoring_statistics, 2026102401906)
        evaluated = controls[method]['method']
    if method == 'laguerre':
        result = evaluate_equivalent_control(evaluated, factory, policy,
                   scoring_statistics, out, mode['allocation'], mode['worker_limits'])
    else:
        result = evaluate_panel(evaluated, factory, policy, scoring_statistics,
                                method, out, mode['allocation'], mode['worker_limits'])
    from famjet.data import beijing as beijing_core
    metadata = beijing_core._verify_manifest(manifest)
    blocks = metadata['splits']['test']['blocks']
    if len(blocks) != 56 or len({b['cluster_28d'] for b in blocks}) != 28 or len({b['cluster_56d'] for b in blocks}) != 14:
        raise ValueError('Beijing 56-block cluster inventory mismatch')
    clusters = {item['history_id']: item for item in blocks}
    rows = native_rows(load_score_rows(result['rows_ref']), refs['normalization'])
    for row in rows:
        block = clusters.get(row['history_id'])
        if block is None:
            raise ValueError('real scored history outside 56-block inventory')
        row['cluster_28d'] = block['cluster_28d']
        row['cluster_56d'] = block['cluster_56d']
        row['block_start'] = block['start']
        row['block_end'] = block['end']
    native_ref = persist_score_rows(rows, Path(out) / 'native-rows.json')
    output_admission = admit_real_output(out, mode['allocation'])
    finite_primary = [row for row in rows if row['score_scope'] == 'primary' and
                      type(row['loss']) in (int, float) and math.isfinite(row['loss'])]
    sensitivity = block_sensitivity(finite_primary, {'28d': 28, '56d': 14})
    return {'schema_version': 1, 'mode': mode['mode_name'], 'method': method,
            'status': 'completed', 'rows_ref': result['rows_ref'], 'native_rows_ref': native_ref,
            'summary': result['summary'], 'costs': result['costs'],
            'beijing_manifest_sha256': refs['beijing_manifest_sha256'],
            'grant_path': str(grant.manifest_path), 'grant_sha256': grant.manifest_sha256,
            'model_pair_sha256': commitment, 'model_manifest_sha256': selected['sha256'],
            'freeze_sha256': freeze.sha256, 'source_sha256': freeze.source_sha256,
            'expected_history_ids': [item['history_id'] for item in blocks],
            'full_inventory_hash': result['full_inventory_hash'],
            'eligible_inventory_hash': result['eligible_inventory_hash'],
            'block_sensitivity': sensitivity,
            'output_admission': output_admission}


def validate_real_method_inventory(receipts, modes, methods):
    if (type(receipts) is not list or type(modes) not in (tuple, list) or
            type(methods) not in (tuple, list) or not modes or not methods or
            len(modes) != len(set(modes)) or len(methods) != len(set(methods))):
        raise ValueError('complete real mode/method inventory required')
    expected = {(mode, method) for mode in modes for method in methods}
    actual = [(item.get('mode'), item.get('method')) for item in receipts]
    if len(actual) != len(expected) or set(actual) != expected or len(actual) != len(set(actual)):
        raise ValueError('real comparison release missing or duplicate method')
    if any(item.get('status') != 'completed' for item in receipts):
        raise ValueError('real comparison release contains failed method')
    return {'mode_count': len(modes), 'method_count_per_mode': len(methods),
            'run_count': len(expected)}


@dataclass(frozen=True)
class RealReleaseRef:
    path: Path
    sha256: str

    def read(self):
        raw = self.path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != self.sha256:
            raise ValueError('real release hash mismatch')
        body = json.loads(raw)
        if body.get('kind') != 'famjet_e4_real_complete_release' or body.get('status') != 'complete':
            raise ValueError('real release incomplete')
        from .protected import FrozenStudyRef
        freeze_raw = Path(body['freeze_path']).read_bytes()
        if hashlib.sha256(freeze_raw).hexdigest() != body['freeze_sha256']:
            raise ValueError('real release frozen study bytes changed')
        frozen = json.loads(freeze_raw)
        freeze = FrozenStudyRef(Path(body['freeze_path']), body['freeze_sha256'],
                                frozen['source_sha256'], frozen['executable']['sha256'])
        freeze.read()
        modes = load_bound_modes(ModeRefs(Path(body['mode_ref_path']), body['mode_ref_sha256']), freeze)
        if (hashlib.sha256(Path(body['beijing_manifest_path']).read_bytes()).hexdigest() !=
                body['beijing_manifest_sha256']):
            raise ValueError('real release Beijing manifest bytes changed')
        for receipt in body['receipts']:
            for field in ('rows_ref', 'native_rows_ref'):
                ref = receipt[field]
                payload = Path(ref['path']).read_bytes()
                if len(payload) != ref['bytes'] or hashlib.sha256(payload).hexdigest() != ref['sha256']:
                    raise ValueError('real release scored row bytes changed')
            if hashlib.sha256(Path(receipt['grant_path']).read_bytes()).hexdigest() != receipt['grant_sha256']:
                raise ValueError('real release grant bytes changed')
        return body


def seal_real_release(freeze, mode_ref, receipts, beijing_manifest, out):
    """Seal both 56-block mode comparisons only after all eight methods each."""
    from .contracts import AccessGrant
    from .study import load_score_rows
    frozen = freeze.read()
    modes = load_bound_modes(mode_ref, freeze)
    roster = tuple(frozen['inputs']['expected_methods'])
    inventory = validate_real_method_inventory(receipts,
                      ('synthetic_frozen', 'task_adapted'), roster)
    manifest = Path(beijing_manifest)
    manifest_sha = hashlib.sha256(manifest.read_bytes()).hexdigest()
    if manifest_sha != frozen['inputs']['beijing_manifest_sha256']:
        raise ValueError('real release Beijing manifest bytes changed')
    histories = frozen['inputs']['beijing_test_ids']
    if len(histories) != 56:
        raise ValueError('real release requires 56 chronological test blocks')
    expected_queries = list(range(120))
    validated = []
    by_key = {}
    for receipt in receipts:
        mode, method = receipt['mode'], receipt['method']
        commitment = canonical_hash(modes[mode])
        if (receipt.get('freeze_sha256') != freeze.sha256 or
                receipt.get('source_sha256') != freeze.source_sha256 or
                receipt.get('model_pair_sha256') != commitment or
                receipt.get('beijing_manifest_sha256') != manifest_sha or
                receipt.get('expected_history_ids') != histories):
            raise ValueError('real method source/model/data/history commitment mismatch')
        grant = AccessGrant(Path(receipt['grant_path']), receipt['grant_sha256'], 'test', 'test')
        grant.verify(source_sha256=freeze.source_sha256, data_sha256=manifest_sha,
                     model_sha256=commitment)
        rows = load_score_rows(receipt['rows_ref'])
        native = load_score_rows(receipt['native_rows_ref'])
        for name, batch in (('normalized', rows), ('native', native)):
            if len(batch) != 56 * 120 or any(row['method'] != method for row in batch):
                raise ValueError('real method query/method inventory incomplete')
            by_history = {}
            for row in batch:
                by_history.setdefault(row['history_id'], []).append(row['query_id'])
            if list(sorted(by_history)) != sorted(histories) or any(sorted(ids) != expected_queries
                    for ids in by_history.values()):
                raise ValueError('real method 56-block query inventory incomplete')
        if [(row['history_id'], row['query_id'], row['task']) for row in rows] != [
                (row['history_id'], row['query_id'], row['task']) for row in native]:
            raise ValueError('real native/normalized row identities differ')
        by_key[(mode, method)] = receipt
        validated.append({'mode': mode, 'method': method, 'normalized_rows_sha256': receipt['rows_ref']['sha256'],
                          'native_rows_sha256': receipt['native_rows_ref']['sha256'],
                          'query_count': len(rows), 'history_count': len(histories),
                          'grant_sha256': receipt['grant_sha256']})
    paired_sensitivity = {}
    for mode in ('synthetic_frozen', 'task_adapted'):
        jet = load_score_rows(by_key[(mode, 'jet')]['native_rows_ref'])
        bank = load_score_rows(by_key[(mode, 'bank')]['native_rows_ref'])
        j_index = {(row['history_id'], row['query_id']): row for row in jet}
        b_index = {(row['history_id'], row['query_id']): row for row in bank}
        if j_index.keys() != b_index.keys():
            raise ValueError('real Jet/Bank paired query inventory differs')
        differences = []
        for key, left in j_index.items():
            right = b_index[key]
            if left['task'] != right['task'] or left['score_scope'] != right['score_scope']:
                raise ValueError('real Jet/Bank task/eligibility mismatch')
            if left['score_scope'] != 'primary':
                continue
            if type(left['loss']) not in (float, int) or type(right['loss']) not in (float, int):
                raise ValueError('real paired primary loss undefined')
            difference = float(right['loss'] - left['loss'])
            if not math.isfinite(difference):
                raise ValueError('real paired primary loss nonfinite')
            differences.append({'history_id': left['history_id'],
                                'cluster_28d': left['cluster_28d'],
                                'cluster_56d': left['cluster_56d'],
                                'loss': difference})
        paired_sensitivity[mode] = block_sensitivity(differences, {'28d': 28, '56d': 14})
    body = {'schema_version': 1, 'kind': 'famjet_e4_real_complete_release',
            'status': 'complete', 'freeze_sha256': freeze.sha256,
            'freeze_path': str(freeze.path),
            'beijing_manifest_path': str(manifest),
            'beijing_manifest_sha256': manifest_sha,
            'mode_ref_path': str(mode_ref.path), 'mode_ref_sha256': mode_ref.sha256,
            'inventory': inventory, 'validated_runs': validated,
            'receipts': receipts, 'paired_block_sensitivity': paired_sensitivity,
            'population_scope': 'finite_2015_2017_test_period'}
    ref = _write_once(Path(out) / 'real-release.json', body)
    return RealReleaseRef(Path(ref['path']), ref['sha256'])
