"""Bounded summary policies: independent fixtures, restart and Snapshot isolation."""
from dataclasses import replace

import numpy as np
import pytest
import torch

from famjet.types import EventBatch, QueryBatch, MemoryMethod


def event(t, value, key=2**64-1, eid=None, observed=None):
    return dict(timestamp=t, value=np.atleast_1d(value), key_id=key,
                event_id=int(t) if eid is None else eid, observed=observed)


def query(T=12, key=2**64-1, task='mean', start=0., end=13.):
    return dict(T=T, key_id=key, task=task, age_start=start, age_end=end)


def methods(kind, capacity=8, value_dtype='float64', accumulation_dtype='float64'):
    from famjet.memory.reservoir import ReservoirMemory, HybridMemory
    from famjet.memory.buckets import TemporalBucketsMemory
    if kind == 'reservoir': return ReservoirMemory(capacity, 2, 7, key_dim=1, value_dtype=value_dtype)
    if kind == 'hybrid': return HybridMemory(capacity, capacity, 2, 7, key_dim=1, value_dtype=value_dtype)
    return TemporalBucketsMemory(capacity, 2, key_dim=1, value_dtype=value_dtype, accumulation_dtype=accumulation_dtype)


def batches():
    e = EventBatch(('h',),torch.arange(4)[None],torch.tensor([[0,1,2,2]]),
                   torch.full((1,4),2**64-1,dtype=torch.uint64),torch.ones(1,4,1),
                   torch.tensor([[[2.,7.],[6.,7.],[10.,7.],[14.,7.]]],dtype=torch.float64),torch.tensor([4]),
                   torch.ones(1,4,dtype=torch.bool),torch.ones(1,4,2,dtype=torch.bool),'ticks')
    q = QueryBatch(('h',),torch.arange(4)[None],torch.full((1,4),2,dtype=torch.int64),
                   torch.full((1,4),2**64-1,dtype=torch.uint64),torch.ones(1,4,1),
                   (('mean','contrast','latest','change_sign'),),torch.zeros(1,4,dtype=torch.float64),
                   torch.ones(1,4,dtype=torch.float64),torch.ones(1,4,dtype=torch.bool),torch.tensor([4]))
    return e,q


def test_reservoir_seed_fixed_golden_ids_and_restart():
    from famjet.memory.reservoir import Reservoir
    full=Reservoir(3,1,7)
    for i in range(12): full.update(event(i,float(i)))
    assert full.arrays()['event_ids'].tolist()==[5,1,7]
    assert full.arrays()['total_writes'].item()==12
    assert full.arrays()['rng_counter'].item()==9
    partial=Reservoir(3,1,7)
    for i in range(6): partial.update(event(i,float(i)))
    resumed=Reservoir(3,1,7)
    resumed._data=partial.arrays()  # The adapter uses this same owned packed inventory.
    for i in range(6,12): resumed.update(event(i,float(i)))
    for name,a in full.arrays().items(): np.testing.assert_array_equal(a,resumed.arrays()[name])


def test_reservoir_gross_sampling_bias_across_seeds():
    from famjet.memory.reservoir import Reservoir
    hits=np.zeros(10,dtype=int)
    for seed in range(600):
        s=Reservoir(2,1,seed)
        for i in range(10): s.update(event(i,float(i)))
        hits[s.arrays()['event_ids'].astype(int)]+=1
    # Expected 120 per position, sd~9.8; broad fixed guard detects ring/first-only bias.
    assert ((hits>75)&(hits<165)).all(), hits


def test_reservoir_no_write_does_not_draw_or_consume_sample_capacity():
    from famjet.memory.reservoir import Reservoir
    s=Reservoir(1,1,7); s.update(event(0,2.))
    s.update(event(1,99.,observed=[False]))
    a=s.arrays(); assert a['total_writes'].item()==1 and a['seen'].item()==2
    assert a['rng_counter'].item()==0 and a['size'].item()==1
    r=s.query(query(key=0))
    assert not r.support.item() and not r.failure.item()
    assert r.diagnostics['zero_sample'].item()
    assert torch.isnan(r.prediction).all()


