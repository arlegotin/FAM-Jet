"""Independent numerical and gate tests for supplementary source controls."""
from dataclasses import asdict, replace
from pathlib import Path
import math
import json
import numpy as np
import pytest
import torch
import yaml


def test_stehfest_factorial_fixtures_and_invalid_orders():
    from famjet.memory.gaver import stehfest_weights
    np.testing.assert_allclose(stehfest_weights(2), [2*math.log(2), -2*math.log(2)], rtol=1e-14)
    np.testing.assert_allclose(stehfest_weights(4)/math.log(2), [-2,26,-48,24], rtol=1e-14)
    for n in (0,1,3,-2,True,2.0,66):
        with pytest.raises(ValueError): stehfest_weights(n)


def test_impulse_high_precision_literal_and_fp32_cancellation():
    from famjet.memory.gaver import gaver_rates, gaver_step, reconstruct
    results={}
    for dtype in (np.float32,np.float64):
        rates=gaver_rates((1.,),12,dtype=dtype)
        state=np.zeros((1,12,1),dtype=dtype)
        state=gaver_step(state,np.array([1.],dtype=dtype),0.,rates,mode='impulse')
        state=gaver_step(state,np.array([0.],dtype=dtype),.7,rates,mode='impulse')
        results[dtype]=reconstruct(state,(1.,),mode='impulse',t_ref=1.)[0,0]
    # Exact rational factorial coefficients; Decimal ln/exp at precision80.
    reference=.73312172921452106204882399047192439244745567520034622709730209101060754139530
    assert abs(results[np.float64]-reference)<1e-8
    assert abs(results[np.float32]-reference)>100*abs(results[np.float64]-reference)


def test_gaver_no_rate_dedup_and_distinct_zero_gap_input_semantics():
    from famjet.memory.gaver import gaver_rates, gaver_step, reconstruct
    rates=gaver_rates((1.,2.),4)
    assert rates.shape==(2,4) and rates[0,0]==rates[1,1]
    state=np.zeros((2,4,1)); value=np.array([3.])
    np.testing.assert_array_equal(gaver_step(state,value,0.,rates,mode='impulse'),np.full_like(state,3.))
    np.testing.assert_array_equal(gaver_step(state,value,0.,rates,mode='zoh_current_interval'),state)
    zoh=gaver_step(state,value,2.,rates,mode='zoh_current_interval')
    np.testing.assert_allclose(zoh[...,0],3*(-np.expm1(-rates*2))/rates)
    np.testing.assert_allclose(reconstruct(zoh,(1.,2.),mode='zoh_current_interval',t_ref=7.),
                               reconstruct(zoh,(1.,2.),mode='zoh_current_interval',t_ref=1.))
    with pytest.raises(ValueError): gaver_step(state,value,-1.,rates,mode='impulse')


def test_scalar_legendre_basis_and_minimum_norm_hand_calculation():
    from famjet.memory.associative_hippo import location_basis, minimum_norm_delta
    x=torch.tensor([0.,.5,1.],dtype=torch.float64)
    expected=torch.tensor([[1,math.sqrt(3),math.sqrt(5)],
                           [1,0,-math.sqrt(5)/2],[1,-math.sqrt(3),math.sqrt(5)]],dtype=torch.float64)
    torch.testing.assert_close(location_basis(x,3),expected)
    C=torch.tensor([[[1.,2.],[3.,4.]]],dtype=torch.float64)
    # At x=.5, k=(1,0); gate .5 and values=(5,7) add 2/(1+1e-8) to first coefficient.
    updated=minimum_norm_delta(C,torch.tensor([.5],dtype=torch.float64),
        torch.tensor([[5.,7.]],dtype=torch.float64),torch.tensor([[.5]],dtype=torch.float64))
    torch.testing.assert_close(updated,torch.tensor([[[1+2/(1+1e-8),2.],[3+2/(1+1e-8),4.]]],dtype=torch.float64))


