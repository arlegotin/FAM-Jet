"""Exact fresh-draw transport, integrity and full optimization equivalence."""
from dataclasses import replace
import json
import pytest
import torch
from tests.test_selection import dev_config


def cached_config(c,path):
    from famjet.provenance import canonical_hash
    manifest=json.loads(path.read_text())
    from famjet.analysis.development import execution_shape
    from famjet.eval.isolation import source_identity
    cc=replace(c,development=replace(c.development,cache_manifest_path=str(path),cache_manifest_hash=canonical_hash(manifest)))
    evidence={'status':'passed','source_hash':source_identity(),'shapes':[execution_shape(cc)],'net_allocation_limit_bytes':201326592}
    calibration=path.parent/'test-calibration.json';calibration.write_text(json.dumps(evidence))
    return replace(cc,development=replace(cc.development,mode='learning',calibration_path=str(calibration),calibration_hash=canonical_hash(evidence)))


def test_cache_trajectory_and_transport_cost(tmp_path):
    from famjet.data.development_cache import prepare_cache,TrainingDrawCache
    from famjet.train import train_model
    from famjet.checkpoint import load_checkpoint
    c=dev_config()
    path=prepare_cache(c,tmp_path/'cache',projected_data_bytes=1000000,output_reserve_bytes=100000)
    cc=cached_config(c,path);cache=TrainingDrawCache(cc)
    assert cache.verification['bytes_read']>0
    assert cache.read(0).events.history_ids[0].startswith('task18-train-')
    fresh=load_checkpoint(train_model(c,tmp_path/'fresh'),{})
    cached=load_checkpoint(train_model(cc,tmp_path/'cached'),{})
    first=train_model(cc,tmp_path/'first',stop_at=1)
    resumed=load_checkpoint(train_model(cc,tmp_path/'resumed',resume=first),{})
    assert fresh['consumed_episode_ids']==cached['consumed_episode_ids']==resumed['consumed_episode_ids']
    assert fresh['model']['schema']['target_statistics']==cached['model']['schema']['target_statistics']
    for k in fresh['model_state']:
        assert torch.equal(fresh['model_state'][k],cached['model_state'][k])
        assert torch.equal(fresh['model_state'][k],resumed['model_state'][k])
    assert fresh['optimizer']['param_groups']==cached['optimizer']['param_groups']
    for key,state in fresh['optimizer']['state'].items():
        for name,value in state.items(): assert torch.equal(value,cached['optimizer']['state'][key][name])
    with pytest.raises(ValueError,match='order|replay'): cache.read(0)


def test_cache_rejects_tamper_reorder_and_identity_mismatch(tmp_path):
    from famjet.data.development_cache import prepare_cache,TrainingDrawCache
    c=dev_config();path=prepare_cache(c,tmp_path/'cache',projected_data_bytes=1000000,output_reserve_bytes=100000)
    cc=cached_config(c,path)
    wrong=replace(cc,development=replace(cc.development,data_seed=12346))
    with pytest.raises(ValueError,match='identity'): TrainingDrawCache(wrong)
    manifest=json.loads(path.read_text()); first=path.parent/manifest['entries'][0]['file']
    first.write_bytes(first.read_bytes()+b'bad')
    with pytest.raises(ValueError,match='bytes|hash'): TrainingDrawCache(cc)
    manifest['entries'].reverse();path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError,match='order|identity'): TrainingDrawCache(cached_config(c,path))


def test_cached_calibration_preserves_2048_horizon_and_requires_matching_transport(tmp_path,monkeypatch):
    from famjet.analysis import development as d
    from famjet.train import train_model
    from famjet.checkpoint import load_checkpoint
    from famjet.provenance import canonical_hash
    from famjet.eval.isolation import source_identity
    c=dev_config()
    c=replace(c,training=replace(c.training,optimizer_steps=2048,effective_batch=3),development=replace(c.development,lengths=(128,512,2048),milestones=(0,128,512,1024,2048),cache_manifest_path='approved.json',cache_manifest_hash='a'*64))
    assert d.resolve_policy(c)['development']['cache_manifest_hash']=='a'*64
    for change in ({'lengths':(128,)},{'cache_manifest_hash':None}):
        with pytest.raises(ValueError):d.resolve_policy(replace(c,development=replace(c.development,**change)))
    with pytest.raises(ValueError):d.resolve_policy(replace(c,training=replace(c.training,optimizer_steps=2049)))
    no_cache=replace(c,development=replace(c.development,cache_manifest_path=None,cache_manifest_hash=None))
    evidence={'status':'passed','source_hash':source_identity(),'shapes':[d.execution_shape(no_cache)],'net_allocation_limit_bytes':201326592}
    path=tmp_path/'cal.json';path.write_text(json.dumps(evidence))
    learning=replace(c,development=replace(c.development,mode='learning',calibration_path=str(path),calibration_hash=canonical_hash(evidence)))
    with pytest.raises(ValueError,match='applicable'): d.resolve_policy(learning)
    # Exercise real optimizer/checkpoint at the same immutable horizon; fake only
    # cache transport here (actual transport+resume is covered above).
    class Transport:
        def __init__(self,config,*,start_ordinal=0): self.config=config;self.next=start_ordinal;self.verification={}
        def read(self,ordinal):
            from famjet.data.synthetic import generate_episode
            assert ordinal==self.next;self.next+=1
            cc,identity=d.draw_config(self.config,ordinal)
            return generate_episode(cc,self.config.development.data_seed,identity)
    monkeypatch.setattr('famjet.data.development_cache.TrainingDrawCache',Transport)
    p=train_model(c,tmp_path/'calibrated',stop_at=2)
    ck=load_checkpoint(p,{})
    assert ck['completed_step']==2 and ck['config']['training']['optimizer_steps']==2048
    assert len(ck['consumed_episode_ids'])==6
    with pytest.raises(ValueError,match='calibration'):train_model(c,tmp_path/'unbounded')
