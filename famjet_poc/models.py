"""CPU64 coordinate-shared query-interaction ridge on frozen native writers."""
from dataclasses import asdict, dataclass, replace
import hashlib
import json
import math
from pathlib import Path
import os
import tempfile
import time

import numpy as np
import torch

from famjet.data.schema import validate_events, validate_queries
from famjet.data.synthetic import batch_hash, batch_hash_tensor
from famjet.eval.metrics import fit_target_statistics
from famjet.memory.jet import JetMemory
from famjet.memory.expbank import ExpBankMemory
from famjet.memory._fixed_writer import _digest_tensor
from famjet.provenance import canonical_hash, canonical_json
from famjet.types import ReadResult
from .contracts import ReaderSpec, ShapeSpec, source_sha256


def feature_map(u, mass, epsilon=1e-6, support_floor=1e-12):
    """[1, eight amplitudes, ratios, log masses, support indicators]."""
    u, mass = np.asarray(u, dtype=np.float64), np.asarray(mass, dtype=np.float64)
    if u.shape != (8,) or mass.shape != (8,) or not np.isfinite(u).all() or not np.isfinite(mass).all() or np.any(mass < 0):
        raise ValueError('nonfinite/negative mass or invalid eight-anchor shape')
    return np.r_[1., u, u / (mass + epsilon), np.log1p(mass), (mass > support_floor).astype(np.float64)]


def query_basis(a, b, task, t_ref, width):
    if not (type(a) in (int, float) and type(b) in (int, float) and
            math.isfinite(a) and math.isfinite(b) and 0 <= a < b and
            type(t_ref) in (int, float) and math.isfinite(t_ref) and t_ref > 0 and
            task in {'mean', 'contrast'} and width in {8, 16}):
        raise ValueError('invalid query endpoint/task/reference')
    x, y, c = math.log1p(a / t_ref), math.log1p((b - a) / t_ref), float(task == 'contrast')
    q = [1., x, y, x * y, x * x, y * y, c, c * x]
    if width == 16:
        q += [c * y, c * x * y, c * x * x, c * y * y, x**3, y**3, x * x * y, x * y * y]
    return np.asarray(q, dtype=np.float64)


def _finite_array(value, shape, name):
    a = np.asarray(value)
    if a.dtype != np.float64 or a.shape != shape or not np.isfinite(a).all():
        raise ValueError(f'invalid {name} shape/dtype/finite values')
    return a.copy()


class RidgeMemoryModel:
    """History-free reader statics; snapshots belong to the fixed writer."""
    def __init__(self, shape, spec, t_ref, target_statistics):
        if not isinstance(shape, ShapeSpec) or not isinstance(spec, ReaderSpec) or not math.isfinite(t_ref) or t_ref <= 0:
            raise ValueError('invalid model shape/spec/t_ref')
        if target_statistics.get('split') != 'training' or target_statistics.get('target_semantics') != 'observed_event_targets_v2':
            raise ValueError('frozen v2 training statistics required')
        for task in ('mean', 'contrast'):
            entry = target_statistics.get('tasks', {}).get(task, {})
            if entry.get('status', 'ok') != 'ok' or len(entry.get('mean', [])) != shape.value_dim:
                raise ValueError('training task priors/shape required')
        self.shape, self.spec, self.t_ref = shape, spec, float(t_ref)
        self._target_statistics = json.loads(canonical_json(target_statistics))
        rates = torch.tensor(np.geomspace(spec.alpha_min, spec.alpha_max, 4 if spec.family == 'jet' else 8)[None] / t_ref,
                             dtype=torch.float64)
        cls = JetMemory if spec.family == 'jet' else ExpBankMemory
        self.writer = cls(rates, shape.key_dim, shape.value_dim, eps=spec.epsilon,
                          support_floor=spec.support_floor, t_ref=t_ref)
        self._coefficients = np.zeros(33 * spec.query_width, dtype=np.float64)
        self.feature_mean = np.zeros(32, dtype=np.float64)
        self.feature_scale = np.ones(32, dtype=np.float64)
        self.query_mean = np.zeros(spec.query_width - 1, dtype=np.float64)
        self.query_scale = np.ones(spec.query_width - 1, dtype=np.float64)
        self.fit_artifact = None

    @property
    def coefficients(self):
        return self._coefficients.copy()

    @property
    def target_statistics(self):
        return json.loads(canonical_json(self._target_statistics))

    @coefficients.setter
    def coefficients(self, value):
        self._coefficients = _finite_array(value, (33 * self.spec.query_width,), 'coefficients')

    @property
    def writer_hash(self):
        return self.writer._parameter_hash()

    def init_state(self, batch_size, *, device, dtype):
        if device != 'cpu' or dtype != 'float64':
            raise ValueError('PoC requires CPU64')
        return self.writer.init_state(batch_size, device=device, dtype=dtype)

    def encode(self, events, state=None, *, mode='stream'):
        validate_events(events)
        if events.values.shape[-1] != self.shape.value_dim or events.key_features.shape[-1] != self.shape.key_dim:
            raise ValueError('model/event shape mismatch')
        events = replace(events, values=events.values.to(torch.float64),
                         key_features=events.key_features.to(torch.float64))
        return self.writer.encode(events, state, mode=mode)

    def advance_copy(self, state, query_time):
        return self.writer.advance_copy(state, query_time)

    def persistent_nbytes(self, state):
        return self.writer.persistent_nbytes(state)

    def parameter_nbytes(self):
        return self.writer.parameter_nbytes() + sum(a.nbytes for a in
            (self._coefficients, self.feature_mean, self.feature_scale, self.query_mean, self.query_scale))

    def _raw_features(self, state, queries):
        self.writer._check_snapshot(state)
        validate_queries(queries, state)
        if queries.key_features.shape[-1] != self.shape.key_dim:
            raise ValueError('model/query shape mismatch')
        identity = torch.stack([_digest_tensor(h) for h in queries.history_ids])
        if bool(state.payload['time_unit_hash'].any()) and not torch.equal(identity, state.payload['history_hash']):
            raise ValueError('query history identity mismatch')
        bcount, qcount = queries.T.shape
        values = np.zeros((bcount, qcount, self.shape.value_dim, 33), dtype=np.float64)
        valid = np.zeros((bcount, qcount), dtype=bool)
        numeric = np.zeros_like(valid)
        for j in range(qcount):
            if not bool(queries.present[:, j].any()):
                continue
            advanced = self.writer._advance_payload(state, queries.T[:, j].tolist(), queries.present[:, j].tolist())
            key = queries.key_features[:, j].to(torch.float64)
            z = torch.einsum('bjkv,bk->bjv', advanced['z'][:, 0], key).detach().cpu().numpy()
            if self.spec.family == 'jet':
                h = torch.einsum('bjkv,bk->bjv', advanced['h'][:, 0], key).detach().cpu().numpy()
                joined = np.concatenate((z, h), axis=1)
            else:
                joined = z
            u, mass = joined[..., :-1], joined[..., -1]
            for i in range(bcount):
                if not bool(queries.present[i, j]) or not bool(state.valid[i]):
                    continue
                if not np.isfinite(u[i]).all() or not np.isfinite(mass[i]).all() or np.any(mass[i] < 0):
                    continue
                numeric[i, j] = True
                for v in range(self.shape.value_dim):
                    values[i, j, v] = feature_map(u[i, :, v], mass[i], self.spec.epsilon, self.spec.support_floor)
                valid[i, j] = bool(np.any(mass[i] > self.spec.support_floor))
        return values, valid, numeric

    def design(self, state, queries):
        raw, valid, numeric = self._raw_features(state, queries)
        f = raw.copy()
        f[..., 1:] = (f[..., 1:] - self.feature_mean) / self.feature_scale
        q = np.zeros((*queries.T.shape, self.spec.query_width), dtype=np.float64)
        for i in range(q.shape[0]):
            for j in range(q.shape[1]):
                if not bool(queries.present[i, j]):
                    continue
                basis = query_basis(float(queries.age_start[i, j]), float(queries.age_end[i, j]),
                                    queries.tasks[i][j], self.t_ref, self.spec.query_width)
                q[i, j] = basis
        q[..., 1:] = (q[..., 1:] - self.query_mean) / self.query_scale
        return (q[..., :, None, None] * f[..., None, :, :]).transpose(0, 1, 3, 2, 4).reshape(
            *queries.T.shape, self.shape.value_dim, 33 * self.spec.query_width), valid, numeric

    def read(self, state, queries):
        phi, valid, numeric = self.design(state, queries)
        prediction = np.einsum('bqvp,p->bqv', phi, self._coefficients)
        failure = ~np.isfinite(prediction).all(axis=-1) | (~numeric & queries.present.numpy())
        valid &= ~failure
        prediction[~valid] = np.nan
        return ReadResult(torch.from_numpy(prediction), None, torch.from_numpy(valid),
                          torch.from_numpy(failure), {'prediction_valid': torch.from_numpy(valid.copy()),
                                                      'numeric_supported': torch.from_numpy(numeric.copy())})


