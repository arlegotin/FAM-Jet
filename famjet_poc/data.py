"""Versioned shape-general numeric generation and guarded real-data iteration."""
import hashlib
import json
from pathlib import Path
import tempfile

import numpy as np
import torch

from famjet.data._processes import REGIMES, ROBUSTNESS, draw_gaps, numeric_values
from famjet.data.schema import validate_events, validate_queries
from famjet.data.synthetic import batch_hash, population_parameters
from famjet.eval.oracle import exact_targets, exact_time_difference
from famjet.provenance import canonical_hash, derive_seed
from famjet.types import Episode, EventBatch, QueryBatch
from .contracts import AccessGrant, PopulationSpec, source_sha256

PROTECTED = frozenset({'pilot', 'confirmation', 'replication'})


def _rng(root, namespace, identity):
    return np.random.Generator(np.random.PCG64(derive_seed(root, namespace, identity)))


def _supported(events, key, T, a, b, contrast):
    keys = events.key_ids[0].tolist()
    times = events.timestamps[0].tolist()
    obs = events.observed[0].numpy()
    for lo, hi in ([(a, b), (b, 2 * b - a)] if contrast else [(a, b)]):
        mask = np.asarray([int(k) == key and lo <= exact_time_difference(T, t) < hi
                           for k, t in zip(keys, times)], dtype=bool)
        if not bool((obs & mask[:, None]).any(axis=0).all()):
            return False
    return True


