"""Independent ordinary-tensor delta equations and explicit deferred-query adaptation.

GDN-2 arXiv:2605.22791v1; inspected repository de8476de0fecae08fc16f0bf3154900244c61c73.
That repository's Source Code License-NC limits research/evaluation use; this
attribution is not legal clearance. No external source/kernel is vendored.
"""
import math
import torch
from torch import nn
from torch.nn import functional as F
from famjet.memory._fixed_writer import SnapshotMemory, _require, _finite, _pack_times, _digest_tensor
from famjet.data.schema import validate_events, validate_queries
from famjet.eval.oracle import exact_time_difference
from famjet.provenance import canonical_hash
from famjet.types import FeatureBatch
from famjet.readers.structured import QUERY_TASK_ORDER, query_inputs


def delta_step(state, k, v, alpha, b, w):
    """Post-decay erase followed by independent write; k is already normalized."""
    decayed=alpha[...,None]*state
    erased=(decayed*(b*k)[...,None]).sum(-2)
    return decayed+k[...,None]*(w*v-erased)[...,None,:]


def _guard_statistics(k,b,g):
    n=k.square().sum(-1,keepdim=True)
    a=(b*k.square()).sum(-1,keepdim=True)
    nu=(b.square()*k.square()).sum(-1,keepdim=True)
    r2=(n*nu-a.square()).clamp_min(0)
    c2=torch.exp(-2*g.amax(-1,keepdim=True))
    R=((c2-1)*(1-(1-a).square()/c2)).clamp_min(0)
    return n,a,nu,r2,R


def _guard_recheck(k,candidate,g,mu):
    """Second-pass storage-value validation; scalar fallback preserves raw mean."""
    n,a,nu,r2,R=_guard_statistics(k,candidate,g)
    tolerance=4*torch.finfo(candidate.dtype).eps*(n*nu+a.square())
    return torch.where((n>1e-20)&(r2>R+tolerance),mu.expand_as(candidate),candidate).to(candidate.dtype)


def guard_erase(k,b,g):
    """Pinned guard mathematics, storage quantization/recheck, identity b STE.

    All projection decisions are detached, including k/g. Strong decay may
    overflow c2 to infinity, which correctly makes the boundary nonbinding.
    Native FP32 arithmetic is the production convention; FP64 is the oracle.
    """
    with torch.no_grad():
        key=k.detach(); raw=b.detach(); log_decay=g.detach()
        n,a,nu,r2,R=_guard_statistics(key,raw,log_decay)
        mu=a/n.clamp_min(1e-20)
        eta=((31/32)*R/r2.clamp_min(1e-30)).sqrt().clamp(0,1)
        candidate=torch.where((n>1e-20)&(r2>R),mu+eta*(raw-mu),raw).to(b.dtype)
        candidate=_guard_recheck(key,candidate,log_decay,mu)
    # This ordering preserves candidate bits as well as the identity gradient.
    return candidate+(b-b.detach())


def normalize_key(x):
    return x/(x.square().sum(-1,keepdim=True)+1e-6).sqrt()


def validate_delta(dim,heads,head_key_dim,head_value_dim,conv_length,variant,decay_policy,erase_policy,allow_neg_eigval):
    for name,n,limit in [('dim',dim,2048),('heads',heads,32),('head_key_dim',head_key_dim,256),
                         ('head_value_dim',head_value_dim,256),('conv_length',conv_length,16)]:
        _require(type(n) is int and 1<=n<=limit,f'invalid delta {name}')
    _require(type(variant) is str and variant in {'gdn2','kda','gdn'},'invalid delta variant')
    _require(type(decay_policy) is str and decay_policy=='raw_per_observed_event','unsupported delta decay policy')
    _require(type(erase_policy) is str and erase_policy in {'raw_paper','pinned_guarded'},'unsupported delta erase policy')
    _require(type(allow_neg_eigval) is bool and (variant=='gdn2' or not allow_neg_eigval),'invalid tied erase range')
    _require(dim*heads*(head_key_dim+head_value_dim)<=2**24,'delta allocation exceeds bound')