def build_model(shape: ShapeSpec, spec: ReaderSpec, t_ref: float, target_statistics: dict) -> RidgeMemoryModel:
    return RidgeMemoryModel(shape, spec, t_ref, target_statistics)


def _episode_digest(ep):
    provenance_fields = ('namespace', 'split', 'split_root', 'population', 'generator_version',
                         'preparation_version', 'normalization', 'regime', 'hashes', 'target_valid')
    return canonical_hash({'events': batch_hash(ep.events), 'queries': batch_hash(ep.queries),
                           'labels': batch_hash_tensor(ep.labels), 'supported': batch_hash_tensor(ep.supported),
                           'metadata': {key: ep.metadata.get(key) for key in provenance_fields}})


def _checked_factory(factory):
    if not callable(factory):
        raise TypeError('episode_factory must be replayable callable')
    episodes = factory()
    if episodes is factory or not hasattr(episodes, '__iter__'):
        raise TypeError('episode_factory must return fresh iterable')
    for ep in episodes:
        if ep.metadata.get('split') != 'training' or ep.metadata.get('target_semantics') != 'observed_event_targets_v2':
            raise ValueError('fit admits current-v2 training episodes only')
        validate_events(ep.events); validate_queries(ep.queries)
        if (ep.events.history_ids != ep.queries.history_ids or ep.labels.shape[:2] != ep.queries.T.shape or
                ep.supported.shape != ep.queries.T.shape or ep.labels.ndim != 3):
            raise ValueError('episode layout mismatch')
        if ep.events.values.shape[-1] != ep.labels.shape[-1]:
            raise ValueError('target/value shape mismatch')
        valid = ep.metadata.get('target_valid')
        if (type(valid) is not list or len(valid) != len(ep.events.history_ids) or
                any(len(row) != ep.queries.T.shape[1] for row in valid) or
                not np.array_equal(np.asarray(valid, dtype=bool), ep.supported.numpy())):
            raise ValueError('numeric target eligibility/mask mismatch')
        yield ep


def fit_training_metadata(episode_factory):
    """Training-only target moments and exact positive-gap median, without histories."""
    import itertools
    digests, inventory, gaps, seen = [], [], [], set()

    def inspected():
        for ep in _checked_factory(episode_factory):
            digests.append(_episode_digest(ep))
            for i, h in enumerate(ep.events.history_ids):
                if h in seen:
                    raise ValueError('duplicate history ID')
                seen.add(h)
                n = int(ep.events.lengths[i]); times = ep.events.timestamps[i, :n].tolist()
                gaps.extend(float(b - a) for a, b in zip(times, times[1:]) if b > a)
                counts = {'mean': 0, 'contrast': 0}
                for j in range(int(ep.queries.lengths[i])):
                    task = ep.queries.tasks[i][j]
                    if task not in counts:
                        raise ValueError('unsupported fit task')
                    if bool(ep.queries.present[i, j]) and bool(ep.supported[i, j]):
                        counts[task] += 1
                regime = ep.metadata.get('regime')
                from famjet.data._processes import REGIMES
                if (regime is None and ep.metadata.get('preparation_version') == 'beijing_observed_v2_targets'
                        and ep.metadata.get('normalization') == 'training_standardized'):
                    regime = 'beijing_observed'
                if regime not in {*REGIMES, 'two_age_uniform', 'beijing_observed'}:
                    raise ValueError('unknown training regime')
                inventory.append({'history_id': h, 'regime': regime, 'eligible': counts})
            yield ep
    stats = fit_target_statistics(inspected())
    if not gaps or not inventory or any(min(x['eligible'].values()) == 0 for x in inventory):
        raise ValueError('fit needs positive gaps and both eligible tasks per history')
    tref = float(np.median(np.asarray(gaps, dtype=np.float64)))
    if not math.isfinite(tref) or tref <= 0:
        raise ValueError('invalid training t_ref')
    return {'target_statistics': stats, 't_ref': tref, 't_ref_policy': 'median_positive_gap',
            'positive_gap_count': len(gaps),
            'history_inventory': inventory,
            'row_sha256': canonical_hash(digests), 'episode_digests': digests,
            'data_sha256': canonical_hash({'digests': digests, 'inventory': inventory})}


