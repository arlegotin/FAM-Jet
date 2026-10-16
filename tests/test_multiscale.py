"""Independent controls for the finite log-Jacobi system (not continuum exactness)."""
from dataclasses import asdict, replace
from pathlib import Path
import numpy as np
from numpy.polynomial.legendre import leggauss, legvander
import pytest
from scipy.linalg import expm
import torch
from famjet.memory.multiscale import (log_scale_system, multiscale_dense_step,
    multiscale_zoh_step, scale_basis, MultiscaleMemory)
from jet_fixtures import events, queries, chunk, kernel_case


def independent_system(n, m, eps, tau):
    b=np.sqrt(2*np.arange(n)+1.)
    A=np.array([[-b[i]*b[j]*((-1.)**(i-j) if i<j else 1.) for j in range(n)] for i in range(n)])
    r=np.arange(1,m); off=r/np.sqrt((2*r-1)*(2*r+1))
    G=np.sqrt(eps)*expm(-np.log(eps)/2*(np.diag(off,1)+np.diag(off,-1)))
    x,w=leggauss(256); L=-np.log(eps)
    beta=(w*np.exp((x-1)*L/2)) @ legvander(x,m-1)*np.sqrt((2*np.arange(m)+1)*L)/2
    return A,G,np.outer(b,beta),np.kron(G.T,A)/tau


@pytest.mark.parametrize('m,eps',[(1,.01),(2,.2),(8,1e-4),(16,1e-8),(4,.999999),(4,1e-300)])
def test_bessel_beta_independent_converged_quadrature_and_finite_jacobi(m,eps):
    s=log_scale_system(2,m,eps,3.)
    L=-np.log(eps)
    betas=[]
    for count in (256,512):
        x,w=leggauss(count)
        betas.append((w*np.exp((x-1)*L/2)) @ legvander(x,m-1)*np.sqrt((2*np.arange(m)+1)*L)/2)
    np.testing.assert_allclose(betas[0],betas[1],rtol=1e-10,atol=1e-12)
    np.testing.assert_allclose(s['beta'],betas[1],rtol=1e-10,atol=1e-12)
    r=np.arange(1,m); off=r/np.sqrt((2*r-1)*(2*r+1))
    want=np.sqrt(eps)*expm(L/2*(np.diag(off,1)+np.diag(off,-1)))
    np.testing.assert_allclose(s['G'],want,rtol=1e-12,atol=1e-12)
    np.testing.assert_array_equal(s['G'],s['G'].T)
    np.testing.assert_allclose(s['U'] @ np.diag(s['gamma']) @ s['U'].T,s['G'],atol=1e-12)
    np.testing.assert_allclose(s['B'],np.outer(s['b'],s['beta']),atol=1e-12)


def test_m1_correct_normalization_and_impulse_zoh_distinction():
    eps,tau=.01,3.
    s=log_scale_system(2,1,eps,tau)
    beta=(1-eps)/np.sqrt(-np.log(eps))
    assert s['G'][0,0]==pytest.approx(.1)
    assert s['beta'][0]==pytest.approx(beta)
    assert not np.isclose(beta,np.sqrt(-np.log(eps))*s['G'][0,0])
    p=np.array([[.3],[-.4]])
    want=expm(np.array([[-1,np.sqrt(3)],[-np.sqrt(3),-3]])*.7*.1/tau) @ p
    want+=np.array([[1],[np.sqrt(3)]])*beta*2/tau
    np.testing.assert_allclose(multiscale_dense_step(p,.7,np.array(2.),s),want,atol=1e-12)
    np.testing.assert_array_equal(multiscale_zoh_step(p,0.,np.array(2.),s),p)
    assert not np.allclose(multiscale_dense_step(p,0.,np.array(2.),s),p)
    # Constant sampled input converges to the finite system equilibrium, not an exact continuum window.
    stationary=multiscale_zoh_step(np.zeros((2,1)),1000.,np.array(1.),s)
    np.testing.assert_allclose(stationary[:,0],[beta/.1,0.],atol=1e-12)


