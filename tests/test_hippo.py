"""Independent finite-system controls for translated-Legendre event memory."""
from dataclasses import replace
import numpy as np
import pytest
import torch
from scipy.linalg import expm
from scipy.integrate import quad_vec
from famjet.memory.hippo import legendre_generator, impulse_transition, zoh_transition, PolynomialMemory
from jet_fixtures import events, queries, chunk, kernel_case


def test_order_two_sign_and_normalization():
    A, b = legendre_generator(2)
    np.testing.assert_allclose(A, [[-1, np.sqrt(3)], [-np.sqrt(3), -3]], atol=1e-15)
    np.testing.assert_array_equal(b, [1, np.sqrt(3)])
    assert A.dtype == b.dtype == np.float64


def test_impulse_composition_and_separate_zoh_integral():
    A, b = legendre_generator(3)
    tau, gap = 2.3, .7
    E, F = zoh_transition(A, b, gap, tau)
    expected = quad_vec(lambda age: expm(A*age/tau) @ b/tau, 0, gap)[0]
    np.testing.assert_allclose(F, expected, atol=1e-14)
    np.testing.assert_allclose(E, impulse_transition(A, gap, tau), atol=1e-14)
    np.testing.assert_allclose(impulse_transition(A, .2, tau) @ impulse_transition(A, .5, tau), E, atol=1e-14)
    np.testing.assert_array_equal(impulse_transition(A, 0, tau), np.eye(3))
    np.testing.assert_array_equal(zoh_transition(A, b, 0, tau)[1], np.zeros(3))
    assert not np.allclose(F, b/tau)  # sampled constant interval != unit event mass


def test_polynomial_stream_terminal_resume_against_dense(kernel_case):
    dtype, device, tol = kernel_case
    e = events(dtype, device)
    m = PolynomialMemory((2, 3), (2., 7.), 3, 2, dtype=dtype, device=device)
    actual = m.encode(e)
    terminal = m.encode(e, mode='terminal')
    resumed = m.encode(chunk(e, 3, 6), m.encode(chunk(e, 0, 3)))
    expected = np.zeros((2, 5, 3, 3))
    for row, length in enumerate(e.lengths.tolist()):
        for j in range(length):
            if not bool(e.observed[row,j].all()): continue
            X = np.outer(e.key_features[row,j].cpu().double(), np.r_[e.values[row,j].cpu().double(), 1.])*float(e.auxiliary['gate'][row,j])
            age = float(e.timestamps[row,length-1]-e.timestamps[row,j])
            start=0
            for order,tau in zip(m.orders,m.taus):
                A,b=legendre_generator(order)
                expected[row,start:start+order] += (expm(A*age/tau) @ b/tau)[:,None,None]*X
                start += order
    oracle=torch.tensor(expected[:,None], device=device,dtype=dtype)
    for state in (actual,terminal,resumed):
        torch.testing.assert_close(state.payload['p'],oracle,rtol=tol[0],atol=tol[1])
    before=actual.payload['p'].clone()
    m.features(actual,queries(e,[[20,8],[20,7]]))
    torch.testing.assert_close(actual.payload['p'],before,rtol=0,atol=0)


def test_zero_gap_is_exact_impulse_and_signed_coefficients_visible():
    e=chunk(events(),0,1)
    m=PolynomialMemory((2,), (2.,),3,2,dtype=torch.float64)
    s=m.encode(e)
    X=e.auxiliary['gate'][:,:,None,None]*e.key_features[:,:,:,None]*torch.cat((e.values,torch.ones_like(e.values[...,:1])),-1)[:,:,None,:]
    b=torch.tensor([1.,np.sqrt(3)],dtype=torch.float64)/2
    torch.testing.assert_close(s.payload['p'], X[:,:,None]*b[None,None,:,None,None],rtol=0,atol=0)
    s.payload['p'].neg_()
    f=m.features(s,queries(e,[[0],[2]]))
    assert f.supported.all() and (f.values < 0).any() and not f.diagnostics['failure'].any()


