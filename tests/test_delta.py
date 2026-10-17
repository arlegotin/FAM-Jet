"""Independent native delta equations and deferred read-only mixer controls."""
from dataclasses import replace
import pytest
import torch
from famjet.memory.delta import delta_step, guard_erase, DeltaMixer
from jet_fixtures import events, queries, chunk, kernel_case


def test_delta_independent_matrix_update_ties_and_gradients(kernel_case):
    dtype,device,tol=kernel_case
    torch.manual_seed(15)
    raw=[torch.randn(2,3,4,dtype=torch.float64),torch.randn(2,3,dtype=torch.float64),
         torch.randn(2,4,dtype=torch.float64),torch.rand(2,3,dtype=torch.float64),
         torch.rand(2,3,dtype=torch.float64),torch.rand(2,4,dtype=torch.float64)]
    raw[1]=raw[1]/(raw[1].square().sum(-1,keepdim=True)+1e-6).sqrt()
    args=[x.to(device,dtype).requires_grad_() for x in raw]
    reference=[x.clone().requires_grad_() for x in raw]
    S,k,v,a,b,w=reference
    want=torch.stack([(torch.eye(3,dtype=torch.float64)-torch.outer(k[h],b[h]*k[h])) @ torch.diag(a[h]) @ S[h]
                       +torch.outer(k[h],w[h]*v[h]) for h in range(2)])
    got=delta_step(*args)
    torch.testing.assert_close(got.cpu().double(),want,rtol=tol[0],atol=tol[1])
    for g,r in zip(torch.autograd.grad(got.square().sum(),args),torch.autograd.grad(want.square().sum(),reference)):
        torch.testing.assert_close(g.cpu().double(),r,rtol=tol[0],atol=tol[1])
    beta=torch.tensor([[.2],[.7]],dtype=torch.float64)
    for decay in [a,a[:,:1].expand_as(a)]:
        bar=decay[...,None]*S
        expected=bar+beta[...,None]*k[...,None]*(v-(bar*k[...,None]).sum(-2))[...,None,:]
        torch.testing.assert_close(delta_step(S,k,v,decay,beta,beta),expected)
    assert not torch.allclose(delta_step(S,k,v,a,b,w),delta_step(S,k,v,a,b[:,:1],b[:,:1]))
    torch.testing.assert_close(delta_step(S,k,v,a,torch.zeros_like(b),torch.zeros_like(w)),a[...,None]*S)


def test_guard_contrast_projection_and_straight_through():
    k=torch.tensor([[.8,.6],[0.,0.]],dtype=torch.float64,requires_grad=True)
    b=torch.tensor([[.01,1.99],[.1,1.7]],dtype=torch.float64,requires_grad=True)
    g=torch.full_like(k,-1e-6,requires_grad=True)
    got=guard_erase(k,b,g)
    n=(k*k).sum(-1,keepdim=True); a=(b*k*k).sum(-1,keepdim=True)
    r2=(n*(b*b*k*k).sum(-1,keepdim=True)-a*a).clamp_min(0)
    c2=torch.exp(-2*g.max(-1,keepdim=True).values)
    R=((c2-1)*(1-(1-a)**2/c2)).clamp_min(0)
    mu=a/n.clamp_min(1e-20)
    eta=((31/32)*R/r2.clamp_min(1e-30)).sqrt().clamp(0,1)
    expected=torch.where((n>1e-20)&(r2>R),mu+eta*(b-mu),b)
    torch.testing.assert_close(got,expected)
    assert not torch.equal(got[0],b[0])
    grad=torch.autograd.grad(got.sum(),(b,k,g),allow_unused=True)
    torch.testing.assert_close(grad[0],torch.ones_like(b)); assert grad[1:] == (None,None)
    torch.testing.assert_close(guard_erase(k,b,torch.full_like(g,-1000)),b)


def delta_events(dtype=torch.float64,device='cpu'):
    return replace(events(dtype,device),auxiliary={})


