"""Source-only fixed Jet4/Bank8 diagnostic wrapper, with no fitted reader.

Fallback statistics must be supplied from an already accepted training export.
This constructor does not certify their provenance or authorize an experiment.
"""
from dataclasses import fields
import math
import sys
import torch
from torch import nn
from famjet.data.schema import validate_queries
from famjet.memory.jet import JetMemory
from famjet.memory.expbank import ExpBankMemory
from famjet.memory._fixed_writer import _digest_tensor
from famjet.models._schema import training_metadata
from famjet.readers.kernel_projection import KernelProjection, _require, _fp64
from famjet.types import QueryBatch, ReadResult
from famjet.eval.state_io import validate_snapshot


class KernelReadModel(nn.Module):
    def __init__(self,kernel,ridge,fit_provenance,target_statistics,*,prior_scale=5224.):
        super().__init__()
        self._validate_kernel(kernel,prior_scale)
        self.kernel=kernel
        family='jet' if type(kernel) is JetMemory else 'bank'
        self.reader=KernelProjection(kernel.rates[0],family,kernel.t_ref,prior_scale=prior_scale,ridge=ridge)
        self._set_fallback(fit_provenance,target_statistics)

    @staticmethod
    def _validate_kernel(kernel,prior_scale):
        _require(type(kernel) in (JetMemory,ExpBankMemory) and not hasattr(kernel,'rate_source'), 'requires fixed Jet/Bank kernel')
        family='jet' if type(kernel) is JetMemory else 'bank'
        count=4 if family=='jet' else 8
        _require(_fp64(kernel.rates) and kernel.rates.shape == (1,count)
                 and kernel.key_dim == 16 and kernel.value_dim == 8
                 and (family!='bank' or not kernel.no_decay), 'requires CPU64 Jet4/Bank8 K16/V8')
        _require(type(prior_scale) in (float,int) and math.isfinite(prior_scale)
                 and prior_scale/kernel.t_ref == 5224., 'prior/time unit ratio mismatch')
        dimensionless=kernel.rates[0]*kernel.t_ref
        logs=torch.log(dimensionless)
        _require(math.isclose(dimensionless[0].item(),1/5224,rel_tol=1e-12)
                 and math.isclose(dimensionless[-1].item(),1.,rel_tol=1e-12)
                 and torch.allclose(logs[1:]-logs[:-1],torch.full((count-1,),math.log(5224)/(count-1),dtype=torch.float64),atol=1e-12,rtol=1e-12),
                 'requires full fixed caller-order log grid')

    def _set_fallback(self,provenance,statistics):
        provenance,statistics=training_metadata(provenance,statistics,8)
        _require(provenance is not None and provenance['writer_hash']==self.kernel._parameter_hash()
                 and provenance['t_ref']==self.kernel.t_ref, 'fallback training writer/time mismatch')
        _require(all(t in statistics['tasks'] and statistics['tasks'][t]['status']=='ok' for t in ('mean','contrast')),
                 'requires frozen mean/contrast training fallbacks')
        self.fit_provenance,self.target_statistics=provenance,statistics
        self.register_buffer('fallback',torch.tensor([statistics['tasks'][t]['mean'] for t in ('mean','contrast')],dtype=torch.float64))

    @classmethod
    def from_statics(cls,kernel,reader,provenance,statistics):
        obj=cls.__new__(cls); nn.Module.__init__(obj)
        _require(type(reader) is KernelProjection, 'unregistered projection reader')
        obj._validate_kernel(kernel,reader.prior_scale)
        expected=kernel.rates[0]*kernel.t_ref
        if type(kernel) is JetMemory: expected=expected.repeat_interleave(2)
        _require(reader.family==('jet' if type(kernel) is JetMemory else 'bank')
                 and reader.t_ref==kernel.t_ref and torch.equal(reader.alpha,expected), 'reader/kernel mismatch')
        obj.kernel,obj.reader=kernel,reader
        obj._set_fallback(provenance,statistics)
        return obj

    def _parameter_hash(self):
        return self.kernel._parameter_hash()

    def init_state(self,*args,**kwargs):
        return self.kernel.init_state(*args,**kwargs)

    def encode(self,*args,**kwargs):
        return self.kernel.encode(*args,**kwargs)

    def advance_copy(self,*args,**kwargs):
        return self.kernel.advance_copy(*args,**kwargs)

    def persistent_nbytes(self,state):
        validate_snapshot(state)
        return self.kernel.persistent_nbytes(state)

    def parameter_nbytes(self):
        return sum(t.numel()*t.element_size() for t in self.buffers())

    def read(self,state,queries):
        self.persistent_nbytes(state)
        _require(type(queries) is QueryBatch and set(vars(queries))=={f.name for f in fields(QueryBatch)}, 'invalid/hidden query schema')
        validate_queries(queries,state)
        _require(_fp64(queries.key_features) and queries.key_features.shape[-1]==16,'query feature precision/dimension mismatch')
        if bool(state.payload['time_unit_hash'].any()):
            _require(torch.equal(torch.stack([_digest_tensor(h) for h in queries.history_ids]),state.payload['history_hash']), 'query history identity mismatch')
        for row,present in zip(queries.tasks,queries.present.tolist()):
            _require(all(t in ('mean','contrast') for t,active in zip(row,present) if active), 'unsupported projection task')
        b,q=queries.T.shape
        prediction=torch.zeros((b,q,8),dtype=torch.float64)
        codes=torch.zeros((b,q,2),dtype=torch.int64)
        masses=torch.full((b,q,2),math.nan,dtype=torch.float64)
        bounds=torch.full_like(masses,math.nan)
        eligible=torch.zeros((b,q),dtype=torch.bool)
        quarantine=torch.zeros(b,dtype=torch.bool)
        for name in self.kernel._state_keys:
            quarantine |= ~torch.isfinite(state.payload[name]).flatten(1).all(1)
        for j in range(q):
            # Existing kernel advance preserves causal Jet cross-term and owns
            # the full temporary copy; it never updates the resumable snapshot.
            advanced=self.kernel._advance_payload(state,queries.T[:,j].tolist(),queries.present[:,j].tolist())
            for i in range(b):
                if not queries.present[i,j]: continue
                task=queries.tasks[i][j]
                prediction[i,j]=self.fallback[0 if task=='mean' else 1]
                if quarantine[i]:
                    codes[i,j,0]=1; continue
                if not state.valid[i]:
                    codes[i,j,0]=5; continue
                parts=[torch.einsum('k,jkv->jv',queries.key_features[i,j],advanced[name][i,0]) for name in self.kernel._state_keys]
                canonical=torch.stack(parts,1).flatten(0,1) if len(parts)==2 else parts[0]
                lower=queries.age_start[i,j].item()/self.kernel.t_ref
                upper=queries.age_end[i,j].item()/self.kernel.t_ref
                intervals=[(lower,upper)]
                if task=='contrast': intervals.append((upper,upper+(upper-lower)))
                values=[]
                for k,(a,z) in enumerate(intervals):
                    if not math.isfinite(a) or not math.isfinite(z) or not a<z:
                        codes[i,j,k]=7; break
                    value,diagnostic=self.reader.window(canonical[:,-1],canonical[:,:-1],a,z)
                    codes[i,j,k]=diagnostic['code']; masses[i,j,k]=diagnostic['mass']; bounds[i,j,k]=diagnostic['cancellation_bound']
                    if value is None: break
                    values.append(value)
                if len(values)==len(intervals):
                    candidate=values[0] if len(values)==1 else values[0]-values[1]
                    if bool(torch.isfinite(candidate).all()):
                        prediction[i,j]=candidate; eligible[i,j]=True
                    else: codes[i,j,len(intervals)-1]=7
        failed=queries.present & ~eligible
        return ReadResult(prediction,None,torch.full((b,q),math.nan,dtype=torch.float64),failed,dict(
            numerical_eligible=eligible,prediction_valid=eligible,numeric_supported=eligible,
            factual_support_available=torch.zeros_like(eligible),quarantined=quarantine[:,None].expand(b,q).clone(),
            failure_code=codes,reconstructed_mass=masses,cancellation_bound=bounds))

    def ownership_ledger(self):
        """All reachable Python instance/config objects and distinct tensor stores.

        Separate from packed state and wire bytes. Does not measure allocator,
        library workspace, interpreter globals or process RSS. Read temporaries
        are released, not cached. Dynamic RSS requires the later allocated probe.
        """
        from famjet.eval.isolation import export_method
        from famjet.provenance import canonical_json
        wire=export_method(self)
        seen=set(); stores={}; python_bytes=0; logical=0
        def visit(value):
            nonlocal python_bytes,logical
            if id(value) in seen: return
            seen.add(id(value)); python_bytes+=sys.getsizeof(value)
            if isinstance(value,torch.Tensor):
                logical+=value.numel()*value.element_size()
                storage=value.untyped_storage(); stores[(str(value.device),storage._cdata)]=storage.nbytes()
                if value._base is not None: visit(value._base)
            elif isinstance(value,dict):
                for k,v in value.items(): visit(k); visit(v)
            elif isinstance(value,(tuple,list,set)):
                for v in value: visit(v)
            elif isinstance(value,nn.Module): visit(vars(value))
        visit(self)
        # Payload+tensor metadata: 9216+32+32+8+8+1+8 =9305B, per batch1.
        return dict(python_bytes=python_bytes,tensor_logical_bytes=logical,tensor_storage_bytes=sum(stores.values()),
                    owned_bytes=python_bytes+sum(stores.values()),serialized_bytes=len(canonical_json(wire)),
                    per_query_delay_copy_logical_bytes=9305,additional_persistent_history_bytes=0)