def make_fit_manifest(model: RidgeMemoryModel, metadata: dict, *, regime_weights=None):
    """Freeze the exact data/source/writer/statistics inputs for a reader fit."""
    if regime_weights is None:
        regimes = sorted({x['regime'] for x in metadata['history_inventory']})
        regime_weights = {r: 1 / len(regimes) for r in regimes}
    if (not isinstance(model, RidgeMemoryModel) or metadata['t_ref'] != model.t_ref or
            canonical_hash(metadata['target_statistics']) != canonical_hash(model.target_statistics)):
        raise ValueError('model does not match training metadata')
    lock_sha = hashlib.sha256((Path(__file__).resolve().parent.parent / 'requirements.lock').read_bytes()).hexdigest()
    return {'schema_version': 1, 'split': 'training', 'source_sha256': source_sha256(),
            'lock_sha256': lock_sha,
            'data_sha256': metadata['data_sha256'], 'row_sha256': metadata['row_sha256'],
            'episode_digests': metadata['episode_digests'],
            'history_inventory': metadata['history_inventory'], 'writer_sha256': model.writer_hash,
            'shape': model.shape.to_json(), 'reader': model.spec.to_json(), 't_ref': model.t_ref,
            'target_statistics_sha256': canonical_hash(model.target_statistics),
            't_ref_policy': metadata['t_ref_policy'],
            'regime_weights': regime_weights}


_FIT_MANIFEST_FIELDS = frozenset({'schema_version', 'split', 'source_sha256', 'lock_sha256',
    'data_sha256', 'row_sha256', 'episode_digests', 'history_inventory', 'writer_sha256',
    'shape', 'reader', 't_ref', 'target_statistics_sha256', 't_ref_policy', 'regime_weights'})


def _sha256_text(value):
    return type(value) is str and len(value) == 64 and all(c in '0123456789abcdef' for c in value)


def _validate_fit_manifest(model: RidgeMemoryModel, manifest: dict, observed: dict | None = None):
    """One exact source/data/config contract for fitting and artifact loading."""
    lock_sha = hashlib.sha256((Path(__file__).resolve().parent.parent / 'requirements.lock').read_bytes()).hexdigest()
    if (type(manifest) is not dict or set(manifest) != _FIT_MANIFEST_FIELDS or
            type(manifest['schema_version']) is not int or manifest['schema_version'] != 1 or
            manifest['split'] != 'training' or manifest['source_sha256'] != source_sha256() or
            manifest['lock_sha256'] != lock_sha or manifest['writer_sha256'] != model.writer_hash or
            manifest['shape'] != model.shape.to_json() or manifest['reader'] != model.spec.to_json() or
            type(manifest['t_ref']) not in (int, float) or manifest['t_ref'] != model.t_ref or
            manifest['target_statistics_sha256'] != canonical_hash(model.target_statistics)):
        raise ValueError('fit manifest source/writer/config/statistics mismatch')
    digests, inventory = manifest['episode_digests'], manifest['history_inventory']
    if (type(digests) is not list or not digests or not all(_sha256_text(d) for d in digests) or
            type(inventory) is not list or not inventory or
            not all(type(x) is dict and set(x) == {'history_id', 'regime', 'eligible'} and
                    type(x['history_id']) is str and bool(x['history_id']) and
                    type(x['regime']) is str and bool(x['regime']) and
                    type(x['eligible']) is dict and set(x['eligible']) == {'mean', 'contrast'} and
                    all(type(n) is int and n > 0 for n in x['eligible'].values()) for x in inventory)):
        raise ValueError('fit manifest history/episode schema mismatch')
    if (len({x['history_id'] for x in inventory}) != len(inventory) or
            manifest['row_sha256'] != canonical_hash(digests) or
            manifest['data_sha256'] != canonical_hash({'digests': digests, 'inventory': inventory})):
        raise ValueError('fit manifest ordered row/data inventory mismatch')
    policy = manifest['t_ref_policy']
    if not (policy == 'median_positive_gap' or policy == 'qualification_fixed_1' and
            model.t_ref == 1. and all(x['regime'] == 'two_age_uniform' for x in inventory)):
        raise ValueError('fit manifest t_ref policy mismatch')
    if (policy == 'median_positive_gap' and model.t_ref == 1. and
            all(x['regime'] == 'two_age_uniform' for x in inventory)):
        raise ValueError('two-age fixture requires declared fixed-reference policy')
    regimes, weights = {x['regime'] for x in inventory}, manifest['regime_weights']
    if (type(weights) is not dict or set(weights) != regimes or
            not all(type(w) in (int, float) and math.isfinite(w) and w > 0 for w in weights.values()) or
            not math.isclose(sum(weights.values()), 1., rel_tol=1e-12)):
        raise ValueError('fit manifest regime weights mismatch')
    if observed is not None:
        if (observed['episode_digests'] != digests or observed['history_inventory'] != inventory or
                observed['data_sha256'] != manifest['data_sha256'] or
                canonical_hash(observed['target_statistics']) != manifest['target_statistics_sha256'] or
                policy == 'median_positive_gap' and observed['t_ref'] != model.t_ref):
            raise ValueError('replay training rows/statistics differ from fit manifest')
    return sum((x['eligible']['mean'] + x['eligible']['contrast']) * model.shape.value_dim for x in inventory)


@dataclass(frozen=True)
class FitArtifact:
    manifest: dict
    objective: float
    scaled_normal_residual: float
    row_count: int
    elapsed_seconds: float
    rates: tuple
    coefficients: tuple
    feature_mean: tuple
    feature_scale: tuple
    query_mean: tuple
    query_scale: tuple
    target_statistics: dict
    solver: dict
    memory_ledger: dict
    failure_status: str = 'none'


@dataclass(frozen=True)
class FileRef:
    path: Path
    sha256: str
    bytes: int