def test_native_convolution_causal_output_and_continuation(kernel_case):
    dtype,device,tol=kernel_case
    torch.manual_seed(15)
    m=DeltaMixer(3,2,dim=8,heads=2,head_key_dim=3,head_value_dim=4,dtype=dtype,device=device)
    x=torch.randn(2,7,8,device=device,dtype=dtype)
    y,core=m.native_sequence(x)
    left,c=m.native_sequence(x[:,:3]); right,c=m.native_sequence(x[:,3:],c)
    torch.testing.assert_close(y,torch.cat((left,right),1),rtol=tol[0],atol=tol[1])
    altered=x.clone(); altered[:,4:]+=10
    y2,_=m.native_sequence(altered)
    torch.testing.assert_close(y[:,:4],y2[:,:4],rtol=0,atol=0)
    assert core['q_cache'].shape==(2,3,6)
    assert core['k_cache'].shape==(2,3,6)
    assert core['v_cache'].shape==(2,3,8)


def test_deferred_resume_cache_bytes_query_immutability_and_active_weights(kernel_case):
    dtype,device,tol=kernel_case
    torch.manual_seed(15)
    m=DeltaMixer(3,2,dim=8,heads=2,head_key_dim=3,head_value_dim=4,dtype=dtype,device=device)
    e=delta_events(dtype,device)
    s=m.encode(e); resumed=m.encode(chunk(e,3,6),m.encode(chunk(e,0,3)))
    for k in s.payload: torch.testing.assert_close(s.payload[k],resumed.payload[k],rtol=tol[0],atol=tol[1])
    q=queries(e,[[8,10],[7,20]])
    before={k:v.clone() for k,v in s.payload.items()}
    f=m.features(s,q)
    for k in before: torch.testing.assert_close(before[k],s.payload[k],rtol=0,atol=0)
    f.values.square().sum().backward()
    for name,p in m.named_parameters():
        assert p.grad is not None and torch.isfinite(p.grad).all() and bool(p.grad.abs().sum()>0),name
    assert s.payload['first_observed_time'].tolist()==[0,2]
    assert s.payload['last_observed_time'].tolist()==[4,7]
    from famjet.eval.budgets import state_ledger
    assert m.persistent_nbytes(s)==state_ledger(s)['logical_bytes']
    expected_numeric=2*(2*3*4+3*(2*2*3+2*4))*torch.empty((),dtype=dtype).element_size()
    assert sum(s.payload[k].numel()*s.payload[k].element_size() for k in m._state_keys)==expected_numeric


def delta_config(device='cpu',variant='gdn2',erase_policy='raw_paper'):
    from pathlib import Path
    from famjet.config import load_config, DeltaConfig
    c=load_config(Path('configs/smoke.yaml'))
    return replace(c,data=replace(c.data,key_dim=3,key_features='dense',value_dim=2,length=12,queries_per_history=2),
        model=replace(c.model,method='delta',K=3,J=None,rates=None,writer='native_delta',encode='stream',
            delta=DeltaConfig(dim=8,head_key_dim=3,head_value_dim=4,variant=variant,erase_policy=erase_policy),
            reader=replace(c.model.reader,kind='delta_mixer',width=8)),
        training=replace(c.training,effective_batch=2),resources=replace(c.resources,device=device,cpu_threads=1))


@pytest.mark.parametrize('variant',['gdn2','kda','gdn'])
def test_task_registration_static_export_and_real_tied_parameters(variant):
    from famjet.train import make_model
    from famjet.eval.isolation import export_method,_reconstruct
    m=make_model(delta_config(variant=variant))
    e=delta_events(torch.float32); q=queries(e,[[8,10],[7,10]])
    expected=m(e,q,encode_mode='stream').prediction
    restored=_reconstruct(export_method(m))
    torch.testing.assert_close(restored(e,q,encode_mode='stream').prediction,expected,rtol=0,atol=0)
    assert m.writer is None and m.query_map is None
    if variant!='gdn2':
        assert m.kernel.beta.out_features==1 and not hasattr(m.kernel,'erase')
    if variant=='gdn': assert m.kernel.decay_out.out_features==1 and m.kernel.dt_bias.numel()==1
    expected.square().sum().backward()
    for name,p in m.kernel.named_parameters(): assert p.grad is not None and bool(p.grad.abs().sum()>0),name


