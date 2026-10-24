"""External CPU FP64 primary MLP; no TaskModel registration or history cache."""
from dataclasses import fields

import torch
from torch import nn

from famjet.data.schema import validate_queries
from famjet.eval.state_io import tensor_from_record, tensor_record
from famjet.memory._fixed_writer import _digest_tensor
from famjet.memory.jet import JetMemory
from famjet.memory.expbank import ExpBankMemory
from famjet.provenance import canonical_hash
from famjet.types import FeatureBatch, QueryBatch, ReadResult, Snapshot

from .contract import ReaderSpec, pinned_source


def _require(ok, message):
    if not ok:
        raise ValueError(message)


def _validate_kernel(kernel, spec):
    cls = JetMemory if spec.family == 'jet' else ExpBankMemory
    _, source, _ = pinned_source(spec.family)
    _require(type(kernel) is cls and not hasattr(kernel, 'rate_source'), 'requires fixed primary kernel')
    _require(kernel._parameter_hash() == source['writer_hash'] and kernel.rates.dtype == torch.float64
             and kernel.rates.device.type == 'cpu' and kernel.rates.shape == (1, 4 if spec.family == 'jet' else 8),
             'kernel hash/dtype/shape mismatch')
    _require(kernel.key_dim == 16 and kernel.value_dim == 8 and kernel.eps == 1e-8
             and kernel.support_floor == 1e-12 and kernel.t_ref == 1.
             and (spec.family != 'bank' or not kernel.no_decay), 'kernel settings mismatch')


def features(kernel, snapshot, queries, spec):
    """Current fixed-kernel advance and contraction; raw state is copied per query."""
    _require(type(spec) is ReaderSpec, 'reader spec required')
    _validate_kernel(kernel, spec)
    _require(type(snapshot) is Snapshot and type(queries) is QueryBatch
             and set(vars(queries)) == {f.name for f in fields(QueryBatch)}, 'public query/snapshot schema required')
    kernel._check_snapshot(snapshot)
    validate_queries(queries, snapshot)
    _require(queries.key_features.device.type == 'cpu' and queries.key_features.dtype == torch.float64
             and queries.key_features.shape[-1] == 16, 'query keys must be CPU FP64 K16')
    _require(all(t in ('mean', 'contrast') for row in queries.tasks for t in row), 'nonprimary task')
    if bool(snapshot.payload['time_unit_hash'].any()):
        _require(torch.equal(torch.stack([_digest_tensor(h) for h in queries.history_ids]),
                             snapshot.payload['history_hash']), 'query history identity mismatch')
    contracted = kernel.features(snapshot, queries)
    b, q = queries.T.shape
    if q == 0:
        return FeatureBatch(contracted.values.new_empty((b, 0, spec.input_dim)), contracted.supported,
                            {'failure': torch.zeros((b, 0), dtype=torch.bool, device=contracted.supported.device)})
    if spec.access == 'C':
        diag = contracted.diagnostics
        if q:
            if spec.family == 'jet':
                memory = torch.cat((diag['u'], diag['h'], diag['z'][..., None], diag['b'][..., None]), -1)
            else:
                memory = torch.cat((diag['u'], diag['z'][..., None]), -1)
            memory = memory.flatten(2)
        else:
            memory = torch.empty((b, 0, 72), dtype=torch.float64)
    else:
        rows = []
        for j in range(q):
            advanced = kernel._advance_payload(snapshot, queries.T[:, j].tolist(), queries.present[:, j].tolist())
            rows.append(torch.cat([advanced[name].flatten(1) for name in kernel._state_keys], -1))
        memory = torch.stack(rows, 1) if rows else torch.empty((b, 0, 1152), dtype=torch.float64)
    task = torch.tensor([[[float(t == 'mean'), float(t == 'contrast')] for t in row]
                         for row in queries.tasks], dtype=torch.float64).reshape(b, q, 2)
    x = torch.cat((memory, queries.key_features, task,
                   queries.age_start[..., None] / kernel.t_ref,
                   queries.age_end[..., None] / kernel.t_ref), -1)
    _require(x.shape == (b, q, spec.input_dim), 'feature width mismatch')
    failed = contracted.diagnostics['failure'] | ~torch.isfinite(x).all(-1)
    supported = contracted.supported & ~failed & queries.present
    return FeatureBatch(torch.where(torch.isfinite(x), x, torch.zeros_like(x)), supported,
                        {'failure': failed & queries.present})