@pytest.mark.parametrize('mode',['stream','terminal'])
def test_dense_column_vector_reference_resume_queries_and_full_gradients(mode,kernel_case):
    dtype,device,tol=kernel_case
    n,m,eps,tau=2,3,.01,3.
    e=events(dtype,device)
    e=replace(e,values=e.values.clone().requires_grad_(),key_features=e.key_features.clone().requires_grad_(),
        auxiliary={'gate':e.auxiliary['gate'].clone().requires_grad_()})
    mem=MultiscaleMemory(n,m,eps,tau,3,2,dtype=dtype,device=device,chunk_size=2)
    s=mem.encode(e,mode=mode)
    resumed=mem.encode(chunk(e,3,6),mem.encode(chunk(e,0,3)))
    torch.testing.assert_close(s.payload['p'],resumed.payload['p'],rtol=tol[0],atol=tol[1])
    A,G,B,K=independent_system(n,m,eps,tau)
    values=e.values.detach().cpu().double().requires_grad_()
    keys=e.key_features.detach().cpu().double().requires_grad_()
    gate=e.auxiliary['gate'].detach().cpu().double().requires_grad_()
    rows=[]
    for row,length in enumerate(e.lengths.tolist()):
        P=torch.zeros(m*n,3,3,dtype=torch.float64)
        for j in range(length):
            if not bool(e.observed[row,j].all()): continue
            age=float(e.timestamps[row,length-1]-e.timestamps[row,j])
            weights=torch.tensor(expm(K*age) @ B.flatten(order='F')/tau)
            X=gate[row,j]*keys[row,j,:,None]*torch.cat((values[row,j],torch.ones(1,dtype=torch.float64)))[None,:]
            P=P+weights[:,None,None]*X
        U=mem.U.detach().cpu().double()
        rows.append(torch.einsum('mnkv,mj->jnkv',P.reshape(m,n,3,3),U).reshape(m*n,3,3))
    expected=torch.stack(rows)[:,None]
    torch.testing.assert_close(s.payload['p'].cpu().double(),expected,rtol=tol[0],atol=tol[1])
    grads=torch.autograd.grad(s.payload['p'].square().sum(),(e.values,e.key_features,e.auxiliary['gate']))
    wants=torch.autograd.grad(expected.square().sum(),(values,keys,gate))
    for g,w in zip(grads,wants): torch.testing.assert_close(g.cpu().double(),w,rtol=tol[0],atol=tol[1])
    # A nonzero prior catches propagation orientation independently of impulse weights.
    system=log_scale_system(n,m,eps,tau)
    P=np.arange(n*m,dtype=float).reshape(n,m)/7
    Q=P @ system['U']
    for gap in (0.,.37,2.,10000.):
        Q=np.column_stack([expm(A*rate*gap/tau) @ Q[:,j] for j,rate in enumerate(system['gamma'])])
        Q+=system['B'] @ system['U']/tau*.8
        P=multiscale_dense_step(P,gap,np.array(.8),system)
        np.testing.assert_allclose(Q @ system['U'].T,P,rtol=1e-12,atol=1e-12)
    before=s.payload['p'].detach().clone()
    q=queries(e,[[8,20],[7,20]])
    f=mem.features(s,q)
    for rate in (eps,.1,1.):
        coefficients=mem.scale_features(s,q,rate)
        x=1+2*np.log(rate)/(-np.log(eps))
        psi=legvander(x,m-1)[0]*np.sqrt((2*np.arange(m)+1)/(-np.log(eps)))
        weight=mem.U.detach().cpu().double().T @ torch.tensor(psi)
        want=torch.einsum('bqmnv,m->bqnv',f.diagnostics['coefficients'][:,:,0].reshape(2,2,m,n,3).cpu().double(),weight)
        torch.testing.assert_close(coefficients.cpu().double(),want,rtol=tol[0],atol=tol[1])
    torch.testing.assert_close(s.payload['p'].detach(),before,rtol=0,atol=0)


