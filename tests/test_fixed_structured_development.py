"""Full structured fixed-rate CPU64 arms retain closed budgets and lifecycle."""
from dataclasses import replace
import json
import pytest
import torch
from tests.test_fixed_basis_development import fixed_config


def structured_config(family,epsilon=1e-8):
    c=fixed_config(family)
    return replace(c,model=replace(c.model,epsilon=epsilon,reader=replace(c.model.reader,
        kind='structured',width=125 if family=='jet' else 122)))


@pytest.mark.parametrize('family',['jet','bank'])
@pytest.mark.parametrize('epsilon',[1e-8,1e-6])
def test_only_declared_full_structured_shape_enters_before_allocation(family,epsilon,tmp_path,monkeypatch):
    from famjet.analysis.development import resolve_policy,run_development
    c=structured_config(family,epsilon)
    assert resolve_policy(c)['fit_histories']==768
    bad=[replace(c,model=replace(c.model,epsilon=1e-10)),
         replace(c,resources=replace(c.resources,device='mps')),
         replace(c,model=replace(c.model,precision='float32')),
         replace(c,model=replace(c.model,writer='learned')),
         replace(c,model=replace(c.model,rates=replace(c.model.rates,mode='learned'))),
         replace(c,model=replace(c.model,rates=replace(c.model.rates,bounds=(.001,1.)))),
         replace(c,data=replace(c.data,key_features='dense')),
         replace(c,model=replace(c.model,learned_abstention_threshold=.5)),
         replace(c,model=replace(c.model,numerical_support_floor=1e-6)),
         replace(c,model=replace(c.model,J=2)),
         replace(c,training=replace(c.training,learning_rate=.003))]
    for kind in ('generic_contracted','generic_full','bank_normalized','fixed_scale'):
        bad.append(replace(c,model=replace(c.model,reader=replace(c.model.reader,kind=kind))))
    if epsilon==1e-6:
        for method in ('jet','bank','multiscale'):
            raw=fixed_config(method)
            bad.append(replace(raw,model=replace(raw.model,epsilon=epsilon)))
    for width in (64,121,123,124,126,128,256):
        bad.append(replace(c,model=replace(c.model,reader=replace(c.model.reader,width=width))))
    bad += [replace(c,model=replace(c.model,reader=replace(c.model.reader,rank=9))),
            replace(c,model=replace(c.model,reader=replace(c.model.reader,max_parameters=30217))),
            replace(c,development=replace(c.development,feature_cache_manifest_path=None,feature_cache_manifest_hash=None))]
    m=fixed_config('multiscale')
    # This family rejects structured readers at typed construction, even earlier.
    with pytest.raises(ValueError,match='full coefficient generic reader'):
        replace(m,model=replace(m.model,reader=replace(m.model.reader,kind='structured',width=c.model.reader.width)))
    def forbidden(*a,**k):raise AssertionError('allocation preceded closed structured rejection')
    monkeypatch.setattr('famjet.train.make_model',forbidden)
    for i,changed in enumerate(bad):
        with pytest.raises(ValueError):resolve_policy(changed)
        with pytest.raises(ValueError):run_development(changed,tmp_path/str(i))


@pytest.mark.parametrize('family,width,dim,params,macs,buffers,zero_log,active_bound',[
    ('jet',125,105,30134,29875,2288,78,29258),
    ('bank',122,113,30021,29768,2448,86,29166)])
@pytest.mark.parametrize('epsilon',[1e-8,1e-6])
def test_structured_fp64_real_export_budget_and_constant_input_accounting(
        family,width,dim,params,macs,buffers,zero_log,active_bound,epsilon):
    from famjet.train import make_model,move_episode,history_loss
    from famjet.analysis.development import draw_config,parameter_accounting
    from famjet.data.synthetic import generate_episode
    from famjet.eval.isolation import export_method,_reconstruct
    from famjet.eval.budgets import model_ledger
    from test_resume import equal_tree
    c=structured_config(family,epsilon);m=make_model(c)
    dc,hid=draw_config(c,0);ep=move_episode(generate_episode(dc,c.development.data_seed,hid),'cpu',dtype=torch.float64)
    m.fit_statistics([ep]);assert m.kernel.t_ref==1.
    state=m.encode(ep.events,mode='terminal');features=m.features(state,ep.queries)
    assert features.values.shape[-1]==dim and features.values.dtype==torch.float64
    assert m.reader.schema['kind']=='structured' and m.reader.schema['budget']=={'width':width,'hidden_layers':2}
    assert m.persistent_nbytes(state)==9345 and not list(m.kernel.parameters())
    ledger=model_ledger(m);assert ledger['parameter_bytes']==params*8 and ledger['buffer_bytes']==buffers
    account=parameter_accounting(m)
    assert account['allocated_parameters']==params and account['macs_per_query']==macs
    assert params<=30217 and macs<=29952 and account['padding_parameters']==0
    assert account['objective_activity_status']=='upper_bound' and account['objective_active_parameters']<=active_bound
    assert zero_log in account['structural_zero_input_columns'] and m.reader.feature_mean[zero_log]==0
    assert account['guaranteed_inactive_support_parameters']==width+1
    restored=_reconstruct(export_method(m));equal_tree(m.state_dict(),restored.state_dict())
    assert m.kernel.eps==restored.kernel.eps==epsilon
    pred=m.read_features(features,ep.queries);other=restored(ep.events,ep.queries,encode_mode='terminal')
    assert torch.equal(pred.prediction,other.prediction)
    loss=history_loss(m,pred,ep);loss.backward();assert loss.dtype==torch.float64
    assert all(x.dtype==torch.float64 for x in m.state_dict().values() if x.is_floating_point())
    assert all(x.grad.dtype==torch.float64 for x in m.parameters() if x.grad is not None)


