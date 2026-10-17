"""Closed learned-rate profile scope and real raw-data optimization lifecycle."""
from dataclasses import replace
from pathlib import Path
import json
import pytest
import torch


def profile_config(family='jet'):
    from famjet.config import load_config
    c=load_config(Path(f'configs/development/{family}_finite_raw_32768.yaml'))
    return replace(c,model=replace(c.model,rates=replace(c.model.rates,mode='learned',bounds=(1/5224,1.))),
        development=replace(c.development,mode='calibration',fit_histories_per_cell=64,eval_histories_per_cell=8,
            milestones=(0,128,512,1024,2048,4096,8192,16384,32768),calibration_path=None,calibration_hash=None,
            feature_cache_manifest_path=None,feature_cache_manifest_hash=None))


@pytest.mark.parametrize('precision',['float32','float64'])
@pytest.mark.parametrize('family',['jet','bank'])
def test_only_approved_learned_rate_raw_profile_shape_enters_calibration(family,precision):
    from famjet.analysis.development import resolve_policy
    c=profile_config(family);c=replace(c,model=replace(c.model,precision=precision));p=resolve_policy(c)
    assert p['fit_histories']==768 and p['development']['eval_histories_per_cell']==8
    forbidden=[replace(c,model=replace(c.model,writer='learned')),
        replace(c,model=replace(c.model,encode='stream')),
        replace(c,model=replace(c.model,J=c.model.J*2)),
        replace(c,model=replace(c.model,reader=replace(c.model.reader,width=256 if precision=='float64' else 128))),
        replace(c,model=replace(c.model,reader=replace(c.model.reader,kind='structured'))),
        replace(c,model=replace(c.model,rates=replace(c.model.rates,bounds=(.001,1.)))),
        replace(c,training=replace(c.training,learning_rate=.003)),
        replace(c,training=replace(c.training,weight_decay=.01)),
        replace(c,training=replace(c.training,optimizer_steps=2048),
            development=replace(c.development,milestones=(0,128,512,1024,2048))),
        replace(c,development=replace(c.development,fit_histories_per_cell=32)),
        replace(c,development=replace(c.development,eval_histories_per_cell=4)),
        replace(c,development=replace(c.development,corpus_histories=12288)),
        replace(c,development=replace(c.development,cache_manifest_path=None,cache_manifest_hash=None)),
        replace(c,development=replace(c.development,feature_cache_manifest_path='forbidden.json',feature_cache_manifest_hash='a'*64))]
    for config in forbidden:
        with pytest.raises(ValueError,match='calibration'):resolve_policy(config)


@pytest.mark.parametrize('family',['jet','bank'])
def test_width128_profile_is_only_exact_cpu64_learned_raw_shape(family):
    from famjet.analysis.development import resolve_policy,parameter_accounting
    from famjet.train import make_model
    from famjet.eval.budgets import model_ledger
    c=profile_config(family)
    c=replace(c,model=replace(c.model,precision='float64',reader=replace(c.model.reader,width=128)))
    resolve_policy(c)
    model=make_model(c);account=parameter_accounting(model)
    assert account['reader_input_width']==97 and account['macs_per_query']==29952
    assert account['allocated_parameters']==(30221 if family=='jet' else 30225)
    assert account['objective_active_parameters']==(29452 if family=='jet' else 29456)
    assert account['objective_activity_status']=='upper_bound' and account['padding_parameters']==0
    assert model_ledger(model)['parameter_bytes']==(241768 if family=='jet' else 241800)
    forbidden=[replace(c,model=replace(c.model,precision='float32')),
        replace(c,resources=replace(c.resources,device='mps')),
        replace(c,model=replace(c.model,rates=replace(c.model.rates,mode='fixed'))),
        replace(c,model=replace(c.model,reader=replace(c.model.reader,kind='structured'))),
        replace(c,model=replace(c.model,reader=replace(c.model.reader,rank=5))),
        replace(c,model=replace(c.model,J=c.model.J*2))]
    forbidden += [replace(c,model=replace(c.model,reader=replace(c.model.reader,width=w)))
                  for w in (32,96,129,256)]
    for changed in forbidden:
        with pytest.raises(ValueError):resolve_policy(changed)


def test_width_calibration_does_not_authorize_other_width_before_allocation(tmp_path,monkeypatch):
    from famjet.analysis.development import execution_shape,run_development
    from famjet.eval.isolation import source_identity
    from famjet.provenance import canonical_hash
    c=profile_config();c=replace(c,model=replace(c.model,precision='float64'))
    evidence={'status':'passed','source_hash':source_identity(),'shapes':[execution_shape(c)],'net_allocation_limit_bytes':201326592}
    p=tmp_path/'width64.json';p.write_text(json.dumps(evidence))
    changed=replace(c,model=replace(c.model,reader=replace(c.model.reader,width=128)),
        development=replace(c.development,mode='learning',calibration_path=str(p),calibration_hash=canonical_hash(evidence)))
    def forbidden(*args,**kwargs):raise AssertionError('allocated before width applicability rejection')
    monkeypatch.setattr('famjet.train.make_model',forbidden)
    with pytest.raises(ValueError,match='applicable'):run_development(changed,tmp_path/'rejected')