def test_original_native_control_is_causal_and_counts_both_arrays():
    from famjet.memory.associative_hippo import OriginalAssociativeHiPPO
    model=OriginalAssociativeHiPPO(embedding_dim=3,channels=2,history_order=2,associative_order=3,hidden=4,seed=42)
    x=torch.tensor([[[1.,-1.,.5],[2.,3.,-1.],[0.,1.,0.]]])
    out,state=model(x)
    changed=x.clone(); changed[:,2]=99
    other,_=model(changed)
    torch.testing.assert_close(out[:,:2],other[:,:2])
    first,partial=model(x[:,:1]); tail,continued=model(x[:,1:],partial)
    torch.testing.assert_close(out,torch.cat((first,tail),1))
    for a,b in zip(state,continued): torch.testing.assert_close(a,b)
    assert sum(t.numel()*t.element_size() for t in state)==2*(2+3)*4
    out.square().mean().backward()
    assert all(p.grad is not None and torch.isfinite(p.grad).all() for p in model.parameters())


def test_original_post_write_read_and_zoh_history_small_calculation():
    from famjet.memory.associative_hippo import OriginalAssociativeHiPPO
    model=OriginalAssociativeHiPPO(embedding_dim=1,channels=1,history_order=1,associative_order=2,hidden=1)
    with torch.no_grad():
        for p in model.parameters(): p.zero_()
        model.input.weight.fill_(1.)
        model.value.weight.fill_(2.); model.value.bias.fill_(1.)
        model.output.weight.fill_(3.); model.output.bias.fill_(4.)
    out,(S,C)=model(torch.tensor([[[2.]]]),(torch.ones(1,1,1),torch.tensor([[[1.,2.]]])))
    # Global key=query=.5 -> phi=(1,0); gates=.5; u2 -> value5.
    torch.testing.assert_close(S,torch.tensor([[[2-math.exp(-.5)]]]))
    torch.testing.assert_close(C,torch.tensor([[[1+2/(1+1e-8),2.]]]))
    torch.testing.assert_close(out,torch.tensor([[[.5*(3*(1+2/(1+1e-8))+4)]]]))


def test_source_fixture_revisions_targets_and_shared_token_table():
    from famjet.memory.associative_hippo import token_table, associative_episodes
    tokens=token_table(42,12,24)
    x,y,ids=associative_episodes(tokens,64,42)
    assert x.shape==y.shape==(64,12,24)
    assert np.count_nonzero(y[:,:-1])==0
    for row,target in zip(ids,y[:,-1]):
        assert row[-1]==24
        last=max(j for j in range(0,10,2) if row[j]==row[-2])
        np.testing.assert_array_equal(target,tokens[row[last+1]])
    eval_x,_,eval_ids=associative_episodes(tokens,16,44)
    np.testing.assert_array_equal(eval_x,tokens[eval_ids])
    assert not any(np.array_equal(a,b) for a in ids for b in eval_ids)


def test_reproduction_config_is_explicit_and_separate_from_main_training():
    from famjet.config import load_config
    from famjet.reproduce import load_reproduction_config
    path=Path('configs/baseline_reproduction.yaml')
    cfg=load_reproduction_config(path)
    assert cfg.reproduction.associative.max_steps==3500
    with pytest.raises(ValueError,match='unknown fields'): load_config(path)
    with pytest.raises(ValueError): replace(cfg,reproduction=replace(cfg.reproduction,max_seconds=-1.))
    with pytest.raises(ValueError): replace(cfg,phase='development')


def test_reproduction_rejects_raising_both_configurable_limits():
    from famjet.reproduce import load_reproduction_config
    cfg=load_reproduction_config(Path('configs/baseline_reproduction.yaml'))
    with pytest.raises(ValueError,match='ceiling|provenance|registered'):
        replace(cfg,resources=replace(cfg.resources,smoke_additional_allocation_limit_bytes=402653184),
                reproduction=replace(cfg.reproduction,additional_peak_limit_bytes=402653184))


@pytest.mark.parametrize('discovered', [None, [], {}, {'resource_policy':None},
    {'resource_policy':{'status':'smoke_only','smoke_additional_allocation_limit_bytes':True}},
    {'resource_policy':{'status':'smoke_only','smoke_additional_allocation_limit_bytes':201326592.0}},
    {'resource_policy':{'status':'uncalibrated','smoke_additional_allocation_limit_bytes':201326592}},
    {'resource_policy':{'status':'smoke_only','smoke_additional_allocation_limit_bytes':-1}}])
