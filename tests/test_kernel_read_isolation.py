"""Source component checks, independent of the deferred Stage A campaign."""
from copy import deepcopy
from dataclasses import replace
import importlib.util
import math
import pytest
import torch
from famjet.memory.jet import JetMemory
from famjet.memory.expbank import ExpBankMemory
from famjet.types import EventBatch, QueryBatch
from famjet.provenance import canonical_hash
from famjet.eval.state_io import snapshot_hash, inference_snapshot, tensor_record
from famjet.eval.isolation import export_method, _reconstruct, isolated_read, model_identity


def model(family='jet'):
    assert importlib.util.find_spec('famjet.models.kernel_read_model'), 'kernel wrapper missing'
    from famjet.models.kernel_read_model import KernelReadModel
    rates = torch.logspace(math.log10(1/5224),0,4 if family=='jet' else 8,dtype=torch.float64)[None]
    kernel = (JetMemory if family=='jet' else ExpBankMemory)(rates,16,8,t_ref=1.)
    tasks = {task:dict(status='ok',count=2,mean=[.25 if task=='mean' else -.5]*8,
        scale=1.,class_distribution=None,constant_coordinates=[False]*8,
        coordinate_variance=[1.]*8,pooled_variance=1.) for task in ('mean','contrast')}
    stats = dict(schema_version=2,split='training',variance_ddof=0,
        pooling='queries_within_task_then_coordinate_variances',
        constant_policy='include_in_scale_pool; report_absolute_error_separately; all_constant_scale_null',
        target_semantics='observed_event_targets_v2',tasks=tasks)
    provenance = dict(split='training',history_identity_hash='a'*64,history_count=2,t_ref=1.,
        reference_source='explicit_duration',feature_rows=2,writer_hash=kernel._parameter_hash(),target_hash=canonical_hash(stats))
    return KernelReadModel(kernel,1e-2,provenance,stats)


def inputs():
    e = EventBatch(('analytic',),torch.tensor([[0,1]]),torch.tensor([[-3,0]]),torch.zeros(1,2,dtype=torch.long),
        torch.nn.functional.one_hot(torch.zeros(1,2,dtype=torch.long),16).double(),
        torch.tensor([[[2.]*8,[7.]*8]],dtype=torch.float64),torch.tensor([2]),torch.ones(1,2,dtype=torch.bool),
        torch.ones(1,2,8,dtype=torch.bool),'ticks')
    q = QueryBatch(e.history_ids,torch.tensor([[0,1]]),torch.tensor([[0,2]]),torch.zeros(1,2,dtype=torch.long),
        e.key_features.clone(),(('mean','contrast'),),torch.zeros(1,2,dtype=torch.float64),torch.full((1,2),4.,dtype=torch.float64),
        torch.ones(1,2,dtype=torch.bool),torch.tensor([2]))
    return e,q


@pytest.mark.parametrize('family',['jet','bank'])
def test_read_order_delay_separate_normalization_and_no_mutation(family):
    m=model(family); e,q=inputs(); s=m.encode(e); before=snapshot_hash(s)
    result=m.read(s,q)
    assert not result.failure.any()
    assert torch.isnan(result.support).all()
    assert result.diagnostics['numerical_eligible'].all()
    assert not result.diagnostics['factual_support_available'].any()
    # Independently contract a delayed snapshot and check TWO ratios.
    adv=m.advance_copy(s,2); key=q.key_features[0,1]
    parts=[torch.einsum('k,jkv->jv',key,adv.payload[name][0,0]) for name in m.kernel._state_keys]
    canonical=torch.stack(parts,1).flatten(0,1) if family=='jet' else parts[0]
    ratios=[]
    for a,b in ((0.,4.),(4.,8.)):
        c=m.reader.coefficients(a,b)
        mass=math.fsum((c*canonical[:,-1]).tolist())
        ratios.append(torch.tensor([math.fsum((c*canonical[:,i]).tolist())/(mass+1e-8) for i in range(8)],dtype=torch.float64))
    torch.testing.assert_close(result.prediction[0,1],ratios[0]-ratios[1],atol=1e-12,rtol=1e-12)
    qq=replace(q,query_ids=q.query_ids.flip(1),T=q.T.flip(1),key_ids=q.key_ids.flip(1),key_features=q.key_features.flip(1),
        tasks=(tuple(reversed(q.tasks[0])),),age_start=q.age_start.flip(1),age_end=q.age_end.flip(1))
    torch.testing.assert_close(m.read(s,qq).prediction.flip(1),result.prediction,atol=1e-12,rtol=1e-12)
    assert snapshot_hash(s)==before
    assert m._parameter_hash()==m.kernel._parameter_hash()
    assert m.persistent_nbytes(s)==9345
    assert not list(m.parameters())