def polynomial_config(kind='generic_contracted', writer='fixed', device='cpu'):
    from famjet.config import load_config, PolynomialConfig
    from pathlib import Path
    c=load_config(Path('configs/smoke.yaml'))
    return replace(c, model=replace(c.model, method='polynomial', J=None, rates=None,
        polynomial=PolynomialConfig(orders=(2,2),taus=(2.,7.),declared_gaps=(0.,1.,2.,4.,16.)),
        reader=replace(c.model.reader,kind=kind,width=16,layers=1),writer=writer),
        resources=replace(c.resources,device=device,cache_limit_bytes=1024),
        data=replace(c.data,length=8,queries_per_history=2))


@pytest.mark.parametrize('kind',['generic_contracted','generic_full','query_only'])
def test_model_polynomial_full_pipeline_and_isolation(kind):
    from famjet.train import make_model, move_episode
    from famjet.data.synthetic import generate_episode
    from famjet.eval.isolation import export_method, _reconstruct, isolated_read
    from famjet.eval.budgets import budget_report
    c=polynomial_config(kind)
    m=make_model(c)
    ep=move_episode(generate_episode(c,14,'poly'),'cpu')
    state=m.encode(ep.events,mode='terminal')
    result=m.read(state,ep.queries)
    clone=_reconstruct(export_method(m))
    torch.testing.assert_close(result.prediction,clone.read(state,ep.queries).prediction,rtol=0,atol=0)
    torch.testing.assert_close(result.prediction,isolated_read(m,state,ep.queries).prediction)
    assert m.reader.schema['feature_spec']['coefficients'] == 4
    report=budget_report(m,state,limit_bytes=100000)
    assert report['eligible']
    assert report['state']['payload_bytes'] == 4*16*9*4
    assert not hasattr(m,'config') and not hasattr(m.kernel,'rates')


def test_config_explicit_polynomial_allocation_and_legacy_semantic_match():
    from dataclasses import asdict
    from famjet.config import config_documents_equal, load_config
    from pathlib import Path
    c=load_config(Path('configs/smoke.yaml'))
    old=asdict(c);old['model'].pop('polynomial')
    assert config_documents_equal(old,asdict(c))
    old['seed']+=1
    assert not config_documents_equal(old,asdict(c))
    old['unknown']=None
    with pytest.raises(ValueError): config_documents_equal(old,asdict(c))
    p=polynomial_config()
    with pytest.raises(ValueError): replace(p,model=replace(p.model,J=2))
    with pytest.raises(ValueError): replace(p,model=replace(p.model,rates=c.model.rates))
    with pytest.raises(ValueError): replace(c,model=replace(c.model,J=None))


@pytest.mark.parametrize('kind',['generic_contracted','generic_full'])
def test_complete_predictor_time_unit_and_large_timestamp_shift(kind):
    from famjet.train import make_model, move_episode
    from famjet.data.synthetic import generate_episode
    c=polynomial_config(kind)
    m=make_model(c); m.kernel.t_ref=3.
    ep=move_episode(generate_episode(c,17,'units'),'cpu')
    e,q=ep.events,ep.queries
    s=m.encode(e,mode='terminal'); features=m.features(s,q); prediction=m.read(s,q).prediction
    cscale=60.
    scaled=replace(c,model=replace(c.model,polynomial=replace(c.model.polynomial,
        taus=tuple(t*cscale for t in c.model.polynomial.taus),
        declared_gaps=tuple(g*cscale for g in c.model.polynomial.declared_gaps))))
    other=make_model(scaled); other.reader.load_state_dict(m.reader.state_dict()); other.kernel.t_ref=180.
    e2=replace(e,timestamps=e.timestamps*cscale,time_unit='seconds')
    q2=replace(q,T=q.T*cscale,age_start=q.age_start*cscale,age_end=q.age_end*cscale)
    s2=other.encode(e2,mode='terminal')
    torch.testing.assert_close(s2.payload['p']*cscale,s.payload['p'],rtol=1e-5,atol=1e-6)
    torch.testing.assert_close(other.features(s2,q2).values,features.values,rtol=1e-5,atol=1e-6)
    torch.testing.assert_close(other.read(s2,q2).prediction,prediction,rtol=1e-5,atol=1e-6)
    shift=2**60
    assert torch.equal(e.timestamps,e.timestamps.long().to(e.timestamps))
    assert torch.equal(q.T,q.T.long().to(q.T))
    e3=replace(e,timestamps=e.timestamps.long()+shift)
    q3=replace(q,T=q.T.long()+shift)
    torch.testing.assert_close(m.read(m.encode(e3,mode='terminal'),q3).prediction,prediction,rtol=0,atol=0)