def test_reproduction_rejects_invalid_discovery_before_allocation(tmp_path,discovered):
    from famjet.reproduce import load_reproduction_config
    cfg=load_reproduction_config(Path('configs/baseline_reproduction.yaml'))
    path=tmp_path/'hardware.json'; path.write_text(json.dumps(discovered))
    with pytest.raises(ValueError,match='provenance'):
        replace(cfg,resources=replace(cfg.resources,resource_provenance=str(path)))


def test_reproduction_independently_binds_common_limit_and_preserves_net_reserve(tmp_path):
    from famjet.reproduce import load_reproduction_config
    cfg=load_reproduction_config(Path('configs/baseline_reproduction.yaml'))
    # A smaller actual discovery must restrict the common limit even when the
    # reproduction-specific request is already below both limits.
    path=tmp_path/'hardware.json'
    path.write_text(json.dumps({'resource_policy':{'status':'smoke_only',
        'smoke_additional_allocation_limit_bytes':180000000}}))
    with pytest.raises(ValueError,match='discovered|provenance'):
        replace(cfg,resources=replace(cfg.resources,resource_provenance=str(path)),
                reproduction=replace(cfg.reproduction,additional_peak_limit_bytes=170000000))
    accepted=replace(cfg,resources=replace(cfg.resources,resource_provenance=str(path),
                     smoke_additional_allocation_limit_bytes=180000000),
                     reproduction=replace(cfg.reproduction,additional_peak_limit_bytes=177471488))
    assert accepted.reproduction.additional_peak_limit_bytes==177471488


@pytest.mark.parametrize('fault',['raised_both','missing','malformed','common_above_discovery','raised_discovery'])
def test_reproduction_entrypoint_revalidates_authorization_before_allocation(tmp_path,monkeypatch,fault):
    import famjet.reproduce as reproduction
    cfg=reproduction.load_reproduction_config(Path('configs/baseline_reproduction.yaml'))
    def forbidden(*args,**kwargs): pytest.fail('unauthorized fixture/model allocation')
    monkeypatch.setattr(reproduction,'token_table',forbidden)
    monkeypatch.setattr(reproduction,'OriginalAssociativeHiPPO',forbidden)
    path=tmp_path/'hardware.json'
    if fault in {'raised_both','raised_discovery'}:
        object.__setattr__(cfg,'resources',replace(cfg.resources,smoke_additional_allocation_limit_bytes=402653184))
        object.__setattr__(cfg,'reproduction',replace(cfg.reproduction,additional_peak_limit_bytes=402653184))
    if fault=='raised_discovery':
        path.write_text(json.dumps({'resource_policy':{'status':'smoke_only','smoke_additional_allocation_limit_bytes':402653184}}))
    if fault=='malformed': path.write_text('{invalid JSON')
    if fault=='common_above_discovery':
        path.write_text(json.dumps({'resource_policy':{'status':'smoke_only','smoke_additional_allocation_limit_bytes':100000000}}))
    if fault!='raised_both':
        object.__setattr__(cfg,'resources',replace(cfg.resources,resource_provenance=str(path)))
    with pytest.raises(ValueError,match='ceiling|provenance|registered'):
        reproduction.reproduce_baseline('associative_original',cfg,tmp_path/'out')
    assert not (tmp_path/'out').exists()


@pytest.mark.parametrize('fault',['raised_both','missing','malformed','duplicate'])
def test_reproduction_cli_rejects_unauthorized_config_before_outputs(tmp_path,monkeypatch,fault):
    import famjet.reproduce as reproduction
    cfg=asdict(reproduction.load_reproduction_config(Path('configs/baseline_reproduction.yaml')))
    def forbidden(*args,**kwargs): pytest.fail('CLI allocated unauthorized source fixture')
    monkeypatch.setattr(reproduction,'token_table',forbidden)
    monkeypatch.setattr(reproduction,'OriginalAssociativeHiPPO',forbidden)
    if fault=='raised_both':
        cfg['resources']['smoke_additional_allocation_limit_bytes']=402653184
        cfg['reproduction']['additional_peak_limit_bytes']=402653184
    else:
        provenance=tmp_path/'discovery.json'
        if fault=='malformed': provenance.write_text('{')
        if fault=='duplicate':
            provenance.write_text('{"resource_policy":{},"resource_policy":{"status":"smoke_only",'
                                  '"smoke_additional_allocation_limit_bytes":201326592}}')
        cfg['resources']['resource_provenance']=str(provenance)
    path=tmp_path/'config.yaml'; path.write_text(yaml.safe_dump(cfg))
    with pytest.raises(ValueError,match='ceiling|provenance|registered'):
        reproduction.main(['--config',str(path),'--out',str(tmp_path/'out')])
    assert not (tmp_path/'out').exists()