@pytest.mark.parametrize('streaming',[False,True])
def test_fit_reference_hash_and_atomic_rollback(streaming):
    from famjet.train import make_model
    from famjet.types import Episode
    from famjet.eval.isolation import model_identity
    m=make_model(delta_config())
    e=delta_events(torch.float32); q=queries(e,[[8,10],[7,10]])
    ep=Episode(e,q,torch.ones(2,2,2),torch.ones(2,2,dtype=torch.bool),metadata={'split':'training'})
    m.fit_statistics((lambda:iter([ep])) if streaming else [ep])
    assert m.kernel.t_ref==1.5 and m.fit_provenance['writer_hash']==m._parameter_hash()
    before=model_identity(m)
    bad=replace(ep,queries=replace(q,key_features=q.key_features*float('nan')))
    with pytest.raises(ValueError): m.fit_statistics((lambda:iter([bad])) if streaming else [bad])
    assert model_identity(m)==before


def test_optimizer_no_decay_and_exact_training_resume(tmp_path):
    from famjet.train import make_model,make_optimizer,train_model
    from famjet.checkpoint import load_checkpoint
    c=delta_config(); c=replace(c,data=replace(c.data,value_dim=8))
    m=make_model(c); opt=make_optimizer(m,c)
    assert len(opt.param_groups)==2 and opt.param_groups[1]['weight_decay']==0
    assert {id(x) for x in opt.param_groups[1]['params']}=={id(m.kernel.A_log),id(m.kernel.dt_bias)}
    full=load_checkpoint(train_model(c,tmp_path/'full'),{})
    resumed=load_checkpoint(train_model(c,tmp_path/'resume',resume=tmp_path/'full'/'checkpoint.pt.previous'),{})
    for k in full['model_state']: torch.testing.assert_close(full['model_state'][k],resumed['model_state'][k],rtol=0,atol=0)
    assert len(full['optimizer']['param_groups'])==2


def independent_native(x,weights,m):
    """FP64 unrolling using matrix transitions and explicit convolution sums."""
    from torch.nn import functional as F
    B,N,_=x.shape; H,K,V=m.heads,m.head_key_dim,m.head_value_dim
    state=x.new_zeros(B,H,K,V); ys=[]
    def linear(z,n): return z @ weights[n+'.weight'].T+weights.get(n+'.bias',0)
    projected={n:linear(x,n+'_proj') for n in ('q','k','v')}
    for t in range(N):
        conv={}
        for n in ('q','k','v'):
            z=sum(projected[n][:,i]*weights[n+'_conv'][m.conv_length-1-(t-i)]
                  for i in range(max(0,t-m.conv_length+1),t+1))
            conv[n]=F.silu(z).reshape(B,H,K if n!='v' else V)
        q,k,v=conv['q'],conv['k'],conv['v']
        q=q/(q.square().sum(-1,keepdim=True)+1e-6).sqrt()/K**.5
        k=k/(k.square().sum(-1,keepdim=True)+1e-6).sqrt()
        g=-weights['A_log'].exp()[None,:,None]*F.softplus(linear(linear(x[:,t],'decay_in'),'decay_out')+weights['dt_bias']).reshape(B,H,-1)
        if m.variant=='gdn2':
            b=linear(x[:,t],'erase').sigmoid().reshape(B,H,K)*(2 if m.allow_neg_eigval else 1)
            w=linear(x[:,t],'write').sigmoid().reshape(B,H,V)
        else: b=w=linear(x[:,t],'beta').sigmoid().reshape(B,H,1)
        transition=(torch.eye(K,dtype=x.dtype)[None,None]-k[...,None]*(b*k)[...,None,:])*g.exp()[...,None,:]
        state=transition @ state+k[...,None]*(w*v)[...,None,:]
        out=(state.transpose(-1,-2) @ q[...,None]).squeeze(-1)
        out=out/(out.square().mean(-1,keepdim=True)+1e-5).sqrt()*weights['norm_scale']
        gate=F.silu(linear(linear(x[:,t],'output_gate_in'),'output_gate_out')).reshape(B,H,V)
        ys.append(linear((out*gate).flatten(1),'output'))
    return torch.stack(ys,1)