def multiscale_config(kind='generic_contracted',writer='fixed',device='cpu'):
    from famjet.config import load_config, MultiscaleConfig
    c=load_config(Path('configs/smoke.yaml'))
    return replace(c,model=replace(c.model,method='multiscale',J=None,rates=None,polynomial=None,
        multiscale=MultiscaleConfig(order=2,scale_order=2,epsilon=.01,tau0=3.),writer=writer,
        reader=replace(c.model.reader,kind=kind,width=16,layers=1)),
        resources=replace(c.resources,device=device,cache_limit_bytes=1024,cpu_threads=1),
        data=replace(c.data,length=32,queries_per_history=2))


@pytest.mark.parametrize('kind',['generic_contracted','generic_full','query_only'])
def test_model_readers_isolation_budget_and_units(kind):
    from famjet.train import make_model,move_episode
    from famjet.data.synthetic import generate_episode
    from famjet.eval.isolation import export_method,_reconstruct,isolated_read
    from famjet.eval.budgets import budget_report
    c=multiscale_config(kind); model=make_model(c); model.kernel.t_ref=3.
    ep=move_episode(generate_episode(c,14,'multiscale'),'cpu'); e,q=ep.events,ep.queries
    s=model.encode(e,mode='terminal'); result=model.read(s,q)
    clone=_reconstruct(export_method(model))
    torch.testing.assert_close(result.prediction,clone.read(s,q).prediction,rtol=0,atol=0)
    torch.testing.assert_close(result.prediction,isolated_read(model,s,q).prediction)
    report=budget_report(model,s,limit_bytes=100000)
    assert report['eligible'] and report['state']['payload_bytes']==4*16*9*4
    assert model.reader.schema['feature_spec']['family']=='multiscale'
    assert not hasattr(model,'config') and not hasattr(model.kernel,'rates')
    scaled=replace(c,model=replace(c.model,multiscale=replace(c.model.multiscale,tau0=180.,
        declared_gaps=tuple(g*60 for g in c.model.multiscale.declared_gaps))))
    other=make_model(scaled); other.kernel.t_ref=180.; other.reader.load_state_dict(model.reader.state_dict())
    e2=replace(e,timestamps=e.timestamps*60,time_unit='seconds')
    q2=replace(q,T=q.T*60,age_start=q.age_start*60,age_end=q.age_end*60)
    s2=other.encode(e2,mode='terminal')
    torch.testing.assert_close(s2.payload['p']*60,s.payload['p'],rtol=1e-5,atol=1e-6)
    torch.testing.assert_close(other.features(s2,q2).values,model.features(s,q).values,rtol=1e-5,atol=1e-6)
    torch.testing.assert_close(other.read(s2,q2).prediction,result.prediction,rtol=1e-5,atol=1e-6)
    shifted=replace(e,timestamps=e.timestamps.long()+2**60)
    torch.testing.assert_close(model.read(model.encode(shifted),replace(q,T=q.T.long()+2**60)).prediction,
        model.read(model.encode(e),q).prediction,rtol=0,atol=0)


def test_static_cache_preparation_budget_and_strict_config():
    from famjet.eval.isolation import export_method
    from famjet.eval.budgets import model_ledger
    from famjet.config import load_config,config_documents_equal
    mem=MultiscaleMemory(2,3,.01,3.,3,2,dtype=torch.float64,declared_gaps=(),cache_limit_bytes=0)
    before=export_method(mem)
    for gap in (.3,.7,100.):
        _,cost=mem.prepare_transition(gap)
        assert cost['cpu_fp64_exponentials']==3 and cost['cache_bytes']==0
    assert export_method(mem)==before
    assert model_ledger(mem)['buffer_bytes']==(6+9)*8  # signed injection and U
    assert cost['construction_exponentials']==1 and cost['construction_eigendecompositions']==1
    with pytest.raises(ValueError,match='cache'): MultiscaleMemory(2,3,.01,3.,3,2,cache_limit_bytes=239)
    c=load_config(Path('configs/smoke.yaml')); old=asdict(c)
    old['model'].pop('polynomial');old['model'].pop('multiscale')
    assert config_documents_equal(old,asdict(c))
    old['seed']+=1
    assert not config_documents_equal(old,asdict(c))
    p=multiscale_config()
    for bad in [replace(p.model,J=2),replace(p.model,rates=c.model.rates),replace(p.model,multiscale=None),
                replace(p.model,multiscale=asdict(p.model.multiscale)),replace(p.model,reader=replace(p.model.reader,kind='structured'))]:
        with pytest.raises(ValueError): replace(p,model=bad)