class PrimaryReader(nn.Module):
    """Two SiLU hidden layers; all eight output coordinates are primary numeric."""
    def __init__(self, spec):
        super().__init__()
        _require(type(spec) is ReaderSpec, 'closed ReaderSpec required')
        self.spec = spec
        self.source = pinned_source(spec.family)[1]
        self.network = nn.Sequential(nn.Linear(spec.input_dim, spec.width, device='cpu', dtype=torch.float64), nn.SiLU(),
                                     nn.Linear(spec.width, spec.width, device='cpu', dtype=torch.float64), nn.SiLU(),
                                     nn.Linear(spec.width, 8, device='cpu', dtype=torch.float64))
        _, _, stats = pinned_source(spec.family)
        self.register_buffer('feature_mean', torch.zeros(spec.input_dim, dtype=torch.float64))
        self.register_buffer('feature_scale', torch.ones(spec.input_dim, dtype=torch.float64))
        self.register_buffer('target_mean', torch.tensor([stats['tasks'][t]['mean'] for t in ('mean', 'contrast')], dtype=torch.float64))
        self.register_buffer('target_scale', torch.tensor([[stats['tasks'][t]['scale']] for t in ('mean', 'contrast')], dtype=torch.float64))
        self.feature_fit = {'scope': 'unfitted', 'row_count': 0, 'identity_hash': None}

    def fit_feature_statistics(self, training_rows, *, provenance='unit_training'):
        """One ordered population-SD reduction for unit or fixture rows only."""
        _require(self.feature_fit['scope'] == 'unfitted', 'feature statistics already fitted')
        _require(type(training_rows) in (tuple, list), 'feature rows must be a replayable ordered sequence')
        if provenance == 'unit_training':
            scope, identity_hash = 'unit_training', None
        elif type(provenance) is dict and set(provenance) == {'scope', 'fixture_id'} and provenance['scope'] == 'fixture_only':
            _require(type(provenance['fixture_id']) is str and bool(provenance['fixture_id']), 'fixture identity required')
            scope, identity_hash = 'fixture_only', canonical_hash(provenance['fixture_id'])
        else:
            raise ValueError('explicit statistics provenance required')
        mean = torch.zeros(self.spec.input_dim, dtype=torch.float64)
        m2 = torch.zeros_like(mean)
        count = 0
        for row in training_rows:
            _require(type(row) is dict and set(row) == {'split', 'values', 'supported'} and row['split'] == 'training',
                     'explicit training rows required')
            x, supported = row['values'], row['supported']
            _require(type(x) is torch.Tensor and x.device.type == 'cpu' and x.dtype == torch.float64
                     and x.ndim == 2 and x.shape[1] == self.spec.input_dim and bool(torch.isfinite(x).all()),
                     'finite CPU FP64 feature matrix required')
            _require(type(supported) is torch.Tensor and supported.dtype == torch.bool
                     and supported.device.type == 'cpu' and supported.shape == (x.shape[0],), 'supported mask mismatch')
            for v in x[supported]:
                count += 1
                delta = v-mean
                mean += delta/count
                m2 += delta*(v-mean)
        _require(count > 0, 'feature fit row count mismatch')
        scale = torch.sqrt(torch.clamp(m2/count, min=0.))
        scale = torch.where(scale == 0, torch.ones_like(scale), scale)
        _require(bool(torch.isfinite(mean).all()) and bool(torch.isfinite(scale).all()), 'nonfinite statistics')
        self.feature_mean.copy_(mean)
        self.feature_scale.copy_(scale)
        self.feature_fit = {'scope': scope, 'row_count': count, 'identity_hash': identity_hash}
        return mean.clone(), scale.clone()

    def read(self, kernel, snapshot, queries):
        batch = features(kernel, snapshot, queries, self.spec)
        _require(all(p.dtype == torch.float64 and p.device.type == 'cpu' and bool(torch.isfinite(p).all())
                     for p in self.parameters()), 'reader weights must be finite CPU FP64')
        _require(all(x.dtype == torch.float64 and x.device.type == 'cpu' and bool(torch.isfinite(x).all())
                     for x in (self.feature_mean, self.feature_scale, self.target_mean, self.target_scale))
                 and bool((self.feature_scale > 0).all()) and bool((self.target_scale > 0).all()),
                 'invalid frozen statistics')
        normalized = (batch.values - self.feature_mean) / self.feature_scale
        numeric = self.network(normalized)
        task = torch.tensor([[0 if t == 'mean' else 1 for t in row] for row in queries.tasks], dtype=torch.int64)
        prediction = numeric*self.target_scale[task] + self.target_mean[task]
        finite = torch.isfinite(prediction).all(-1)
        prediction = torch.where(finite[..., None], prediction, torch.zeros_like(prediction))
        valid = batch.supported & finite & ~batch.diagnostics['failure']
        failure = queries.present & (~valid | batch.diagnostics['failure'])
        return ReadResult(prediction, None, valid.to(torch.float64), failure,
                          {'numeric_supported': batch.supported, 'prediction_valid': valid,
                           'failure': failure})

    def export_static(self, *, require_production=False):
        _require(type(require_production) is bool and not require_production,
                 'production static export awaits verified original-training row binding')
        _require(self.source == pinned_source(self.spec.family)[1], 'source identity mismatch')
        _, _, stats = pinned_source(self.spec.family)
        _require(torch.equal(self.target_mean, torch.tensor([stats['tasks'][t]['mean'] for t in ('mean', 'contrast')], dtype=torch.float64))
                 and torch.equal(self.target_scale, torch.tensor([[stats['tasks'][t]['scale']] for t in ('mean', 'contrast')], dtype=torch.float64)),
                 'frozen target statistics mismatch')
        _require(set(self.feature_fit) == {'scope', 'row_count', 'identity_hash'} and self.feature_fit['scope'] in
                 ('unfitted', 'unit_training', 'fixture_only'), 'fit provenance mismatch')
        _require(all(x.dtype == torch.float64 and x.device.type == 'cpu' and bool(torch.isfinite(x).all())
                     for x in self.state_dict().values()) and bool((self.feature_scale > 0).all()),
                 'static tensors must be finite CPU FP64')
        return {'schema_version': 1, 'spec': {'family': self.spec.family, 'access': self.spec.access,
                                              'width': self.spec.width}, 'source': dict(self.source),
                'feature_fit': dict(self.feature_fit),
                'weights': {k: tensor_record(v) for k, v in self.state_dict().items()}}

    @classmethod
    def from_static(cls, static, *, require_production=False):
        _require(type(require_production) is bool and not require_production,
                 'production static load awaits verified original-training row binding')
        _require(type(static) is dict and set(static) == {'schema_version', 'spec', 'source', 'feature_fit', 'weights'}
                 and static['schema_version'] == 1, 'reader static schema mismatch')
        s = static['spec']
        _require(type(s) is dict and set(s) == {'family', 'access', 'width'}, 'reader spec schema mismatch')
        spec = ReaderSpec(**s)
        obj = cls(spec)
        _require(static['source'] == obj.source, 'frozen source identity mismatch')
        fit = static['feature_fit']
        _require(type(fit) is dict and set(fit) == {'scope', 'row_count', 'identity_hash'}
                 and fit['scope'] in ('unfitted', 'unit_training', 'fixture_only')
                 and type(fit['row_count']) is int and 0 <= fit['row_count'] <= 6144
                 and ((fit['scope'] == 'unfitted') == (fit['row_count'] == 0))
                 and (fit['scope'] not in ('unfitted', 'unit_training') or fit['identity_hash'] is None)
                 and (fit['scope'] != 'fixture_only' or (type(fit['identity_hash']) is str
                      and len(fit['identity_hash']) == 64)), 'feature fit provenance mismatch')
        state = obj.state_dict()
        _require(type(static['weights']) is dict and set(static['weights']) == set(state), 'weight inventory mismatch')
        tensors = {k: tensor_from_record(v) for k, v in static['weights'].items()}
        _require(all(v.dtype == torch.float64 and v.device.type == 'cpu' and v.shape == state[k].shape
                     and bool(torch.isfinite(v).all()) for k, v in tensors.items()), 'weight dtype/shape/finite mismatch')
        _require(torch.equal(tensors['target_mean'], obj.target_mean)
                 and torch.equal(tensors['target_scale'], obj.target_scale)
                 and bool((tensors['feature_scale'] > 0).all()), 'frozen statistics mismatch')
        obj.load_state_dict(tensors, strict=True)
        obj.feature_fit = dict(fit)
        return obj