def generate_episode(spec: PopulationSpec, episode_id: str, *, grant: AccessGrant | None = None) -> Episode:
    """Value-blind deferred-query population; legacy mode reproduces public 16/8 draws."""
    if not isinstance(spec, PopulationSpec) or type(episode_id) is not str or not episode_id:
        raise ValueError('valid population and nonempty episode_id required')
    if spec.namespace in PROTECTED:
        if grant is None:
            raise ValueError('protected generation requires content-verified grant')
        grant.verify(source_sha256=source_sha256(), data_sha256=canonical_hash(spec.to_json()),
                     population=spec, episode_id=episode_id)
        if grant.split != spec.namespace or grant.phase != spec.namespace:
            raise ValueError('grant split/namespace mismatch')
    elif grant is not None:
        raise ValueError('unneeded grant for public namespace')
    root = derive_seed(spec.seed, 'initial_spec_v1' if spec.version == 'legacy_golden_v1' else 'poc_numeric_v1', spec.namespace)
    shape = spec.shape
    length = spec.lengths[0] if spec.version == 'legacy_golden_v1' else spec.lengths[derive_seed(root, 'length', episode_id) % len(spec.lengths)]
    regime = (REGIMES[derive_seed(root, 'regime', episode_id) % 4] if spec.version == 'legacy_golden_v1' else
              spec.regimes[derive_seed(root, 'regime', episode_id) % len(spec.regimes)])
    seed = derive_seed(root, 'history', episode_id)
    active = [int(i) for i in _rng(seed, 'keys', 'active').permutation(shape.key_dim)]
    indices = _rng(seed, 'events', 'keys').choice(shape.key_dim, length)
    gaps = draw_gaps(_rng(seed, 'events', 'gaps'), max(0, length - 1), 'standard')
    times = np.r_[0., np.cumsum(gaps)]
    values, schedule = numeric_values(times, indices, shape.key_dim, shape.value_dim,
                                      derive_seed(seed, 'events', 'values'), regime, 'standard')
    keys = [active[int(i)] for i in indices]
    onehot = np.eye(shape.key_dim, dtype=np.float32)
    events = EventBatch((episode_id,), torch.arange(length, dtype=torch.int64)[None],
                        torch.from_numpy(times[None]), torch.tensor([keys], dtype=torch.uint64),
                        torch.from_numpy(onehot[np.asarray(keys)][None]), torch.from_numpy(values[None]),
                        torch.tensor([length], dtype=torch.int64), torch.ones((1, length), dtype=torch.bool),
                        torch.ones((1, length, shape.value_dim), dtype=torch.bool), 'generator_reference_1')
    validate_events(events)
    rng = _rng(derive_seed(root, 'queries', episode_id), 'query_seed', '0')
    T = float(times[-1]); A = T - float(times[0])
    count = 0 if A < 2 else spec.queries_per_history
    rng.permutation([True] * (count // 2) + [False] * (count // 2))
    qkeys, starts, ends, tasks = [], [], [], []
    attempts = failed = 0
    universe = list(range(shape.key_dim))
    supported_keys = sorted({int(k) for k in events.key_ids[0].tolist()})
    for q in range(count):
        task = 'mean' if q % 2 == 0 else 'contrast'
        # The public sampler makes this provisional value-blind key draw before
        # its bounded rejection loop; retain its RNG consumption in golden mode.
        rng.choice(supported_keys or universe)
        ok = False
        for _ in range(spec.max_query_attempts):
            attempts += 1
            key = int(rng.choice(universe))
            width = float(np.exp(rng.uniform(np.log(max(1., A / 128.)), np.log(A * .5))))
            a = float(rng.uniform(0, max(0, A - (2 if task == 'contrast' else 1) * width)))
            b = a + width
            if _supported(events, key, T, a, b, task == 'contrast'):
                ok = True
                break
        if not ok:
            failed += 1
        qkeys.append(key); starts.append(a); ends.append(b); tasks.append(task)
    queries = QueryBatch((episode_id,), torch.arange(count, dtype=torch.int64)[None],
                         torch.full((1, count), T, dtype=torch.float64), torch.tensor([qkeys], dtype=torch.uint64),
                         torch.from_numpy(onehot[np.asarray(qkeys, dtype=np.int64)][None]), (tuple(tasks),),
                         torch.tensor([starts], dtype=torch.float64), torch.tensor([ends], dtype=torch.float64),
                         torch.ones((1, count), dtype=torch.bool), torch.tensor([count], dtype=torch.int64))
    validate_queries(queries)
    oracle = exact_targets(events, queries, arithmetic_version=2)
    diagnostics = {'status': 'insufficient_span' if A < 2 else 'sampling_exhausted' if failed else 'ok',
                   'attempts': attempts, 'failed_queries': failed,
                   'requested_queries': spec.queries_per_history, 'generated_queries': count,
                   'history_span': A, 'query_age_span': A, 'active_key_shortfall': 0}
    metadata = {'target_semantics': 'observed_event_targets_v2',
                'generator_version': 'initial_spec_v2_targets' if spec.version == 'legacy_golden_v1' else spec.version,
                'seed_version': 'sha256_named_v1', 'feature_version': 'squared_gaussian.pcg64_box_muller_v1',
                'namespace': spec.namespace, 'split': spec.namespace, 'split_root': root,
                'population': 'primary', 'regime': regime, 'regime_weight': .25,
                'robustness': 'standard', 'robustness_parameters': ROBUSTNESS['standard'],
                'population_parameters': population_parameters(), 'status': diagnostics['status'],
                'diagnostics': diagnostics, 'target_valid': oracle.metadata['target_valid'],
                'observed_counts': oracle.metadata['observed_counts'],
                'private_generator': {'excursions': schedule},
                'hashes': {'events': batch_hash(events), 'queries': batch_hash(queries), 'oracle': batch_hash(oracle)}}
    return Episode(events, queries, oracle.target, oracle.supported, metadata)


def invert_normalized_prediction(prediction, task: str, normalization: dict):
    """Return native units; contrast has no location shift."""
    if task not in {'mean', 'contrast', 'latest'} or normalization.get('split') != 'training':
        raise ValueError('unsupported task or normalization')
    scale, mean = normalization.get('scale'), normalization.get('mean')
    if not all(type(v) in (int, float) and np.isfinite(v) for v in (scale, mean)) or scale <= 0:
        raise ValueError('invalid training normalization')
    return np.asarray(prediction, dtype=np.float64) * scale + (mean if task != 'contrast' else 0.)


def iter_beijing(manifest: Path, split: str, *, grant: AccessGrant | None = None):
    """Replay current-v2 episodes from a verified archive/array inventory.

    A `beijing_unit_test` seal is admitted only with phase=unit_test and an
    exact content grant. Production `beijing` requires the official archive.
    """
    from famjet.data import beijing
    manifest = Path(manifest)
    payload = beijing._verify_manifest(manifest)
    if (split not in {'training', 'development_fit', 'development_calibration', 'test'} or
            payload.get('preparation_version') != beijing.VERSION or
            payload.get('target_semantics') != 'observed_event_targets_v2'):
        raise ValueError('current-v2 Beijing split required')
    unit = payload.get('dataset') == 'beijing_unit_test'
    if payload.get('dataset') not in {'beijing', 'beijing_unit_test'}:
        raise ValueError('unknown Beijing dataset')
    if unit and not manifest.resolve().is_relative_to(Path(tempfile.gettempdir()).resolve()):
        raise ValueError('unit Beijing fixture must live under separate temporary root')
    if split == 'test' or unit:
        if grant is None:
            raise ValueError('Beijing test/unit fixture requires grant')
        grant.verify(source_sha256=source_sha256(), data_sha256=hashlib.sha256(manifest.read_bytes()).hexdigest())
        if grant.split != split or (unit and grant.phase != 'unit_test') or (not unit and grant.phase == 'unit_test'):
            raise ValueError('Beijing grant phase/split mismatch')
        declared = json.loads(grant.manifest_path.read_bytes())['episode_ids']
        if declared != [b['history_id'] for b in payload['splits'][split]['blocks']]:
            raise ValueError('Beijing grant episode inventory mismatch')
    elif grant is not None:
        raise ValueError('unneeded Beijing grant')
    normalization = payload.get('normalization', {})
    if (normalization.get('split') != 'training' or normalization.get('source') != 'all_observed_training_events' or
            not np.isfinite(normalization.get('mean', np.nan)) or
            not np.isfinite(normalization.get('scale', np.nan)) or normalization['scale'] <= 0):
        raise ValueError('Beijing training normalization missing')
    if not unit:
        archive = Path(payload['archive']['path'])
        if (not archive.is_file() or archive.stat().st_size != 8192212 or
                beijing._sha(archive) != beijing.ARCHIVE_SHA256 or
                payload['archive']['sha256'] != beijing.ARCHIVE_SHA256):
            raise ValueError('official Beijing archive identity mismatch')
        reference = beijing.block_inventory()
        for name, info in reference.items():
            observed = payload['splits'][name]['blocks']
            fields = ('history_id', 'split', 'index', 'start_tick', 'end_tick', 'cluster_28d', 'cluster_56d')
            if [tuple(b[k] for k in fields) for b in observed] != [tuple(b[k] for k in fields) for b in info['blocks']]:
                raise ValueError('Beijing chronological inventory mismatch')
    root = (manifest.parent / payload['bulk_root']).resolve()
    for block in payload['splits'][split]['blocks']:
        path = (manifest.parent / block['artifact']).resolve()
        if path.parent != root or path.suffix != '.npz' or beijing._sha(path) != block['sha256']:
            raise ValueError('unsafe or modified Beijing artifact')
        with np.load(path, allow_pickle=False) as arrays:
            if set(arrays.files) != {'times', 'keys', 'raw_values', 'labels_raw', 'labels_normalized',
                                     'supported', 'observed_counts'}:
                raise ValueError('Beijing array inventory mismatch')
            data = {'times': arrays['times'].copy(), 'keys': arrays['keys'].copy(),
                    'values': arrays['raw_values'].copy()}
            episode = beijing.make_episode(data, block, normalization, normalized=True)
            raw = beijing.make_episode(data, block, normalization, normalized=False)
            if not (np.array_equal(episode.labels.numpy(), arrays['labels_normalized'], equal_nan=True) and
                    np.array_equal(raw.labels.numpy(), arrays['labels_raw'], equal_nan=True) and
                    np.array_equal(episode.supported.numpy(), arrays['supported']) and
                    np.array_equal(np.asarray(episode.metadata['observed_counts']), arrays['observed_counts'])):
                raise ValueError('Beijing target/mask/count replay mismatch')
        yield episode
