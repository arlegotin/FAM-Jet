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


@pytest.mark.parametrize('changed_field',['commit','diff'])
def test_development_source_change_rejects_before_model_allocation(tmp_path,monkeypatch,changed_field):
    # Package hashes alone miss commit-only and tracked-document changes.
    # Exercise the real trainer/checkpoint boundary; substitute only Git discovery.
    from tests.test_selection import dev_config
    import famjet.eval.isolation as isolation
    from famjet.checkpoint import load_checkpoint,capture_rng
    t=api();c=dev_config();path=t.train_model(c,tmp_path/'first',stop_at=1)
    stored=load_checkpoint(path,{})
    changed=copy.deepcopy(stored['source'])
    changed[changed_field]=('f'*40 if changed_field=='commit' else changed['diff']+'\ntracked README amendment\n')
    monkeypatch.setattr(t,'_source',lambda:changed)
    # Archival loading is explicit and keeps the recorded source; continuation
    # is the operation that must enforce the new full-source expectation.
    assert load_checkpoint(path,{})['source']==stored['source']
    def forbidden(*args,**kwargs):
        raise AssertionError('model allocation reached before development source rejection')
    monkeypatch.setattr(t,'make_model',forbidden)
    monkeypatch.setattr(t,'_reconstruct',forbidden)
    monkeypatch.setattr(isolation,'_reconstruct',forbidden)
    before=capture_rng('cpu')
    with pytest.raises(ValueError,match='checkpoint source mismatch'):
        t.train_model(c,tmp_path/'rejected',resume=path)
    equal_tree(before,capture_rng('cpu'))
    record=json.loads((tmp_path/'rejected/run.json').read_text())
    assert record['status']=='failed' and record['completed_step']==0
    assert record['attempted_episode_ids']==[] and not (tmp_path/'rejected/checkpoint.pt').exists()


def test_legacy_smoke_resume_keeps_package_identity_compatibility(tmp_path,monkeypatch):
    from famjet.checkpoint import load_checkpoint
    t=api();c=tiny();path=t.train_model(c,tmp_path/'first',stop_at=1)
    old=load_checkpoint(path,{})
    changed={**old['source'],'commit':'f'*40,'diff':'tracked docs changed'}
    monkeypatch.setattr(t,'_source',lambda:changed)
    result=load_checkpoint(t.train_model(c,tmp_path/'resume',resume=path),{})
    assert result['completed_step']==2 and result['source']==changed


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


@pytest.fixture(scope='module')
def completed_checkpoint(tmp_path_factory):
    from famjet.checkpoint import load_checkpoint
    t=api()
    return load_checkpoint(t.train_model(tiny(),tmp_path_factory.mktemp('raw-adam')/'run'),{})


@pytest.mark.parametrize('boundary',['save','load'])
@pytest.mark.parametrize('damage',['float64_mean','float64_second_moment','fractional_step',
    'vector_step','nonfinite_step','extra_state_cache','negative_second_moment',
    'unknown_parameter_id','float_parameter_id','float_group_id','extra_optimizer_cache'])
def test_raw_adam_checkpoint_rejected_before_coercion(tmp_path,completed_checkpoint,boundary,damage):
    import hashlib
    import io
    from famjet.checkpoint import save_checkpoint,load_checkpoint,capture_rng
    context=copy.deepcopy(completed_checkpoint)
    optimizer=context['optimizer']; states=optimizer['state']; key=next(iter(states)); state=states[key]
    if damage=='float64_mean': state['exp_avg']=state['exp_avg'].double()
    elif damage=='float64_second_moment': state['exp_avg_sq']=state['exp_avg_sq'].double()
    elif damage=='fractional_step': state['step'].fill_(2.5)
    elif damage=='vector_step': state['step']=state['step'].reshape(1)
    elif damage=='nonfinite_step': state['step'].fill_(float('inf'))
    elif damage=='extra_state_cache': state['unexpected_cache']=state['exp_avg'].clone()
    elif damage=='negative_second_moment': state['exp_avg_sq'].flatten()[0]=-1
    elif damage=='unknown_parameter_id': states[99999]=states.pop(key)
    elif damage=='float_parameter_id': states[float(key)]=states.pop(key)
    elif damage=='float_group_id': optimizer['param_groups'][0]['params'][0]=0.
    else: optimizer['unexpected_cache']=torch.ones(4)
    path=tmp_path/'malformed.pt'
    previous=capture_rng('cpu')
    if boundary=='load':
        # Bypass the saving validator to exercise acceptance of raw serialized
        # bytes with a correct checksum, not checksum-corruption rejection.
        buffer=io.BytesIO(); torch.save(context,buffer); payload=buffer.getvalue()
        path.write_bytes(b'FAMJET-CHECKPOINT-1\n'+hashlib.sha256(payload).hexdigest().encode()+b'\n'+payload)
    with pytest.raises(ValueError,match='checkpoint'):
        if boundary=='save': save_checkpoint(path,context)
        else: load_checkpoint(path,{})
    equal_tree(previous,capture_rng('cpu'))