def test_scalar_allocation_and_zero_cache_policy():
    from famjet.eval.budgets import model_ledger
    from famjet.eval.isolation import export_method
    m=PolynomialMemory(2,3.,3,2,declared_gaps=(),cache_limit_bytes=0,dtype=torch.float64)
    before=export_method(m)
    matrices,cost=m.prepare_transition(.333)
    assert cost['cpu_fp64_exponentials']==1 and cost['cache_bytes']==0
    assert cost['host_preparation_seconds'] >= 0
    assert model_ledger(m)['buffer_bytes']==16
    np.testing.assert_allclose(matrices[0],expm(legendre_generator(2)[0]*(.333/3.)),atol=1e-14)
    for gap in (.3,.7,100.): m.prepare_transition(gap)
    assert export_method(m)==before
    with pytest.raises(ValueError,match='cache'):
        PolynomialMemory((2,),(3.,),3,2,cache_limit_bytes=79)
    cached=PolynomialMemory((2,),(3.,),3,2,cache_limit_bytes=80)
    assert cached.preparation_cost([0,1,.5])['cpu_fp64_exponentials']==1
    assert model_ledger(cached)['buffer_bytes']==88


@pytest.mark.parametrize('mode',['stream','terminal'])
def test_terminal_full_gradients_match_stream_and_dense_values(mode,kernel_case):
    dtype,device,tol=kernel_case
    e=events(dtype,device)
    e=replace(e,values=e.values.clone().requires_grad_(),key_features=e.key_features.clone().requires_grad_(),
              auxiliary={'gate':e.auxiliary['gate'].clone().requires_grad_()})
    m=PolynomialMemory((2,3),(2.,7.),3,2,dtype=dtype,device=device,chunk_size=2)
    s=m.encode(e,mode=mode)
    loss=s.payload['p'].square().sum()
    grads=torch.autograd.grad(loss,(e.values,e.key_features,e.auxiliary['gate']))
    ref=replace(e,values=e.values.detach().cpu().double().requires_grad_(),
        key_features=e.key_features.detach().cpu().double().requires_grad_(),
        auxiliary={'gate':e.auxiliary['gate'].detach().cpu().double().requires_grad_()},
        present=e.present.cpu(),observed=e.observed.cpu())
    oracle=PolynomialMemory((2,3),(2.,7.),3,2,dtype=torch.float64,chunk_size=1)
    expected=oracle.encode(ref,mode='terminal').payload['p'].square().sum()
    refgrads=torch.autograd.grad(expected,(ref.values,ref.key_features,ref.auxiliary['gate']))
    for g,want in zip(grads,refgrads): torch.testing.assert_close(g.cpu().double(),want,rtol=tol[0],atol=tol[1])


def test_learned_writer_all_parameters_receive_matching_terminal_gradients():
    from famjet.train import make_model,move_episode
    from famjet.data.synthetic import generate_episode
    m=make_model(polynomial_config(writer='learned'))
    ep=move_episode(generate_episode(polynomial_config(writer='learned'),19,'grad'),'cpu')
    gradients=[]
    for mode in ['stream','terminal']:
        m.zero_grad(set_to_none=True)
        m.read(m.encode(ep.events,mode=mode),ep.queries).prediction.square().sum().backward()
        gradients.append({n:p.grad.clone() for n,p in m.named_parameters() if p.grad is not None})
    assert gradients[0]['writer.value.weight'].abs().sum()>0
    assert gradients[0]['writer.key.weight'].abs().sum()>0
    assert gradients[0]['writer.gate.weight'].abs().sum()>0
    for name,g in gradients[0].items(): torch.testing.assert_close(g,gradients[1][name],rtol=1e-5,atol=1e-6)