def test_buckets_merge_same_key_neighbors_across_interleaved_keys():
    from famjet.memory.buckets import TemporalBuckets
    s=TemporalBuckets(3,1)
    for t,k,v in [(0,5,2.),(1,8,20.),(2,5,6.),(3,8,40.)]: s.update(event(t,v,key=k))
    a=s.arrays(); occupied=a['occupied']
    assert a['size'].item()==3 and a['merges'].item()==1 and a['evicted_keys'].item()==0
    j=np.flatnonzero(occupied & (a['key_ids']==5) & (a['event_counts']==2)).item()
    assert a['values'][j,0]==8 and a['counts'][j,0]==2
    assert s.query(query(T=3,key=5,end=4)).prediction.item()==4.


def test_bucket_minimum_combined_span_and_deterministic_tie():
    from famjet.memory.buckets import TemporalBuckets
    s=TemporalBuckets(3,1)
    for t in (0,10,11,20): s.update(event(t,float(t)))
    a=s.arrays(); j=np.flatnonzero(a['event_counts']==2).item()
    assert a['values'][j,0]==21 and a['merges'].item()==1
    tied=TemporalBuckets(3,1)
    for t,k in [(0,9),(1,4),(2,9),(3,4)]: tied.update(event(t,1.,key=k))
    a=tied.arrays(); j=np.flatnonzero(a['event_counts']==2).item()
    assert int(a['key_ids'][j])==9  # equal span: oldest start first, then key/slots.


def test_bucket_whole_least_recent_key_eviction_when_no_pair():
    from famjet.memory.buckets import TemporalBuckets
    s=TemporalBuckets(2,1)
    for t,k in [(0,8),(1,5),(2,4)]: s.update(event(t,float(k),key=k))
    a=s.arrays(); assert set(a['key_ids'][a['occupied']].tolist())=={4,5}
    assert a['evicted_keys'].item()==1 and a['discarded'].item()==1
    r=s.query(query(T=2,key=8,task='presence'))
    assert not r.diagnostics['prediction_valid'].item() and torch.isnan(r.prediction).all()


@pytest.mark.parametrize('start,end,want',[(0.,1.,False),(1.,2.,True),(2.,3.,False),(1.,1.,False)])
def test_point_bucket_boundaries_are_exact(start,end,want):
    from famjet.memory.buckets import TemporalBuckets
    s=TemporalBuckets(1,1); s.update(event(1,2.)); s.update(event(1,6.,eid=2))
    r=s.query(query(T=2,start=start,end=end))
    assert r.support.item()==want
    if want: assert r.prediction.item()==4.
    else: assert torch.isnan(r.prediction).all() and not r.diagnostics['prediction_valid'].item()


def test_bucket_overlap_decoder_and_factual_support_are_distinct():
    from famjet.memory.buckets import TemporalBuckets
    s=TemporalBuckets(2,1)
    for t,v in [(0,2.),(4,6.),(10,20.)]: s.update(event(t,v))
    # [0,4] sum8/count2 contributes half; point10 contributes fully: (4+20)/(1+1)=12.
    r=s.query(query(T=10,end=8))
    assert r.prediction.item()==12. and r.diagnostics['observed_counts'][0,0,0,0].item()==2.
    assert r.diagnostics['approximate'].item() and not r.diagnostics['evidence_complete'].item()
    # Interior of a merged span gives a valid estimate but no proof of an event there.
    r=s.query(query(T=10,start=7.,end=9.))
    assert r.prediction.item()==4. and r.diagnostics['prediction_valid'].item()
    assert not r.support.item()
    binary=s.query(query(T=10,start=7.,end=9.,task='interval_support'))
    assert not binary.diagnostics['prediction_valid'].item() and torch.isnan(binary.prediction).all()