@pytest.mark.parametrize('boundary',['save','load'])
@pytest.mark.parametrize('damage',['reader_depth','reader_width','reader_rank','reader_features',
    'kernel_key_dim','kernel_value_dim','component_shape','source_count','config_depth'])
def test_checkpoint_descriptors_reject_before_model_allocation(tmp_path,completed_checkpoint,monkeypatch,damage,boundary):
    import famjet.eval.isolation as isolation
    import hashlib
    import io
    from famjet.checkpoint import save_checkpoint,load_checkpoint
    from famjet.provenance import canonical_hash
    context=copy.deepcopy(completed_checkpoint)
    model=context['model']; schema=model['schema']; kernel=schema['kernel']
    if damage=='reader_depth': schema['reader']['budget']['hidden_layers']=1_000_000
    elif damage=='reader_width': schema['reader']['budget']['width']=1_000_000
    elif damage=='reader_rank': schema['reader']['budget']['rank']=1_000_000
    elif damage=='reader_features': schema['reader']['feature_spec']['anchors']=1_000_000
    elif damage=='kernel_key_dim': kernel['schema']['key_dim']=1_000_000
    elif damage=='kernel_value_dim': kernel['schema']['value_dim']=1_000_000
    elif damage=='component_shape': kernel['weights']['rates']['shape']=[1,1_000_000]
    elif damage=='source_count':
        context['config']['model']['rates']['mode']='learned'
        schema['inference_config']['rate_mode']='learned'
        kernel['schema']['rate_source']={'count':1_000_000,'log_min':-6.907755278982137,'log_max':0.}
    else: context['config']['model']['reader']['layers']=1_000_000
    # Matching digests make this exercise descriptor/config preflight, rather
    # than an incidental changed-hash rejection.
    context['model_hash']=canonical_hash(model)
    context['config_hash']=canonical_hash(context['config'])
    def allocation_forbidden(*args,**kwargs):
        pytest.fail('oversized checkpoint reached model reconstruction')
    monkeypatch.setattr(isolation,'_reconstruct',allocation_forbidden)
    path=tmp_path/'oversized.pt'
    if boundary=='load':
        buffer=io.BytesIO(); torch.save(context,buffer); payload=buffer.getvalue()
        path.write_bytes(b'FAMJET-CHECKPOINT-1\n'+hashlib.sha256(payload).hexdigest().encode()+b'\n'+payload)
    with pytest.raises(ValueError,match='checkpoint|smoke envelope'):
        if boundary=='save': save_checkpoint(path,context)
        else: load_checkpoint(path,{})


def test_expected_checkpoint_identity_checked_before_reconstruction(tmp_path,completed_checkpoint,monkeypatch):
    import famjet.eval.isolation as isolation
    from famjet.checkpoint import save_checkpoint,load_checkpoint
    path=tmp_path/'valid.pt'; save_checkpoint(path,completed_checkpoint)
    def allocation_forbidden(*args,**kwargs):
        pytest.fail('identity mismatch reached model reconstruction')
    monkeypatch.setattr(isolation,'_reconstruct',allocation_forbidden)
    with pytest.raises(ValueError,match='config_hash mismatch'):
        load_checkpoint(path,{'config_hash':'wrong'})


def test_rejected_raw_adam_preserves_current_and_previous(tmp_path,completed_checkpoint):
    from famjet.checkpoint import save_checkpoint
    path=tmp_path/'valid.pt'
    save_checkpoint(path,completed_checkpoint); save_checkpoint(path,completed_checkpoint)
    previous=path.with_suffix('.pt.previous')
    original=(path.read_bytes(),previous.read_bytes())
    bad=copy.deepcopy(completed_checkpoint)
    next(iter(bad['optimizer']['state'].values()))['exp_avg']=torch.zeros(1,dtype=torch.float64)
    with pytest.raises(ValueError,match='moment'):
        save_checkpoint(path,bad)
    assert (path.read_bytes(),previous.read_bytes())==original
