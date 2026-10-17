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


@pytest.mark.parametrize('family',['jet','bank'])
def test_only_approved_learned_rate_raw_profile_shape_enters_calibration(family):
    from famjet.analysis.development import resolve_policy
    c=profile_config(family);p=resolve_policy(c)
    assert p['fit_histories']==768 and p['development']['eval_histories_per_cell']==8
    forbidden=[replace(c,model=replace(c.model,writer='learned')),
        replace(c,model=replace(c.model,encode='stream')),
        replace(c,model=replace(c.model,J=c.model.J*2)),
        replace(c,model=replace(c.model,reader=replace(c.model.reader,width=128))),
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


@pytest.mark.parametrize('family',['jet','bank'])
def test_learned_rates_raw_transport_and_resume_preserve_optimizer_trajectory(tmp_path,family):
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
    c=dev_config();c=replace(c,model=replace(c.model,method=family,J=4 if family=='jet' else 8,
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