@pytest.mark.parametrize('variant',['gdn2','kda','gdn'])
def test_full_native_cpu64_independent_output_input_parameter_gradients(variant,kernel_case):
    dtype,device,tol=kernel_case
    torch.manual_seed(151)
    m=DeltaMixer(3,2,dim=8,heads=2,head_key_dim=3,head_value_dim=4,variant=variant,dtype=dtype,device=device)
    x=torch.randn(2,5,8,dtype=torch.float64).to(device,dtype).requires_grad_()
    native={n:p for n,p in m.named_parameters() if not n.startswith(('event_adapter','query_adapter'))}
    w={n:p.detach().cpu().double().requires_grad_() for n,p in native.items()}
    xx=x.detach().cpu().double().requires_grad_()
    expected=independent_native(xx,w,m); got,_=m.native_sequence(x)
    torch.testing.assert_close(got.cpu().double(),expected,rtol=tol[0],atol=tol[1])
    actual_grads=torch.autograd.grad(got.square().sum(),(x,*native.values()))
    expected_grads=torch.autograd.grad(expected.square().sum(),(xx,*w.values()))
    for name,g,r in zip(('input',*native),actual_grads,expected_grads):
        torch.testing.assert_close(g.cpu().double(),r,rtol=tol[0],atol=tol[1],msg=name)


def test_gap_split_padding_empty_uint64_shift_units_and_future_query_resume():
    from famjet.eval.state_io import snapshot_hash,inference_snapshot
    torch.manual_seed(15); m=DeltaMixer(3,2,dtype=torch.float64)
    e=delta_events(); e=replace(e,key_ids=torch.full(e.key_ids.shape,2**64-1,dtype=torch.uint64))
    prefix=chunk(e,0,3); suffix=chunk(e,3,6)
    s=m.encode(prefix); before=snapshot_hash(inference_snapshot(s))
    m.features(s,queries(prefix,[[10,20],[10,20]]))
    assert snapshot_hash(inference_snapshot(s))==before
    resumed=m.encode(suffix,s); full=m.encode(e)
    for name in full.payload: torch.testing.assert_close(resumed.payload[name],full.payload[name],rtol=0,atol=0)
    # Two no-write markers between observed events do not enter E or conv clocks.
    gap=replace(chunk(e,3,4),timestamps=torch.tensor([[2],[3]]),event_ids=torch.tensor([[100],[100]]),
                observed=torch.zeros(2,1,2,dtype=torch.bool))
    # The second history's following event is at 7, first at 3; no simultaneous ID conflict.
    with_gap=m.encode(gap,s)
    suffix=replace(suffix,event_ids=suffix.event_ids+200)
    split=m.encode(suffix,with_gap)
    for name in m._state_keys+m._clock_keys: torch.testing.assert_close(split.payload[name],full.payload[name],rtol=0,atol=0)
    q=queries(e,[[8,12],[7,20]]); y=m.features(full,q).values
    shifted=replace(e,timestamps=e.timestamps+2**50)
    torch.testing.assert_close(m.features(m.encode(shifted),replace(q,T=q.T+2**50)).values,y,rtol=0,atol=0)
    m.t_ref*=1000
    scaled=replace(e,timestamps=e.timestamps*1000,time_unit='milliseconds')
    scaledq=replace(q,T=q.T*1000,age_start=q.age_start*1000,age_end=q.age_end*1000)
    torch.testing.assert_close(m.features(m.encode(scaled),scaledq).values,y,rtol=1e-12,atol=1e-12)
    empty=m.encode(chunk(e,0,0)); emptyq=queries(e,[[0],[0]])
    f=m.features(empty,emptyq); assert not f.supported.any() and torch.isfinite(f.values).all()
    gaps=replace(e,observed=torch.zeros_like(e.observed)); sg=m.encode(gaps)
    assert sg.valid.all() and not sg.payload['has_observation'].any()
    assert not m.features(sg,q).supported.any()