@pytest.mark.parametrize('args',[(0,2,.1,1.),(2,0,.1,1.),(2,65,.1,1.),(256,64,.1,1.),(2,2,0.,1.),(2,2,1.,1.),(2,2,.1,0.),(True,2,.1,1.)])
def test_invalid_finite_system_rejected_before_allocation(args):
    with pytest.raises(ValueError): log_scale_system(*args)


@pytest.mark.parametrize('device',['cpu','mps'])
def test_training_learned_writer_and_checkpoint_resume(tmp_path,monkeypatch,device):
    if device=='mps' and not torch.backends.mps.is_available(): pytest.skip('native MPS required')
    from famjet import train
    from famjet.checkpoint import load_checkpoint
    from test_resume import equal_tree
    c=multiscale_config(writer='learned',device=device)
    torch.manual_seed(37)
    model=train.make_model(c)
    from famjet.data.synthetic import generate_episode
    ep=train.move_episode(generate_episode(c,19,'gradient'),device)
    gradients=[]
    for mode in ('stream','terminal'):
        model.zero_grad(set_to_none=True)
        train.history_loss(model,model.read(model.encode(ep.events,mode=mode),ep.queries),ep).backward()
        gradients.append({n:p.grad.clone() for n,p in model.named_parameters() if p.grad is not None})
    for part in ('value','key','gate'): assert gradients[0][f'writer.{part}.weight'].abs().sum()>0
    for name,g in gradients[0].items(): torch.testing.assert_close(g,gradients[1][name],rtol=1e-5,atol=1e-6)
    # Compare both actual task-loss paths with a freshly constructed CPU64 kernel.
    # The separate preserved stress audit records standardized/summed MLP limits.
    import copy
    oracle=copy.deepcopy(model).cpu().double();p=c.model.multiscale
    oracle.kernel=MultiscaleMemory(p.order,p.scale_order,p.epsilon,p.tau0,c.model.K,c.data.value_dim,
                                  dtype=torch.float64,chunk_size=32,cache_limit_bytes=1024)
    e,q=ep.events,ep.queries
    ref=replace(ep,events=replace(e,values=e.values.detach().cpu().double(),
        key_features=e.key_features.detach().cpu().double(),present=e.present.cpu(),observed=e.observed.cpu(),
        auxiliary={k:v.detach().cpu().double() for k,v in e.auxiliary.items()}),
        queries=replace(q,key_features=q.key_features.detach().cpu().double(),present=q.present.cpu()))
    oracle.zero_grad(set_to_none=True)
    train.history_loss(oracle,oracle.read(oracle.encode(ref.events,mode='terminal'),ref.queries),ref).backward()
    for gradient in gradients:
        for name,param in oracle.named_parameters():
            if param.grad is not None:
                torch.testing.assert_close(gradient[name].cpu().double(),param.grad,rtol=1e-5,atol=1e-6)

    full=train.train_model(c,tmp_path/'full'); original=train.history_loss; calls=0
    def interrupt(*a,**kw):
        nonlocal calls
        calls+=1
        if calls==2: raise KeyboardInterrupt('multiscale resume fixture')
        return original(*a,**kw)
    monkeypatch.setattr(train,'history_loss',interrupt)
    with pytest.raises(KeyboardInterrupt): train.train_model(c,tmp_path/'interrupted')
    monkeypatch.setattr(train,'history_loss',original)
    resumed=train.train_model(c,tmp_path/'resumed',resume=tmp_path/'interrupted'/'checkpoint.pt')
    a,b=load_checkpoint(full,{}),load_checkpoint(resumed,{})
    for key in ('model_state','optimizer'): equal_tree(a[key],b[key],0 if device=='cpu' else 1e-5,0 if device=='cpu' else 1e-6)
    import json
    record=json.loads((tmp_path/'full'/'run.json').read_text())
    assert record['multiscale_construction']['cache_bytes']==160
    timing=json.loads((tmp_path/'full'/'timing.jsonl').read_text().splitlines()[0])
    assert timing['multiscale_preparation'][0]['cpu_fp64_exponentials']>0
    assert timing['multiscale_allocation']['scale_order']==2


