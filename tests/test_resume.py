"""Checkpoint integrity and interrupted versus uninterrupted trajectories."""
import copy
import json
import random
import numpy as np
import pytest
import torch
from test_training import api, tiny


def equal_tree(a,b,rtol=0,atol=0):
    if isinstance(a,torch.Tensor):
        torch.testing.assert_close(a,b,rtol=rtol,atol=atol)
    elif isinstance(a,dict):
        assert a.keys()==b.keys()
        for k in a: equal_tree(a[k],b[k],rtol,atol)
    elif isinstance(a,(tuple,list)):
        assert len(a)==len(b)
        for x,y in zip(a,b): equal_tree(x,y,rtol,atol)
    else: assert a==b


@pytest.mark.parametrize('device',['cpu','mps'])
def test_interrupted_training_matches_trajectory(tmp_path,monkeypatch,device):
    if device=='mps' and not torch.backends.mps.is_available(): pytest.skip('native MPS required')
    t=api()
    from famjet.checkpoint import load_checkpoint
    c=tiny(device,learned=True)
    full=t.train_model(c,tmp_path/'full')
    original=t.history_loss
    calls=0
    def interrupt(*args,**kw):
        nonlocal calls
        calls+=1
        if calls==4: raise KeyboardInterrupt('simulated mid-accumulation interruption')
        return original(*args,**kw)
    monkeypatch.setattr(t,'history_loss',interrupt)
    with pytest.raises(KeyboardInterrupt): t.train_model(c,tmp_path/'interrupted')
    monkeypatch.setattr(t,'history_loss',original)
    random.random(); np.random.rand(); torch.rand(13)
    resumed=t.train_model(c,tmp_path/'resumed',resume=tmp_path/'interrupted'/'checkpoint.pt')
    a,b=load_checkpoint(full,{}),load_checkpoint(resumed,{})
    assert a['consumed_episode_ids']==b['consumed_episode_ids']
    assert a['completed_step']==b['completed_step']==2
    tolerance=(0,0) if device=='cpu' else (1e-5,1e-6)
    equal_tree(a['model_state'],b['model_state'],*tolerance)
    equal_tree(a['optimizer'],b['optimizer'],*tolerance)
    equal_tree(a['rng'],b['rng'])
    pa=[json.loads(x) for x in (tmp_path/'full'/'predictions.jsonl').read_text().splitlines()]
    pb=[json.loads(x) for x in (tmp_path/'resumed'/'predictions.jsonl').read_text().splitlines()]
    assert len(pa)==len(pb)>0
    for x,y in zip(pa,pb):
        torch.testing.assert_close(torch.tensor(x['prediction']),torch.tensor(y['prediction']),rtol=tolerance[0],atol=tolerance[1])
    deltas=[(a['model_state'][k]-b['model_state'][k]).abs().max().item() for k in a['model_state']]
    print(f'{device} resume maximum parameter absolute difference={max(deltas):.9g}; rtol={tolerance[0]}, atol={tolerance[1]}')


def test_missing_accumulation_restarts_full_step(tmp_path):
    t=api()
    from famjet.checkpoint import save_checkpoint,load_checkpoint
    p=t.train_model(tiny(),tmp_path/'run')
    ctx=load_checkpoint(p,{})
    ctx['accumulation_position']=1
    ctx['sampler']['position']+=1
    save_checkpoint(tmp_path/'partial.pt',ctx)
    result=load_checkpoint(tmp_path/'partial.pt',{})
    assert result['accumulation_position']==0
    assert result['sampler']['position']==4
    assert result['restarted_accumulation'] is True


def test_old_cached_writer_state_rejected(tmp_path):
    t=api()
    from famjet.checkpoint import save_checkpoint,load_checkpoint
    p=t.train_model(tiny(),tmp_path/'run')
    ctx=load_checkpoint(p,{})
    ctx['cached_writer_state']={'parameter_hash':'outdated'}
    with pytest.raises(ValueError,match='cache|schema'):
        save_checkpoint(tmp_path/'stale.pt',ctx)


def test_checkpoint_integrity_identity_and_previous(tmp_path):
    t=api()
    from famjet.checkpoint import load_checkpoint
    p=t.train_model(tiny(),tmp_path/'run')
    for name in ['config_hash','source_hash','data_hash','lock_hash']:
        with pytest.raises(ValueError,match='mismatch'):
            load_checkpoint(p,{name:'wrong'})
    old=load_checkpoint(p.with_suffix('.pt.previous'),{})
    assert old['completed_step']==1
    p.write_bytes(p.read_bytes()[:-20])
    with pytest.raises(ValueError,match='checksum|corrupt'):
        load_checkpoint(p,{})
    assert load_checkpoint(p.with_suffix('.pt.previous'),{})['completed_step']==1


@pytest.mark.parametrize('damage',['optimizer_shape','optimizer_missing','optimizer_hyperparameter','rng_missing','model_parameters','sampler_position'])
def test_checkpoint_rejects_incomplete_or_inconsistent_state(tmp_path,damage):
    t=api()
    from famjet.checkpoint import save_checkpoint,load_checkpoint
    ctx=load_checkpoint(t.train_model(tiny(),tmp_path/'run'),{})
    states=ctx['optimizer']['state']; key=next(iter(states))
    if damage=='optimizer_shape': states[key]['exp_avg']=torch.zeros(1)
    elif damage=='optimizer_missing': states.pop(key)
    elif damage=='optimizer_hyperparameter': ctx['optimizer']['param_groups'][0]['lr']=100.
    elif damage=='rng_missing': ctx['rng'].pop('numpy')
    elif damage=='model_parameters': next(iter(ctx['model_state'].values())).add_(1)
    else: ctx['sampler']['position']+=1
    with pytest.raises(ValueError,match='checkpoint'):
        save_checkpoint(tmp_path/'bad.pt',ctx)


def test_checkpoint_validation_does_not_advance_rng(tmp_path):
    t=api()
    from famjet.checkpoint import capture_rng,load_checkpoint,save_checkpoint
    path=t.train_model(tiny(),tmp_path/'run')
    previous=capture_rng('cpu')
    context=load_checkpoint(path,{})
    save_checkpoint(tmp_path/'copy.pt',context)
    equal_tree(previous,capture_rng('cpu'))