def delta_weight_shapes(schema):
    """Closed analytic allocation inventory, before constructing any tensors."""
    _require(type(schema) is dict and set(schema)=={*DeltaMixer.schema_fields,'dtype'},'invalid delta schema')
    validate_delta(**{k:schema[k] for k in ('dim','heads','head_key_dim','head_value_dim','conv_length',
                                          'variant','decay_policy','erase_policy','allow_neg_eigval')})
    _require(type(schema['dtype']) is str and schema['dtype'] in {'float32','float64'},'invalid delta dtype')
    _require(all(type(schema[k]) is int and 0<schema[k]<=1024 for k in ('key_dim','value_dim')),'invalid public delta dimensions')
    _require(type(schema['t_ref']) in (int,float) and math.isfinite(schema['t_ref']) and schema['t_ref']>0,'invalid delta t_ref')
    d,h,k,v,L=(schema[n] for n in ('dim','heads','head_key_dim','head_value_dim','conv_length'))
    decay=h if schema['variant']=='gdn' else h*k
    shapes={'event_adapter.weight':(d,schema['key_dim']+schema['value_dim']+2),
        'query_adapter.weight':(d,schema['key_dim']+len(QUERY_TASK_ORDER)+4),
        'q_proj.weight':(h*k,d),'k_proj.weight':(h*k,d),'v_proj.weight':(h*v,d),
        'q_conv':(L,h*k),'k_conv':(L,h*k),'v_conv':(L,h*v),'A_log':(h,),'dt_bias':(decay,),
        'decay_in.weight':(v,d),'decay_out.weight':(decay,v),'norm_scale':(v,),
        'output_gate_in.weight':(v,d),'output_gate_out.weight':(h*v,v),
        'output_gate_out.bias':(h*v,),'output.weight':(d,h*v)}
    shapes.update({'erase.weight':(h*k,d),'write.weight':(h*v,d)} if schema['variant']=='gdn2' else {'beta.weight':(h,d)})
    return shapes


def validate_delta_weights(schema,weights):
    shapes=delta_weight_shapes(schema)
    _require(type(weights) is dict and set(weights)==set(shapes),'invalid delta weights')
    for name,shape in shapes.items():
        record=weights[name]
        _require(type(record) is dict and set(record)=={'shape','dtype','data'}
                 and type(record['shape']) is list and all(type(n) is int for n in record['shape'])
                 and record['shape']==list(shape) and record['dtype']==schema['dtype']
                 and type(record['data']) is str,'invalid delta weight layout')
    return shapes