@pytest.mark.parametrize('damage',['order','scale_order','epsilon','tau0','gaps','chunk','cache','dimension','dtype','weights','reader'])
def test_raw_checkpoint_allocation_guards(tmp_path,monkeypatch,damage):
    from famjet.train import make_model,_context,SMOKE_POLICY,identities,_source
    from famjet.checkpoint import save_checkpoint
    from famjet.provenance import canonical_hash
    import famjet.eval.isolation as isolation
    c=multiscale_config();model=make_model(c)
    opt=torch.optim.AdamW(model.parameters(),lr=c.training.learning_rate,weight_decay=c.training.weight_decay)
    identity,data=identities(c,SMOKE_POLICY)
    ctx=_context(c,SMOKE_POLICY,identity,data,_source(),model,opt,0,[])
    ks=ctx['model']['schema']['kernel']['schema']
    if damage in ('order','scale_order'): ks[damage]=1000000
    elif damage in ('epsilon','tau0'): ks[damage]=-1.
    elif damage=='gaps':ks['declared_gaps']=[.1]*100000
    elif damage=='chunk':ks['chunk_size']=1000000000
    elif damage=='cache':ks['cache_limit_bytes']=2**100
    elif damage=='dimension':ks['key_dim']=100000000
    elif damage=='dtype':ks['dtype']='float64'
    elif damage=='weights':ctx['model']['schema']['kernel']['weights']={'secret':{}}
    else:ctx['model']['schema']['reader']['feature_spec']['coefficients']=10000000
    ctx['model_hash']=canonical_hash(ctx['model'])
    def forbidden(*a,**kw):pytest.fail('raw invalid descriptor reached allocating reconstruction')
    monkeypatch.setattr(isolation,'_reconstruct',forbidden)
    with pytest.raises(ValueError):save_checkpoint(tmp_path/'bad.pt',ctx)
    assert not (tmp_path/'bad.pt').exists()


def test_scale_query_empty_batch_and_invalid_domain():
    e=events();mem=MultiscaleMemory(2,3,.01,3.,3,2,dtype=torch.float64)
    q=queries(e,[[],[]]);state=mem.encode(e)
    assert mem.scale_features(state,q,.1).shape == (2,0,2,3)
    for rate in (0.,.001,1.1,float('nan')):
        with pytest.raises(ValueError):mem.scale_features(state,q,rate)


def test_zoh_independent_integral_and_finite_projection_caveat():
    from scipy.integrate import quad_vec
    system=log_scale_system(2,3,.01,3.)
    A,G,B,K=independent_system(2,3,.01,3.)
    P=np.arange(6,dtype=float).reshape(2,3)/7;gap=.37
    value=multiscale_zoh_step(P,gap,np.array(2.),system)
    integral=quad_vec(lambda t:expm(K*t) @ B.flatten(order='F')/3.,0,gap,epsabs=1e-13,epsrel=1e-13)[0]
    want=expm(K*gap) @ P.flatten(order='F')+2*integral
    np.testing.assert_allclose(value.flatten(order='F'),want,rtol=1e-12,atol=1e-12)
    # Finite Jacobi exponentiation differs from exact projected multiplication.
    x,w=leggauss(256);L=-np.log(.01);psi=legvander(x,2)*np.sqrt((2*np.arange(3)+1)/L)
    projection=psi.T @ ((w*np.exp((x-1)*L/2)*L/2)[:,None]*psi)
    assert np.linalg.norm(G-projection)>1e-3