def test_constant_sampled_reconstruction_positive_control():
    from numpy.polynomial.legendre import legval
    A,b=legendre_generator(4)
    _,F=zoh_transition(A,b,100.,1.)
    coefficients=F*np.sqrt(2*np.arange(4)+1)*(-1.)**np.arange(4)
    np.testing.assert_allclose(legval(2*np.linspace(0,1,11)-1,coefficients),1.,atol=1e-12)
    # Constant event mass rate integrated through the impulse response has the
    # same stationary state, unlike a single unit impulse at interval end.
    integral=quad_vec(lambda t: expm(A*t) @ b,0,100)[0]
    np.testing.assert_allclose(integral,F,atol=1e-12)


def test_empty_unobserved_identity_and_failed_coefficients():
    from famjet.eval.state_io import snapshot_record,snapshot_from_record
    e=events(); m=PolynomialMemory((2,),(3.,),3,2,dtype=torch.float64)
    empty=m.init_state(2,device='cpu',dtype='float64')
    assert not m.features(empty,queries(e,[[100],[100]])).supported.any()
    no=replace(e,observed=torch.zeros_like(e.observed))
    state=m.encode(no)
    assert state.valid.all() and not state.payload['p'].any()
    assert state.last_time.tolist()==[8,7]
    restored=snapshot_from_record(snapshot_record(state),state.parameter_hash)
    with pytest.raises(ValueError,match='identity'): m.encode(replace(e,history_ids=('wrong','b')),restored)
    with pytest.raises(ValueError,match='time_unit'): m.encode(replace(e,time_unit='wrong'),restored)
    with pytest.raises(ValueError,match='before'): m.features(state,queries(e,[[7],[7]]))
    state.payload['p'][0,0,0,0,0]=float('nan')
    assert m.features(state,queries(e,[[8],[7]])).diagnostics['failure'][0].all()


@pytest.mark.parametrize('invalid', [True,0,-1,257])
def test_invalid_orders_reject(invalid):
    with pytest.raises(ValueError): legendre_generator(invalid)


def test_call_work_accounting_includes_uncached_terminal_and_query_gaps():
    e=events();q=queries(e,[[8,9],[7,8]])
    m=PolynomialMemory((2,),(3.,),3,2,dtype=torch.float64)
    cost=m.call_preparation_cost(e,q,mode='terminal',reader_kind='generic_full')
    assert cost['cpu_fp64_exponentials']>0 and cost['cache_bytes']==160
    assert cost['query_advances']==8 and cost['encode_advances']==14


@pytest.mark.parametrize('device',['cpu','mps'])
def test_polynomial_training_checkpoint_resume(tmp_path,monkeypatch,device):
    if device=='mps' and not torch.backends.mps.is_available(): pytest.skip('native MPS required')
    from famjet import train
    from famjet.checkpoint import load_checkpoint
    from test_resume import equal_tree
    c=polynomial_config(writer='learned',device=device)
    c=replace(c,data=replace(c.data,length=32),resources=replace(c.resources,cpu_threads=1))
    full=train.train_model(c,tmp_path/'full')
    original=train.history_loss
    calls=0
    def interrupt(*a,**kw):
        nonlocal calls
        calls+=1
        if calls==2: raise KeyboardInterrupt('polynomial boundary resume fixture')
        return original(*a,**kw)
    monkeypatch.setattr(train,'history_loss',interrupt)
    with pytest.raises(KeyboardInterrupt): train.train_model(c,tmp_path/'interrupted')
    monkeypatch.setattr(train,'history_loss',original)
    resumed=train.train_model(c,tmp_path/'resumed',resume=tmp_path/'interrupted'/'checkpoint.pt')
    a,b=load_checkpoint(full,{}),load_checkpoint(resumed,{})
    equal_tree(a['model_state'],b['model_state'],0 if device=='cpu' else 1e-5,0 if device=='cpu' else 1e-6)
    equal_tree(a['optimizer'],b['optimizer'],0 if device=='cpu' else 1e-5,0 if device=='cpu' else 1e-6)
    import json
    record=json.loads((tmp_path/'full'/'run.json').read_text())
    assert record['polynomial_construction']['cache_bytes']==160
    timing=json.loads((tmp_path/'full'/'timing.jsonl').read_text().splitlines()[0])
    assert timing['polynomial_preparation'][0]['cpu_fp64_exponentials']>0
    assert timing['polynomial_allocation']['orders']==[2,2]


