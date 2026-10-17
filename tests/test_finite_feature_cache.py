"""Repeated empirical-corpus transport must preserve real optimizer trajectories."""
from dataclasses import replace
from pathlib import Path
import importlib.util
import json
import pytest
import torch
from tests.test_selection import dev_config
from tests.test_development_cache import cached_config


def finite_config():
    c=dev_config()
    return replace(c,training=replace(c.training,optimizer_steps=8),development=replace(c.development,
        corpus_histories=4,milestones=(0,4,8)))


def attach_features(c,path):
    from famjet.provenance import canonical_hash
    from famjet.analysis.development import execution_shape
    from famjet.eval.isolation import source_identity
    c=replace(c,development=replace(c.development,feature_cache_manifest_path=str(path),
        feature_cache_manifest_hash=canonical_hash(json.loads(path.read_text()))))
    e={'status':'passed','source_hash':source_identity(),'shapes':[execution_shape(c)],'net_allocation_limit_bytes':201326592}
    p=path.parent/'calibration.json';p.write_text(json.dumps(e))
    return replace(c,development=replace(c.development,calibration_path=str(p),calibration_hash=canonical_hash(e)))


def fitted(c):
    from famjet.train import make_model,move_episode
    from famjet.analysis.development import iter_fit_panel
    torch.manual_seed(c.seed);m=make_model(c);m.fit_statistics(lambda:(move_episode(ep,'cpu') for ep in iter_fit_panel(c)));return m


def fixtures(tmp_path):
    assert importlib.util.find_spec('famjet.data.feature_cache') is not None, 'fixed-feature transport absent'
    from famjet.data.development_cache import prepare_cache
    from famjet.data.feature_cache import prepare_feature_cache
    c=finite_config();p=prepare_cache(c,tmp_path/'raw',projected_data_bytes=2000000,output_reserve_bytes=100000)
    c=cached_config(c,p);m=fitted(c)
    f=prepare_feature_cache(c,m,tmp_path/'features',projected_data_bytes=1000000,output_reserve_bytes=100000)
    return c,attach_features(c,f),m,f


def test_repeated_features_equal_recomputed_parameters_optimizer_predictions_and_resume(tmp_path):
    # Removing repeated corpus addressing, detaching a learned writer, or changing
    # shared decoder/loss semantics must break this real two-pass comparison.
    from famjet.train import train_model
    from famjet.checkpoint import load_checkpoint
    from famjet.data.synthetic import generate_episode
    c,fc,m,path=fixtures(tmp_path)
    from famjet.train import move_episode
    probe=move_episode(generate_episode(c,c.development.data_seed,'independent-training-probe'),'cpu')
    observed={name:[] for name in ('raw','features','resumed')}
    def observer(name):
        def observe(model,step,directory):
            with torch.no_grad(): observed[name].append((step,model(probe.events,probe.queries,encode_mode='terminal').prediction.clone()))
        return observe
    raw=load_checkpoint(train_model(c,tmp_path/'raw-run',observer=observer('raw')),{})
    feature=load_checkpoint(train_model(fc,tmp_path/'feature-run',observer=observer('features')),{})
    first=train_model(fc,tmp_path/'first',stop_at=3)
    resumed=load_checkpoint(train_model(fc,tmp_path/'resume',resume=first,observer=observer('resumed')),{})
    for other in (feature,resumed):
        for k,v in raw['model_state'].items(): assert torch.equal(v,other['model_state'][k]),k
        assert raw['optimizer']['param_groups']==other['optimizer']['param_groups']
        for k,state in raw['optimizer']['state'].items():
            for n,v in state.items():assert torch.equal(v,other['optimizer']['state'][k][n]),(k,n)
    for (step,a),(other_step,b) in zip(observed['raw'],observed['features']):
        assert step==other_step and torch.equal(a,b)
    assert torch.equal(observed['raw'][-1][1],observed['resumed'][-1][1])
    draws=list(map(json.loads,(tmp_path/'feature-run/draws.jsonl').read_text().splitlines()))
    assert [d['episode_id'] for d in draws[:4]]==[d['episode_id'] for d in draws[4:]]
    assert [d['corpus_pass'] for d in draws]==[0]*4+[1]*4
    assert [d['corpus_offset'] for d in draws]==[0,1,2,3]*2
    assert feature['sampler']['corpus_histories']==4 and feature['sampler']['completed_passes']==2
    assert feature['sampler']['pass_offset']==0
    timing=list(map(json.loads,(tmp_path/'feature-run/timing.jsonl').read_text().splitlines()))
    assert all(t['generation_seconds']==0 and t['events']==0 and t['source_events']==128 for t in timing)
    assert all(t['delivery_boundary']=='fixed_feature_read_sha_decode' for t in timing)