def _replay(model, factory, manifest):
    digests = []
    history_ids = []
    for ep in _checked_factory(factory):
        digests.append(_episode_digest(ep))
        history_ids.extend(ep.events.history_ids)
        if ep.events.key_features.shape[-1] != model.shape.key_dim or ep.labels.shape[-1] != model.shape.value_dim:
            raise ValueError('training shape mismatch')
        yield ep
    if (digests != manifest['episode_digests'] or canonical_hash(digests) != manifest['row_sha256'] or
            history_ids != [x['history_id'] for x in manifest['history_inventory']]):
        raise ValueError('replay factory rows changed')


def _training_rows(model, ep, buffers=None):
    state = model.encode(ep.events, mode='terminal')
    raw, _, numeric = model._raw_features(state, ep.queries)
    if buffers is not None:
        b, q, v, _ = raw.shape
        j = 4 if model.spec.family == 'jet' else 8
        buffers['max_episode_raw_features'] = max(buffers['max_episode_raw_features'], raw.nbytes)
        buffers['max_episode_validity_masks'] = max(buffers['max_episode_validity_masks'], 2 * b * q)
        buffers['max_episode_writer_state'] = max(buffers['max_episode_writer_state'],
                                                   model.persistent_nbytes(state))
        # One query is contracted at a time; the episode's incoming tensors
        # belong to the factory and are outside the model's owned buffers.
        contract = ((2 if model.spec.family == 'jet' else 1) * b * j * (v + 1) * 8 +
                    b * 8 * (v + 1) * 8 + b * model.shape.key_dim * 8)
        buffers['max_query_contract_arrays'] = max(buffers['max_query_contract_arrays'], contract)
    for i, h in enumerate(ep.events.history_ids):
        for j in range(int(ep.queries.lengths[i])):
            if not bool(ep.queries.present[i, j]) or not bool(ep.supported[i, j]):
                continue
            if not bool(numeric[i, j]) or not np.isfinite(ep.labels[i, j].numpy()).all():
                raise ArithmeticError('eligible row has numerical failure')
            q = query_basis(float(ep.queries.age_start[i, j]), float(ep.queries.age_end[i, j]),
                            ep.queries.tasks[i][j], model.t_ref, model.spec.query_width)
            for v in range(model.shape.value_dim):
                yield h, ep.queries.tasks[i][j], raw[i, j, v], q, float(ep.labels[i, j, v])