def test_empty_absent_and_nonfinite_fallback_preserve_failures():
    m=model(); e,q=inputs(); s=m.init_state(1,device='cpu',dtype='float64')
    out=m.read(s,q)
    assert out.failure.all() and not out.diagnostics['numerical_eligible'].any()
    torch.testing.assert_close(out.prediction[0,0],torch.full((8,),.25,dtype=torch.float64))
    torch.testing.assert_close(out.prediction[0,1],torch.full((8,),-.5,dtype=torch.float64))
    s=m.encode(e); s.payload['z'][0,0,0,0,0]=float('nan'); before=snapshot_hash(s)
    out=m.read(s,q)
    assert out.failure.all() and out.diagnostics['quarantined'].all()
    assert snapshot_hash(s)==before
    assert torch.isfinite(out.prediction).all()
    assert m.read(s,q).diagnostics['quarantined'].all()


@pytest.mark.parametrize('family',['jet','bank'])
def test_byte_exact_static_reconstruction_and_clean_worker(family):
    m=model(family); e,q=inputs(); s=inference_snapshot(m.encode(e)); spec=export_method(m)
    restored=_reconstruct(spec)
    assert export_method(restored)==spec
    assert model_identity(restored)==model_identity(m)
    for name,value in m.state_dict().items():
        assert tensor_record(value)==tensor_record(restored.state_dict()[name])
    direct=m.read(s,q); isolated=isolated_read(m,s,q,timeout=15)
    torch.testing.assert_close(direct.prediction,isolated.prediction,atol=1e-12,rtol=1e-12)
    assert torch.equal(direct.failure,isolated.failure)
    assert torch.isnan(isolated.support).all()


@pytest.mark.parametrize('bad', ['history','array','callable','hook'])
def test_export_rejects_hidden_ownership(bad):
    m=model()
    if bad=='history': m.raw_history={'labels':[1.,2.]}
    elif bad=='array': m.reader.register_buffer('cache',torch.ones(4))
    elif bad=='callable': m.reference=lambda: None
    else: m.reader.register_forward_hook(lambda *a: None)
    with pytest.raises(ValueError): export_method(m)


def test_closed_wire_and_direct_input_validation():
    m=model(); e,q=inputs(); s=m.encode(e)
    spec=export_method(m); spec['schema']['history']=[]
    with pytest.raises(ValueError): _reconstruct(spec)
    for qq in (replace(q,T=q.T-1),replace(q,key_features=q.key_features.float()),replace(q,tasks=(('presence','mean'),)),
               replace(q,history_ids=('other',))):
        with pytest.raises(ValueError): m.read(s,qq)
    ss=replace(s,parameter_hash='b'*64)
    with pytest.raises(ValueError): m.read(ss,q)
    object.__setattr__(q,'labels',torch.ones(1))
    with pytest.raises(ValueError): m.read(s,q)


def test_accounting_includes_python_ownership_and_serialization_separately():
    from famjet.eval.budgets import budget_report
    m=model(); e,q=inputs(); s=inference_snapshot(m.encode(e))
    ledger=m.ownership_ledger()
    assert ledger['python_bytes']>0
    assert ledger['tensor_storage_bytes']==sum(t.untyped_storage().nbytes() for t in m.buffers())
    assert ledger['owned_bytes']==ledger['python_bytes']+ledger['tensor_storage_bytes']
    assert ledger['serialized_bytes']>ledger['tensor_logical_bytes']
    assert ledger['per_query_delay_copy_logical_bytes']==9305
    assert budget_report(m,s,limit_bytes=9345)['eligible']


def test_worker_transport_rejects_extra_query_metadata_before_stripping():
    m=model(); e,q=inputs(); s=inference_snapshot(m.encode(e))
    object.__setattr__(q,'reference_events',e)
    with pytest.raises(ValueError): isolated_read(m,s,q,timeout=15)


def test_empty_query_batch_and_units_are_read_only():
    m=model(); e,q=inputs(); s=m.encode(e); before=snapshot_hash(s)
    empty=replace(q,query_ids=q.query_ids[:,:0],T=q.T[:,:0],key_ids=q.key_ids[:,:0],key_features=q.key_features[:,:0],
                  tasks=((),),age_start=q.age_start[:,:0],age_end=q.age_end[:,:0],present=q.present[:,:0],lengths=torch.tensor([0]))
    assert m.read(s,empty).prediction.shape==(1,0,8)
    n=model(); n.kernel.rates.div_(8); n.kernel.t_ref*=8
    from famjet.models.kernel_read_model import KernelReadModel
    provenance=deepcopy(n.fit_provenance); provenance['t_ref']=8.; provenance['writer_hash']=n.kernel._parameter_hash()
    n=KernelReadModel(n.kernel,1e-2,provenance,n.target_statistics,prior_scale=5224.*8)
    ee=replace(e,timestamps=e.timestamps*8,time_unit='eighth_ticks')
    qq=replace(q,T=q.T*8,age_start=q.age_start*8,age_end=q.age_end*8)
    torch.testing.assert_close(m.read(s,q).prediction,n.read(n.encode(ee),qq).prediction,atol=1e-12,rtol=1e-12)
    assert snapshot_hash(s)==before


def test_wire_binds_numerical_policy():
    spec=export_method(model())
    config=spec['schema']['reader']['config']
    assert config['epsilon']==1e-8 and config['mass_floor']==1e-8
    assert config['cancellation']==64*2**-53
    altered=deepcopy(spec); altered['schema']['reader']['config']['mass_floor']=0.
    with pytest.raises(ValueError): _reconstruct(altered)