def test_writer_hash_readonly_reuse_isolation_and_snapshot_roundtrip(tmp_path):
    from famjet.train import make_model
    from famjet.eval.isolation import model_identity,isolated_read
    from famjet.eval.state_io import save_state,load_state,inference_snapshot
    m=make_model(delta_config()); e=delta_events(torch.float32); q=queries(e,[[8,10],[7,11]])
    with torch.no_grad(): s=m.encode(e)
    save_state(tmp_path/'state',s); s=load_state(tmp_path/'state',m._parameter_hash())
    initial=model_identity(m); h=s.parameter_hash
    for name in ('query_adapter.weight','q_conv','norm_scale','output_gate_in.weight','output.weight'):
        with torch.no_grad(): dict(m.kernel.named_parameters())[name].add_(.001)
        assert m._parameter_hash()==h and model_identity(m)!=initial
        m.read(s,q)
    torch.testing.assert_close(isolated_read(m,s,q).prediction,m.read(s,q).prediction,rtol=1e-5,atol=1e-6)
    for name in ('q_proj.weight','k_conv','event_adapter.weight','A_log'):
        old=dict(m.kernel.named_parameters())[name].detach().clone()
        with torch.no_grad(): dict(m.kernel.named_parameters())[name].add_(.001)
        with pytest.raises(ValueError,match='hash'): m.read(s,q)
        with torch.no_grad(): dict(m.kernel.named_parameters())[name].copy_(old)
    m.kernel.t_ref*=2
    with pytest.raises(ValueError,match='hash'): m.read(s,q)


def test_recompute_retains_whole_history_gradients():
    from famjet.train import make_model,forward_training
    from famjet.types import Episode
    m=make_model(delta_config()); e=delta_events(torch.float32); q=queries(e,[[8,12],[7,14]])
    e=replace(e,values=e.values.clone().requires_grad_())
    ep=Episode(e,q,torch.ones(2,2,2),torch.ones(2,2,dtype=torch.bool))
    direct=forward_training(m,ep,'stream',recompute=False)
    direct.prediction.square().sum().backward()
    expected={n:p.grad.clone() for n,p in m.named_parameters() if p.grad is not None}; input_grad=e.values.grad.clone()
    m.zero_grad(); e.values.grad=None
    recomputed=forward_training(m,ep,'stream',recompute=True)
    recomputed.prediction.square().sum().backward()
    for n,p in m.named_parameters():
        if n in expected: torch.testing.assert_close(p.grad,expected[n],rtol=0,atol=0)
    torch.testing.assert_close(e.values.grad,input_grad,rtol=0,atol=0)
    assert e.values.grad[:,0].abs().sum()>0


def test_guard_quantized_output_is_exact_and_has_no_projection_gradient():
    k=torch.tensor([[.8,.6]],dtype=torch.float32)
    b=torch.tensor([[.01,1.99]],dtype=torch.float32,requires_grad=True)
    g=torch.full_like(k,-1e-6)
    n=k.square().sum(-1,keepdim=True); a=(b.detach()*k.square()).sum(-1,keepdim=True)
    r2=(n*(b.detach().square()*k.square()).sum(-1,keepdim=True)-a.square()).clamp_min(0)
    c2=(-2*g.amax(-1,keepdim=True)).exp()
    R=((c2-1)*(1-(1-a).square()/c2)).clamp_min(0)
    mu=a/n; eta=((31/32)*R/r2).sqrt()
    want=(mu+eta*(b.detach()-mu)).to(b.dtype)
    torch.testing.assert_close(guard_erase(k,b,g),want,rtol=0,atol=0)


def test_hostile_delta_allocation_and_weight_schema_fail_before_allocation(monkeypatch):
    from copy import deepcopy
    from famjet.train import make_model
    from famjet.eval.isolation import export_method,_reconstruct
    from famjet.memory import delta
    wire=export_method(make_model(delta_config()).kernel)
    malformed=[]
    for field,value in [('dim',True),('heads',100000),('erase_policy',[]),('decay_policy',False)]:
        bad=deepcopy(wire); bad['schema'][field]=value; malformed.append(bad)
    bad=deepcopy(wire); bad['weights']['q_proj.weight']['shape']=[True,8]; malformed.append(bad)
    bad=deepcopy(wire); bad['weights']['q_proj.weight']['shape']=[1_000_000,8]; malformed.append(bad)
    def forbidden(*args,**kwargs): raise AssertionError('allocated before validating hostile descriptor')
    monkeypatch.setattr(delta.nn,'Linear',forbidden)
    for bad in malformed:
        with pytest.raises(ValueError): _reconstruct(bad)