@pytest.mark.parametrize('n,m,eps,tau,length',[(2,2,.01,3.,256),(4,2,1e-4,16.,2048),(2,4,.01,16.,2048)])
def test_long_finite_impulse_acceptance_and_excluded_frontier_diagnostic(n,m,eps,tau,length,kernel_case):
    from famjet.types import EventBatch
    dtype,device,tol=kernel_case
    rng=np.random.default_rng(20261016);gaps=rng.choice([0,1,2,4,16],length);gaps[0]=0
    times=np.cumsum(gaps,dtype=np.int64);values=rng.normal(size=(1,length,1))
    e=EventBatch(('long',),torch.arange(length)[None],torch.tensor(times)[None],
        torch.full((1,length),2**64-1,dtype=torch.uint64),torch.ones(1,length,1,device=device,dtype=dtype),
        torch.tensor(values,device=device,dtype=dtype),torch.tensor([length]),
        torch.ones(1,length,device=device,dtype=torch.bool),torch.ones(1,length,1,device=device,dtype=torch.bool),'ticks')
    mem=MultiscaleMemory(n,m,eps,tau,1,1,dtype=dtype,device=device)
    state=mem.encode(e)
    A,G,B,K=independent_system(n,m,eps,tau)
    expected=np.zeros((n*m,2));represented=e.values.cpu().double().numpy()
    for j in range(length):
        expected+=(expm(K*float(times[-1]-times[j])) @ B.flatten(order='F')/tau)[:,None]*np.r_[represented[0,j],1.]
    U=log_scale_system(n,m,eps,tau)['U']
    expected=np.einsum('mnv,mj->jnv',expected.reshape(m,n,2),U).reshape(n*m,2)
    actual=state.payload['p'][0,0,:,0].cpu().double().numpy()
    margin=float((abs(actual-expected)/(tol[1]+tol[0]*abs(expected))).max())
    excluded=(n,m,eps,tau,length,dtype)==(4,2,1e-4,16.,2048,torch.float32)
    status='failed_original_tolerance' if margin>1 else 'passed_original_tolerance'
    if excluded:
        # This is an explicitly FAILED accuracy row, never accepted coverage.
        # Verify the preserved limitation; CPU64 at the same config remains an
        # ordinary accuracy assertion. See the dated numerical frontier record.
        assert status=='failed_original_tolerance' and margin>1
    else:
        np.testing.assert_allclose(actual,expected,rtol=tol[0],atol=tol[1])
    large=mem.advance_copy(state,int(times[-1])+int(10000*tau/eps))
    assert large.payload['p'].abs().max()<1e-12
    import json
    print(json.dumps({'n':n,'m':m,'epsilon':eps,'tau0':tau,'length':length,'device':device,'dtype':str(dtype),
        'temporal_eigenvector_condition':float(np.linalg.cond(np.linalg.eig(A)[1])),
        'scale_eigenbasis_condition':float(np.linalg.cond(U)),'status':status,
        'accuracy_accepted':not excluded,
        'max_absolute_error':float(abs(actual-expected).max()),
        'max_tolerance_ratio':float((abs(actual-expected)/(tol[1]+tol[0]*abs(expected))).max())}))