def test_bucket_coordinate_counts_never_share_an_invalid_denominator():
    from famjet.memory.buckets import TemporalBuckets
    s=TemporalBuckets(1,2)
    s.update(event(0,[2.,99.],observed=[True,False]))
    s.update(event(1,[6.,7.],observed=[True,True]))
    r=s.query(query(T=1,end=2))
    assert r.prediction.tolist()==[[[4.,7.]]]
    assert r.diagnostics['observed_counts'][0,0,0].tolist()==[2.,1.]
    a=s.arrays(); assert a['counts'][0].tolist()==[2,1]


def test_hybrid_read_deduplicates_overlap_and_owns_both_stores():
    from famjet.memory.reservoir import HybridStore
    s=HybridStore(2,4,1,7)
    for t,v in enumerate([1.,3.,9.]): s.update(event(t,v))
    r=s.query(query(T=2,end=3))
    assert r.prediction.item()==13/3
    assert r.diagnostics['observed_counts'][0,0,0,0].item()==3
    assert r.diagnostics['overlap_count'].item()==2
    assert r.diagnostics['evidence_complete'].item()
    a=s.arrays(); assert any(k.startswith('recent_') for k in a) and any(k.startswith('reservoir_') for k in a)
    assert all(isinstance(v,np.ndarray) for v in a.values())


@pytest.mark.parametrize('kind',['reservoir','buckets','hybrid'])
def test_snapshot_adapter_exact_control_raw_oracle_bytes_and_fresh_reader(kind):
    from famjet.eval.oracle import exact_targets
    e,q=batches(); m=methods(kind)
    assert isinstance(m,MemoryMethod)
    initial=m.init_state(1,device='cpu',dtype='float64'); state=m.encode(e)
    r=m.read(state,q)
    torch.testing.assert_close(r.prediction,exact_targets(e,q).target)
    assert torch.equal(r.support,exact_targets(e,q).supported)
    assert m.persistent_nbytes(state)==m.persistent_nbytes(initial)
    assert m.persistent_nbytes(state)==sum(t.numel()*t.element_size() for t in (*state.payload.values(),state.last_time,state.valid,state.event_offset))+40
    assert m.parameter_nbytes()==0
    saved={k:v.clone() for k,v in state.payload.items()}
    e.values.fill_(99.)
    torch.testing.assert_close(methods(kind).read(state,q).prediction,r.prediction)
    advanced=m.advance_copy(state,3)
    assert advanced.last_time.item()==3 and state.last_time.item()==2
    for k,v in saved.items(): assert torch.equal(v,state.payload[k])
    with pytest.raises(ValueError,match='hash'): methods(kind,capacity=7).read(state,q)
    with pytest.raises(ValueError,match='history'): m.read(state,replace(q,history_ids=('other',)))


@pytest.mark.parametrize('kind',['reservoir','buckets','hybrid'])
def test_adapter_resumes_from_only_snapshot_with_equal_counters_and_draws(kind):
    e,q=batches(); m=methods(kind,capacity=2)
    fields=('event_ids','timestamps','key_ids','key_features','values','present','observed')
    first=replace(e,**{k:getattr(e,k)[:,:2] for k in fields},lengths=torch.tensor([2]))
    last=replace(e,**{k:getattr(e,k)[:,2:] for k in fields},lengths=torch.tensor([2]))
    interrupted=m.encode(first); saved={k:v.clone() for k,v in interrupted.payload.items()}
    full=m.encode(e); resumed=methods(kind,capacity=2).encode(last,interrupted)
    for k,v in full.payload.items(): assert torch.equal(v,resumed.payload[k]),k
    for k,v in saved.items(): assert torch.equal(v,interrupted.payload[k]),k
    assert full.event_offset.item()==resumed.event_offset.item()==4
    torch.testing.assert_close(m.read(full,q).prediction,m.read(resumed,q).prediction,equal_nan=True)