def test_guard_second_pass_injected_violating_candidate_scalar_fallback():
    """Fault injection, NOT an observed naturally activating FP32 quantization."""
    from famjet.memory.delta import _guard_recheck
    k=torch.tensor([[.8,.6]],dtype=torch.float32)
    candidate=torch.tensor([[0.,2.]],dtype=torch.float32)
    g=torch.full_like(k,-1e-7)
    mu=(candidate*k.square()).sum(-1,keepdim=True)/k.square().sum(-1,keepdim=True)
    fixed=_guard_recheck(k,candidate,g,mu)
    torch.testing.assert_close(fixed,mu.expand_as(candidate),rtol=0,atol=0)
    torch.testing.assert_close(_guard_recheck(k,fixed,g,mu),fixed,rtol=0,atol=0)


def test_guard_native_invariants_and_untouched_decay_write(kernel_case):
    dtype,device,tol=kernel_case
    from famjet.memory.delta import normalize_key
    k=normalize_key(torch.tensor([[.3,.7,.4]],device=device,dtype=dtype))
    b=torch.tensor([[.01,1.99,.02]],device=device,dtype=dtype)
    g=torch.full_like(k,-1e-6)
    out=guard_erase(k,b,g)
    torch.testing.assert_close((out*k.square()).sum(-1),(b*k.square()).sum(-1),rtol=tol[0],atol=tol[1])
    assert (out>=b.min()).all() and (out<=b.max()).all()
    for beta in (.01,.5,1.):
        tied=torch.full_like(k,beta)
        torch.testing.assert_close(guard_erase(k,tied,g),tied,rtol=0,atol=0)
    torch.manual_seed(10)
    m=DeltaMixer(3,2,dim=8,head_key_dim=3,head_value_dim=4,dtype=dtype,device=device,allow_neg_eigval=True)
    x=torch.randn(1,8,device=device,dtype=dtype)
    gates=m._gates(x); m.erase_policy='pinned_guarded'; guarded=m._gates(x)
    for a,z in zip(gates,guarded): torch.testing.assert_close(a,z,rtol=0,atol=0)
    n=k.square().sum(-1); a=(out*k.square()).sum(-1); nu=(out.square()*k.square()).sum(-1)
    c2=(-2*g.amax(-1)).exp(); R=((c2-1)*(1-(1-a).square()/c2)).clamp_min(0)
    assert bool((n*nu-a.square()<=R+4*torch.finfo(dtype).eps*(n*nu+a.square())).all())


def test_all_query_adapter_columns_and_convolution_taps_active():
    from famjet.readers.structured import QUERY_TASK_ORDER
    m=DeltaMixer(3,2,dim=8,head_key_dim=3,head_value_dim=4,dtype=torch.float64)
    e=delta_events(); count=len(QUERY_TASK_ORDER)
    q=queries(e,[[10+i for i in range(count)]]*2)
    q=replace(q,tasks=(QUERY_TASK_ORDER,)*2,age_start=torch.ones(2,count,dtype=torch.float64),
              age_end=torch.full((2,count),3.,dtype=torch.float64))
    m.features(m.encode(e),q).values.square().sum().backward()
    for name,p in m.named_parameters():
        assert p.grad is not None and torch.isfinite(p.grad).all(),name
        if p.ndim==2: assert bool((p.grad.abs().sum(0)>0).all()),name+' input columns'
    for name in ('q_conv','k_conv','v_conv'):
        assert bool((getattr(m,name).grad.abs().sum(-1)>0).all()),name+' taps'