@pytest.mark.parametrize('change',['data_seed','query_seed'])
def test_profile_calibration_cannot_authorize_different_training_population(tmp_path,monkeypatch,change):
    from famjet.analysis.development import execution_shape,resolve_policy,run_development
    from famjet.eval.isolation import source_identity
    from famjet.provenance import canonical_hash
    c=profile_config()
    evidence={'status':'passed','source_hash':source_identity(),'shapes':[execution_shape(c)],'net_allocation_limit_bytes':201326592}
    p=tmp_path/'profile.json';p.write_text(json.dumps(evidence))
    c=replace(c,development=replace(c.development,mode='learning',calibration_path=str(p),calibration_hash=canonical_hash(evidence)))
    resolve_policy(c)
    changed=(replace(c,development=replace(c.development,data_seed=c.development.data_seed+1)) if change=='data_seed'
        else replace(c,data=replace(c.data,generator=replace(c.data.generator,query_seed=c.data.generator.query_seed+1))))
    with pytest.raises(ValueError,match='applicable'):resolve_policy(changed)
    def forbidden(*args,**kwargs):raise AssertionError('allocated before calibration data rejection')
    monkeypatch.setattr('famjet.train.make_model',forbidden)
    with pytest.raises(ValueError,match='applicable'):run_development(changed,tmp_path/'rejected')


@pytest.mark.parametrize('precision,width',[('float32',64),('float64',64),('float64',128)])
@pytest.mark.parametrize('family',['jet','bank'])
def test_learned_rates_raw_transport_and_resume_preserve_optimizer_trajectory(tmp_path,monkeypatch,family,precision,width):
    # A raw cache must not detach learned rates or substitute stale fixed states.
    from tests.test_selection import dev_config
    from tests.test_development_cache import cached_config
    from famjet.data.development_cache import prepare_cache
    from famjet.analysis.development import execution_shape
    from famjet.eval.isolation import source_identity
    from famjet.provenance import canonical_hash
    from famjet.train import train_model,make_model
    from famjet.checkpoint import load_checkpoint
    from test_resume import equal_tree
    c=dev_config();c=replace(c,model=replace(c.model,precision=precision,method=family,J=4 if family=='jet' else 8,
        reader=replace(c.model.reader,width=width),
        rates=replace(c.model.rates,mode='learned',bounds=(1/5224,1.))))
    path=prepare_cache(c,tmp_path/'raw',projected_data_bytes=1000000,output_reserve_bytes=100000)
    cached=cached_config(c,path)
    # Explicit bounded test evidence permits the small fixture, not scientific
    # initial calibration. Production permission is tested separately above.
    evidence={'status':'passed','source_hash':source_identity(),'shapes':[execution_shape(c)],'net_allocation_limit_bytes':201326592}
    p=tmp_path/'test-fresh-calibration.json';p.write_text(json.dumps(evidence))
    fresh=replace(c,development=replace(c.development,mode='learning',calibration_path=str(p),calibration_hash=canonical_hash(evidence)))
    initial=make_model(c).kernel.rate_source.logits.detach().clone()
    a=load_checkpoint(train_model(fresh,tmp_path/'fresh'),{})
    b=load_checkpoint(train_model(cached,tmp_path/'cached'),{})
    first=train_model(cached,tmp_path/'first',stop_at=1)
    resumed=load_checkpoint(train_model(cached,tmp_path/'resume',resume=first),{})
    for other in (b,resumed):
        equal_tree(a['model_state'],other['model_state']);equal_tree(a['optimizer'],other['optimizer'])
        assert a['consumed_episode_ids']==other['consumed_episode_ids']
    logits=a['model_state']['kernel.rate_source.logits']
    assert torch.isfinite(logits).all() and bool((logits!=initial).all())
    assert len(a['optimizer_active_parameters'])>0

    dtype=getattr(torch,precision)
    assert all(v.dtype==dtype for v in a['model_state'].values() if v.is_floating_point())
    for state in a['optimizer']['state'].values():
        assert state['exp_avg'].dtype==state['exp_avg_sq'].dtype==dtype
        assert state['step'].dtype==torch.float32
    timing=[json.loads(line) for line in (tmp_path/'fresh'/'timing.jsonl').read_text().splitlines()]
    assert all(row['precision']==precision for row in timing)
    if precision=='float64':
        import copy,io,hashlib
        from famjet.checkpoint import _MAGIC
        def write_unvalidated(path,context):
            buffer=io.BytesIO();torch.save(context,buffer);payload=buffer.getvalue()
            path.write_bytes(_MAGIC+hashlib.sha256(payload).hexdigest().encode()+b'\n'+payload)
        # Wire precision is rejected before model reconstruction/allocation.
        for part in ('rate','reader'):
            bad=copy.deepcopy(a)
            weights=bad['model']['schema']['kernel']['weights'] if part=='rate' else bad['model']['weights']
            weights[next(iter(weights))]['dtype']='float32'
            bad['model_hash']=canonical_hash(bad['model']);path=tmp_path/f'bad-{part}.pt';write_unvalidated(path,bad)
            with monkeypatch.context() as patch:
                def forbidden(*args,**kwargs):raise AssertionError('allocated before dtype rejection')
                patch.setattr('famjet.eval.isolation._reconstruct',forbidden)
                with pytest.raises(ValueError,match='layout|precision'):load_checkpoint(path,{})
        bad=copy.deepcopy(a);state=next(iter(bad['optimizer']['state'].values()));state['exp_avg']=state['exp_avg'].float()
        path=tmp_path/'bad-moment.pt';write_unvalidated(path,bad)
        with pytest.raises(ValueError,match='moment shape/dtype'):load_checkpoint(path,{})


