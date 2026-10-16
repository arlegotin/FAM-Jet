"""Packed policies: independent hand fixtures and raw-oracle cross-checks."""
from dataclasses import replace

import numpy as np
import pytest
import torch

from famjet.types import EventBatch, MemoryMethod, QueryBatch, Snapshot


def event(t, value, *, key=2**64-1, eid=None, observed=None):
    return dict(timestamp=t, event_id=int(t) if eid is None else eid, key_id=key,
                value=np.atleast_1d(value), observed=observed)


def query(*, T=2, key=2**64-1, task='mean', start=1., end=3.):
    return dict(T=T, key_id=key, task=task, age_start=start, age_end=end)


def batches(values=((2., 7.), (6., 7.), (10., 7.), (14., 7.)), tasks=('mean', 'contrast', 'latest', 'change_sign')):
    n, q = len(values), len(tasks)
    e = EventBatch(('h',), torch.arange(n)[None], torch.tensor([[0, 1, 2, 2]]),
                   torch.tensor([[2**64-1]*n], dtype=torch.uint64), torch.ones(1,n,1),
                   torch.tensor([values], dtype=torch.float64), torch.tensor([n]),
                   torch.ones(1,n,dtype=torch.bool), torch.ones(1,n,len(values[0]),dtype=torch.bool), 'ticks')
    x = QueryBatch(('h',), torch.arange(q)[None], torch.full((1,q),2,dtype=torch.int64),
                   torch.tensor([[2**64-1]*q],dtype=torch.uint64), torch.ones(1,q,1), (tasks,),
                   torch.zeros(1,q,dtype=torch.float64), torch.ones(1,q,dtype=torch.float64),
                   torch.ones(1,q,dtype=torch.bool), torch.tensor([q]))
    return e,x


def test_recent_eviction_cannot_invent_old_window():
    from famjet.memory.exact_store import PackedHistory
    ring = PackedHistory(1, 1, 'recent')
    exact = PackedHistory(None, 1, 'exact')
    for store in (ring, exact):
        store.update(event(0, 2.))
        store.update(event(2, 6.))
    r = ring.query(query(start=1., end=3.))
    assert not r.support.item() and not r.failure.item()
    assert torch.isnan(r.prediction).all()
    assert exact.query(query()).prediction.item() == 2.


@pytest.mark.parametrize('policy,capacity', [('recent', 2), ('exact', None), ('latest_lru', 2)])
def test_latest_ties_and_full_uint64_identity(policy, capacity):
    from famjet.memory.exact_store import PackedHistory
    s = PackedHistory(capacity, 1, policy)
    s.update(event(2, 2., eid=2, key=2**63))
    s.update(event(2, 6., eid=3))
    s.update(event(2, 8., eid=4))
    assert s.query(query(task='latest')).prediction.item() == 8.
    assert s.query(query(key=2**63,task='latest')).support.item() == (policy != 'recent')


def test_lru_metadata_is_packed_and_queries_do_not_touch_recency():
    from famjet.memory.exact_store import PackedHistory
    s = PackedHistory(2, 1, 'latest_lru')
    for t,k,v in [(0, 10, 2.), (1, 20, 4.), (2, 10, 6.)]:
        s.update(event(t,v,key=k))
    before=s.arrays()
    assert before['key_ids'].dtype == np.uint64
    assert before['values'].dtype == np.float64
    assert before['occupied'].dtype == np.bool_
    assert before['recency'].dtype == before['size'].dtype == np.int64
    assert before['occupied'].sum() == 2
    assert before['recency'].tolist() == [3,2]
    s.query(query(T=2,key=20,task='latest'))
    s.update(event(3,8.,key=30))
    assert not s.query(query(T=3,key=20,task='latest')).support.item()
    assert s.query(query(T=3,key=10,task='latest')).prediction.item() == 6.
    # Exposed inventory is an owned copy, never a backdoor mutation.
    before['values'][:]=99
    assert s.query(query(T=3,key=10,task='latest')).prediction.item() == 6.
    assert all(isinstance(a,np.ndarray) for a in s.arrays().values())


def test_masks_no_write_and_independent_coordinate_means():
    from famjet.memory.exact_store import PackedHistory
    s = PackedHistory(2,2,'recent')
    s.update(event(0,[2.,99.], observed=[True,False]))
    s.update(event(1,[88.,7.], observed=[False,True]))
    s.update(event(2,[100.,100.], observed=[False,False]))
    assert s.arrays()['size'].item()==2
    assert s.query(query(start=0,end=3)).prediction.tolist()==[[[2.,7.]]]
    assert not s.query(query(task='latest')).support.item()


@pytest.mark.parametrize('times,T', [([2**60-2,2**60-1,2**60],float(2**60)), ([float(2**60),2**60+1,2**60+2],2**60+2)])
def test_mixed_times_remain_exact(times,T):
    from famjet.memory.exact_store import PackedHistory
    s=PackedHistory(None,1,'exact')
    for i,t in enumerate(times): s.update(event(t,float(i+1),eid=i))
    assert s.query(query(T=T,start=0,end=1)).prediction.item()==3.