@pytest.mark.parametrize('kind',['reservoir','buckets','hybrid'])
def test_fp32_retained_values_actual_bytes_and_mixed_time_identity(kind):
    e,q=batches(); small=methods(kind,value_dtype='float32',accumulation_dtype='float32')
    large=methods(kind)
    a,b=small.encode(e),large.encode(e)
    assert small.persistent_nbytes(a)<large.persistent_nbytes(b)
    torch.testing.assert_close(small.read(a,q).prediction,large.read(b,q).prediction)
    with pytest.raises(ValueError,match='hash'): large.read(a,q)
    from famjet.memory.reservoir import Reservoir,HybridStore
    from famjet.memory.buckets import TemporalBuckets
    s={'reservoir':lambda:Reservoir(4,1,7,value_dtype='float32'),
       'buckets':lambda:TemporalBuckets(4,1,value_dtype='float32'),
       'hybrid':lambda:HybridStore(2,4,1,7,value_dtype='float32')}[kind]()
    for i,t in enumerate([2**60-2,2**60-1,2**60]): s.update(event(t,0.1*(i+1),eid=i))
    r=s.query(query(T=float(2**60),end=1))
    assert r.prediction.item()==float(np.float32(0.3))


def test_bucket_sum_precision_is_separate_from_input_rounding():
    from famjet.memory.buckets import TemporalBuckets
    s=TemporalBuckets(1,1,value_dtype='float32',accumulation_dtype='float64')
    for t,v in enumerate([2**24,1.,-2**24]): s.update(event(t,v))
    assert s.arrays()['values'].dtype==np.float64
    assert s.query(query(T=2,end=3)).prediction.item()==1/3


@pytest.mark.parametrize('kind',['reservoir','buckets','hybrid'])
def test_invalid_values_reject_before_state_mutation_and_capacity_never_grows(kind):
    from famjet.memory.reservoir import Reservoir,HybridStore
    from famjet.memory.buckets import TemporalBuckets
    s={'reservoir':lambda:Reservoir(2,1,7,value_dtype='float32'),
       'buckets':lambda:TemporalBuckets(2,1,value_dtype='float32'),
       'hybrid':lambda:HybridStore(2,2,1,7,value_dtype='float32')}[kind]()
    s.update(event(0,2.)); before=s.arrays()
    with pytest.raises(ValueError,match='representable'): s.update(event(1,1e100))
    for k,v in before.items(): np.testing.assert_array_equal(v,s.arrays()[k])
    for i in range(1,25): s.update(event(i,float(i)))
    for k,v in before.items(): assert v.shape==s.arrays()[k].shape,k


def test_hybrid_weights_uniform_old_sample_without_overweighting_recent():
    from famjet.memory.reservoir import HybridStore
    s=HybridStore(2,1,1,7)
    for t,v in enumerate([0.,0.,2.,10.,20.]): s.update(event(t,v))
    # Seed7 retains old ordinal3/value2. Its inclusion probability is1/5;
    # recent ordinals4,5 have certainty weights1. Ratio=(5*2+10+20)/(5+1+1).
    r=s.query(query(T=4,end=5))
    assert r.prediction.item()==40/7
    assert r.diagnostics['observed_counts'][0,0,0,0].item()==7.
    assert not r.diagnostics['evidence_complete'].item()
    a=s.arrays()
    assert a['recent_write_ordinals'][a['recent_occupied']].tolist()==[5,4]
    assert a['reservoir_write_ordinals'][a['reservoir_occupied']].tolist()==[3]