@pytest.mark.parametrize('width',[64,128])
def test_fp64_profile_initialization_presentation_fit_and_inference_roundtrip(width):
    from famjet.train import make_model,move_episode,history_loss
    from famjet.analysis.development import draw_config
    from famjet.data.synthetic import generate_episode
    from famjet.eval.isolation import export_method,_reconstruct
    from test_resume import equal_tree
    c=profile_config();c=replace(c,model=replace(c.model,reader=replace(c.model.reader,width=width)))
    c64=replace(c,model=replace(c.model,precision='float64'))
    torch.manual_seed(c.seed);m32=make_model(c)
    torch.manual_seed(c.seed);m64=make_model(c64)
    for (name,a),(other,b) in zip(m32.named_parameters(),m64.named_parameters()):
        assert name==other and torch.equal(a.double(),b)
    dc,hid=draw_config(c,0);raw=generate_episode(dc,c.development.data_seed,hid)
    ep=move_episode(raw,'cpu',dtype=torch.float64)
    assert torch.equal(ep.events.values,raw.events.values.float().double())
    assert ep.events.timestamps.dtype==raw.events.timestamps.dtype
    assert ep.labels.dtype==raw.labels.dtype and torch.equal(ep.labels,raw.labels)
    model2=_reconstruct(export_method(m64));m64.fit_statistics([ep]);model2.fit_statistics(lambda:iter([ep]))
    equal_tree(m64.state_dict(),model2.state_dict());assert m64.target_statistics==model2.target_statistics
    restored=_reconstruct(export_method(m64));result=m64(ep.events,ep.queries,encode_mode='terminal')
    equal_tree(result.prediction,restored(ep.events,ep.queries,encode_mode='terminal').prediction)
    loss=history_loss(m64,result,ep);assert loss.dtype==torch.float64
    loss.backward();assert all(p.grad.dtype==torch.float64 for p in m64.parameters() if p.grad is not None)
    snapshot=m64.encode(ep.events,mode='terminal');assert m64.persistent_nbytes(snapshot)==9345
    from famjet.eval.budgets import model_ledger
    ledger=model_ledger(m64)
    assert ledger['parameter_bytes']==sum(p.numel()*8 for p in m64.parameters())==(88168 if width==64 else 241768)
    assert ledger['buffer_bytes']==sum(p.numel()*8 for p in m64.buffers())
    assert ledger['logical_bytes']==ledger['parameter_bytes']+ledger['buffer_bytes']


@pytest.mark.parametrize('change',['precision','device'])
def test_precision_calibration_rejects_before_allocation(tmp_path,monkeypatch,change):
    from famjet.analysis.development import execution_shape,run_development
    from famjet.eval.isolation import source_identity
    from famjet.provenance import canonical_hash
    c=profile_config();evidence={'status':'passed','source_hash':source_identity(),'shapes':[execution_shape(c)],'net_allocation_limit_bytes':201326592}
    p=tmp_path/'cal.json';p.write_text(json.dumps(evidence))
    c=replace(c,development=replace(c.development,mode='learning',calibration_path=str(p),calibration_hash=canonical_hash(evidence)))
    changed=replace(c,model=replace(c.model,precision='float64'))
    if change=='device':changed=replace(changed,resources=replace(c.resources,device='mps'))
    def forbidden(*args,**kwargs):raise AssertionError('allocated before precision rejection')
    monkeypatch.setattr('famjet.train.make_model',forbidden)
    with pytest.raises(ValueError):run_development(changed,tmp_path/'rejected')