@pytest.mark.parametrize('task', ['mean','latest'])
def test_empty_retained_evidence_is_unsupported(task):
    from famjet.memory.exact_store import PackedHistory
    r=PackedHistory(1,1,'recent').query(query(task=task))
    assert not r.support.item() and not r.failure.item()
    assert not r.diagnostics['prediction_valid'].item()
    assert torch.isnan(r.prediction).all()


def test_numeric_failure_distinct_from_missing_evidence():
    from famjet.memory.exact_store import PackedHistory
    s=PackedHistory(None,1,'exact')
    s.update(event(0,1e308)); s.update(event(1,1e308))
    r=s.query(query())
    assert r.support.item() and r.failure.item()
    assert not r.diagnostics['prediction_valid'].item()


@pytest.mark.parametrize('policy,capacity', [('exact',None),('recent',4)])
def test_snapshot_adapter_matches_independent_oracle(policy,capacity):
    from famjet.memory.exact_store import PackedHistoryMemory
    from famjet.eval.oracle import exact_targets
    e,q=batches()
    m=PackedHistoryMemory(capacity,2,policy,key_dim=1)
    assert isinstance(m,MemoryMethod)
    state=m.encode(e)
    result=m.read(state,q)
    torch.testing.assert_close(result.prediction,exact_targets(e,q).target)
    assert result.support.all() and not result.failure.any()
    inventory=[*state.payload.values(),state.last_time,state.valid,state.event_offset]
    assert m.persistent_nbytes(state)==sum(t.numel()*t.element_size() for t in inventory)+40
    assert m.parameter_nbytes()==0
    # Fresh reader receives only static schema and an owned Snapshot.
    fresh=PackedHistoryMemory(capacity,2,policy,key_dim=1)
    torch.testing.assert_close(fresh.read(state,q).prediction,result.prediction)


def test_snapshot_reads_advance_resume_and_inputs_are_owned():
    from famjet.memory.exact_store import PackedHistoryMemory
    e,q=batches()
    m=PackedHistoryMemory(4,2,'recent',key_dim=1)
    state=m.encode(e)
    saved={k:v.clone() for k,v in state.payload.items()}
    e.values[:]=99
    first=m.read(state,q).prediction.clone()
    m.read(state,replace(q,T=q.T+1))
    torch.testing.assert_close(m.read(state,q).prediction,first)
    advanced=m.advance_copy(state,3)
    assert advanced.last_time.item()==3 and state.last_time.item()==2
    for k,v in saved.items(): assert torch.equal(v,state.payload[k])
    with pytest.raises(ValueError,match='before'): m.read(state,replace(q,T=q.T-1))
    with pytest.raises(ValueError,match='history'): m.read(state,replace(q,history_ids=('wrong',)))
    one=replace(e,event_ids=torch.tensor([[4]]),timestamps=torch.tensor([[3]]),key_ids=e.key_ids[:,:1],
                key_features=e.key_features[:,:1],values=torch.tensor([[[20.,7.]]],dtype=torch.float64),
                present=e.present[:,:1],observed=e.observed[:,:1],lengths=torch.tensor([1]))
    resumed=m.encode(one,state)
    assert resumed.event_offset.item()==5
    assert m.read(resumed,replace(q,T=q.T+1)).prediction[0,2].tolist()==[20.,7.]
    with pytest.raises(ValueError,match='before'): m.encode(e,advanced)


def test_categorical_handoff_and_missing_category():
    from famjet.memory.exact_store import PackedHistoryMemory
    e,q=batches(tasks=('random_binding',))
    e.values=torch.eye(32,dtype=torch.float64)[torch.tensor([[0,1,2,3]])]
    e.observed=torch.ones_like(e.values,dtype=torch.bool)
    m=PackedHistoryMemory(1,32,'latest_lru',key_dim=1)
    r=m.read(m.encode(e),q)
    assert r.prediction is None and r.logits.argmax(-1).item()==3
    assert r.diagnostics['category_index'].item()==3
    missing=m.read(m.encode(e),replace(q,key_ids=torch.zeros_like(q.key_ids)))
    assert not missing.support.item() and torch.isnan(missing.logits).all()


def test_empty_padded_queries_and_schema_rejection():
    from famjet.memory.exact_store import PackedHistoryMemory, PackedHistory
    e,q=batches()
    m=PackedHistoryMemory(1,2,'recent',key_dim=1)
    empty=m.init_state(1,device='cpu',dtype='float64')
    assert not m.read(empty,q).support.any()
    padded=replace(q,present=torch.zeros_like(q.present),lengths=torch.tensor([0]))
    assert not m.read(m.encode(e),padded).support.any()
    for cap,policy in [(None,'recent'),(0,'recent'),(1,'bad'),(2,'exact')]:
        with pytest.raises(ValueError): PackedHistory(cap,1,policy)
    with pytest.raises(ValueError,match='hash'): m.read(replace(empty,parameter_hash='0'*64),q)
    with pytest.raises(ValueError): m.init_state(1,device='cpu',dtype='float32')