def test_feature_identity_tamper_and_learned_upstream_rejected(tmp_path):
    c,fc,m,path=fixtures(tmp_path)
    from famjet.data.feature_cache import TrainingFeatureCache,prepare_feature_cache
    from famjet.train import make_model
    cache=TrainingFeatureCache(fc,m);cache.read(0)
    with pytest.raises(ValueError,match='order|replay'):cache.read(0)
    with torch.no_grad():m.reader.feature_mean[0]+=1
    with pytest.raises(ValueError,match='identity'):TrainingFeatureCache(fc,m)
    for model in (replace(c.model,writer='learned'),replace(c.model,rates=replace(c.model.rates,mode='learned'))):
        learned=replace(c,model=model)
        with pytest.raises(ValueError,match='fixed|learned|upstream'):
            prepare_feature_cache(learned,make_model(learned),tmp_path/'forbidden',projected_data_bytes=1000000,output_reserve_bytes=1)
    manifest=json.loads(path.read_text());entry=path.parent/manifest['entries'][0]['file'];entry.write_bytes(entry.read_bytes()+b'bad')
    with pytest.raises(ValueError,match='bytes|hash'):TrainingFeatureCache(fc,fitted(fc))


def test_finite_sampling_is_explicit_and_default_null_only_compatibility():
    from dataclasses import asdict
    from famjet.config import config_documents_equal
    c=dev_config();old=asdict(c)
    for k in ('corpus_histories','feature_cache_manifest_path','feature_cache_manifest_hash'):old['development'].pop(k,None)
    assert config_documents_equal(old,asdict(c))
    assert not config_documents_equal(old,asdict(replace(c,development=replace(c.development,corpus_histories=4))))
    with pytest.raises(ValueError):replace(c,development=replace(c.development,corpus_histories=0))


def test_feature_record_never_detaches_learned_upstream():
    from famjet.data.feature_cache import feature_record
    from famjet.data.synthetic import generate_episode
    from famjet.train import make_model
    c=finite_config();ep=generate_episode(c,c.development.data_seed,'guard-probe')
    for spec in (replace(c.model,writer='learned'),replace(c.model,rates=replace(c.model.rates,mode='learned'))):
        with pytest.raises(ValueError,match='fixed|learned|upstream'):
            feature_record(make_model(replace(c,model=spec)),ep,'terminal')


def test_runner_stop_is_execution_boundary_not_changed_policy(tmp_path):
    from famjet.analysis.development import run_development
    from famjet.checkpoint import load_checkpoint
    c,fc,m,path=fixtures(tmp_path)
    first=run_development(fc,tmp_path/'stage1',stop_at=3)
    final=run_development(fc,tmp_path/'stage2',resume=Path(first['checkpoint']),stop_at=5)
    ck=load_checkpoint(Path(final['checkpoint']),{})
    assert first['configured_training_horizon']==final['configured_training_horizon']==8
    assert first['last_evaluation']['step']==3 and final['last_evaluation']['step']==5
    assert ck['completed_step']==5 and ck['sampler']['completed_passes']==1 and ck['sampler']['pass_offset']==1
    assert first['execution_policy']==final['execution_policy']


