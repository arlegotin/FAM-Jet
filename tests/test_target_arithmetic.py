from dataclasses import replace
from fractions import Fraction
import numpy as np
import pytest
import torch
from famjet.types import EventBatch,QueryBatch
from famjet.eval.oracle import exact_targets
from famjet.memory.exact_store import PackedHistoryMemory


def arithmetic(values,padding=0):
    n=len(values)+padding
    observed=torch.tensor([[[True]]*len(values)+[[False]]*padding])
    e=EventBatch(('h',),torch.arange(n)[None],torch.zeros(1,n,dtype=torch.float64),torch.ones(1,n,dtype=torch.int64),
                 torch.ones(1,n,1),torch.tensor([[ [v] for v in values+[0.]*padding]],dtype=torch.float64),torch.tensor([n]),
                 torch.ones(1,n,dtype=torch.bool),observed,'ticks')
    q=QueryBatch(('h',),torch.tensor([[0]]),torch.zeros(1,1,dtype=torch.float64),torch.ones(1,1,dtype=torch.int64),torch.ones(1,1,1),
                 (('mean',),),torch.zeros(1,1,dtype=torch.float64),torch.ones(1,1,dtype=torch.float64),torch.ones(1,1,dtype=torch.bool),torch.tensor([1]))
    return e,q


@pytest.mark.parametrize('values',[[1e16,1.,-1e16,1.],[1e308,1e308], [1e308,1e308,-1e308,-1e308,1.]])
@pytest.mark.parametrize('padding',[0,4,17])
def test_reference_and_store_mean_match_rational_truth_without_padding_dependence(values,padding):
    e,q=arithmetic(values,padding)
    truth=float(sum(map(Fraction,values))/len(values))
    assert exact_targets(e,q).target.item()==truth
    m=PackedHistoryMemory(None,1,'exact',key_dim=1)
    assert m.read(m.encode(e),q).prediction.item()==truth


def test_target_version_alias_preserves_event_query_seed_draws():
    from pathlib import Path
    from famjet.config import load_config
    from famjet.data.synthetic import generate_episode
    c=load_config(Path('configs/smoke.yaml'))
    old=replace(c,data=replace(c.data,generator_version='initial_spec_v1'))
    new=replace(c,data=replace(c.data,generator_version='initial_spec_v2_targets'))
    a,b=(generate_episode(x,20261013,'arithmetic-version') for x in [old,new])
    assert a.metadata['hashes']['events']==b.metadata['hashes']['events']
    assert a.metadata['hashes']['queries']==b.metadata['hashes']['queries']
    assert a.metadata['split_root']==b.metadata['split_root']
    assert a.metadata['hashes']['oracle']!=b.metadata['hashes']['oracle']
    assert b.metadata['target_semantics']=='observed_event_targets_v2'


def test_reservoir_and_hybrid_zero_sample_include_older_contrast_interval():
    from famjet.memory.reservoir import Reservoir,HybridStore
    for s in [Reservoir(2,1,3),HybridStore(1,1,1,3)]:
        s.update({'timestamp':0.,'event_id':0,'key_id':1,'value':np.array([2.]),'observed':np.array([True])})
        r=s.query({'T':0.,'key_id':1,'task':'contrast','age_start':0.,'age_end':1.})
        assert r.diagnostics['zero_sample'].item() and not r.diagnostics['prediction_valid'].item()


def test_archived_beijing_manifest_verifies_but_cannot_supply_current_training():
    from pathlib import Path
    from famjet.data.beijing import _verify_manifest,iter_beijing_episodes
    path=Path('configs/manifests/beijing_v1.json')
    assert _verify_manifest(path)['preparation_version']=='beijing_observed_v1'
    with pytest.raises(ValueError,match='legacy target'): list(iter_beijing_episodes(path,'training'))


def test_current_manifest_names_target_semantics_and_rejects_relabeling():
    from pathlib import Path
    from famjet.config import load_config
    from famjet.eval.splits import _population_manifest,_split_roots,_check_seal,_seal
    c=load_config(Path('configs/smoke.yaml'))
    payload=_population_manifest(c,_split_roots(c))
    assert payload['target_semantics']=='observed_event_targets_v2'
    payload['target_semantics']='observed_event_targets_v1'
    payload=_seal({k:v for k,v in payload.items() if k!='manifest_hash'})
    with pytest.raises(ValueError,match='target semantics'): _check_seal(payload)