def fit_reader(model: RidgeMemoryModel, episode_factory, fit_manifest: dict, *, chunk_rows: int = 1024) -> FitArtifact:
    """Two bounded passes; update statics only after manifest replay and solve checks."""
    started = time.perf_counter()
    if not isinstance(model, RidgeMemoryModel) or type(chunk_rows) is not int or chunk_rows <= 0:
        raise ValueError('invalid model/chunk_rows')
    if model.fit_artifact is not None:
        raise ValueError('refit requires a fresh model instance')
    expected_rows = _validate_fit_manifest(model, fit_manifest)
    inventory = fit_manifest['history_inventory']
    observed = fit_training_metadata(episode_factory)
    _validate_fit_manifest(model, fit_manifest, observed)
    regimes = {x['regime'] for x in inventory}
    weights = fit_manifest['regime_weights']
    fsum = np.zeros(32); fsq = np.zeros(32); qsum = np.zeros(model.spec.query_width - 1)
    qsq = np.zeros_like(qsum); count = 0
    episode_buffers = {'max_episode_raw_features': 0, 'max_episode_validity_masks': 0,
                       'max_episode_writer_state': 0, 'max_query_contract_arrays': 0}
    for ep in _replay(model, episode_factory, fit_manifest):
        for _, _, f, q, _ in _training_rows(model, ep, episode_buffers):
            fsum += f[1:]; fsq += f[1:]**2
            qsum += q[1:]; qsq += q[1:]**2; count += 1
    if count == 0:
        raise ValueError('no eligible training rows')
    fmean, qmean = fsum / count, qsum / count
    fscale = np.sqrt(np.maximum(0., fsq / count - fmean**2)); fscale[fscale == 0] = 1.
    qscale = np.sqrt(np.maximum(0., qsq / count - qmean**2)); qscale[qscale == 0] = 1.
    p = model.spec.query_width * 33
    G = np.zeros((p, p)); rhs = np.zeros(p); yy = 0.; total_weight = 0.; rows = 0
    regime_count = {r: sum(x['regime'] == r for x in inventory) for r in regimes}
    by_h = {x['history_id']: x for x in inventory}
    buffered = []
    max_buffered_rows = 0
    def flush():
        nonlocal yy, total_weight, rows
        if not buffered:
            return
        X = np.stack([r[0] for r in buffered]); y = np.array([r[1] for r in buffered]); w = np.array([r[2] for r in buffered])
        G[:] += X.T @ (w[:, None] * X); rhs[:] += X.T @ (w * y)
        yy += float(np.dot(w, y * y)); total_weight += float(w.sum()); rows += len(buffered)
        buffered.clear()
    for ep in _replay(model, episode_factory, fit_manifest):
        for h, task, f, q, y in _training_rows(model, ep):
            item = by_h[h]
            fs = np.r_[1., (f[1:] - fmean) / fscale]
            qs = np.r_[1., (q[1:] - qmean) / qscale]
            phi = np.outer(qs, fs).ravel()
            scale = model.target_statistics['tasks'][task].get('scale')
            if scale is None or not math.isfinite(scale) or scale <= 0:
                raise ValueError('positive training task scale required for ridge fit')
            weight = (weights[item['regime']] / regime_count[item['regime']] / 2 /
                      item['eligible'][task] / model.shape.value_dim / scale**2)
            buffered.append((phi, y, weight))
            max_buffered_rows = max(max_buffered_rows, len(buffered))
            if len(buffered) == chunk_rows:
                flush()
    flush()
    if rows != count or rows != expected_rows or not math.isfinite(total_weight) or total_weight <= 0:
        raise ValueError('training row inventory changed')
    G /= total_weight; rhs /= total_weight; yy /= total_weight
    normal = G + model.spec.ridge * np.eye(p)
    coefficients = np.linalg.solve(normal, rhs)
    residual = float(np.linalg.norm(normal @ coefficients - rhs) / max(1., np.linalg.norm(rhs)))
    objective = float(coefficients @ G @ coefficients - 2 * coefficients @ rhs + yy + model.spec.ridge * (coefficients @ coefficients))
    if not np.isfinite(coefficients).all() or not math.isfinite(objective) or objective < -1e-8 or residual > 1e-7:
        raise ArithmeticError('ridge solve failed numerical verification')
    objective = max(0., objective)
    p8, chunk8, matrix8 = p * 8, max_buffered_rows * 8, p * p * 8
    statics = (coefficients.nbytes + fmean.nbytes + fscale.nbytes + qmean.nbytes + qscale.nbytes +
               model.writer.parameter_nbytes())
    rate_values = model.writer.rates.numel() * 8
    scaler_values = fmean.nbytes + fscale.nbytes + qmean.nbytes + qscale.nbytes
    artifact_values = rate_values + coefficients.nbytes + scaler_values
    arrays = {'gram': G.nbytes, 'normal_matrix': normal.nbytes,
              'ridge_identity_temporary': matrix8, 'scaled_ridge_identity_temporary': matrix8,
              'gram_product_temporary': matrix8, 'rhs': rhs.nbytes,
              'rhs_product_temporary': p8, 'normal_residual_vectors': 2 * p8,
              'buffered_phi': max_buffered_rows * p8,
              'stacked_design': max_buffered_rows * p8,
              'weighted_design': max_buffered_rows * p8,
              'chunk_labels_and_weights': 2 * chunk8,
              'chunk_reduction_temporaries': 3 * chunk8,
              'feature_query_sums_and_squares': fsum.nbytes + fsq.nbytes + qsum.nbytes + qsq.nbytes,
              'feature_query_means_and_scales': fmean.nbytes + fscale.nbytes + qmean.nbytes + qscale.nbytes,
              'max_query_basis': model.spec.query_width * 8,
              'max_feature_standardization_vectors': (33 + model.spec.query_width + p) * 8,
              'metadata_positive_gap_values': observed['positive_gap_count'] * 8,
              'model_static_arrays': statics,
              'artifact_coefficient_values': coefficients.nbytes,
              'artifact_scaler_values': scaler_values,
              'artifact_rate_values': rate_values,
              'max_advanced_snapshot_copy': episode_buffers['max_episode_writer_state'],
              **episode_buffers}
    simultaneous = {
        'query_extraction': arrays['model_static_arrays'] + arrays['max_episode_writer_state'] +
                            arrays['max_advanced_snapshot_copy'] +
                            arrays['max_episode_raw_features'] + arrays['max_episode_validity_masks'] +
                            arrays['max_query_contract_arrays'] + arrays['max_query_basis'],
        'chunk_flush': arrays['model_static_arrays'] + arrays['max_episode_writer_state'] +
                       arrays['max_episode_raw_features'] + arrays['max_episode_validity_masks'] +
                       arrays['gram'] + arrays['rhs'] + arrays['buffered_phi'] + arrays['stacked_design'] +
                       arrays['weighted_design'] + arrays['chunk_labels_and_weights'] +
                       arrays['chunk_reduction_temporaries'] + arrays['gram_product_temporary'] +
                       arrays['rhs_product_temporary'],
        'normal_construction': arrays['model_static_arrays'] + arrays['gram'] + arrays['rhs'] +
                               arrays['normal_matrix'] + arrays['ridge_identity_temporary'] +
                               arrays['scaled_ridge_identity_temporary'],
        'postsolve_artifact': arrays['model_static_arrays'] + arrays['gram'] + arrays['rhs'] +
                              arrays['normal_matrix'] + coefficients.nbytes +
                              arrays['normal_residual_vectors'] + artifact_values,
    }
    memory_ledger = {'schema_version': 2, 'scope': 'known_logical_allocations_not_peak_or_rss',
                     'observed_peak_chunk_rows': max_buffered_rows,
                     'logical_arrays_bytes': arrays,
                     'known_simultaneous_groups_bytes': simultaneous,
                     'unmeasured': {'solver_workspace_bytes': None, 'process_rss_bytes': None,
                                    'python_object_overhead_bytes': None,
                                    'torch_kernel_temporary_bytes': None,
                                    'input_episode_tensors_bytes': None},
                     'gram_bytes': G.nbytes, 'rhs_bytes': rhs.nbytes,
                     'max_design_chunk_bytes': max_buffered_rows * p8,
                     'static_bytes': statics, 'rss_status': 'not_measured_in_source_fit'}
    artifact = FitArtifact(json.loads(canonical_json(fit_manifest)), objective, residual, rows,
                           time.perf_counter() - started,
                           tuple(model.writer.rates.detach().cpu().flatten().tolist()),
                           tuple(coefficients.tolist()), tuple(fmean.tolist()), tuple(fscale.tolist()),
                           tuple(qmean.tolist()), tuple(qscale.tolist()), model.target_statistics,
                           {'method': 'numpy.linalg.solve_fp64_normal_equations', 'ridge': model.spec.ridge,
                            'scaled_normal_residual': residual},
                           memory_ledger)
    model.feature_mean, model.feature_scale = fmean, fscale
    model.query_mean, model.query_scale = qmean, qscale
    model.coefficients = coefficients
    model.fit_artifact = artifact
    return artifact


_ARRAY_NAMES = ('rates', 'coefficients', 'feature_mean', 'feature_scale', 'query_mean', 'query_scale')


