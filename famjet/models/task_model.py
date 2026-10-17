"""Causal trainable writer/readers around bounded temporal snapshots.

Fixed writers preserve raw public keys, values and auxiliary gates (default1).
Learned maps are event-local, rate-independent and preserve state dimensions.
Task12 owns optimizers/run lifecycle; Task17 owns failure-complete scoring.
"""
from dataclasses import asdict, replace
import math
import statistics
import torch
from torch import nn
from famjet.config import RunConfig
from famjet.data.schema import validate_events, validate_queries
from famjet.eval.metrics import fit_target_statistics
from famjet.eval.oracle import BINARY_TASKS, CATEGORICAL_TASKS, exact_time_difference
from famjet.memory.delta import DeltaMixer
from famjet.memory.jet import JetMemory
from famjet.memory.hippo import PolynomialMemory
from famjet.memory.multiscale import MultiscaleMemory
from famjet.memory.expbank import ExpBankMemory
from famjet.provenance import canonical_hash
from famjet.readers.structured import TASK_ORDER, memory_inputs, query_inputs, input_width, validate_reader_schema
from famjet.types import FeatureBatch, ReadResult
from famjet.models._schema import inference_config, training_metadata


class CausalWriter(nn.Module):
    """Signed affine values; softplus affine keys/gate, current event only."""
    def __init__(self, key_dim, value_dim):
        super().__init__()
        self.value = nn.Linear(value_dim, value_dim)
        self.key = nn.Linear(key_dim, key_dim)
        self.gate = nn.Linear(key_dim+value_dim, 1)

    def forward(self, events):
        validate_events(events)
        if events.normalization != 'shared':
            raise ValueError('learned writer requires shared normalization')
        raw_gate = events.auxiliary.get('gate', events.auxiliary.get('gates'))
        if 'gate' in events.auxiliary and 'gates' in events.auxiliary:
            raise ValueError('provide gate or gates, not both')
        gate = torch.nn.functional.softplus(self.gate(torch.cat((events.key_features, events.values), -1))).squeeze(-1)
        if raw_gate is not None:
            gate = gate * raw_gate.reshape(gate.shape)
        auxiliary = {k: v for k, v in events.auxiliary.items() if k not in {'gate', 'gates'}}
        return replace(events, key_features=torch.nn.functional.softplus(self.key(events.key_features)),
                       values=self.value(events.values), auxiliary={**auxiliary, 'gate': gate})