def test_zero_output_gate_and_guarded_ties_preserve_native_reductions():
    m=DeltaMixer(3,2,dim=8,head_key_dim=3,head_value_dim=4,dtype=torch.float64)
    x=torch.randn(2,4,8,dtype=torch.float64)
    with torch.no_grad(): m.output_gate_out.weight.zero_(); m.output_gate_out.bias.zero_()
    y,_=m.native_sequence(x); torch.testing.assert_close(y,torch.zeros_like(y),rtol=0,atol=0)
    for variant in ('kda','gdn'):
        m=DeltaMixer(3,2,dim=8,variant=variant,dtype=torch.float64)
        a,_=m.native_sequence(x); m.erase_policy='pinned_guarded'; b,_=m.native_sequence(x)
        torch.testing.assert_close(a,b,rtol=0,atol=0)


def test_observation_clock_ledger_classifies_every_clock_byte():
    from famjet.eval.budgets import state_ledger
    m=DeltaMixer(3,2); s=m.encode(delta_events(torch.float32)); ledger=state_ledger(s)
    for name,size in [('first_observed_time',16),('last_observed_time',16),('has_observation',2)]:
        assert ledger['metadata']['payload.'+name]==size
    assert ledger['payload_bytes']==sum(s.payload[k].numel()*s.payload[k].element_size() for k in m._state_keys)


def test_guarded_recurrence_gradients_follow_ste_not_projected_map():
    k=torch.tensor([[.8,.6]],dtype=torch.float64,requires_grad=True)
    b=torch.tensor([[.01,1.99]],dtype=torch.float64,requires_grad=True)
    g=torch.full_like(k,-1e-6,requires_grad=True)
    S=torch.tensor([[[.3,-.7],[.9,.1]]],dtype=torch.float64,requires_grad=True)
    v=torch.tensor([[.7,.2]],dtype=torch.float64,requires_grad=True)
    w=torch.tensor([[.3,.9]],dtype=torch.float64,requires_grad=True)
    effective=guard_erase(k,b,g)
    actual=delta_step(S,k,v,g.exp(),effective,w)
    # Frozen projected forward gate with identity derivative only in raw b.
    frozen=effective.detach()+b-b.detach()
    bar=g.exp()[...,None]*S
    expected=(torch.eye(2,dtype=torch.float64)-k[...,None]*(frozen*k)[...,None,:]) @ bar+k[...,None]*(w*v)[...,None,:]
    for a,z in zip(torch.autograd.grad(actual.square().sum(),(S,k,v,b,g,w),retain_graph=True),
                   torch.autograd.grad(expected.square().sum(),(S,k,v,b,g,w))):
        torch.testing.assert_close(a,z,rtol=1e-12,atol=1e-12)


@pytest.mark.parametrize('device',['cpu','mps'])
def test_actual_standardized_task_cpu64_reference_gradients(device):
    if device=='mps' and not torch.backends.mps.is_available(): pytest.skip('native MPS unavailable')
    from famjet.train import make_model
    from famjet.types import Episode
    from famjet.eval.isolation import export_method,_reconstruct
    torch.manual_seed(150)
    m=make_model(delta_config(device=device,erase_policy='pinned_guarded'))
    e=delta_events(torch.float32,device); q=queries(e,[[8,10],[7,11]])
    ep=Episode(e,q,torch.ones(2,2,2,device=device),torch.ones(2,2,dtype=torch.bool,device=device),metadata={'split':'training'})
    m.fit_statistics([ep])
    oracle=_reconstruct(export_method(m)).double()
    e64=replace(e,values=e.values.cpu().double().requires_grad_(),key_features=e.key_features.cpu().double().requires_grad_(),
                present=e.present.cpu(),observed=e.observed.cpu())
    q64=replace(q,key_features=q.key_features.cpu().double(),present=q.present.cpu())
    e=replace(e,values=e.values.clone().requires_grad_(),key_features=e.key_features.clone().requires_grad_())
    reference=oracle(e64,q64,encode_mode='stream'); result=m(e,q,encode_mode='stream')
    torch.testing.assert_close(result.prediction.cpu().double(),reference.prediction,rtol=1e-5,atol=1e-6)
    oracle.loss(reference,replace(ep,events=e64,queries=q64,labels=ep.labels.cpu().double(),supported=ep.supported.cpu())).backward()
    m.loss(result,replace(ep,events=e)).backward()
    for actual,want in ((e.values.grad,e64.values.grad),(e.key_features.grad,e64.key_features.grad)):
        torch.testing.assert_close(actual.cpu().double(),want,rtol=1e-5,atol=1e-6)
    for (name,p),(n,r) in zip(m.named_parameters(),oracle.named_parameters()):
        assert name==n
        if p.grad is None: assert r.grad is None; continue
        error=(p.grad.cpu().double()-r.grad).abs()
        point_ratio=float((error/(1e-6+1e-5*r.grad.abs())).max())
        norm_ratio=float(error.norm()/(1e-6+1e-5*r.grad.norm()))
        # Task14 common-MLP amendment only. Native mixer remains pointwise.
        print(f'delta_task_gradient {device} {name} pointwise_ratio={point_ratio:.9g} norm_ratio={norm_ratio:.9g}')
        if name.startswith('reader.'): assert norm_ratio<=1
        else: assert point_ratio<=1