def _sha_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save_model(model: RidgeMemoryModel, manifest_path: Path) -> FileRef:
    """Atomically publish finite numeric statics in NPZ plus strict JSON inventory."""
    if not isinstance(model, RidgeMemoryModel) or model.fit_artifact is None:
        raise ValueError('only verified fitted models can be saved')
    path = Path(manifest_path)
    if path.suffix != '.json':
        raise ValueError('model manifest path must end in .json')
    path.parent.mkdir(parents=True, exist_ok=True)
    arrays = {'rates': model.writer.rates.detach().cpu().numpy().copy(),
              'coefficients': model.coefficients, 'feature_mean': model.feature_mean.copy(),
              'feature_scale': model.feature_scale.copy(), 'query_mean': model.query_mean.copy(),
              'query_scale': model.query_scale.copy()}
    if any(a.dtype != np.float64 or not np.isfinite(a).all() for a in arrays.values()):
        raise ValueError('nonfinite or non-FP64 model statics')
    npz_path = path.with_suffix('.npz')
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix='.poc-', suffix='.npz', delete=False) as tmp:
        temp_npz = Path(tmp.name)
        np.savez(tmp, **arrays)
    try:
        inventory = {name: {'dtype': str(a.dtype), 'shape': list(a.shape),
                            'sha256': hashlib.sha256(a.tobytes()).hexdigest()} for name, a in arrays.items()}
        payload = {'schema_version': 1, 'kind': 'famjet_poc_ridge_model', 'source_sha256': source_sha256(),
                   'shape': model.shape.to_json(), 'reader': model.spec.to_json(), 't_ref': model.t_ref,
                   'target_statistics': model.target_statistics, 'writer_sha256': model.writer_hash,
                   'fit': asdict(model.fit_artifact), 'arrays': inventory,
                   'npz_file': npz_path.name, 'npz_sha256': _sha_file(temp_npz)}
        raw = canonical_json(payload)
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix='.poc-', suffix='.json', delete=False) as tmp:
            temp_json = Path(tmp.name)
            tmp.write(raw)
        os.replace(temp_npz, npz_path)
        os.replace(temp_json, path)
    finally:
        temp_npz.unlink(missing_ok=True)
    return FileRef(path, hashlib.sha256(raw).hexdigest(), len(raw))


def load_model(manifest_path: Path, expected_sha256: str) -> RidgeMemoryModel:
    """Fail closed on manifest, source, shape, every array and NPZ byte identity."""
    path = Path(manifest_path)
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected_sha256:
        raise ValueError('model manifest SHA mismatch')
    payload = json.loads(raw)
    required = {'schema_version', 'kind', 'source_sha256', 'shape', 'reader', 't_ref',
                'target_statistics', 'writer_sha256', 'fit', 'arrays', 'npz_file', 'npz_sha256'}
    if (set(payload) != required or payload['schema_version'] != 1 or payload['kind'] != 'famjet_poc_ridge_model' or
            payload['source_sha256'] != source_sha256() or set(payload['arrays']) != set(_ARRAY_NAMES) or
            payload['npz_file'] != path.with_suffix('.npz').name):
        raise ValueError('model source/schema/array inventory mismatch')
    npz_path = path.with_suffix('.npz')
    if _sha_file(npz_path) != payload['npz_sha256']:
        raise ValueError('model NPZ bytes changed')
    shape = ShapeSpec.from_json(payload['shape'])
    spec = ReaderSpec.from_json(payload['reader'])
    model = build_model(shape, spec, payload['t_ref'], payload['target_statistics'])
    with np.load(npz_path, allow_pickle=False) as z:
        if set(z.files) != set(_ARRAY_NAMES):
            raise ValueError('model NPZ member inventory mismatch')
        arrays = {name: np.asarray(z[name]) for name in _ARRAY_NAMES}
    shapes = {'rates': (1, 4 if spec.family == 'jet' else 8), 'coefficients': (33 * spec.query_width,),
              'feature_mean': (32,), 'feature_scale': (32,),
              'query_mean': (spec.query_width - 1,), 'query_scale': (spec.query_width - 1,)}
    for name, a in arrays.items():
        record = payload['arrays'][name]
        if (set(record) != {'dtype', 'shape', 'sha256'} or record['dtype'] != 'float64' or
                record['shape'] != list(shapes[name]) or a.shape != shapes[name] or a.dtype != np.float64 or
                not np.isfinite(a).all() or hashlib.sha256(a.tobytes()).hexdigest() != record['sha256']):
            raise ValueError(f'model array {name} mismatch')
    if (not np.array_equal(arrays['rates'], model.writer.rates.detach().cpu().numpy()) or
            payload['writer_sha256'] != model.writer_hash or
            np.any(arrays['feature_scale'] <= 0) or np.any(arrays['query_scale'] <= 0)):
        raise ValueError('model writer/scaler mismatch')
    fit = payload['fit']
    _validate_loaded_fit(model, fit, arrays)
    model.coefficients = arrays['coefficients']
    model.feature_mean, model.feature_scale = arrays['feature_mean'].copy(), arrays['feature_scale'].copy()
    model.query_mean, model.query_scale = arrays['query_mean'].copy(), arrays['query_scale'].copy()
    model.fit_artifact = FitArtifact(**fit)
    return model


def _finite_number(value, *, minimum=0.):
    return type(value) in (int, float) and math.isfinite(value) and value >= minimum