class TaskModel(nn.Module):
    def __init__(self, kernel: nn.Module, reader: nn.Module, config: RunConfig, *, _frozen_rates=False):
        if type(kernel) not in (JetMemory, ExpBankMemory, PolynomialMemory, MultiscaleMemory, DeltaMixer):
            raise ValueError('TaskModel requires registered memory kernel')
        family = kernel.reader_feature_spec['family']
        m, d = config.model, config.data
        if m.method != family or m.heads != (kernel.heads if family=='delta' else 1) or m.K != kernel.key_dim or d.value_dim != kernel.value_dim:
            raise ValueError('kernel/config dimensions or family mismatch')
        if str(kernel.reference_tensor.dtype).split('.')[-1] != m.precision:
            raise ValueError('kernel/config precision mismatch')
        if m.interpolation or m.probes != 1 or m.reader.activation != 'silu':
            raise ValueError('unsupported TaskModel interpolation/probes/activation')
        if family == 'delta':
            if m.writer != 'native_delta' or any(getattr(kernel,k) != v for k,v in asdict(m.delta).items()):
                raise ValueError('delta allocation/writer mismatch')
        elif family == 'multiscale':
            if kernel.cache_limit_bytes != config.resources.cache_limit_bytes:
                raise ValueError('multiscale cache allowance/config mismatch')
            if any(getattr(kernel,k) != getattr(m.multiscale,k) for k in ('order','scale_order','epsilon','tau0','declared_gaps')):
                raise ValueError('multiscale allocation/config mismatch')
        elif family == 'polynomial':
            if kernel.cache_limit_bytes != config.resources.cache_limit_bytes:
                raise ValueError('polynomial cache allowance/config mismatch')
            if kernel.orders != m.polynomial.orders or kernel.taus != m.polynomial.taus or kernel.declared_gaps != m.polynomial.declared_gaps:
                raise ValueError('polynomial allocation/config mismatch')
        elif m.J != kernel.coefficient_count:
            raise ValueError('kernel/config anchor mismatch')
        expected = kernel.reader_feature_spec
        if reader.schema is None or reader.schema['feature_spec'] != expected or reader.schema['kind'] != m.reader.kind:
            raise ValueError('reader/config schema mismatch')
        if reader.width != m.reader.width or reader.hidden_layers != m.reader.layers:
            raise ValueError('reader/config architecture mismatch')
        if input_width(m.reader.kind, expected, dict(key_dim=m.K)) != reader.input_dim:
            raise ValueError('reader input width mismatch')
        if family not in {'polynomial','multiscale','delta'} and (kernel.eps != m.epsilon or kernel.support_floor != m.numerical_support_floor):
            raise ValueError('kernel/config support policy mismatch')
        self._initialize(kernel, reader, {'schema_version': 1, 'writer': m.writer,
                         'rate_mode': 'fixed' if m.rates is None else m.rates.mode}, _frozen_rates)

    @classmethod
    def _from_inference(cls, kernel, reader, schema, *, _frozen_rates=False):
        """Strict worker construction without inventing/retaining a RunConfig."""
        model = cls.__new__(cls)
        model._initialize(kernel, reader, schema, _frozen_rates)
        return model

    def _initialize(self, kernel, reader, schema, frozen_rates):
        nn.Module.__init__(self)
        self.inference_config = inference_config(schema)
        if type(kernel) not in (JetMemory, ExpBankMemory, PolynomialMemory, MultiscaleMemory, DeltaMixer):
            raise ValueError('TaskModel requires registered memory kernel')
        from famjet.readers.mlp import NumericReader
        if type(reader) is not NumericReader or reader.schema is None:
            raise ValueError('TaskModel requires registered reader schema')
        validate_reader_schema(reader.schema)
        expected = kernel.reader_feature_spec
        if reader.schema['feature_spec'] != expected or input_width(reader.schema['kind'], expected,
                reader.schema['query_spec']) != reader.input_dim:
            raise ValueError('reader/kernel schema mismatch')
        if (type(kernel) is DeltaMixer) != (self.inference_config['writer']=='native_delta'):
            raise ValueError('native delta writer/kernel mismatch')
        learned = hasattr(kernel, 'rate_source')
        mode = self.inference_config['rate_mode']
        if type(frozen_rates) is not bool or (frozen_rates and (mode != 'learned' or learned)):
            raise ValueError('invalid inference frozen-rate marker')
        if not frozen_rates and learned != (mode == 'learned'):
            raise ValueError('kernel/config rate mode mismatch')
        self._frozen_rates = frozen_rates
        self.kernel, self.reader = kernel, reader
        learned_writer = self.inference_config['writer'] == 'learned'
        self.writer = CausalWriter(kernel.key_dim, kernel.value_dim).to(kernel.reference_tensor) if learned_writer else None
        self.query_map = nn.Linear(kernel.key_dim, kernel.key_dim).to(kernel.reference_tensor) if learned_writer else None
        self.fit_provenance = None
        self.target_statistics = None
        self.register_buffer('target_mean', kernel.reference_tensor.new_zeros((len(TASK_ORDER), kernel.value_dim)))
        self.register_buffer('target_scale', kernel.reference_tensor.new_ones((len(TASK_ORDER), 1)))

    def validate_metadata(self):
        """Called by static export and direct ledger inspection, before copying."""
        inference_config(self.inference_config)
        validate_reader_schema(self.reader.schema)
        return training_metadata(self.fit_provenance, self.target_statistics, self.kernel.value_dim)

    def _parameter_hash(self):
        if self.writer is None:
            return self.kernel._parameter_hash()
        # Numeric byte records preserve dtype and represented bits; no graph is retained.
        from famjet.eval.state_io import tensor_record
        return canonical_hash({'kernel': self.kernel._parameter_hash(), 'writer': 'affine-value-softplus-key-gate-v1',
                               'weights': {k: tensor_record(v) for k, v in self.writer.state_dict().items()}})

    def _kernel_state(self, state):
        if state.parameter_hash != self._parameter_hash():
            raise ValueError('snapshot writer/rate parameter hash mismatch')
        return replace(state, parameter_hash=self.kernel._parameter_hash())

    def init_state(self, batch_size, *, device, dtype):
        return replace(self.kernel.init_state(batch_size, device=device, dtype=dtype), parameter_hash=self._parameter_hash())

    def encode(self, events, state=None, *, mode='stream'):
        if self._frozen_rates:
            raise ValueError('frozen represented rates are inference-read-only')
        prior = None if state is None else self._kernel_state(state)
        written = events if self.writer is None else self.writer(events)
        return replace(self.kernel.encode(written, prior, mode=mode), parameter_hash=self._parameter_hash())

    def advance_copy(self, state, query_time):
        return replace(self.kernel.advance_copy(self._kernel_state(state), query_time), parameter_hash=self._parameter_hash())

    def features(self, state, queries):
        state = self._kernel_state(state)
        validate_queries(queries, state)
        if self.query_map is not None:
            queries = replace(queries, key_features=torch.nn.functional.softplus(self.query_map(queries.key_features)))
        f = self.kernel.features(state, queries)
        kind = self.reader.schema['kind']
        if queries.T.shape[1] == 0:
            return FeatureBatch(f.values.new_empty((*queries.T.shape, self.reader.input_dim)), f.supported,
                                {'failure': torch.zeros_like(f.supported)})
        full = None
        if kind == 'generic_full':
            rows = []
            for j in range(queries.T.shape[1]):
                payload = self.kernel._advance_payload(state, queries.T[:, j].tolist(), queries.present[:, j].cpu().tolist())
                rows.append(torch.cat([payload[k].flatten(1) for k in self.kernel._state_keys], -1))
            width = len(self.kernel._state_keys)*self.kernel.coefficient_count*self.kernel.key_dim*(self.kernel.value_dim+1)
            full = torch.stack(rows, 1) if rows else f.values.new_empty((state.last_time.numel(), 0, width))
        if full is not None and type(self.kernel) in (PolynomialMemory,MultiscaleMemory):
            full = full*self.kernel.t_ref
        memory = memory_inputs(kind, f, full)
        # Zero derived normalized values only where undefined; raw controls retain amplitude.
        if kind in {'structured', 'bank_normalized', 'fixed_scale'} or kind.startswith('fixed_scale:'):
            memory = torch.where(torch.isfinite(memory), memory, torch.zeros_like(memory))
        inputs = torch.cat((memory, query_inputs(queries, self.kernel.t_ref)), -1)
        failed = f.diagnostics.get('failure', torch.zeros_like(f.supported)) | ~torch.isfinite(inputs).all(-1)
        return FeatureBatch(torch.where(torch.isfinite(inputs), inputs, torch.zeros_like(inputs)), f.supported,
                            {**f.diagnostics, 'failure': failed})

    def read(self, state, queries):
        f = self.features(state, queries)
        numeric, support_logit = self.reader(f.values)
        active = {t for row, mask in zip(queries.tasks, queries.present.cpu().tolist()) for t, yes in zip(row, mask) if yes}
        families = {'binary' if t in BINARY_TASKS else 'categorical' if t in CATEGORICAL_TASKS else 'numeric' for t in active}
        if len(families) > 1:
            raise ValueError('tasks must have a homogeneous output family')
        family = next(iter(families), 'numeric')
        ids = torch.tensor([[TASK_ORDER.index('contrast' if t == 'change_sign' else t) if t in TASK_ORDER else 0
                             for t in row] for row in queries.tasks], device=numeric.device).reshape(queries.T.shape).long()
        continuous = numeric*self.target_scale[ids] + self.target_mean[ids]
        sign_mask = torch.tensor([[t == 'change_sign' for t in row] for row in queries.tasks], device=numeric.device, dtype=torch.bool).reshape(queries.T.shape)
        prediction = torch.where(sign_mask[..., None], torch.sign(continuous), continuous)
        logits = None
        if family == 'binary':
            prediction = torch.sigmoid(support_logit)[..., None]
        elif family == 'categorical':
            if self.kernel.value_dim != 32:
                raise ValueError('categorical arms require V32 logits')
            logits, prediction = numeric, None
        finite = torch.isfinite(logits if logits is not None else prediction).all(-1) & torch.isfinite(support_logit)
        failed = queries.present & (f.diagnostics['failure'] | ~finite)
        supported = f.supported if family != 'binary' and self.reader.schema['kind'] != 'query_only' else torch.ones_like(f.supported)
        valid = queries.present & supported & ~failed
        return ReadResult(prediction, logits, torch.sigmoid(support_logit), failed, {
            **f.diagnostics, 'numeric_supported': f.supported, 'prediction_valid': valid,
            'support_logit': support_logit, 'continuous_prediction': continuous,
        })

    def forward(self, events, queries, *, encode_mode):
        return self.read(self.encode(events, mode=encode_mode), queries)

    def persistent_nbytes(self, state):
        return self.kernel.persistent_nbytes(self._kernel_state(state))

    def parameter_nbytes(self):
        return sum(t.numel()*t.element_size() for t in (*self.parameters(), *self.buffers()))

    def loss(self, result, episode):
        """Query-pooled training plumbing; not evaluation/fallback aggregation.

        Training validity comes from available target labels, never predicted
        support. Sign labels cannot train contrast: pass the continuous contrast
        task/labels instead. Task12 owns batching/weighting/optimization.
        """
        q = episode.queries
        active = {t for row, mask in zip(q.tasks, q.present.cpu().tolist()) for t, yes in zip(row, mask) if yes}
        if 'change_sign' in active:
            raise ValueError('train with continuous contrast targets; sign is evaluation-only')
        valid = q.present if active <= BINARY_TASKS else q.present & episode.supported.to(q.present.device)
        if not bool(valid.any()):
            raise ValueError('no valid training targets')
        if active <= BINARY_TASKS:
            return nn.functional.binary_cross_entropy_with_logits(result.diagnostics['support_logit'][valid],
                episode.labels.to(result.support).reshape(q.T.shape)[valid])
        if active <= CATEGORICAL_TASKS:
            return nn.functional.cross_entropy(result.logits[valid], episode.labels.to(result.logits.device)[valid].long())
        ids = torch.tensor([[TASK_ORDER.index(t) if t in TASK_ORDER else 0 for t in row] for row in q.tasks],
                           device=result.prediction.device).reshape(q.T.shape).long()
        residual = (result.prediction-episode.labels.to(result.prediction))/self.target_scale[ids]
        return residual[valid].square().mean()

    def fit_statistics(self, episodes, *, reference_duration=None):
        """Explicit training-only fit; never called by encode/read.

        Constant features use unit scale. Constant target tasks retain scale=None
        in the metric provenance and use1 solely as an invertible output transform.
        A writer/rate update does not refit these frozen preprocessing buffers.
        """
        if self._frozen_rates:
            raise ValueError('frozen represented rates are inference-read-only')
        # A repeatable external factory bounds raw-history memory. List callers
        # retain their original API; both paths use the same ordered reductions.
        streaming = callable(episodes)
        if streaming:
            factory = episodes
        else:
            episodes = tuple(episodes)
            factory = lambda: iter(episodes)
        from famjet.data.synthetic import batch_hash, batch_hash_tensor
        def identity(ep):
            return canonical_hash({'events': batch_hash(ep.events), 'queries': batch_hash(ep.queries),
                'labels': batch_hash_tensor(ep.labels), 'supported': batch_hash_tensor(ep.supported),
                'metadata': ep.metadata})
        gaps, histories, identities = [], [], []
        def target_pass():
            for ep in factory():
                if ep.metadata.get('split') != 'training':
                    raise ValueError('statistics require explicit nonempty training split')
                validate_events(ep.events)
                histories.extend(ep.events.history_ids)
                if streaming: identities.append(identity(ep))
                for row, length in zip(ep.events.timestamps.tolist(), ep.events.lengths.tolist()):
                    gaps.extend(float(exact_time_difference(row[i], row[i-1])) for i in range(1, length)
                                if exact_time_difference(row[i], row[i-1]) > 0)
                yield ep
            if not histories: raise ValueError('statistics require explicit nonempty training split')
        targets = fit_target_statistics(target_pass())
        if not gaps and (type(reference_duration) not in (int, float) or not math.isfinite(reference_duration) or reference_duration <= 0):
            raise ValueError('no positive training gap: explicit positive reference duration required')
        reference = statistics.median(gaps) if gaps else float(reference_duration)
        previous = self.kernel.t_ref
        # Feature construction needs the proposed t_ref, but a rejected fit must
        # leave the existing model's output transform unchanged.
        try:
            self.kernel.t_ref = reference
            with torch.no_grad():
                rows = []
                count = 0
                for count, ep in enumerate(factory(), 1):
                    if streaming and (count > len(identities) or identity(ep) != identities[count-1]):
                        raise ValueError('repeatable statistics stream changed between passes')
                    features = self.features(self.encode(ep.events, mode='terminal'), ep.queries)
                    if bool(features.diagnostics['failure'][ep.queries.present].any()):
                        raise ValueError('cannot fit failed training features')
                    rows.append(features.values[ep.queries.present])
                if streaming and count != len(identities):
                    raise ValueError('repeatable statistics stream changed length between passes')
                x = torch.cat(rows, 0)
                if x.shape[0] == 0:
                    raise ValueError('feature statistics require training queries')
                mean = x.mean(0)
                scale = x.std(0, correction=0)
                scale = torch.where(scale > 0, scale, torch.ones_like(scale))
                if not bool(torch.isfinite(mean).all() & torch.isfinite(scale).all()):
                    raise ValueError('nonfinite training feature statistics')
                target_mean = torch.zeros_like(self.target_mean)
                target_scale = torch.ones_like(self.target_scale)
                for task, record in targets['tasks'].items():
                    if task in BINARY_TASKS | CATEGORICAL_TASKS or task == 'change_sign' or record['status'] != 'ok':
                        continue
                    if len(record['mean']) != self.kernel.value_dim:
                        raise ValueError('target dimension mismatch')
                    index = TASK_ORDER.index(task)
                    target_mean[index].copy_(target_mean.new_tensor(record['mean']))
                    target_scale[index].fill_(record['scale'] or 1.)
            provenance = {'split': 'training',
                'history_identity_hash': canonical_hash(histories),
                'history_count': len(histories),
                't_ref': reference, 'reference_source': 'median_positive_training_gap' if gaps else 'explicit_duration',
                'feature_rows': x.shape[0], 'writer_hash': self._parameter_hash(), 'target_hash': canonical_hash(targets)}
            provenance, targets = training_metadata(provenance, targets, self.kernel.value_dim)
        except Exception:
            self.kernel.t_ref = previous
            raise
        with torch.no_grad():
            self.reader.feature_mean.copy_(mean)
            self.reader.feature_scale.copy_(scale)
            self.target_mean.copy_(target_mean)
            self.target_scale.copy_(target_scale)
        self.target_statistics = targets
        self.fit_provenance = provenance