def test_dispatcher_records_equations_and_explicit_exclusions(tmp_path):
    from famjet.reproduce import load_reproduction_config, reproduce_baseline
    cfg=load_reproduction_config(Path('configs/baseline_reproduction.yaml'))
    report=reproduce_baseline('gaver_equations',cfg,tmp_path)
    assert report['status']=='component_passed'
    assert report['integrated_competitor'] is False
    authorization=report['resource_authorization']
    assert authorization['authorized_additional_peak_limit_bytes']==201326592
    assert authorization['discovered_net_ceiling_bytes']==201326592
    import hashlib
    assert authorization['provenance_sha256']==hashlib.sha256(Path('artifacts/environment/hardware.json').read_bytes()).hexdigest()
    assert report['precision_frontier'][1]['state_bytes']==2*report['precision_frontier'][0]['state_bytes']
    assert report['cancellation']['float32_absolute_error']>report['cancellation']['float64_absolute_error']
    fp64=report['precision_frontier'][1]
    assert fp64['exponential_arithmetic_absolute_error']<1e-8
    assert fp64['exponential_finite_N_approximation_absolute_error']>1e-6
    assert fp64['exponential_exact_finite_N_reference']==pytest.approx(.3678693892124888829,abs=1e-16)
    for name in ('gaver_deferred','associative_deferred','compact_gru_routing','gaver_source_reuse'):
        excluded=reproduce_baseline(name,cfg,tmp_path)
        assert excluded['status']=='excluded_preconfirmation' and excluded['reason']
        assert excluded['integrated_competitor'] is False
    with pytest.raises(ValueError): reproduce_baseline('typo',cfg,tmp_path)
    with pytest.raises(FileExistsError): reproduce_baseline('gaver_equations',cfg,tmp_path)


def test_source_resource_failure_is_retained_before_training(tmp_path):
    from famjet.reproduce import load_reproduction_config, reproduce_baseline
    cfg=load_reproduction_config(Path('configs/baseline_reproduction.yaml'))
    cfg=replace(cfg,reproduction=replace(cfg.reproduction,max_seconds=1e-12))
    report=reproduce_baseline('associative_original',cfg,tmp_path)
    assert report['status']=='component_failed'
    assert report['steps_completed']==0
    assert report['failure']['type']=='RuntimeError'
    assert 'metrics' not in report


def test_short_source_control_retains_failure_and_rejects_zero_target_success(tmp_path):
    from famjet.reproduce import load_reproduction_config, reproduce_baseline
    cfg=load_reproduction_config(Path('configs/baseline_reproduction.yaml'))
    a=replace(cfg.reproduction.associative,max_steps=1,train_episodes=16,eval_episodes=8)
    cfg=replace(cfg,reproduction=replace(cfg.reproduction,associative=a))
    report=reproduce_baseline('associative_original',cfg,tmp_path)
    assert report['status']=='component_unaccepted'
    assert report['steps_completed']==1
    assert report['metrics']['final_write_mse']>report['metrics']['all_step_mse']
    assert report['metrics']['b_retrieval_accuracy']<a.min_retrieval_accuracy
    assert report['state_bytes']==32*(32+32)*4
    assert report['data']['train_hash']!=report['data']['eval_hash']
    assert (tmp_path/'associative_original'/'trials.jsonl').exists()
    from famjet.memory.associative_hippo import token_table, associative_episodes
    tokens=token_table(a.token_seed)
    ex,ey,eids=associative_episodes(tokens,a.eval_episodes,a.eval_data_seed)
    expected=float(np.mean((ex[:,-3]-ey[:,-1])**2))
    assert report['metrics']['latest_b_final_write_mse']==pytest.approx(expected)
    assert report['metrics']['latest_b_retrieval_accuracy']==pytest.approx(float(np.mean(eids[:,9]==np.argmax(ey[:,-1]@tokens.T,axis=-1))))
    raw=np.load(tmp_path/'associative_original'/'final_predictions.npz')
    np.testing.assert_array_equal(raw['targets'],ey)
    assert raw['predictions'].shape==ey.shape