def test_bucket_sum_overflow_remains_a_failure_across_snapshot_restart():
    from famjet.memory.buckets import TemporalBucketsMemory
    e,q=batches(); e.values.fill_(3e38)
    m=TemporalBucketsMemory(1,2,key_dim=1,value_dtype='float32',accumulation_dtype='float32')
    state=m.encode(e)
    assert torch.isfinite(state.payload['values']).all() and state.payload['sum_failed'].all()
    r=m.read(state,replace(q,age_end=torch.full_like(q.age_end,3.)))
    assert r.failure[0,0] and not r.diagnostics['prediction_valid'][0,0]
    assert torch.isnan(r.prediction[0,0]).all()
    torch.testing.assert_close(TemporalBucketsMemory(1,2,key_dim=1,value_dtype='float32',accumulation_dtype='float32').read(state,q).failure,m.read(state,q).failure)


def test_bucket_narrow_sum_overflow_cannot_return_fabricated_zero_latest():
    from famjet.memory.buckets import TemporalBuckets
    s=TemporalBuckets(1,1,value_dtype='float64',accumulation_dtype='float32')
    with np.errstate(over='raise'):
        s.update(event(0,1e100))
    r=s.query(query(T=0,task='latest'))
    assert r.failure.item() and not r.diagnostics['prediction_valid'].item()
    assert torch.isnan(r.prediction).all()


@pytest.mark.parametrize('kind',['reservoir','buckets','hybrid'])
@pytest.mark.parametrize('field',['algorithm','counter','layout'])
def test_malformed_restart_metadata_rejects_before_any_query(kind,field):
    e,q=batches(); m=methods(kind,capacity=2); state=m.encode(e)
    payload={k:v.clone() for k,v in state.payload.items()}
    if field=='algorithm':
        payload['algorithm_version'].fill_(99)
    elif field=='counter':
        name={'reservoir':'rng_counter','buckets':'counts','hybrid':'recent_write_ordinals'}[kind]
        payload[name].zero_()
    else:
        name='recent_values' if kind=='hybrid' else 'values'
        payload[name]=payload[name].float()
    with pytest.raises(ValueError): m.read(replace(state,payload=payload),q)


@pytest.mark.parametrize('kind',['reservoir','buckets','hybrid'])
def test_adapter_independent_coordinate_masks_and_usable_binary_zero(kind):
    from famjet.eval.oracle import exact_targets
    e,q=batches(); e.normalization='independent'; e.observed[0,2:,1]=False
    m=methods(kind); r=m.read(m.encode(e),q)
    torch.testing.assert_close(r.prediction,exact_targets(e,q).target,equal_nan=True)
    q=replace(q,tasks=(('presence',)*4,),key_ids=torch.zeros_like(q.key_ids))
    missing=m.read(m.encode(e),q)
    assert not missing.support.any() and missing.diagnostics['prediction_valid'].all()
    assert not missing.prediction.any()


def test_hybrid_tied_time_ring_cutoff_does_not_claim_completeness():
    from famjet.memory.reservoir import HybridStore
    s=HybridStore(1,1,1,7)
    for i,v in enumerate([1.,3.,9.]): s.update(event(2,v,eid=i))
    r=s.query(query(T=2,end=1))
    assert r.prediction.item()==9. and r.diagnostics['overlap_count'].item()==1
    assert not r.diagnostics['evidence_complete'].item() and r.diagnostics['sampling_uncertainty'].item()


def test_bucket_feature_inventory_is_owned_and_matches_snapshot_arithmetic_state():
    e,q=batches(); m=methods('buckets',capacity=2); state=m.encode(e)
    features=m.bucket_arrays(state)
    for name,array in features[0].items(): np.testing.assert_array_equal(array,state.payload[name][0].numpy())
    features[0]['values'].fill(999.)
    assert not torch.any(state.payload['values']==999.)


