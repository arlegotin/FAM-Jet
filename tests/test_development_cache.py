"""Exact fresh-draw transport, integrity and full optimization equivalence."""
from dataclasses import replace
import json
import pytest
import torch
from tests.test_selection import dev_config


def cached_config(c,path):
    from famjet.provenance import canonical_hash
    manifest=json.loads(path.read_text())
    return replace(c,development=replace(c.development,cache_manifest_path=str(path),cache_manifest_hash=canonical_hash(manifest)))


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
