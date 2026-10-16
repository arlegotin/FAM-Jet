"""Shared snapshot protocol for fixed linear temporal columns.

Each column bank has a coupled Leg-T generator; injection may be signed.
Subclasses own construction, allocation, basis identity and static hashing.
"""
import math
import time
import torch
from famjet.data.schema import validate_events
from famjet.eval.oracle import exact_time_difference
from famjet.memory._fixed_writer import SnapshotMemory, _require, _finite
from famjet.types import FeatureBatch


class LinearCoefficientMemory(SnapshotMemory):
    _state_keys = ('p',)

    @property
    def reference_tensor(self):
        return self.injection

    @property
    def coefficient_count(self):
        return sum(self.orders)

    @property
    def feature_dim(self):
        return self.coefficient_count*(self.value_dim+1)

    def _zero_payload(self, z):
        return {'p': z}

    def _raw(self, events):
        validate_events(events)
        _require(events.normalization == 'shared', 'polynomial raw writer requires shared normalization')
        _require(events.key_features.dtype == events.values.dtype == self.injection.dtype
                 and events.values.device == self.injection.device, 'raw tensors must match polynomial device/dtype')
        _require(not ('gate' in events.auxiliary and 'gates' in events.auxiliary), 'provide gate or gates, not both')
        gate = events.auxiliary.get('gate', events.auxiliary.get('gates', torch.ones_like(events.values[...,0])))
        if gate.shape == (*events.values.shape[:2],1): gate=gate[...,0]
        _require(gate.shape == events.values.shape[:2] and gate.device == self.injection.device, 'raw gate layout mismatch')
        gate=gate.to(self.injection)
        _finite(gate, 'raw gate')
        return gate*events.validation.write_mask.to(gate.dtype)

    def preparation_cost(self, gaps):
        """Deterministic work inventory; no counters or arbitrary-gap memoization."""
        uncached = sum(float(g) != 0 and float(g) not in self.declared_gaps for g in gaps)
        return dict(cpu_fp64_exponentials=uncached*len(self.orders),
                    matrix_cubic_work=uncached*sum(n**3 for n in self.orders),
                    cache_bytes=sum(getattr(self,f'gap_bank_{i}').numel()*self.injection.element_size() for i in range(len(self.orders))),
                    construction_exponentials=sum(g != 0 for g in self.declared_gaps)*len(self.orders))

    def call_preparation_cost(self, events, queries, *, mode, reader_kind):
        """Exact fresh-encode + feature-read preparation work, without executing.

        Padding/no-write rows and the duplicate full-reader advance are included.
        Recompute may repeat this forward work during backward; trainer labels
        this inventory as forward-only and wall time includes all preparation.
        """
        _require(mode in {'stream','terminal'}, 'invalid encoding mode')
        times, lengths = events.timestamps.tolist(), events.lengths.tolist()
        b,n = events.values.shape[:2]
        gaps=[]
        for i,length in enumerate(lengths):
            if mode == 'terminal':
                gaps.append(0.)  # advance the empty prior
            for j in range(n):
                if j >= length or (mode == 'stream' and j == 0): gap=0.
                else:
                    gap=float(exact_time_difference(times[i][length-1],times[i][j]) if mode == 'terminal'
                              else exact_time_difference(times[i][j],times[i][j-1]))
                gaps.append(gap)
        encode_count=len(gaps)
        qgaps=[]
        for i,(row,present) in enumerate(zip(queries.T.tolist(),queries.present.cpu().tolist())):
            for t,yes in zip(row,present):
                qgaps.append(float(exact_time_difference(t,times[i][lengths[i]-1])) if yes and lengths[i] else 0.)
        qgaps=qgaps*(2 if reader_kind == 'generic_full' else 1)
        return {**self.preparation_cost(gaps+qgaps),'encode_advances':encode_count,
                'query_advances':len(qgaps),'scope':'fresh_encode_and_features_forward_only'}

    def prepare_transition(self, gap):
        """Explicit host preparation boundary; returns matrices and local cost."""
        from famjet.memory.hippo import impulse_transition, legendre_generator
        _require(type(gap) in (int,float) and math.isfinite(gap) and gap >= 0, 'invalid elapsed gap')
        start=time.perf_counter()
        if gap in self.declared_gaps:
            index=self.declared_gaps.index(gap)
            matrices=tuple(getattr(self,f'gap_bank_{i}')[index] for i in range(len(self.orders)))
        else:
            matrices=tuple(torch.tensor(impulse_transition(legendre_generator(n)[0],gap,tau),
                dtype=self.injection.dtype, device=self.injection.device) for n,tau in zip(self.orders,self.taus))
        return matrices, {**self.preparation_cost([gap]), 'host_preparation_seconds':time.perf_counter()-start}

    def _propagate(self, core, gaps):
        rows=[]
        for row,gap in enumerate(gaps):
            matrices,_=self.prepare_transition(gap)
            parts=[]; offset=0
            for n,E in zip(self.orders,matrices):
                parts.append((E @ core['p'][row,0,offset:offset+n].flatten(1)).reshape(n,self.key_dim,self.value_dim+1))
                offset+=n
            rows.append(torch.cat(parts,0))
        return {'p':torch.stack(rows)[:,None]}

    def _encode_core(self, events, core, gates, times, lengths, last, valid, first_gaps, mode):
        b,n,_=events.values.shape
        aug=torch.cat((events.values,torch.ones_like(events.values[...,:1])),-1)
        if mode == 'stream':
            for j in range(n):
                gaps=[first_gaps[i] if j == 0 else float(exact_time_difference(times[i][j],times[i][j-1]))
                      if j < lengths[i] else 0. for i in range(b)]
                core=self._propagate(core,gaps)
                X=gates[:,j,None,None]*events.key_features[:,j,:,None]*aug[:,j,None,:]
                core={'p':core['p']+self.injection[None,None,:,None,None]*X[:,None,None]}
            return core
        # Exact terminal linear contraction in bounded event chunks. Coefficient
        # weights are constant; gradients reach every key/value/gate, including
        # causal learned writers, without recurrent/truncated backpropagation.
        gaps=[float(exact_time_difference(times[i][length-1],last[i])) if length and valid[i] else 0.
              for i,length in enumerate(lengths)]
        result=self._propagate(core,gaps)['p']
        for start in range(0,n,self.chunk_size):
            end=min(start+self.chunk_size,n)
            rows=[]
            for i,length in enumerate(lengths):
                weights=[]
                for j in range(start,end):
                    age=float(exact_time_difference(times[i][length-1],times[i][j])) if j < length else 0.
                    matrices,_=self.prepare_transition(age)
                    parts=[]; offset=0
                    for order,E in zip(self.orders,matrices):
                        parts.append(E @ self.injection[offset:offset+order]); offset+=order
                    weights.append(torch.cat(parts))
                rows.append(torch.stack(weights))
            W=torch.stack(rows)*gates[:,start:end,None]
            weighted_keys=W[:,:,:,None]*events.key_features[:,start:end,None,:]
            result=result+torch.einsum('bnck,bnv->bckv',weighted_keys,aug[:,start:end])[:,None]
        return {'p':result}

    def _contract(self, payload, query_features):
        _finite(query_features,'query_features')
        _require(query_features.dtype == self.injection.dtype and query_features.device == self.injection.device,
                 'query features must match polynomial device/dtype')
        coefficients=torch.einsum('bqk,bhckv->bqhcv',query_features,payload['p'])*self.t_ref
        finite=torch.isfinite(coefficients).all(dim=(-1,-2,-3))
        # Finite zero/signed coefficients are numerically usable. This flag is
        # NOT factual key/window support, learned abstention, or positive mass.
        return FeatureBatch(coefficients.flatten(2),finite,{'coefficients':coefficients,'failure':~finite})

    def read(self, state, queries):
        return self.features(state,queries)
