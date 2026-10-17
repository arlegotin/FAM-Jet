"""Fixed CPU64 bases: closed permission and exact external feature transport."""
from dataclasses import replace
from pathlib import Path
import json
import math
import pytest
import torch
from tests.test_learned_rate_development import profile_config


def fixed_config(family):
    from famjet.config import load_config
    c=profile_config('bank' if family=='bank' else 'jet')
    m=replace(c.model,precision='float64',rates=replace(c.model.rates,mode='fixed'),
        reader=replace(c.model.reader,width=128))
    if family=='multiscale':
        spec=load_config(Path('configs/multiscale-smoke.yaml')).model.multiscale
        m=replace(m,method='multiscale',J=None,rates=None,
            multiscale=replace(spec,order=4,scale_order=2,epsilon=1e-4,tau0=16.,declared_gaps=()))
    return replace(c,model=m,resources=replace(c.resources,cache_limit_bytes=0),development=replace(c.development,
        feature_cache_manifest_path='fixed-features.json',feature_cache_manifest_hash='b'*64))


@pytest.mark.parametrize('family',['jet','bank','multiscale'])
def test_fixed_basis_calibration_is_closed_before_allocation(family,tmp_path,monkeypatch):
    from famjet.analysis.development import resolve_policy,run_development
    c=fixed_config(family)
    assert resolve_policy(c)['fit_histories']==768
    bad=[replace(c,resources=replace(c.resources,device='mps')),
         replace(c,model=replace(c.model,precision='float32')),
         replace(c,data=replace(c.data,key_features='dense')),
         replace(c,model=replace(c.model,numerical_support_floor=1e-6)),
         replace(c,model=replace(c.model,learned_abstention_threshold=.5)),
         replace(c,model=replace(c.model,writer='learned')),
         replace(c,model=replace(c.model,reader=replace(c.model.reader,width=256))),
         replace(c,model=replace(c.model,reader=replace(c.model.reader,rank=5))),
         replace(c,model=replace(c.model,reader=replace(c.model.reader,kind='generic_full'))),
         replace(c,development=replace(c.development,fit_histories_per_cell=32)),
         replace(c,development=replace(c.development,feature_cache_manifest_path=None,feature_cache_manifest_hash=None)),
         replace(c,training=replace(c.training,learning_rate=.003))]
    if family=='multiscale':
        bad += [replace(c,model=replace(c.model,multiscale=replace(c.model.multiscale,epsilon=.01))),
                replace(c,resources=replace(c.resources,cache_limit_bytes=1280))]
    else:
        bad += [replace(c,model=replace(c.model,J=2)),
                replace(c,model=replace(c.model,rates=replace(c.model.rates,mode='learned')))]
    def forbidden(*a,**k):raise AssertionError('model allocated before closed policy rejection')
    monkeypatch.setattr('famjet.train.make_model',forbidden)
    for i,changed in enumerate(bad):
        with pytest.raises(ValueError):resolve_policy(changed)
        with pytest.raises(ValueError):run_development(changed,tmp_path/str(i))