def test_exact_grows_and_bounded_bytes_stay_fixed():
    from famjet.memory.exact_store import PackedHistoryMemory
    e,q=batches()
    exact=PackedHistoryMemory(None,2,'exact',key_dim=1)
    ring=PackedHistoryMemory(1,2,'recent',key_dim=1)
    assert exact.persistent_nbytes(exact.encode(e)) > exact.persistent_nbytes(exact.init_state(1,device='cpu',dtype='float64'))
    assert ring.persistent_nbytes(ring.encode(e)) == ring.persistent_nbytes(ring.init_state(1,device='cpu',dtype='float64'))


@pytest.mark.parametrize('task', ['presence', 'interval_support'])
def test_binary_absence_requires_complete_retained_history(task):
    from famjet.memory.exact_store import PackedHistory
    for policy,cap in [('exact',None),('recent',1)]:
        s=PackedHistory(cap,1,policy)
        r=s.query(query(task=task))
        assert r.prediction.item()==0 and not r.support.item()
        assert r.diagnostics['prediction_valid'].item()
        assert r.diagnostics['evidence_complete'].item()
    s=PackedHistory(1,1,'recent')
    s.update(event(0,2.,key=5)); s.update(event(2,6.,key=6))
    r=s.query(query(task=task,key=5))
    assert torch.isnan(r.prediction).all() and not r.support.item()
    assert not r.diagnostics['prediction_valid'].item()
    assert not r.diagnostics['evidence_complete'].item()


def test_ragged_exact_resume_reuses_padding_slots():
    from famjet.memory.exact_store import PackedHistoryMemory
    e,_=batches()
    fields=('event_ids','timestamps','key_ids','key_features','values','present','observed')
    changes={k:getattr(e,k).repeat(2,*([1]*(getattr(e,k).ndim-1))) for k in fields}
    changes.update(history_ids=('a','b'),lengths=torch.tensor([4,1]))
    changes['present'][1,1:]=False; changes['observed'][1,1:]=False
    first=replace(e,**changes)
    m=PackedHistoryMemory(None,2,'exact',key_dim=1)
    state=m.encode(first)
    changes={k:getattr(first,k)[:,:3].clone() for k in fields}
    changes.update(lengths=torch.tensor([0,3]))
    changes['timestamps'][1]=torch.tensor([3,4,5]); changes['event_ids'][1]=torch.tensor([4,5,6])
    changes['present'][0]=False; changes['observed'][0]=False
    changes['present'][1]=True; changes['observed'][1]=True
    resumed=m.encode(replace(first,**changes),state)
    assert resumed.payload['occupied'].shape==(2,4)
    assert resumed.payload['occupied'].all()
    assert resumed.event_offset.tolist()==[4,4]


@pytest.mark.parametrize('policy,cap', [('exact',None),('recent',4)])
@pytest.mark.parametrize('tasks', [('mean','contrast','latest','change_sign'), ('presence','interval_support')])
def test_independent_observed_adapter_agrees_with_oracle(policy,cap,tasks):
    from famjet.memory.exact_store import PackedHistoryMemory
    from famjet.eval.oracle import exact_targets
    e,q=batches(tasks=tasks)
    e.normalization='independent'; e.observed[0,2:,1]=False
    r=PackedHistoryMemory(cap,2,policy,key_dim=1).read(PackedHistoryMemory(cap,2,policy,key_dim=1).encode(e),q)
    expected=exact_targets(e,q)
    torch.testing.assert_close(r.prediction,expected.target,equal_nan=True)
    assert torch.equal(r.support,expected.supported)
    assert r.diagnostics['prediction_valid'].tolist()==expected.metadata['target_valid']


def test_policy_metadata_does_not_charge_unused_indices():
    from famjet.memory.exact_store import PackedHistory
    for policy,cap in [('exact',None),('recent',2),('latest_lru',2)]:
        arrays=PackedHistory(cap,1,policy).arrays()
        assert ('recency' in arrays)==(policy=='latest_lru')
        assert ('cursor' in arrays)==(policy=='recent')
        assert arrays['time_words'].dtype==np.uint64
        assert arrays['time_words'].nbytes+arrays['time_is_tick'].nbytes==(cap or 0)*9


def test_corrupt_snapshot_stream_status_rejects():
    from famjet.memory.exact_store import PackedHistoryMemory
    e,q=batches()
    m=PackedHistoryMemory(4,2,'recent',key_dim=1)
    state=m.encode(e)
    payload={k:v.clone() for k,v in state.payload.items()}
    payload['last_valid'].zero_()
    with pytest.raises(ValueError,match='stream'):
        m.read(replace(state,payload=payload,valid=torch.zeros_like(state.valid)),q)