@pytest.mark.parametrize('kind',['reservoir','buckets','hybrid'])
def test_advanced_state_can_resume_and_padded_queries_remain_invalid(kind):
    e,q=batches(); m=methods(kind); state=m.encode(e); advanced=m.advance_copy(state,3)
    e.timestamps+=4; e.event_ids+=4
    resumed=m.encode(e,advanced)
    assert resumed.event_offset.item()==8
    assert resumed.last_time.item()==6
    padded=replace(q,T=q.T+4,present=torch.zeros_like(q.present),lengths=torch.tensor([0]))
    result=m.read(resumed,padded)
    assert not result.support.any() and not result.diagnostics['prediction_valid'].any()


def test_hybrid_duplicate_ordinals_must_refer_to_identical_events():
    e,q=batches(); m=methods('hybrid'); state=m.encode(e)
    payload={k:v.clone() for k,v in state.payload.items()}; payload['reservoir_values'][0,0,0]=999.
    with pytest.raises(ValueError,match='overlap'): m.read(replace(state,payload=payload),q)


def test_mean_partial_overlap_diagnostic_ignores_unused_contrast_interval():
    from famjet.memory.buckets import TemporalBuckets
    s=TemporalBuckets(2,1)
    for t,v in [(0,2.),(4,6.),(10,20.)]: s.update(event(t,v))
    # Recent[0,4) contains only point10. Older[4,8) clips span[0,4].
    r=s.query(query(T=10,end=4))
    assert r.prediction.item()==20. and not r.diagnostics['partial_overlap'].item()


@pytest.mark.parametrize('kind',['reservoir','buckets','hybrid'])
def test_categorical_full_capacity_control_and_empty_category(kind):
    from famjet.memory.reservoir import ReservoirMemory,HybridMemory
    from famjet.memory.buckets import TemporalBucketsMemory
    e,q=batches(); e.values=torch.eye(32,dtype=torch.float64)[torch.tensor([[0,1,2,3]])]
    e.observed=torch.ones_like(e.values,dtype=torch.bool)
    q=replace(q,tasks=(('random_binding',)*4,))
    m={'reservoir':lambda:ReservoirMemory(8,32,7,key_dim=1),
       'buckets':lambda:TemporalBucketsMemory(8,32,key_dim=1),
       'hybrid':lambda:HybridMemory(2,8,32,7,key_dim=1)}[kind]()
    state=m.encode(e); r=m.read(state,q)
    assert r.prediction is None and r.diagnostics['category_index'].tolist()==[[3]*4]
    assert r.logits.argmax(-1).tolist()==[[3]*4]
    missing=m.read(state,replace(q,key_ids=torch.zeros_like(q.key_ids)))
    assert not missing.support.any() and not missing.diagnostics['prediction_valid'].any()


def test_bucket_merged_latest_is_unsupported_instead_of_mean_as_last_value():
    from famjet.memory.buckets import TemporalBuckets
    s=TemporalBuckets(1,1)
    s.update(event(0,2.)); s.update(event(1,6.))
    r=s.query(query(T=1,task='latest'))
    assert not r.support.item() and not r.failure.item() and not r.diagnostics['prediction_valid'].item()
    assert torch.isnan(r.prediction).all()


def test_bucket_overlap_fraction_preserves_mixed_large_age_differences():
    from famjet.memory.buckets import TemporalBuckets
    s=TemporalBuckets(1,1)
    s.update(event(0,2.)); s.update(event(2,6.))
    # Bucket ages [2**60-1,2**60+1], exact half lies below represented float2**60.
    r=s.query(query(T=2**60+1,end=float(2**60)))
    assert r.diagnostics['estimated_count'][0,0,0,0].item()==1.
    assert r.prediction.item()==4. and r.diagnostics['prediction_valid'].item()