class DeltaMixer(SnapshotMemory):
    """Full active native mixer with E/R public-input adapters for deferred tasks.

    terminal is a stream alias, never a linear closed form. No query advances
    observed-token caches or recurrence. Native event controls use native_sequence.
    """
    _state_keys=('S','q_cache','k_cache','v_cache')
    _clock_keys=('first_observed_time','last_observed_time','has_observation')
    schema_fields=('key_dim','value_dim','dim','heads','head_key_dim','head_value_dim','conv_length',
                   'variant','decay_policy','erase_policy','allow_neg_eigval','t_ref')

    def __init__(self,key_dim,value_dim,*,dim=16,heads=1,head_key_dim=4,head_value_dim=4,conv_length=4,
                 variant='gdn2',decay_policy='raw_per_observed_event',erase_policy='raw_paper',
                 allow_neg_eigval=False,t_ref=1.,dtype=torch.float32,device='cpu'):
        super().__init__()
        validate_delta(dim,heads,head_key_dim,head_value_dim,conv_length,variant,decay_policy,erase_policy,allow_neg_eigval)
        _require(all(type(n) is int and 0<n<=1024 for n in (key_dim,value_dim)),'invalid public delta dimensions')
        _require(type(t_ref) in (int,float) and math.isfinite(t_ref) and t_ref>0,'invalid delta t_ref')
        _require(dtype in {torch.float32,torch.float64},'invalid delta dtype')
        for name in self.schema_fields: setattr(self,name,locals()[name])
        hk,hv=heads*head_key_dim,heads*head_value_dim
        self.event_adapter=nn.Linear(key_dim+value_dim+2,dim,bias=False)
        self.query_adapter=nn.Linear(key_dim+len(QUERY_TASK_ORDER)+4,dim,bias=False)
        self.q_proj=nn.Linear(dim,hk,bias=False); self.k_proj=nn.Linear(dim,hk,bias=False)
        self.v_proj=nn.Linear(dim,hv,bias=False)
        # Explicit native initialization where the dependency revision is unpinned:
        # Conv weights uniform +/-1/sqrt(L), chronological oldest-to-current taps.
        self.q_conv=nn.Parameter(torch.empty(conv_length,hk).uniform_(-conv_length**-.5,conv_length**-.5))
        self.k_conv=nn.Parameter(torch.empty(conv_length,hk).uniform_(-conv_length**-.5,conv_length**-.5))
        self.v_conv=nn.Parameter(torch.empty(conv_length,hv).uniform_(-conv_length**-.5,conv_length**-.5))
        decay_width=heads if variant=='gdn' else hk
        self.decay_in=nn.Linear(dim,head_value_dim,bias=False)
        self.decay_out=nn.Linear(head_value_dim,decay_width,bias=False)
        self.A_log=nn.Parameter(torch.empty(heads).uniform_(1,16).log())
        dt=torch.empty(decay_width).uniform_(math.log(.001),math.log(.1)).exp().clamp_min(1e-4)
        self.dt_bias=nn.Parameter(dt+torch.log(-torch.expm1(-dt)))
        if variant=='gdn2':
            self.erase=nn.Linear(dim,hk,bias=False); self.write=nn.Linear(dim,hv,bias=False)
        else: self.beta=nn.Linear(dim,heads,bias=False)
        self.norm_scale=nn.Parameter(torch.ones(head_value_dim))
        self.output_gate_in=nn.Linear(dim,head_value_dim,bias=False)
        self.output_gate_out=nn.Linear(head_value_dim,hv,bias=True)
        self.output=nn.Linear(hv,dim,bias=False)
        for module in self.modules():
            if isinstance(module,nn.Linear):
                nn.init.xavier_uniform_(module.weight,gain=2**-2.5)
                if module.bias is not None: nn.init.zeros_(module.bias)
        self.to(device=device,dtype=dtype)

    @property
    def reference_tensor(self): return self.A_log

    @property
    def feature_dim(self): return self.dim

    @property
    def reader_feature_spec(self):
        return dict(family='delta',mixer_dim=self.dim,key_dim=self.key_dim,value_dim=self.value_dim)

    def _payload_shapes(self,b):
        return {'S':(b,self.heads,self.head_key_dim,self.head_value_dim),
                'q_cache':(b,self.conv_length-1,self.heads*self.head_key_dim),
                'k_cache':(b,self.conv_length-1,self.heads*self.head_key_dim),
                'v_cache':(b,self.conv_length-1,self.heads*self.head_value_dim)}

    def _extra_metadata(self,b):
        return {'first_observed_time':torch.zeros(b,dtype=torch.int64),
                'last_observed_time':torch.zeros(b,dtype=torch.int64),'has_observation':torch.zeros(b,dtype=torch.bool)}

    def _check_extra_metadata(self,state):
        b=state.last_time.numel()
        for name in self._clock_keys:
            t=state.payload[name]
            _require(t.shape==(b,) and t.device.type=='cpu' and t.dtype in
                     ((torch.bool,) if name=='has_observation' else (torch.int64,torch.float64))
                     and bool(torch.isfinite(t).all()),'invalid delta observation clock')
        for first,last,has,end,valid in zip(*(state.payload[n].tolist() for n in self._clock_keys),state.last_time.tolist(),state.valid.tolist()):
            _require((valid and first<=last<=end) if has else first==last==0,'invalid delta observation clock order')

    def _parameter_hash(self):
        from famjet.eval.state_io import tensor_record
        readonly=('query_adapter.','q_conv','norm_scale','output_gate_in.','output_gate_out.','output.')
        return canonical_hash({'family':'delta-deferred-v1','schema':{k:getattr(self,k) for k in self.schema_fields},
            'weights':{k:tensor_record(v) for k,v in self.state_dict().items() if not k.startswith(readonly)}})

    def _native_zero(self,b):
        return {k:self.reference_tensor.new_zeros(shape) for k,shape in self._payload_shapes(b).items()}

    @staticmethod
    def _convolve(projected,cache,weights):
        window=torch.cat((cache,projected[:,None]),1)
        return F.silu((window*weights).sum(1)),window[:,1:].clone()

    def _gates(self,x):
        b=x.shape[0]
        log_decay=-self.A_log.exp()[None,:,None]*F.softplus(
            self.decay_out(self.decay_in(x))+self.dt_bias).reshape(b,self.heads,-1)
        if self.variant=='gdn': log_decay=log_decay.expand(-1,-1,self.head_key_dim)
        if self.variant=='gdn2':
            erase=torch.sigmoid(self.erase(x)).reshape(b,self.heads,self.head_key_dim)*(2 if self.allow_neg_eigval else 1)
            write=torch.sigmoid(self.write(x)).reshape(b,self.heads,self.head_value_dim)
        else: erase=write=torch.sigmoid(self.beta(x)).reshape(b,self.heads,1)
        return log_decay,erase,write

    def _observe(self,x,core,*,output=False):
        b=x.shape[0]
        qp=self.q_proj(x)
        k,kc=self._convolve(self.k_proj(x),core['k_cache'],self.k_conv)
        v,vc=self._convolve(self.v_proj(x),core['v_cache'],self.v_conv)
        k=normalize_key(k.reshape(b,self.heads,self.head_key_dim)); v=v.reshape(b,self.heads,self.head_value_dim)
        g,erase,write=self._gates(x)
        if self.erase_policy=='pinned_guarded' and self.variant=='gdn2': erase=guard_erase(k,erase,g)
        S=delta_step(core['S'],k,v,g.exp(),erase,write)
        qc=torch.cat((core['q_cache'],qp[:,None]),1)[:,1:].clone()
        result={'S':S,'q_cache':qc,'k_cache':kc,'v_cache':vc}
        return result,self._read_native(x,S,core['q_cache'],projected=qp) if output else None

    def _read_native(self,x,S,qcache,*,projected=None):
        q,_=self._convolve(self.q_proj(x) if projected is None else projected,qcache,self.q_conv)
        q=normalize_key(q.reshape(x.shape[0],self.heads,self.head_key_dim))/math.sqrt(self.head_key_dim)
        out=(S*q[...,None]).sum(-2)
        out=out*torch.rsqrt(out.square().mean(-1,keepdim=True)+1e-5)*self.norm_scale
        gate=F.silu(self.output_gate_out(self.output_gate_in(x))).reshape_as(out)
        return self.output((out*gate).flatten(1))

    def native_sequence(self,x,core=None):
        """Native per-token mixer control; x already has native D dimensions."""
        _require(x.ndim==3 and x.shape[-1]==self.dim and x.dtype==self.reference_tensor.dtype
                 and x.device==self.reference_tensor.device,'invalid native delta input')
        core=self._native_zero(x.shape[0]) if core is None else core
        outputs=[]
        for j in range(x.shape[1]):
            core,y=self._observe(x[:,j],core,output=True); outputs.append(y)
        return (torch.stack(outputs,1) if outputs else x.new_empty(x.shape)),core

    def _raw(self,events):
        validate_events(events)
        _require(events.normalization=='shared','delta requires shared normalization')
        _require(events.key_features.dtype==events.values.dtype==self.reference_tensor.dtype
                 and events.values.device==self.reference_tensor.device,'delta input device/dtype mismatch')
        _require(not ('gate' in events.auxiliary and 'gates' in events.auxiliary),'provide gate or gates, not both')
        for name in ('gate','gates'):
            if name in events.auxiliary:
                gate=events.auxiliary[name]
                _require(gate.shape in (events.present.shape,(*events.present.shape,1)) and bool((gate==1).all()),
                         'delta accepts only unit external gates')
        return events.validation.write_mask

    def _encode_core(self,events,core,gates,times,lengths,last,valid,first_gaps,mode):
        first=core['first_observed_time'].tolist(); observed_last=core['last_observed_time'].tolist()
        has=core['has_observation'].tolist()
        for j in range(events.values.shape[1]):
            rows=[]
            for i in range(events.values.shape[0]):
                row={k:core[k][i:i+1] for k in self._state_keys}
                if bool(gates[i,j]):
                    t=times[i][j]
                    gap=float(exact_time_difference(t,observed_last[i])) if has[i] else 0.
                    span=float(exact_time_difference(t,first[i])) if has[i] else 0.
                    time_features=events.values.new_tensor([math.log1p(gap/self.t_ref),math.log1p(span/self.t_ref)])
                    raw=torch.cat((events.key_features[i,j],events.values[i,j],time_features))
                    row,_=self._observe(self.event_adapter(raw[None]),row)
                    if not has[i]: first[i]=t
                    observed_last[i]=t; has[i]=True
                rows.append(row)
            core={k:torch.cat([row[k] for row in rows],0) for k in self._state_keys}
        return {**{k:core[k] for k in self._state_keys},'first_observed_time':_pack_times(first),
                'last_observed_time':_pack_times(observed_last),'has_observation':torch.tensor(has,dtype=torch.bool)}

    def _propagate(self,core,gaps):
        return {k:core[k].clone() for k in self._state_keys}

    def features(self,state,queries):
        self._check_snapshot(state); validate_queries(queries,state)
        identity=torch.stack([_digest_tensor(h) for h in queries.history_ids])
        if bool(state.payload['time_unit_hash'].any()):
            _require(torch.equal(identity,state.payload['history_hash']),'query history identity mismatch')
        _require(queries.key_features.shape[-1]==self.key_dim and queries.key_features.dtype==self.reference_tensor.dtype
                 and queries.key_features.device==self.reference_tensor.device,'delta query layout mismatch')
        public=query_inputs(queries,self.t_ref); results=[]
        for j in range(queries.T.shape[1]):
            self._advance_payload(state,queries.T[:,j].tolist(),queries.present[:,j].cpu().tolist())
            temporal=[]
            for t,first,last,has,present in zip(queries.T[:,j].tolist(),state.payload['first_observed_time'].tolist(),
                    state.payload['last_observed_time'].tolist(),state.payload['has_observation'].tolist(),queries.present[:,j].cpu().tolist()):
                temporal.append([math.log1p(float(exact_time_difference(t,last))/self.t_ref),
                                 math.log1p(float(exact_time_difference(t,first))/self.t_ref)] if has and present else [0.,0.])
            x=self.query_adapter(torch.cat((public[:,j],public.new_tensor(temporal)),-1))
            results.append(self._read_native(x,state.payload['S'],state.payload['q_cache']))
        values=torch.stack(results,1) if results else public.new_empty((*queries.T.shape,self.dim))
        finite=torch.isfinite(values).all(-1)
        supported=queries.present & state.payload['has_observation'].to(values.device)[:,None] & finite
        return FeatureBatch(values,supported,{'failure':~finite})

    def read(self,state,queries): return self.features(state,queries)