@pytest.mark.parametrize('family,kernel_bytes',[('jet',32),('bank',64),('multiscale',96)])
def test_fixed_basis_true_fp64_fit_export_and_budget(family,kernel_bytes):
    from famjet.train import make_model,move_episode,history_loss
    from famjet.eval.isolation import export_method,_reconstruct
    from famjet.eval.budgets import model_ledger
    from famjet.analysis.development import draw_config,parameter_accounting
    from famjet.data.synthetic import generate_episode
    from test_resume import equal_tree
    c=fixed_config(family);model=make_model(c)
    assert not list(model.kernel.parameters())
    assert all(t.dtype==torch.float64 for t in model.state_dict().values() if t.is_floating_point())
    if family=='multiscale':
        from famjet.memory.multiscale import MultiscaleMemory
        reference=MultiscaleMemory(4,2,1e-4,16.,16,8,declared_gaps=(),cache_limit_bytes=0,dtype=torch.float64,chunk_size=32)
        equal_tree(model.kernel.state_dict(),reference.state_dict())
        assert model.kernel.preparation_cost([1.,2.])['cache_bytes']==0
    else:
        assert torch.equal(model.kernel.rates.flatten(),torch.logspace(math.log10(1/5224),0,c.model.J,dtype=torch.float64))
    dc,hid=draw_config(c,0);raw=generate_episode(dc,c.development.data_seed,hid)
    ep=move_episode(raw,'cpu',dtype=torch.float64);model.fit_statistics([ep])
    restored=_reconstruct(export_method(model));equal_tree(model.state_dict(),restored.state_dict())
    result=model(ep.events,ep.queries,encode_mode='terminal')
    assert torch.equal(result.prediction,restored(ep.events,ep.queries,encode_mode='terminal').prediction)
    loss=history_loss(model,result,ep);assert loss.dtype==torch.float64;loss.backward()
    assert all(p.grad.dtype==torch.float64 for p in model.parameters() if p.grad is not None)
    snapshot=model.encode(ep.events,mode='terminal');assert model.persistent_nbytes(snapshot)==9345
    ledger=model_ledger(model);assert ledger['parameter_bytes']==241736
    assert ledger['buffer_bytes']==2128+kernel_bytes
    account=parameter_accounting(model);assert account['allocated_parameters']==30217
    assert account['objective_active_parameters']==29448 and account['objective_activity_status']=='upper_bound'
    assert account['reader_input_width']==97 and account['macs_per_query']==29952