@pytest.mark.parametrize('accumulation_dtype',['float32','float64'])
def test_shared_bucket_normalization_packs_one_count_and_matches_independent(accumulation_dtype):
    from famjet.memory.buckets import TemporalBuckets,TemporalBucketsMemory
    shared=TemporalBuckets(2,8,value_dtype='float32',accumulation_dtype=accumulation_dtype,normalization='shared')
    independent=TemporalBuckets(2,8,value_dtype='float32',accumulation_dtype=accumulation_dtype)
    for s in (shared,independent):
        for t,v in [(0,2.),(4,6.),(10,20.)]: s.update(event(t,[v]*8))
        s.update(event(11,[999.]*8,observed=[False]*8))
    a=shared.arrays(); assert a['counts'].shape==(2,1) and a['observed'].shape==(2,1)
    assert 'event_counts' not in a
    for task in ('mean','contrast','change_sign','latest','presence','interval_support'):
        left=shared.query(query(T=11,start=1.,end=9.,task=task))
        right=independent.query(query(T=11,start=1.,end=9.,task=task))
        torch.testing.assert_close(left.prediction,right.prediction,equal_nan=True)
        torch.testing.assert_close(left.diagnostics['observed_counts'],right.diagnostics['observed_counts'])
        assert torch.equal(left.support,right.support)
    s=TemporalBucketsMemory(16,8,key_dim=1,value_dtype='float32',accumulation_dtype=accumulation_dtype,normalization='shared')
    i=TemporalBucketsMemory(16,8,key_dim=1,value_dtype='float32',accumulation_dtype=accumulation_dtype)
    ss=s.init_state(1,device='cpu',dtype='float32'); si=i.init_state(1,device='cpu',dtype='float32')
    assert i.persistent_nbytes(si)-s.persistent_nbytes(ss)==16*(7*8+7+8)
    assert ss.parameter_hash!=si.parameter_hash


def test_shared_bucket_rejects_partial_masks_without_mutating_state():
    from famjet.memory.buckets import TemporalBuckets,TemporalBucketsMemory
    s=TemporalBuckets(2,2,normalization='shared'); s.update(event(0,[2.,7.]))
    before=s.arrays()
    with pytest.raises(ValueError,match='shared'): s.update(event(1,[6.,7.],observed=[True,False]))
    for k,v in before.items(): np.testing.assert_array_equal(v,s.arrays()[k])
    e,q=batches(); m=TemporalBucketsMemory(2,2,key_dim=1,normalization='shared'); state=m.encode(e)
    with pytest.raises(ValueError,match='hash'): TemporalBucketsMemory(2,2,key_dim=1).read(state,q)
    bad=replace(e,timestamps=e.timestamps+4,event_ids=e.event_ids+4,normalization='independent',observed=e.observed.clone())
    bad.observed[0,-1,1]=False
    saved={k:v.clone() for k,v in state.payload.items()}
    with pytest.raises(ValueError,match='shared'): m.encode(bad,state)
    for k,v in saved.items(): assert torch.equal(v,state.payload[k])


def test_shared_bucket_snapshot_restart_and_feature_counts_use_scalar_layout():
    from famjet.memory.buckets import TemporalBucketsMemory
    e,q=batches(); m=TemporalBucketsMemory(2,2,key_dim=1,normalization='shared')
    fields=('event_ids','timestamps','key_ids','key_features','values','present','observed')
    first=replace(e,**{k:getattr(e,k)[:,:2] for k in fields},lengths=torch.tensor([2]))
    last=replace(e,**{k:getattr(e,k)[:,2:] for k in fields},lengths=torch.tensor([2]))
    state=m.encode(first); resumed=TemporalBucketsMemory(2,2,key_dim=1,normalization='shared').encode(last,state)
    full=m.encode(e)
    for k,v in full.payload.items(): assert torch.equal(v,resumed.payload[k]),k
    assert full.payload['counts'].shape==(1,2,1)
    assert m.bucket_arrays(full)[0]['counts'].shape==(2,1)
    torch.testing.assert_close(m.read(full,q).prediction,m.read(resumed,q).prediction,equal_nan=True)
    with pytest.raises(ValueError,match='normalization'): TemporalBucketsMemory(2,2,key_dim=1,normalization='bad')