def _validate_loaded_fit(model, fit, arrays):
    if type(fit) is not dict or set(fit) != set(FitArtifact.__dataclass_fields__):
        raise ValueError('model fit artifact schema mismatch')
    expected_rows = _validate_fit_manifest(model, fit['manifest'])
    if (not _finite_number(fit['objective']) or
            not _finite_number(fit['scaled_normal_residual']) or fit['scaled_normal_residual'] > 1e-7 or
            type(fit['row_count']) is not int or fit['row_count'] != expected_rows or
            not _finite_number(fit['elapsed_seconds']) or
            fit['failure_status'] != 'none' or fit['target_statistics'] != model.target_statistics):
        raise ValueError('model fit status/diagnostics mismatch')
    for name in _ARRAY_NAMES:
        try:
            original = np.asarray(fit[name], dtype=np.float64).reshape(arrays[name].shape)
        except (TypeError, ValueError, KeyError) as exc:
            raise ValueError(f'model fit {name} layout mismatch') from exc
        if not np.isfinite(original).all() or not np.array_equal(original, arrays[name]):
            raise ValueError(f'model fit {name} array mismatch')
    solver = fit['solver']
    if (type(solver) is not dict or set(solver) != {'method', 'ridge', 'scaled_normal_residual'} or
            solver['method'] != 'numpy.linalg.solve_fp64_normal_equations' or
            type(solver['ridge']) not in (int, float) or solver['ridge'] != model.spec.ridge or
            solver['scaled_normal_residual'] != fit['scaled_normal_residual']):
        raise ValueError('model fit solver diagnostics mismatch')
    ledger = fit['memory_ledger']
    required = {'schema_version', 'scope', 'observed_peak_chunk_rows', 'logical_arrays_bytes',
                'known_simultaneous_groups_bytes', 'unmeasured', 'gram_bytes', 'rhs_bytes',
                'max_design_chunk_bytes', 'static_bytes', 'rss_status'}
    if (type(ledger) is not dict or set(ledger) != required or ledger['schema_version'] != 2 or
            ledger['scope'] != 'known_logical_allocations_not_peak_or_rss' or
            type(ledger['observed_peak_chunk_rows']) is not int or
            not 0 < ledger['observed_peak_chunk_rows'] <= fit['row_count'] or
            ledger['rss_status'] != 'not_measured_in_source_fit'):
        raise ValueError('model fit memory ledger schema mismatch')
    logical, groups, unmeasured = (ledger[k] for k in ('logical_arrays_bytes',
                                                        'known_simultaneous_groups_bytes', 'unmeasured'))
    array_fields = {'gram', 'normal_matrix', 'ridge_identity_temporary',
                    'scaled_ridge_identity_temporary', 'gram_product_temporary', 'rhs',
                    'rhs_product_temporary', 'normal_residual_vectors', 'buffered_phi',
                    'stacked_design', 'weighted_design', 'chunk_labels_and_weights',
                    'chunk_reduction_temporaries', 'feature_query_sums_and_squares',
                    'feature_query_means_and_scales', 'max_query_basis',
                    'max_feature_standardization_vectors', 'metadata_positive_gap_values',
                    'model_static_arrays', 'artifact_coefficient_values', 'artifact_scaler_values',
                    'artifact_rate_values', 'max_advanced_snapshot_copy',
                    'max_episode_raw_features', 'max_episode_validity_masks',
                    'max_episode_writer_state', 'max_query_contract_arrays'}
    if (type(logical) is not dict or set(logical) != array_fields or
            not all(type(n) is int and n >= 0 for n in logical.values()) or
            type(groups) is not dict or set(groups) != {'query_extraction', 'chunk_flush',
                                                         'normal_construction', 'postsolve_artifact'} or
            not all(type(n) is int and n > 0 for n in groups.values()) or
            type(unmeasured) is not dict or set(unmeasured) != {'solver_workspace_bytes',
                'process_rss_bytes', 'python_object_overhead_bytes',
                'torch_kernel_temporary_bytes', 'input_episode_tensors_bytes'} or
            any(value is not None for value in unmeasured.values()) or
            ledger['gram_bytes'] != logical['gram'] or ledger['rhs_bytes'] != logical['rhs'] or
            ledger['max_design_chunk_bytes'] != logical['stacked_design'] or
            ledger['static_bytes'] != logical['model_static_arrays']):
        raise ValueError('model fit memory ledger mismatch')


def _two_age_episodes(shape: ShapeSpec, count: int, seed: int, split: str):
    """Original two-age law: independent CPU64 Uniform[-1,1], all keys."""
    from famjet.types import Episode, EventBatch, QueryBatch
    from famjet.eval.oracle import exact_targets
    generator = torch.Generator(device='cpu').manual_seed(seed)
    values = 2 * torch.rand((count, 2, shape.key_dim, shape.value_dim),
                             generator=generator, dtype=torch.float64) - 1
    ids = torch.arange(shape.key_dim, dtype=torch.int64).repeat(2)
    qkeys = torch.arange(shape.key_dim, dtype=torch.int64).repeat(4)
    key = torch.nn.functional.one_hot(ids, shape.key_dim).to(torch.float64)[None]
    qkey = torch.nn.functional.one_hot(qkeys, shape.key_dim).to(torch.float64)[None]
    starts = torch.tensor([0.] * shape.key_dim + [2.] * shape.key_dim +
                          [0.] * shape.key_dim + [0.] * shape.key_dim, dtype=torch.float64)[None]
    ends = torch.tensor([1.] * shape.key_dim + [3.] * shape.key_dim +
                        [2.] * shape.key_dim + [1.5] * shape.key_dim, dtype=torch.float64)[None]
    result = []
    for i in range(count):
        name = f'qualification-{shape.key_dim}-{split}-{i:03d}'
        n, qn = 2 * shape.key_dim, 4 * shape.key_dim
        events = EventBatch((name,), torch.arange(n)[None],
                            torch.tensor([0.] * shape.key_dim + [2.] * shape.key_dim,
                                         dtype=torch.float64)[None], ids[None], key.clone(),
                            values[i].reshape(1, n, shape.value_dim), torch.tensor([n]),
                            torch.ones((1, n), dtype=torch.bool),
                            torch.ones((1, n, shape.value_dim), dtype=torch.bool), 's')
        queries = QueryBatch((name,), torch.arange(qn)[None], torch.full((1, qn), 2., dtype=torch.float64),
                             qkeys[None], qkey.clone(),
                             (('mean',) * (2 * shape.key_dim) + ('contrast',) * (2 * shape.key_dim),),
                             starts.clone(), ends.clone(), torch.ones((1, qn), dtype=torch.bool), torch.tensor([qn]))
        oracle = exact_targets(events, queries, arithmetic_version=2)
        result.append(Episode(events, queries, oracle.target, oracle.supported,
                              {'split': split, 'target_semantics': 'observed_event_targets_v2',
                               'regime': 'two_age_uniform', 'target_valid': oracle.metadata['target_valid']}))
    return result


def _qualification_reference(model, episodes):
    """Independent augmented SVD and direct two-age state reconstruction."""
    X, y, weights = [], [], []
    max_reconstruction_error = 0.
    rates = model.writer.rates.detach().cpu().numpy()[0]
    for ep in episodes:
        state = model.encode(ep.events, mode='terminal')
        phi, valid, numeric = model.design(state, ep.queries)
        if not valid.all() or not numeric.all():
            raise ArithmeticError('qualification training read has missing numeric support')
        vdim = model.shape.value_dim
        for j, task in enumerate(ep.queries.tasks[0]):
            for v in range(vdim):
                X.append(phi[0, j, v]); y.append(float(ep.labels[0, j, v]))
                weights.append(1 / model.target_statistics['tasks'][task]['scale']**2)
        z = state.payload['z'][0, 0].detach().cpu().numpy()
        h = state.payload.get('h')
        for key in range(model.shape.key_dim):
            true_old = ep.events.values[0, key].numpy()
            true_recent = ep.events.values[0, model.shape.key_dim + key].numpy()
            if model.spec.family == 'jet':
                a = math.exp(-2 * rates[-1])
                old = h[0, 0, -1, key, :vdim].detach().cpu().numpy() / (2 * rates[-1] * a)
                recent = z[-1, key, :vdim] - a * old
            else:
                a, b = math.exp(-2 * rates[0]), math.exp(-2 * rates[-1])
                old = (z[0, key, :vdim] - z[-1, key, :vdim]) / (a - b)
                recent = z[0, key, :vdim] - a * old
            max_reconstruction_error = max(max_reconstruction_error,
                                           float(np.max(np.abs(old - true_old))),
                                           float(np.max(np.abs(recent - true_recent))))
    X, y, weights = np.stack(X), np.asarray(y), np.asarray(weights)
    weights /= weights.sum()
    augmented = np.vstack((np.sqrt(weights)[:, None] * X,
                           np.sqrt(model.spec.ridge) * np.eye(X.shape[1])))
    target = np.r_[np.sqrt(weights) * y, np.zeros(X.shape[1])]
    reference = np.linalg.lstsq(augmented, target, rcond=None)[0]
    objective = float(np.sum(weights * (X @ reference - y)**2) +
                      model.spec.ridge * np.dot(reference, reference))
    return {'method': 'numpy_lstsq_augmented_svd',
            'coefficient_max_abs_difference': float(np.max(np.abs(reference - model.coefficients))),
            'prediction_max_abs_difference': float(np.max(np.abs(X @ (reference - model.coefficients)))),
            'objective': objective, 'writer_two_age_reconstruction_max_abs_error': max_reconstruction_error,
            'design_rows': len(y), 'design_width': X.shape[1]}