@pytest.mark.parametrize('damage',['orders','taus','gaps','chunk','cache','dimension','dtype','weights','reader','config_orders'])
def test_raw_polynomial_checkpoint_guard_before_reconstruction(tmp_path,monkeypatch,damage):
    from famjet.train import make_model,_context,SMOKE_POLICY,identities,_source
    from famjet.checkpoint import save_checkpoint
    from famjet.provenance import canonical_hash
    from famjet import checkpoint
    c=polynomial_config()
    m=make_model(c)
    opt=torch.optim.AdamW(m.parameters(),lr=c.training.learning_rate,weight_decay=c.training.weight_decay)
    identity,data=identities(c,SMOKE_POLICY)
    ctx=_context(c,SMOKE_POLICY,identity,data,_source(),m,opt,0,[])
    ks=ctx['model']['schema']['kernel']['schema']
    if damage=='orders': ks['orders']=[1000000]
    elif damage=='taus': ks['taus']=[-1.,7.]
    elif damage=='gaps': ks['declared_gaps']=[.1]*100000
    elif damage=='chunk': ks['chunk_size']=1000000000
    elif damage=='cache': ks['cache_limit_bytes']=2**100
    elif damage=='dimension': ks['key_dim']=100000000
    elif damage=='dtype': ks['dtype']='float64'
    elif damage=='weights': ctx['model']['schema']['kernel']['weights']={'secret':{}}
    elif damage=='reader': ctx['model']['schema']['reader']['feature_spec']['coefficients']=100000000
    else:
        ctx['config']['model']['polynomial']['orders']=[9]
        ctx['config']['model']['polynomial']['taus']=[3.]
        ctx['config_hash']=canonical_hash(ctx['config'])
    ctx['model_hash']=canonical_hash(ctx['model'])
    import famjet.eval.isolation as isolation
    def forbidden(*a,**kw): pytest.fail('raw polynomial descriptor reached allocating reconstruction')
    monkeypatch.setattr(isolation,'_reconstruct',forbidden)
    before=torch.get_rng_state().clone()
    with pytest.raises(ValueError): save_checkpoint(tmp_path/'bad.pt',ctx)
    assert torch.equal(before,torch.get_rng_state())
    assert not (tmp_path/'bad.pt').exists()


def test_legacy_manifest_compatibility_preserves_seals_and_draw_hashes(tmp_path):
    from pathlib import Path
    import json
    from famjet.eval.splits import build_split_manifest,verify_split_manifest,_seal
    from famjet.config import load_config
    from famjet.provenance import canonical_hash
    c=load_config(Path('configs/smoke.yaml'))
    c=replace(c,data=replace(c.data,length=8,queries_per_history=2))
    path=tmp_path/'legacy.json'
    root=build_split_manifest(c,path)
    for record in root['populations'].values():
        p=path.parent/record['path'];pop=json.loads(p.read_text())
        pop['config']['model'].pop('polynomial')
        pop=_seal({k:v for k,v in pop.items() if k!='manifest_hash'})
        p.write_text(json.dumps(pop));record['manifest_hash']=pop['manifest_hash']
    root['config']['model'].pop('polynomial')
    root['config_hash']=canonical_hash(root['config'])
    root=_seal({k:v for k,v in root.items() if k!='manifest_hash'})
    path.write_text(json.dumps(root))
    before={p:p.read_bytes() for p in tmp_path.rglob('*.json')}
    assert verify_split_manifest(path)==root
    assert before=={p:p.read_bytes() for p in tmp_path.rglob('*.json')}
    original=path.read_text()
    root['config_hash']='0'*64
    path.write_text(json.dumps(_seal({k:v for k,v in root.items() if k!='manifest_hash'})))
    with pytest.raises(ValueError,match='config checksum'): verify_split_manifest(path)
    path.write_text(original)
    first=next(iter(root['populations'].values()))
    p=path.parent/first['path'];pop=json.loads(p.read_text())
    namespace=next(n for n,s in pop['splits'].items() if s['episodes'])
    pop['splits'][namespace]['episodes'][0]['hashes']['events']='0'*64
    pop=_seal({k:v for k,v in pop.items() if k!='manifest_hash'})
    p.write_text(json.dumps(pop))
    root=json.loads(original);root['populations'][next(iter(root['populations']))]['manifest_hash']=pop['manifest_hash']
    path.write_text(json.dumps(_seal({k:v for k,v in root.items() if k!='manifest_hash'})))
    with pytest.raises(ValueError,match='regenerated'): verify_split_manifest(path)