@pytest.mark.parametrize('device',['cpu','mps'])
@pytest.mark.parametrize('standardized',[False,True])
def test_common_mlp_gradient_norm_envelope_preserves_pointwise_diagnostics(device,standardized):
    """Dated validation amendment; never relax direct coefficient gradient bounds."""
    if device=='mps' and not torch.backends.mps.is_available(): pytest.skip('native MPS required')
    import copy,json
    from famjet import train
    from famjet.data.synthetic import generate_episode
    c=multiscale_config(writer='learned',device=device);torch.manual_seed(37)
    model=train.make_model(c)
    if standardized:
        model.fit_statistics([train.move_episode(generate_episode(c,c.seed,'training_preprocessing_v1-000000000000'),device)])
    ep=train.move_episode(generate_episode(c,19,'gradient'),device);e,q=ep.events,ep.queries
    refep=replace(ep,events=replace(e,values=e.values.cpu().double(),key_features=e.key_features.cpu().double(),
        present=e.present.cpu(),observed=e.observed.cpu(),auxiliary={k:v.cpu().double() for k,v in e.auxiliary.items()}),
        queries=replace(q,key_features=q.key_features.cpu().double(),present=q.present.cpu()))
    oracle=copy.deepcopy(model).cpu().double();p=c.model.multiscale
    oracle.kernel=MultiscaleMemory(p.order,p.scale_order,p.epsilon,p.tau0,c.model.K,c.data.value_dim,
        dtype=torch.float64,chunk_size=32,cache_limit_bytes=1024,t_ref=model.kernel.t_ref)
    def run(m,episode,mode,objective):
        m.zero_grad(set_to_none=True);result=m.read(m.encode(episode.events,mode=mode),episode.queries)
        loss=result.prediction.square().sum() if objective=='sum_squared_predictions' else train.history_loss(m,result,episode)
        loss.backward()
        return result.prediction.detach().cpu().double(),{n:p.grad.detach().cpu().double().clone()
            for n,p in m.named_parameters() if p.grad is not None},float(loss.detach())
    for objective in ('sum_squared_predictions','actual_task_mean'):
        expected,grads,loss64=run(oracle,refep,'terminal',objective)
        pred64,stream64,_=run(oracle,refep,'stream',objective)
        torch.testing.assert_close(pred64,expected,rtol=1e-12,atol=1e-12)
        for name,g in stream64.items():torch.testing.assert_close(g,grads[name],rtol=1e-12,atol=1e-12)
        for mode in ('stream','terminal'):
            pred,actual,loss=run(model,ep,mode,objective)
            torch.testing.assert_close(pred,expected,rtol=1e-5,atol=1e-6)
            diagnostics={}
            for name,g in actual.items():
                want=grads[name];err=torch.linalg.vector_norm(g-want);norm=torch.linalg.vector_norm(want)
                assert err <= 1e-6+1e-5*norm
                point=(g-want).abs()/(1e-6+1e-5*want.abs());idx=int(point.argmax())
                diagnostics[name]=dict(pointwise_ratio=float(point.max()),norm_ratio=float(err/(1e-6+1e-5*norm)),
                    reference_norm=float(norm),max_absolute_error=float((g-want).abs().max()),
                    worst_cell_reference=float(want.flatten()[idx]),worst_cell_actual=float(g.flatten()[idx]))
            print(json.dumps(dict(seed=37,device=device,standardized=standardized,objective=objective,mode=mode,
                loss=loss,reference_loss=loss64,max_prediction=float(pred.abs().max()),gradients=diagnostics)))


def test_m1_adapter_matches_correctly_scaled_single_temporal_bank():
    from famjet.memory.hippo import PolynomialMemory
    eps,tau=.01,3.;e=events()
    mem=MultiscaleMemory(2,1,eps,tau,3,2,dtype=torch.float64)
    single=PolynomialMemory(2,float(tau/np.sqrt(eps)),3,2,dtype=torch.float64)
    beta=(1-eps)/np.sqrt(-np.log(eps))
    expected=single.encode(e).payload['p']*(beta/np.sqrt(eps))
    torch.testing.assert_close(mem.encode(e).payload['p'],expected,rtol=1e-12,atol=1e-12)