def _atomic_qualification_json(path: Path, payload: dict):
    raw = canonical_json(payload)
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix='.qualification-', suffix='.json',
                                     delete=False) as tmp:
        staged = Path(tmp.name)
        tmp.write(raw); tmp.flush(); os.fsync(tmp.fileno())
    try:
        os.replace(staged, path)
    finally:
        staged.unlink(missing_ok=True)


def _run_qualification_case(shape, train_seed, fresh_seed, family, width, out):
    """One fixed case; outer helper owns the durable all-case journal."""
    name = f'{shape.key_dim}x{shape.value_dim}-{family}-q{width}'
    training = _two_age_episodes(shape, 4, train_seed, 'training')
    fresh = _two_age_episodes(shape, 32, fresh_seed, 'development_fit')
    metadata = fit_training_metadata(lambda: iter(training))
    # This exact age fixture predeclares t_ref=1 rather than its observed gap=2.
    metadata['t_ref'] = 1.
    metadata['t_ref_policy'] = 'qualification_fixed_1'
    spec = ReaderSpec('ridge_v1', family, width, 1e-10, 1 / 5224, 1, 1e-6, 1e-12)
    model = build_model(shape, spec, 1., metadata['target_statistics'])
    fit = fit_reader(model, lambda: iter(training), make_fit_manifest(model, metadata))
    reference = _qualification_reference(model, training)
    errors = {}
    for split, episodes in (('fit', training), ('fresh', fresh)):
        cells = {task: {key: [] for key in range(shape.key_dim)} for task in ('mean', 'contrast')}
        for ep in episodes:
            state = model.encode(ep.events, mode='terminal')
            result = model.read(state, ep.queries)
            if not bool(result.diagnostics['prediction_valid'].all()) or bool(result.failure.any()):
                raise ArithmeticError(f'{name} {split} numerical read failure')
            for j, task in enumerate(ep.queries.tasks[0]):
                key = int(ep.queries.key_ids[0, j])
                difference = result.prediction[0, j].numpy() - ep.labels[0, j].numpy()
                cells[task][key].extend((difference**2).tolist())
        errors[split] = {task: {str(key): float(np.mean(rows) /
                        metadata['target_statistics']['tasks'][task]['scale']**2)
                        for key, rows in group.items()} for task, group in cells.items()}
    maximum = max(value for split in errors.values() for group in split.values() for value in group.values())
    numerical_gate = (reference['prediction_max_abs_difference'] <= 1e-7 and
                      abs(reference['objective'] - fit.objective) <= 1e-8 and
                      reference['writer_two_age_reconstruction_max_abs_error'] <= 1e-12)
    ref = save_model(model, out / f'{name}.json')
    return {'fit': asdict(fit), 'reference': reference, 'normalized_mse_by_task_key': errors,
            'maximum_normalized_mse': maximum, 'numerical_gate': numerical_gate,
            'gate': maximum <= 1e-4 and numerical_gate,
            'model_file': ref.path.name, 'model_sha256': ref.sha256}


def qualify_models(out: Path):
    """Finite closed eight-case gate; persist each outcome and any exception."""
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    path = out / 'qualification.json'
    if path.exists():
        raise ValueError('existing qualification journal; use a new output directory')
    plan = [(shape, train_seed, fresh_seed, family, width)
            for shape, train_seed, fresh_seed in ((ShapeSpec(16, 8), 2026102401, 2026102403),
                                                  (ShapeSpec(12, 1), 2026102402, 2026102404))
            for family in ('jet', 'bank') for width in (8, 16)]
    cases = [{'name': f'{shape.key_dim}x{shape.value_dim}-{family}-q{width}',
              'shape': shape.to_json(), 'family': family, 'query_width': width,
              'train_seed': train_seed, 'fresh_seed': fresh_seed,
              'status': 'pending', 'gate': False} for shape, train_seed, fresh_seed, family, width in plan]
    payload = {'schema_version': 1, 'source_sha256': source_sha256(),
               'config': {'alpha_min': 1 / 5224, 'alpha_max': 1., 'ridge': 1e-10,
                          't_ref': 1., 'fresh_histories_per_shape': 32,
                          'fresh_seeds': {'16x8': 2026102403, '12x1': 2026102404}},
               'status': 'incomplete', 'all_passed': False, 'cases': cases}
    _atomic_qualification_json(path, payload)
    for index, (shape, train_seed, fresh_seed, family, width) in enumerate(plan):
        case = cases[index]
        case['status'] = 'running'
        _atomic_qualification_json(path, payload)
        try:
            result = _run_qualification_case(shape, train_seed, fresh_seed, family, width, out)
            case.update(result)
            case['status'] = 'passed' if case['gate'] else 'failed_gate'
        except Exception as exc:
            case.update(status='failed_exception', gate=False,
                        exception_type=type(exc).__name__, exception_message=str(exc))
            _atomic_qualification_json(path, payload)
            raise
        _atomic_qualification_json(path, payload)
    payload['status'] = 'passed' if all(c['gate'] for c in cases) else 'failed_gate'
    payload['all_passed'] = payload['status'] == 'passed'
    _atomic_qualification_json(path, payload)
    return payload