@pytest.mark.parametrize('completed_step',[1,2])
def test_partial_accumulation_loader_normalizes_all_finite_sampler_fields(tmp_path,completed_step):
    # Restart must roll back unique-count and pass offset with consumed position,
    # both before the first corpus boundary and after one complete pass.
    from famjet.train import train_model
    from famjet.checkpoint import load_checkpoint,save_checkpoint,_validate
    c,fc,model,path=fixtures(tmp_path)
    c=replace(c,training=replace(c.training,effective_batch=2))
    context=load_checkpoint(train_model(c,tmp_path/'run',stop_at=completed_step),{})
    context['accumulation_position']=1
    context['sampler'].update(position=2*completed_step+1,
        unique_histories=3 if completed_step==1 else 4,
        completed_passes=0 if completed_step==1 else 1,
        pass_offset=3 if completed_step==1 else 1)
    save_checkpoint(tmp_path/'partial.pt',context)
    result=load_checkpoint(tmp_path/'partial.pt',{})
    assert result['restarted_accumulation'] and result['accumulation_position']==0
    assert result['sampler']['position']==2*completed_step
    assert result['sampler']['unique_histories']==2*completed_step
    assert result['sampler']['completed_passes']==completed_step-1
    assert result['sampler']['pass_offset']==(2 if completed_step==1 else 0)
    _validate(result)
    save_checkpoint(tmp_path/'normalized.pt',result)
    again=load_checkpoint(tmp_path/'normalized.pt',{})
    assert again['sampler']==result['sampler'] and not again['restarted_accumulation']


def test_finite_calibration_is_closed_and_requires_exact_feature_transport(tmp_path):
    from famjet.analysis.development import resolve_policy,execution_shape
    from famjet.provenance import canonical_hash
    from famjet.eval.isolation import source_identity
    c=finite_config()
    c=replace(c,training=replace(c.training,optimizer_steps=32768,effective_batch=3),development=replace(c.development,
        mode='calibration',lengths=(128,512,2048),milestones=(0,8192,32768),corpus_histories=6144,fit_histories_per_cell=32,eval_histories_per_cell=4,
        cache_manifest_path='raw.json',cache_manifest_hash='a'*64,feature_cache_manifest_path='feature.json',feature_cache_manifest_hash='b'*64))
    assert resolve_policy(c)['development']['corpus_histories']==6144
    for change in ({'corpus_histories':12288},{'fit_histories_per_cell':16},{'feature_cache_manifest_path':None,'feature_cache_manifest_hash':None}):
        with pytest.raises(ValueError):resolve_policy(replace(c,development=replace(c.development,**change)))
    with pytest.raises(ValueError):resolve_policy(replace(c,training=replace(c.training,optimizer_steps=32769)))
    evidence={'status':'passed','source_hash':source_identity(),'shapes':[execution_shape(c)],'net_allocation_limit_bytes':201326592}
    path=tmp_path/'cal.json';path.write_text(json.dumps(evidence))
    learning=replace(c,development=replace(c.development,mode='learning',calibration_path=str(path),calibration_hash=canonical_hash(evidence)))
    assert resolve_policy(learning)['development']['feature_cache_manifest_hash']=='b'*64
    with pytest.raises(ValueError,match='applicable'):
        resolve_policy(replace(learning,development=replace(learning.development,feature_cache_manifest_hash='c'*64)))


@pytest.mark.parametrize('effective_batch',[1,2])
def test_finite_failure_keeps_durable_attempts_progress_and_full_final_record(tmp_path,monkeypatch,effective_batch):
    from famjet.train import train_model
    from famjet.data.feature_cache import TrainingFeatureCache
    c,fc,m,path=fixtures(tmp_path)
    fc=replace(fc,training=replace(fc.training,effective_batch=effective_batch))
    read=TrainingFeatureCache.read
    def fail_after_pass_start(self,ordinal):
        if ordinal==3:raise RuntimeError('injected delivery failure')
        return read(self,ordinal)
    monkeypatch.setattr(TrainingFeatureCache,'read',fail_after_pass_start)
    out=tmp_path/'failed'
    with pytest.raises(RuntimeError,match='injected'):train_model(fc,out)
    record=json.loads((out/'run.json').read_text())
    assert record['completed_step']==3//effective_batch and len(record['consumed_episode_ids'])==(3//effective_batch)*effective_batch
    assert len(record['attempted_episode_ids'])==4 and record['status']=='failed'
    attempts=list(map(json.loads,(out/'attempts.jsonl').read_text().splitlines()))
    assert [r['episode_ids'] for r in attempts]==[[f'train-{i:012d}'] for i in range(4)]
    progress=json.loads((out/'progress.json').read_text())
    assert progress['completed_step']==3//effective_batch and progress['consumed_count']==(3//effective_batch)*effective_batch
    assert progress['attempted_count']==4 and progress['status']=='failed'