@pytest.mark.parametrize('family',['jet','bank'])
def test_feature_identity_rejects_read_epsilon_not_matching_config(family,tmp_path,monkeypatch):
    from famjet.train import make_model,move_episode
    from famjet.analysis.development import draw_config
    from famjet.data.synthetic import generate_episode
    from famjet.data.feature_cache import feature_identity,TrainingFeatureCache
    from famjet.provenance import canonical_hash
    c=structured_config(family);m=make_model(c)
    dc,hid=draw_config(c,0)
    ep=move_episode(generate_episode(dc,c.development.data_seed,hid),'cpu',dtype=torch.float64)
    m.fit_statistics([ep]);before=feature_identity(c,m)
    # Epsilon is a read policy, not a writer/state parameter. A stale fitted
    # buffer or an accidentally mutated read policy must not identify old data.
    writer_hash=m._parameter_hash();m.kernel.eps=1e-6
    assert m._parameter_hash()==writer_hash
    with pytest.raises(ValueError,match='identity|epsilon|read policy'):
        feature_identity(c,m)
    changed=structured_config(family,1e-6)
    after=feature_identity(changed,m)
    assert after['version']==2 and after['read_policy']=={'epsilon':1e-6,'numerical_support_floor':1e-8}
    assert before['read_policy']=={'epsilon':1e-8,'numerical_support_floor':1e-8}
    # Same exact fitted arrays and writer/state hash cannot hide a new read map.
    assert after['feature_mean']==before['feature_mean'] and after['feature_scale']==before['feature_scale']
    assert after['writer_rates_hash']==before['writer_rates_hash']
    assert canonical_hash(after)!=canonical_hash(before)
    stale={'status':'complete','identity':before,'entries':[],'total_bytes':0}
    path=tmp_path/'old-epsilon-manifest.json';path.write_text(json.dumps(stale))
    changed=replace(changed,development=replace(changed.development,
        feature_cache_manifest_path=str(path),feature_cache_manifest_hash=canonical_hash(stale)))
    def forbidden(*a,**k):raise AssertionError('raw/tensor allocation before stale read identity rejection')
    monkeypatch.setattr('famjet.data.feature_cache.TrainingDrawCache',forbidden)
    monkeypatch.setattr(torch,'load',forbidden)
    with pytest.raises(ValueError,match='feature cache identity mismatch'):
        TrainingFeatureCache(changed,m)
    m.kernel.support_floor=1e-6
    with pytest.raises(ValueError,match='read policy identity'):
        feature_identity(changed,m)


@pytest.mark.parametrize('family',['jet','bank'])
def test_epsilon_calibration_rejects_other_read_policy_before_allocation(family,tmp_path,monkeypatch):
    from famjet.analysis.development import execution_shape,resolve_policy,run_development
    from famjet.eval.isolation import source_identity
    from famjet.provenance import canonical_hash
    old=structured_config(family);new=structured_config(family,1e-6)
    evidence={'status':'passed','source_hash':source_identity(),'shapes':[execution_shape(old)],'net_allocation_limit_bytes':201326592}
    path=tmp_path/'epsilon1e-8.json';path.write_text(json.dumps(evidence))
    changed=replace(new,development=replace(new.development,mode='learning',calibration_path=str(path),calibration_hash=canonical_hash(evidence)))
    assert execution_shape(old)!=execution_shape(new)
    def forbidden(*a,**k):raise AssertionError('allocation preceded epsilon applicability rejection')
    monkeypatch.setattr('famjet.train.make_model',forbidden)
    with pytest.raises(ValueError):resolve_policy(changed)
    with pytest.raises(ValueError):run_development(changed,tmp_path/'rejected')


@pytest.mark.parametrize('family',['jet','bank'])
def test_raw_calibration_cannot_authorize_structured_reader_before_allocation(family,tmp_path,monkeypatch):
    from famjet.analysis.development import execution_shape,resolve_policy,run_development
    from famjet.eval.isolation import source_identity
    from famjet.provenance import canonical_hash
    raw=fixed_config(family);c=structured_config(family)
    evidence={'status':'passed','source_hash':source_identity(),'shapes':[execution_shape(raw)],'net_allocation_limit_bytes':201326592}
    path=tmp_path/'raw.json';path.write_text(json.dumps(evidence))
    c=replace(c,development=replace(c.development,mode='learning',calibration_path=str(path),calibration_hash=canonical_hash(evidence)))
    def forbidden(*a,**k):raise AssertionError('allocation preceded structured applicability rejection')
    monkeypatch.setattr('famjet.train.make_model',forbidden)
    with pytest.raises(ValueError,match='applicable'):resolve_policy(c)
    with pytest.raises(ValueError,match='applicable'):run_development(c,tmp_path/'rejected')
