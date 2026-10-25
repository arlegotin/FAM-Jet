"""Shape-matched Beijing transfer with training-only fit and native-unit audit."""
from dataclasses import dataclass
import hashlib
import json
import math
import itertools
from pathlib import Path
import time

import numpy as np

from famjet.provenance import canonical_hash, canonical_json
from .contracts import ShapeSpec, ReaderSpec
from .data import invert_normalized_prediction, iter_beijing
from .protected import _write_once
from .comparators import COORDINATE_POLICY, coordinate_model_sha256, validate_coordinate_audits, load_coordinate_model


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
    if e3_source_sha256() != 'e25b63ee60f51ed511fc7af5d3f713c9a404301f51178283c0a2066d940e68ba':
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
    reference_seconds = sum(item['coordinate_seconds'] + item['conversion_seconds'] + item['diagnostic_seconds']
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
    guard_ref: dict | None = None

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
    probe_ref: dict | None = None

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
        if self.probe_ref is None:
            raise ValueError('measured Beijing fit probe required before pre-freeze fitting')
        probe = verify_transfer_probe(self.probe_ref, self.beijing_manifest_sha256,
                                      self.worker_limits)
        if (self.allocation['max_wall_seconds'] != probe['recommended_wall_seconds'] or
                self.allocation['max_disk_bytes'] != probe['recommended_disk_bytes'] or
                self.allocation['max_rss_bytes'] != probe['recommended_rss_bytes']):
            raise ValueError('real fit allocation differs from measured probe')


def verify_transfer_probe(ref, manifest_sha256, worker_limits):
    """Admit only an actual source-bound public Beijing profile receipt."""
    from .protected import _read_bound_file
    from .cache import e3_source_sha256
    probe = _read_bound_file(ref)
    measured = probe.get('measured_profile', {})
    if (probe.get('schema_version') != 1 or probe.get('kind') != 'famjet_e4_real_fit_probe' or
            probe.get('status') != 'measured' or
            probe.get('beijing_manifest_sha256') != manifest_sha256 or
            probe.get('worker_limits') != worker_limits or
            probe.get('transfer_source_sha256') != hashlib.sha256(Path(__file__).read_bytes()).hexdigest() or
            probe.get('e3_source_sha256') != e3_source_sha256() or
            measured.get('train_blocks') != 2 or measured.get('dev_blocks') != 1 or
            any(type(measured.get(key)) not in (int, float) or
                not math.isfinite(measured[key]) or measured[key] <= 0
                for key in ('cache_seconds', 'fit_seconds', 'evaluation_seconds',
                            'fit_rows', 'probe_output_bytes', 'peak_tree_rss_bytes')) or
            any(type(probe.get(key)) not in (int, float) or
                not math.isfinite(probe[key]) or probe[key] <= 0
                for key in ('forecast_seconds', 'recommended_wall_seconds',
                            'recommended_disk_bytes', 'recommended_rss_bytes')) or
            type(probe.get('allocation')) is not dict or
            probe['allocation'].get('phase') != 'probe' or
            probe['allocation'].get('manifest_sha256') != manifest_sha256):
        raise ValueError('measured current-source real fit probe mismatch')
    forecast = (measured['cache_seconds'] * (39 + 4) / 3 +
                36 * (measured['fit_seconds'] * 39 / 2 +
                      measured['evaluation_seconds'] * 4))
    expected_wall = max(1800, math.ceil((2 * forecast + 180) / 300) * 300)
    if (not math.isclose(probe['forecast_seconds'], forecast, rel_tol=1e-12) or
            probe['recommended_wall_seconds'] != expected_wall or expected_wall > 7200 or
            probe.get('forecast_output_bytes') != measured['probe_output_bytes'] * 200 or
            probe['forecast_output_bytes'] > 2 * 2**30 or
            probe['recommended_disk_bytes'] != 2 * 2**30 or
            probe['recommended_rss_bytes'] != 1610612736):
        raise ValueError('real fit probe forecast/allocation not derived from measurements')
    guard = _read_bound_file(probe.get('guard_ref'))
    if (guard.get('kind') != 'famjet_e4_live_stage_guard' or
            guard.get('status') != 'completed' or guard.get('violation') is not None or
            guard.get('allocation') != probe['allocation'] or
            measured['peak_tree_rss_bytes'] != max(
                (sample.get('tree_rss_bytes', 0) for sample in guard.get('samples', [])),
                default=0) or
            measured['peak_tree_rss_bytes'] > probe['recommended_rss_bytes']):
        raise ValueError('real fit probe live guard failed')
    from .study import load_score_rows
    rows = load_score_rows(probe['score_rows_ref'])
    if (type(measured.get('development_query_count')) is not int or
            not 1 <= measured['development_query_count'] <= 120 or
            len(rows) != measured['development_query_count'] or
            len({row['history_id'] for row in rows}) != 1 or
            any(row.get('method') != 'real-profile-probe' or
                row.get('manifest_hash') != manifest_sha256 for row in rows)):
        raise ValueError('real fit probe scoring artifact incomplete')
    return probe


def verify_selected_reference(modes):
    """Bind complete public coordinate diagnostics to the selected adapted Jet."""
    ref = modes.get('selected_reference') if type(modes) is dict else None
    selected = modes.get('task_adapted', {}).get('jet') if type(modes) is dict else None
    if (type(ref) is not dict or type(selected) is not dict or
            ref.get('model_sha256') != selected.get('sha256') or
            ref.get('manifest_sha256') != modes.get('beijing_manifest_sha256') or
            type(ref.get('rows_ref')) is not dict):
        raise ValueError('selected task-adapted Jet equivalent reference missing/mismatched')
    from .study import load_score_rows
    rows = load_score_rows(ref['rows_ref'])
    if not rows or any(row.get('method') != 'laguerre' or
                       row.get('manifest_hash') != ref['manifest_sha256'] for row in rows):
        raise ValueError('selected task-adapted Jet reference row contract mismatch')
    expected = {item['history_id'] for item in modes.get('development_cache', [])}
    if (len(expected) != 4 or len(rows) != 4 * 120 or
            {(row['history_id'], row['query_id']) for row in rows} !=
            {(history, query) for history in expected for query in range(120)} or
            any(row.get('target_semantics') != 'observed_event_targets_v2'
                for row in rows)):
        raise ValueError('selected Jet reference lacks complete four-block public query inventory')
    if (ref.get('schema_version') != 2 or ref.get('status') != 'diagnostic_complete' or
            ref.get('policy') != COORDINATE_POLICY):
        raise ValueError('selected coordinate reference diagnostic status/policy mismatch')
    from .models import load_model
    model = load_model(Path(selected['path']), selected['sha256'])
    model_hash = coordinate_model_sha256(model)
    if model.shape != ShapeSpec(12, 1) or model.spec.family != 'jet' or ref.get('model_numeric_sha256') != model_hash:
        raise ValueError('selected coordinate reference model mismatch')
    validate_coordinate_audits(ref.get('costs'), rows, expected_model=model)
    return ref


def probe_transfer_profile(beijing_manifest, worker_limits, allocation, out, *, observer=None):
    """Measure a bounded public 2-train/1-dev Beijing K12 fit and read."""
    from .cache import e3_source_sha256
    from .models import build_model, fit_reader, fit_training_metadata, make_fit_manifest
    from .study import evaluate_panel, freeze_score_policy, load_score_rows
    from .resources import LiveStageGuard
    manifest = Path(beijing_manifest)
    manifest_sha = hashlib.sha256(manifest.read_bytes()).hexdigest()
    if (type(allocation) is not dict or allocation.get('phase') != 'probe' or
            allocation.get('manifest_sha256') != manifest_sha or
            type(worker_limits) is not dict or set(worker_limits) !=
            {'max_frame_bytes', 'max_array_bytes', 'max_histories'}):
        raise ValueError('bounded real fit probe allocation required')
    out = Path(out)
    out.mkdir(parents=True, exist_ok=False)
    live = LiveStageGuard(out, allocation, out / 'live-guard.json', observer=observer)
    started = time.monotonic()
    with live:
        train_started = time.perf_counter()
        training = list(itertools.islice(iter_beijing(manifest, 'training'), 2))
        live.check()
        development = list(itertools.islice(iter_beijing(manifest, 'development_fit'), 1))
        live.check()
        if len(training) != 2 or len(development) != 1:
            raise ValueError('Beijing probe requires two training and one development block')
        cache_seconds = time.perf_counter() - train_started
        factory = lambda: iter(training)
        fit_started = time.perf_counter()
        metadata = fit_training_metadata(factory)
        shape = ShapeSpec(12, 1)
        reader = ReaderSpec('ridge_v1', 'jet', 8, 1e-2, 1 / 5224,
                            1., 1e-6, 1e-12)
        model = build_model(shape, reader, metadata['t_ref'], metadata['target_statistics'])
        fit = fit_reader(model, factory, make_fit_manifest(model, metadata))
        fit_seconds = time.perf_counter() - fit_started
        live.check()
        policy = freeze_score_policy(iter(development), manifest_hash=manifest_sha)
        evaluation_allocation = {**allocation, 'phase': 'development'}
        eval_started = time.perf_counter()
        scored = evaluate_panel(model, lambda: iter(development), policy,
                                metadata['target_statistics'], 'real-profile-probe',
                                out / 'evaluation', evaluation_allocation, worker_limits)
        evaluation_seconds = time.perf_counter() - eval_started
        live.check()
        if scored['summary']['status'] != 'ok':
            raise RuntimeError('Beijing public profile probe scoring failed')
        development_query_count = len(load_score_rows(scored['rows_ref']))
        forecast = (cache_seconds * (39 + 4) / 3 +
                    36 * (fit_seconds * 39 / 2 + evaluation_seconds * 4))
        recommended_wall = max(1800, math.ceil((2 * forecast + 180) / 300) * 300)
        if recommended_wall > 7200:
            raise RuntimeError('Beijing measured fit forecast exceeds finite 7200s cap')
        measured_output = sum(path.stat().st_size for path in out.rglob('*') if path.is_file())
        forecast_output = measured_output * 200
        recommended_disk = 2 * 2**30
        if forecast_output > recommended_disk:
            raise RuntimeError('Beijing measured fit output forecast exceeds two GiB cap')
    body = {'schema_version': 1, 'kind': 'famjet_e4_real_fit_probe',
            'status': 'measured', 'beijing_manifest_sha256': manifest_sha,
            'allocation': allocation,
            'transfer_source_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'e3_source_sha256': e3_source_sha256(), 'worker_limits': worker_limits,
            'measured_profile': {'train_blocks': 2, 'dev_blocks': 1,
                                 'cache_seconds': cache_seconds,
                                 'fit_seconds': fit_seconds,
                                 'evaluation_seconds': evaluation_seconds,
                                 'development_query_count': development_query_count,
                                 'fit_rows': fit.row_count,
                                 'probe_output_bytes': measured_output,
                                 'peak_tree_rss_bytes': max(
                                     sample.get('tree_rss_bytes', 0)
                                     for sample in live.samples)},
            'forecast_seconds': forecast,
            'forecast_output_bytes': forecast_output,
            'recommended_wall_seconds': recommended_wall,
            'recommended_disk_bytes': recommended_disk,
            'recommended_rss_bytes': 1610612736,
            'elapsed_seconds': time.monotonic() - started,
            'score_rows_ref': scored['rows_ref'],
            'guard_ref': live.receipt_ref}
    return _write_once(out / 'probe.json', body)


def load_bound_modes(ref: ModeRefs, freeze):
    """Read weights only after the immutable freeze binds the mode artifact."""
    from .cache import e3_source_sha256
    body = freeze.read()
    if body['inputs'].get('transfer_modes_sha256') != ref.sha256:
        raise ValueError('transfer mode SHA absent from freeze')
    modes = ref.read()
    if (modes['beijing_manifest_sha256'] != body['inputs'].get('beijing_manifest_sha256') or
            modes.get('transfer_source_sha256') != hashlib.sha256(Path(__file__).read_bytes()).hexdigest() or
            modes.get('e3_source_sha256') != e3_source_sha256() or
            modes.get('real_probe_ref') != body['inputs'].get('transfer_probe_ref')):
        raise ValueError('Beijing manifest/transfer freeze mismatch')
    verify_transfer_probe(modes['real_probe_ref'], modes['beijing_manifest_sha256'],
                          body['inputs']['worker_limits'])
    verify_selected_reference(modes)
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
    """Fit/tune public real blocks under a live bound resource allocation."""
    if type(inputs) is not PrefreezeTransferInputs:
        raise ValueError('typed pre-freeze transfer inputs required; frozen studies cannot create weights')
    verify_transfer_probe(inputs.probe_ref, inputs.beijing_manifest_sha256,
                          inputs.worker_limits)
    out = Path(out)
    out.mkdir(parents=True, exist_ok=False)
    from .resources import LiveStageGuard
    live = LiveStageGuard(out, inputs.allocation, out / 'live-guard.json')
    with live:
        ref = _fit_transfer_modes_body(inputs, beijing_manifest, out, live)
    return ModeRefs(ref.path, ref.sha256, live.receipt_ref)


def _fit_transfer_modes_body(inputs, beijing_manifest, out, live):
    """Use one verified raw cache for 36 candidate fits and selected Jet reference."""
    from .models import build_model, fit_reader, fit_training_metadata, load_model, make_fit_manifest, save_model
    from .study import evaluate_panel, freeze_score_policy, select_candidate
    from .cache import e3_source_sha256
    transfer = {'synthetic_k12_selected': inputs.synthetic_k12_selected,
                'allocation': inputs.allocation, 'worker_limits': inputs.worker_limits,
                'cache_max_bytes': inputs.cache_max_bytes}
    manifest = Path(beijing_manifest)
    raw = manifest.read_bytes()
    manifest_sha = hashlib.sha256(raw).hexdigest()
    if inputs.beijing_manifest_sha256 != manifest_sha:
        raise ValueError('Beijing manifest commitment mismatch')
    out = Path(out)
    started = time.monotonic()
    def guard():
        from .pipeline import observe_resources
        live.check()
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
    guard()
    selected_jet_ref = selected_real['jet']
    selected_jet = load_model(Path(selected_jet_ref['path']), selected_jet_ref['sha256'])
    selected_check = evaluate_equivalent_control(
        selected_jet, development, policy, meta['target_statistics'],
        out / 'selected-reference', transfer['allocation'], transfer['worker_limits'])
    if selected_check['summary']['status'] != 'ok':
        raise RuntimeError('selected task-adapted Jet public equivalent reference failed')
    selected_reference = {'schema_version': 2, 'status': 'diagnostic_complete',
                          'policy': COORDINATE_POLICY,
                          'model_numeric_sha256': coordinate_model_sha256(selected_jet),
                          'model_sha256': selected_jet_ref['sha256'],
                          'manifest_sha256': manifest_sha,
                          'rows_ref': selected_check['rows_ref'],
                          'summary': selected_check['summary'],
                          'costs': selected_check['costs']}
    guard()
    body = {'schema_version': 1, 'kind': 'famjet_e4_transfer_modes',
            'prefreeze': True, 'beijing_manifest_sha256': manifest_sha,
            'transfer_source_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'e3_source_sha256': e3_source_sha256(), 'shape': shape.to_json(),
            'normalization': json.loads(raw)['normalization'],
            'synthetic_frozen': frozen_refs, 'task_adapted': selected_real,
            'selected_reference': selected_reference,
            'real_probe_ref': inputs.probe_ref,
            'real_development_ledger': ledger,
            'training_cache': train_entries, 'development_cache': dev_entries,
            'cache_bytes': train_bytes + dev_bytes, 'elapsed_seconds': time.monotonic() - started,
            'test_accessed': False, 'final_allocation': guard()}
    verify_selected_reference(body)
    ref = _write_once(out / 'transfer-modes.json', body)
    return ModeRefs(Path(ref['path']), ref['sha256'])


def evaluate_real_mode(mode, grant, out):
    """Open test blocks only inside a live whole-method resource boundary."""
    if type(mode) is not dict or not {'mode_name', 'family'} <= set(mode):
        raise ValueError('frozen real mode descriptor required')
    if mode['mode_name'] not in {'synthetic_frozen', 'task_adapted'} or mode['family'] not in {
            'jet', 'bank', 'exact', 'recent', 'latest_lru', 'reservoir', 'buckets', 'laguerre'}:
        raise ValueError('unknown real transfer mode/method')
    if not {'allocation', 'freeze_path', 'freeze_sha256',
            'source_sha256', 'executable_sha256'} <= set(mode):
        raise ValueError('frozen real mode descriptor required')
    from .protected import FrozenStudyRef
    freeze = FrozenStudyRef(Path(mode['freeze_path']), mode['freeze_sha256'],
                            mode['source_sha256'], mode['executable_sha256'])
    if freeze.read()['inputs']['profile'] != 'study':
        return _evaluate_real_mode_body(mode, grant, out, None)
    from .resources import LiveStageGuard
    out = Path(out)
    out.mkdir(parents=True, exist_ok=False)
    live = LiveStageGuard(out, mode['allocation'], out / 'live-guard.json')
    with live:
        result = _evaluate_real_mode_body(mode, grant, out, live)
    result['live_guard_ref'] = live.receipt_ref
    return result


def _evaluate_real_mode_body(mode, grant, out, live):
    """Use E3's evaluator with exact frozen real mode and query counts."""
    from .models import load_model
    from .study import evaluate_panel, freeze_score_policy, load_score_rows, persist_score_rows
    from .comparators import build_controls
    from .protected import (FrozenStudyRef, episode_count_records,
                            write_count_sidecar)
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
    expected_family = method if method in {'jet', 'bank'} else 'jet'
    if model.shape != ShapeSpec(12, 1) or model.spec.family != expected_family:
        raise ValueError('real transfer requires bound K12/V1 family checkpoint')
    commitment = canonical_hash(refs[mode['mode_name']])
    grant.verify(source_sha256=freeze.read()['source_sha256'],
                 data_sha256=refs['beijing_manifest_sha256'], model_sha256=commitment)
    captured_counts = []
    def factory(capture=False):
        if live is not None:
            live.check()
        freeze.read()
        grant.verify(source_sha256=mode['source_sha256'], data_sha256=refs['beijing_manifest_sha256'],
                     model_sha256=commitment)
        for episode in iter_beijing(manifest, 'test', grant=grant):
            if live is not None:
                live.check()
            if capture:
                captured_counts.extend(episode_count_records(episode))
            yield episode
    policy = freeze_score_policy(factory(capture=True), manifest_hash=refs['beijing_manifest_sha256'])
    policy_ref = _write_once(Path(out) / 'score-policy.json', policy)
    counts_ref = write_count_sidecar(captured_counts, refs['beijing_manifest_sha256'], out)
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
                   scoring_statistics, Path(out) / 'equivalent',
                   mode['allocation'], mode['worker_limits'])
    else:
        result = evaluate_panel(evaluated, factory, policy, scoring_statistics,
                                method, out, mode['allocation'], mode['worker_limits'])
    if live is not None:
        live.check()
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
    if live is not None:
        live.check()
    output_admission = admit_real_output(out, mode['allocation'])
    finite_primary = [row for row in rows if row['score_scope'] == 'primary' and
                      type(row['loss']) in (int, float) and math.isfinite(row['loss'])]
    sensitivity = block_sensitivity(finite_primary, {'28d': 28, '56d': 14})
    if live is not None:
        live.check()
    return {'schema_version': 1, 'mode': mode['mode_name'], 'method': method,
            'status': 'completed', 'rows_ref': result['rows_ref'], 'native_rows_ref': native_ref,
            'counts_ref': counts_ref,
            'score_contract': {'policy_ref': policy_ref,
                               'statistics_sha256': canonical_hash(scoring_statistics)},
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
        from .protected import FrozenStudyRef, _read_bound_file, validate_scored_receipt
        from .study import load_score_rows
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
        if (len({item['counts_ref']['sha256'] for item in body['receipts']}) != 1 or
                body['counts_ref']['sha256'] != body['receipts'][0]['counts_ref']['sha256']):
            raise ValueError('real release observed-count inventory differs')
        for receipt in body['receipts']:
            for field in ('rows_ref', 'native_rows_ref'):
                ref = receipt[field]
                payload = Path(ref['path']).read_bytes()
                if len(payload) != ref['bytes'] or hashlib.sha256(payload).hexdigest() != ref['sha256']:
                    raise ValueError('real release scored row bytes changed')
            if hashlib.sha256(Path(receipt['grant_path']).read_bytes()).hexdigest() != receipt['grant_sha256']:
                raise ValueError('real release grant bytes changed')
            live = _read_bound_file(receipt['live_guard_ref'])
            if live.get('status') != 'completed' or live.get('violation') is not None:
                raise ValueError('real release live resource guard changed')
            validate_scored_receipt(receipt, load_score_rows(receipt['rows_ref']),
                                    body['beijing_manifest_sha256'],
                                    frozen['inputs']['beijing_test_ids'], list(range(120)),
                                    coordinate_model=load_coordinate_model(modes[receipt['mode']]['jet'], ShapeSpec(12, 1))
                                    if receipt['method'] == 'laguerre' else None)
        return body

    def iter_counts(self):
        """Replay the one complete hash-bound 56-block query-count inventory."""
        from .protected import _read_bound_file
        body = self.read()
        for record in _read_bound_file(body['counts_ref'])['records']:
            yield record


def seal_real_release(freeze, mode_ref, receipts, beijing_manifest, out):
    """Seal both 56-block mode comparisons only after all eight methods each."""
    from .contracts import AccessGrant
    from .protected import validate_scored_receipt, _read_bound_file
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
    expected_statistics_sha256 = canonical_hash(real_scoring_statistics(manifest))
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
        if receipt.get('score_contract', {}).get('statistics_sha256') != expected_statistics_sha256:
            raise ValueError('real score statistics differ from frozen training prior')
        live = _read_bound_file(receipt.get('live_guard_ref'))
        if (live.get('kind') != 'famjet_e4_live_stage_guard' or
                live.get('status') != 'completed' or live.get('violation') is not None or
                live.get('allocation', {}).get('allocation_id') !=
                'e4-beijing-' + mode + '-' + method or
                any(live['allocation'].get(name) != value for name, value in
                    frozen['inputs']['real_method_allocation_template'].items())):
            raise ValueError('real method live resource guard incomplete')
        grant = AccessGrant(Path(receipt['grant_path']), receipt['grant_sha256'], 'test', 'test')
        grant.verify(source_sha256=freeze.source_sha256, data_sha256=manifest_sha,
                     model_sha256=commitment)
        rows = load_score_rows(receipt['rows_ref'])
        native = load_score_rows(receipt['native_rows_ref'])
        coordinate_model = load_coordinate_model(modes[mode]['jet'], ShapeSpec(12, 1)) if method == 'laguerre' else None
        validate_scored_receipt(receipt, rows, manifest_sha, histories, expected_queries, coordinate_model=coordinate_model)
        validate_scored_receipt(receipt, native, manifest_sha, histories, expected_queries, coordinate_model=coordinate_model)
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
    if len({receipt['counts_ref']['sha256'] for receipt in receipts}) != 1:
        raise ValueError('real methods have differing observed-count inventories')
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
            'counts_ref': receipts[0]['counts_ref'],
            'receipts': receipts, 'paired_block_sensitivity': paired_sensitivity,
            'population_scope': 'finite_2015_2017_test_period'}
    ref = _write_once(Path(out) / 'real-release.json', body)
    return RealReleaseRef(Path(ref['path']), ref['sha256'])
