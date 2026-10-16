"""Run lifecycle: real optimization, full gradients, and failure evidence."""
from dataclasses import replace
import importlib.util
import json
from pathlib import Path
import pytest
import torch
from famjet.config import load_config


def api():
    assert importlib.util.find_spec('famjet.train') is not None, 'training lifecycle is missing'
    from famjet import train
    return train


def tiny(device='cpu', family='jet', learned=False):
    c = load_config(Path('configs/smoke.yaml'))
    return replace(c, data=replace(c.data, queries_per_history=2),
        model=replace(c.model, method=family, J=2, writer='learned' if learned else 'fixed',
            rates=replace(c.model.rates, mode='learned' if learned else 'fixed'),
            reader=replace(c.model.reader, width=8)),
        training=replace(c.training, effective_batch=2),
        resources=replace(c.resources, device=device, cpu_threads=1))


def test_training_records_fresh_draws_and_real_optimizer_steps(tmp_path):
    t = api()
    path = t.train_model(tiny(learned=True), tmp_path/'run')
    from famjet.checkpoint import load_checkpoint
    ctx = load_checkpoint(path, {})
    assert ctx['completed_step'] == 2
    assert ctx['sampler']['position'] == 4
    assert ctx['consumed_episode_ids'] == [f'train-{i:012d}' for i in range(4)]
    assert all(v['step'].item() == 2 for v in ctx['optimizer']['state'].values())
    run = json.loads((tmp_path/'run'/'run.json').read_text())
    assert run['status'] == 'completed' and run['scientific_status'] == 'non_scientific_smoke'
    rows = [json.loads(x) for x in (tmp_path/'run'/'training.jsonl').read_text().splitlines()]
    assert len(rows) == 2 and all(r['gradient_norm'] > 0 for r in rows)
    assert rows[0]['writer_hash_before'] != rows[1]['writer_hash_before']
    assert rows[0]['episode_ids'] != rows[1]['episode_ids']
    assert (tmp_path/'run'/'predictions.jsonl').stat().st_size > 0
    assert (tmp_path/'run'/'timing.jsonl').stat().st_size > 0


def test_failed_run_is_retained(tmp_path, monkeypatch):
    t = api()
    def failure(*args, **kwargs):
        raise FloatingPointError('injected nonfinite objective')
    monkeypatch.setattr(t, 'history_loss', failure)
    with pytest.raises(FloatingPointError):
        t.train_model(tiny(), tmp_path/'failed')
    record = json.loads((tmp_path/'failed'/'run.json').read_text())
    assert record['status'] == 'failed' and record['failure_category'] == 'numerical_model_failure'
    assert record['attempted_episode_ids'] == ['train-000000000000']
    assert record['completed_step'] == 0
    assert (tmp_path/'failed'/'checkpoint.pt').is_file()
    with pytest.raises(FileExistsError):
        t.train_model(tiny(), tmp_path/'failed')


def test_history_loss_equal_task_weight_and_valid_absence():
    t = api()
    from famjet.types import ReadResult, Episode
    from jet_fixtures import events, queries
    e = events(torch.float32)
    q = queries(e, [[8,8,8], [7,7,7]])
    q = replace(q, tasks=(('mean','mean','contrast'),)*2)
    m = t.make_model(tiny())
    prediction = torch.tensor([[[1.]*8,[1.]*8,[3.]*8]]*2, requires_grad=True)
    ep = Episode(e,q,torch.zeros_like(prediction),torch.ones((2,3),dtype=torch.bool))
    result = ReadResult(prediction,None,torch.ones(2,3),torch.zeros(2,3,dtype=torch.bool),{})
    assert t.history_loss(m,result,ep).item() == 5
    qb = replace(q,tasks=(('presence',)*3,)*2)
    logits = torch.zeros(2,3,requires_grad=True)
    binary = Episode(e,qb,torch.zeros(2,3,1),torch.zeros(2,3,dtype=torch.bool))
    rb = ReadResult(torch.sigmoid(logits)[...,None],None,torch.sigmoid(logits),result.failure,{'support_logit':logits})
    loss = t.history_loss(m,rb,binary)
    loss.backward()
    assert torch.all(logits.grad > 0)


@pytest.mark.parametrize('family',['jet','bank'])
def test_checkpoint_recompute_preserves_all_gradients(family):
    t = api()
    from famjet.data.synthetic import generate_episode
    c=tiny(family=family,learned=True)
    torch.manual_seed(9)
    m=t.make_model(c)
    ep=t.move_episode(generate_episode(c,71,'gradient-history'),'cpu')
    a=t.forward_training(m,ep,'stream',recompute=False)
    t.history_loss(m,a,ep).backward()
    grads={n:p.grad.clone() for n,p in m.named_parameters() if p.grad is not None}
    m.zero_grad(set_to_none=True)
    b=t.forward_training(m,ep,'stream',recompute=True)
    t.history_loss(m,b,ep).backward()
    for n,p in m.named_parameters():
        if n in grads:
            torch.testing.assert_close(p.grad,grads[n],rtol=0,atol=0)
    assert grads['writer.value.weight'].abs().sum()>0
    assert grads['kernel.rate_source.logits'].abs().sum()>0


def test_valid_binary_absence_is_not_dropped_in_training_run(tmp_path):
    t=api(); c=tiny()
    c=replace(c,data=replace(c.data,generator=replace(c.data.generator,population='presence')))
    path=t.train_model(c,tmp_path/'presence')
    from famjet.checkpoint import load_checkpoint
    assert load_checkpoint(path,{})['completed_step']==2