def test_query_permutation_padding_and_advance_copy_clock_ownership():
    m=DeltaMixer(3,2,dtype=torch.float64); e=delta_events(); q=queries(e,[[8,9,10],[7,9,10]])
    s=m.encode(e); expected=m.features(s,q).values
    order=torch.tensor([2,0,1])
    perm=replace(q,**{n:getattr(q,n)[:,order] for n in ('query_ids','T','key_ids','key_features','age_start','age_end','present')},
                 tasks=tuple(tuple(row[i] for i in order.tolist()) for row in q.tasks))
    torch.testing.assert_close(m.features(s,perm).values,expected[:,order],rtol=0,atol=0)
    pad_values=e.values.clone(); pad_keys=e.key_features.clone(); pad_values[~e.present]=10000; pad_keys[~e.present]=10000
    padded=m.encode(replace(e,values=pad_values,key_features=pad_keys))
    for k in m._state_keys+m._clock_keys: torch.testing.assert_close(s.payload[k],padded.payload[k],rtol=0,atol=0)
    advanced=m.advance_copy(s,100)
    assert advanced.last_time.tolist()==[100,100] and s.last_time.tolist()==[8,7]
    for k in m._state_keys+m._clock_keys:
        torch.testing.assert_close(s.payload[k],advanced.payload[k],rtol=0,atol=0)
        assert s.payload[k].untyped_storage()._cdata!=advanced.payload[k].untyped_storage()._cdata


def test_delta_checkpoint_groups_precoercion_and_clock_rejection(tmp_path):
    from copy import deepcopy
    from famjet.train import train_model
    from famjet.checkpoint import load_checkpoint,_validate
    c=delta_config(erase_policy='pinned_guarded'); c=replace(c,data=replace(c.data,value_dim=8))
    context=load_checkpoint(train_model(c,tmp_path/'run'),{})
    bad=deepcopy(context); bad['optimizer']['param_groups'][1]['weight_decay']=.01
    with pytest.raises(ValueError,match='group'): _validate(bad)
    bad=deepcopy(context); bad['optimizer']['param_groups'][1]['params'].reverse()
    with pytest.raises(ValueError,match='group'): _validate(bad)
    bad=deepcopy(context); i=bad['optimizer']['param_groups'][1]['params'][0]
    bad['optimizer']['state'][i]['exp_avg']=bad['optimizer']['state'][i]['exp_avg'].double()
    with pytest.raises(ValueError,match='moment'): _validate(bad)
    m=DeltaMixer(3,2); s=m.encode(delta_events(torch.float32))
    for name in m._clock_keys:
        bad=replace(s,payload={**s.payload,name:s.payload[name].float()})
        with pytest.raises(ValueError,match='clock'): m.features(bad,queries(delta_events(torch.float32),[[8],[7]]))
    bad=replace(s,payload={**s.payload,'last_observed_time':torch.tensor([9,8])})
    with pytest.raises(ValueError,match='clock'): m.persistent_nbytes(bad)