@pytest.mark.parametrize('length',[128,512,2048])
@pytest.mark.parametrize('order,tau',[(4,32.),(8,256.)])
def test_length_conditioning_and_long_gap_envelope(length,order,tau,kernel_case):
    dtype,device,tol=kernel_case
    from famjet.types import EventBatch
    rng=np.random.default_rng(20261016)
    gaps=rng.choice([0,1,2,4,16],size=length)
    gaps[0]=0
    times=np.cumsum(gaps,dtype=np.int64)
    values=rng.normal(size=(1,length,1))
    e=EventBatch(('long',),torch.arange(length)[None],torch.tensor(times)[None],
        torch.full((1,length),2**64-1,dtype=torch.uint64),torch.ones(1,length,1,device=device,dtype=dtype),
        torch.tensor(values,device=device,dtype=dtype),torch.tensor([length]),
        torch.ones(1,length,device=device,dtype=torch.bool),torch.ones(1,length,1,device=device,dtype=torch.bool),'ticks')
    m=PolynomialMemory(order,tau,1,1,dtype=dtype,device=device)
    state=m.encode(e)
    A,b=legendre_generator(order)
    # Direct impulse sum is independent of the streaming recurrence/adapter.
    expected=np.zeros((order,2))
    represented=e.values.detach().cpu().double().numpy()
    for j in range(length):
        expected+=(expm(A*((times[-1]-times[j])/tau)) @ (b/tau))[:,None]*np.r_[represented[0,j],1.]
    actual=state.payload['p'][0,0,:,0].cpu().double().numpy()
    np.testing.assert_allclose(actual,expected,rtol=tol[0],atol=tol[1])
    long=m.advance_copy(state,int(times[-1])+10000*int(tau))
    assert torch.isfinite(long.payload['p']).all() and long.payload['p'].abs().max() < 1e-12
    _,vec=np.linalg.eig(A)
    import json
    print(json.dumps({'order':order,'tau':tau,'length':length,'device':device,'dtype':str(dtype),
        'eigenvector_condition':float(np.linalg.cond(vec)),'max_absolute_error':float(np.max(np.abs(actual-expected))),
        'max_tolerance_ratio':float(np.max(np.abs(actual-expected)/(tol[1]+tol[0]*np.abs(expected)))),
        'long_gap_multiple':10000}))


def test_nonfinite_preparation_rejects_without_hidden_fallback():
    A,b=legendre_generator(2)
    for delta,tau in [(float('nan'),1.),(-1.,1.),(1.,0.),(1e308,1e-308)]:
        with pytest.raises(ValueError): impulse_transition(A,delta,tau)
    with pytest.raises(ValueError): zoh_transition(A,np.array([float('nan'),1.]),1.,1.)


def test_direct_config_requires_actual_typed_optional_dataclasses():
    from dataclasses import asdict
    from famjet.config import load_config
    from pathlib import Path
    c=load_config(Path('configs/smoke.yaml'))
    with pytest.raises(ValueError): replace(c,model=replace(c.model,rates=asdict(c.model.rates)))
    p=polynomial_config()
    with pytest.raises(ValueError): replace(p,model=replace(p.model,polynomial=asdict(p.model.polynomial)))


@pytest.mark.parametrize('field',['chunk_size','key_dim','value_dim','t_ref'])
def test_polynomial_constructor_rejects_unbounded_static_scalars(field):
    args=dict(orders=(2,),taus=(3.,),key_dim=3,value_dim=2)
    args[field]=2**1000
    with pytest.raises(ValueError): PolynomialMemory(**args)


def test_task_model_binds_polynomial_cache_allowance_to_logged_config():
    from famjet.train import make_model
    from famjet.models.task_model import TaskModel
    c=polynomial_config();m=make_model(c)
    c=replace(c,resources=replace(c.resources,cache_limit_bytes=4096))
    with pytest.raises(ValueError,match='cache'): TaskModel(m.kernel,m.reader,c)