@pytest.mark.parametrize('family',['jet','bank','multiscale'])
def test_fp64_fixed_feature_multpass_optimizer_resume_and_identity(tmp_path,family):
    from famjet.train import make_model,move_episode,train_model
    from famjet.analysis.development import iter_fit_panel
    from famjet.data.development_cache import prepare_cache
    from famjet.data.feature_cache import prepare_feature_cache,TrainingFeatureCache,feature_record
    from famjet.checkpoint import load_checkpoint
    from tests.test_development_cache import cached_config
    from tests.test_finite_feature_cache import attach_features
    from test_resume import equal_tree
    c=fixed_config(family)
    c=replace(c,training=replace(c.training,optimizer_steps=8,effective_batch=1),development=replace(c.development,
        lengths=(128,),fit_histories_per_cell=1,eval_histories_per_cell=1,corpus_histories=4,milestones=(0,4,8),
        cache_manifest_path=None,cache_manifest_hash=None,feature_cache_manifest_path=None,feature_cache_manifest_hash=None))
    p=prepare_cache(c,tmp_path/'raw',projected_data_bytes=2000000,output_reserve_bytes=100000)
    c=cached_config(c,p);torch.manual_seed(c.seed);model=make_model(c)
    model.fit_statistics(lambda:(move_episode(ep,'cpu',dtype=torch.float64) for ep in iter_fit_panel(c)))
    f=prepare_feature_cache(c,model,tmp_path/'features',projected_data_bytes=1000000,output_reserve_bytes=100000)
    fc=attach_features(c,f);cache=TrainingFeatureCache(fc,model);example=cache.read(0)
    if family=='multiscale':
        manifest=json.loads(f.read_text())
        costs=manifest['upstream_preparation_totals']
        assert costs['cpu_fp64_exponentials']==4*127*2
        assert costs['matrix_cubic_work']==4*127*128
        assert costs['scope']=='unique_corpus_encode_and_feature_reads_forward_only'
    from famjet.data.feature_cache import feature_identity
    with pytest.raises(ValueError,match='precision|identity'):
        feature_identity(replace(c,model=replace(c.model,precision='float32')),model)
    assert example.features.values.dtype==torch.float64
    with pytest.raises(ValueError,match='order|replay'):cache.read(0)
    probe=next(iter(iter_fit_panel(c)));wire=feature_record(model,probe,'terminal')
    assert torch.equal(wire['labels'],probe.labels) and torch.equal(wire['queries']['query_ids'],probe.queries.query_ids)
    observed={k:[] for k in ('raw','features','resumed')};ep=move_episode(probe,'cpu',dtype=torch.float64)
    def observer(name):
        def observe(m,step,directory):
            with torch.no_grad():observed[name].append(m(ep.events,ep.queries,encode_mode='terminal').prediction.clone())
        return observe
    a=load_checkpoint(train_model(c,tmp_path/'raw-run',observer=observer('raw')),{})
    b=load_checkpoint(train_model(fc,tmp_path/'feature-run',observer=observer('features')),{})
    first=train_model(fc,tmp_path/'first',stop_at=3)
    resumed=load_checkpoint(train_model(fc,tmp_path/'resumed',resume=first,observer=observer('resumed')),{})
    for other in (b,resumed):
        equal_tree(a['model_state'],other['model_state']);equal_tree(a['optimizer'],other['optimizer'])
        assert a['sampler']==other['sampler'] and a['consumed_episode_ids']==other['consumed_episode_ids']
    for x,y in zip(observed['raw'],observed['features']):assert torch.equal(x,y)
    assert torch.equal(observed['raw'][-1],observed['resumed'][-1])
    assert b['sampler']['completed_passes']==2 and b['sampler']['pass_offset']==0
    timing=[json.loads(row) for row in (tmp_path/'feature-run/timing.jsonl').read_text().splitlines()]
    assert all(row['events']==0 and row['source_events']==128 for row in timing)
    if family=='multiscale':assert all(row['multiscale_preparation']==[] for row in timing)
    for state in a['optimizer']['state'].values():
        assert state['exp_avg'].dtype==state['exp_avg_sq'].dtype==torch.float64
        assert state['step'].dtype==torch.float32
    # Re-sealing changed bytes is not permission to change their FP64 layout.
    import io,hashlib,copy
    from famjet.provenance import canonical_hash
    manifest=json.loads(f.read_text());entry=manifest['entries'][0];file=f.parent/entry['file']
    original=file.read_bytes();document=f.read_bytes()
    wire=torch.load(io.BytesIO(original),weights_only=True);wire['values']=wire['values'].float()
    buffer=io.BytesIO();torch.save(wire,buffer);payload=buffer.getvalue();file.write_bytes(payload)
    entry['bytes']=len(payload);entry['sha256']=hashlib.sha256(payload).hexdigest()
    manifest['total_bytes']+=len(payload)-len(original);f.write_text(json.dumps(manifest))
    changed=attach_features(c,f)
    with pytest.raises(ValueError,match='identity/shape'):TrainingFeatureCache(changed,model).read(0)
    file.write_bytes(original);f.write_bytes(document)
    # Closed checkpoint preallocation still validates actual FP64 reader wires.
    from famjet.checkpoint import _MAGIC
    bad=copy.deepcopy(a);weights=bad['model']['weights'];weights[next(iter(weights))]['dtype']='float32'
    bad['model_hash']=canonical_hash(bad['model']);buffer=io.BytesIO();torch.save(bad,buffer);payload=buffer.getvalue()
    path=tmp_path/'wrong-dtype.pt';path.write_bytes(_MAGIC+hashlib.sha256(payload).hexdigest().encode()+b'\n'+payload)
    with pytest.raises(ValueError,match='layout|precision'):load_checkpoint(path,{})
    with torch.no_grad():model.reader.feature_mean[0]+=1
    with pytest.raises(ValueError,match='identity'):TrainingFeatureCache(fc,model)
    with torch.no_grad():model.reader.feature_mean[0]-=1
    if family=='multiscale':model.kernel.injection[0]+=1
    else:model.kernel.rates[0,0]+=1
    with pytest.raises(ValueError,match='identity'):TrainingFeatureCache(fc,model)
    # A nominally fixed kernel with an upstream learned tensor cannot be detached.
    model.kernel.register_parameter('forbidden_upstream',torch.nn.Parameter(torch.tensor(1.,dtype=torch.float64)))
    with pytest.raises(ValueError,match='upstream'):feature_record(model,probe,'terminal')