def test_missing_labels_and_nonfinite_gradients_are_distinct(tmp_path,monkeypatch):
    t=api(); original=t.history_loss
    def invalid(*a,**kw): raise ValueError('missing training labels')
    monkeypatch.setattr(t,'history_loss',invalid)
    with pytest.raises(ValueError): t.train_model(tiny(),tmp_path/'missing')
    assert json.loads((tmp_path/'missing'/'run.json').read_text())['failure_category']=='infrastructure_or_contract_failure'
    def bad_gradient(model,*args,**kw):
        result=original(model,*args,**kw)
        next(model.parameters()).register_hook(lambda grad: grad*float('nan'))
        return result
    monkeypatch.setattr(t,'history_loss',bad_gradient)
    with pytest.raises(FloatingPointError): t.train_model(tiny(),tmp_path/'nan')
    assert json.loads((tmp_path/'nan'/'run.json').read_text())['failure_category']=='numerical_model_failure'


def test_microbatch_accumulation_and_shared_method_draws(tmp_path):
    t=api(); c=tiny()
    from famjet.checkpoint import load_checkpoint
    a=load_checkpoint(t.train_model(c,tmp_path/'accum'),{})
    batched=replace(c,training=replace(c.training,microbatch=2))
    b=load_checkpoint(t.train_model(batched,tmp_path/'batch'),{})
    for name in a['model_state']:
        torch.testing.assert_close(a['model_state'][name],b['model_state'][name],rtol=1e-5,atol=1e-6)
    t.train_model(tiny(family='bank'),tmp_path/'bank')
    def draws(name): return [json.loads(x) for x in (tmp_path/name/'draws.jsonl').read_text().splitlines()]
    assert draws('accum')==draws('bank')


def test_evaluate_manifest_development_only_and_hash_validation(tmp_path):
    t=api(); c=tiny()
    from famjet.eval.splits import _population_manifest,_split_roots
    from famjet.artifacts import atomic_json
    p=t.train_model(c,tmp_path/'train')
    manifest=_population_manifest(c,_split_roots(c))
    atomic_json(tmp_path/'manifest.json',manifest)
    out=t.evaluate_model(p,tmp_path/'manifest.json',tmp_path/'evaluation')
    records=[json.loads(x) for x in out.read_text().splitlines()]
    assert records and {r['split'] for r in records}=={'development_fit'}
    assert len({r['history_id'] for r in records})==4
    manifest['splits']['development_fit']['episodes'][0]['hashes']['events']='corrupt'
    # A resealed record still must match regenerated exploratory inputs.
    from famjet.provenance import canonical_hash
    manifest['manifest_hash']=canonical_hash({k:v for k,v in manifest.items() if k!='manifest_hash'})
    atomic_json(tmp_path/'tampered.json',manifest)
    with pytest.raises(ValueError,match='hash|manifest'):
        t.evaluate_model(p,tmp_path/'tampered.json',tmp_path/'bad-evaluation')
    assert json.loads((tmp_path/'bad-evaluation'/'run.json').read_text())['status']=='failed'


def test_non_smoke_and_oversize_attempts_retained(tmp_path):
    t=api()
    for name,c in [('development',replace(tiny(),phase='development')),
                   ('oversize',replace(tiny(),training=replace(tiny().training,optimizer_steps=100)))]:
        with pytest.raises(ValueError,match='calibration|envelope'):
            t.train_model(c,tmp_path/name)
        assert json.loads((tmp_path/name/'run.json').read_text())['status']=='failed'


def test_smoke_limit_already_contains_the_discovery_reserve():
    t=api(); c=tiny()
    t.check_smoke_memory(c,177471488)
    with pytest.raises(MemoryError):
        t.check_smoke_memory(c,201326593)


def test_recompute_reaches_earliest_observed_write():
    t=api()
    from famjet.data.synthetic import generate_episode
    c=tiny(learned=True)
    torch.manual_seed(6); m=t.make_model(c)
    ep=t.move_episode(generate_episode(c,71,'gradient-history'),'cpu')
    ep.events.values.requires_grad_()
    result=t.forward_training(m,ep,'stream',recompute=True)
    t.history_loss(m,result,ep).backward()
    first=int(torch.where(ep.events.observed[0].any(-1))[0][0])
    assert ep.events.values.grad[0,first].abs().sum()>0
    assert torch.all(ep.events.values.grad[~ep.events.observed]==0)


def test_evaluation_rejects_protected_inventory_before_predictions(tmp_path):
    t=api(); c=tiny()
    from famjet.eval.splits import _population_manifest,_split_roots
    from famjet.artifacts import atomic_json
    from famjet.provenance import canonical_hash
    p=t.train_model(c,tmp_path/'train')
    manifest=_population_manifest(c,_split_roots(c))
    manifest['splits']['confirmation']['episodes']=[{'secret':'must not score'}]
    manifest['manifest_hash']=canonical_hash({k:v for k,v in manifest.items() if k!='manifest_hash'})
    atomic_json(tmp_path/'protected.json',manifest)
    with pytest.raises(ValueError,match='protected'):
        t.evaluate_model(p,tmp_path/'protected.json',tmp_path/'refused')
    assert not (tmp_path/'refused'/'predictions.jsonl').exists()


def test_config_cannot_raise_the_discovered_smoke_ceiling(tmp_path):
    t=api(); c=tiny()
    c=replace(c,resources=replace(c.resources,smoke_additional_allocation_limit_bytes=2**40))
    with pytest.raises(ValueError,match='discovered|provenance'):
        t.train_model(c,tmp_path/'unsafe')
    assert json.loads((tmp_path/'unsafe'/'run.json').read_text())['status']=='failed'
