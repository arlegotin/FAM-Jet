"""Retained bytes count storage, identity, counters and graph retention honestly."""
from dataclasses import replace
import pytest
import torch
from famjet.memory.jet import JetMemory
from famjet.memory.expbank import ExpBankMemory
from famjet.memory.exact_store import PackedHistoryMemory
from test_exact_store import batches


def test_equal_payload_total_metadata():
    from famjet.eval.budgets import state_ledger
    ledgers=[]
    for method in (JetMemory(torch.ones(1,4),16,8), ExpBankMemory(torch.ones(1,8),16,8)):
        s=method.init_state(1,device='cpu',dtype='float32')
        ledger=state_ledger(s); ledgers.append(ledger)
        assert ledger['payload_bytes']==4608
        assert ledger['metadata_bytes']==129
        assert ledger['logical_bytes']==4737==method.persistent_nbytes(s)
        assert ledger['retained_storage_bytes']==4697
        assert ledger['serialized_bytes']>ledger['logical_bytes']
    assert ledgers[0]['metadata']==ledgers[1]['metadata']


def test_noncontiguous_tensor_bytes():
    from famjet.eval.budgets import state_ledger
    m=JetMemory(torch.ones(1,1),1,1)
    s=m.init_state(1,device='cpu',dtype='float32')
    backing=torch.arange(100,dtype=torch.float32)
    s=replace(s,payload={**s.payload,'z':backing[::10], 'h':backing[1::10]})
    ledger=state_ledger(s)
    assert ledger['payload_bytes']==80
    assert ledger['retained_storage_bytes']==489  # one 400-byte storage + 89 metadata
    assert ledger['fields']['payload.z']['storage_id']==ledger['fields']['payload.h']['storage_id']
    assert ledger['fields']['payload.z']['contiguous'] is False


def test_exact_is_unbounded_even_below_limit_and_counts_padded_capacity():
    from famjet.eval.budgets import budget_report
    events,_=batches()
    method=PackedHistoryMemory(None,2,'exact',key_dim=1)
    s=method.encode(events)
    report=budget_report(method,s,limit_bytes=4608)
    assert report['bounded'] is False and report['eligible'] is False
    assert report['state']['logical_bytes']==method.persistent_nbytes(s)
    assert budget_report(method,s,limit_bytes=1)['within_limit'] is False


def test_model_buffers_and_shared_parameters_counted_separately():
    from famjet.eval.budgets import model_ledger
    model=torch.nn.Module()
    p=torch.nn.Parameter(torch.ones(12,dtype=torch.float64))
    model.register_parameter('weight',p); model.register_parameter('tied',p)
    model.register_buffer('view',p.detach()[::2])
    ledger=model_ledger(model)
    assert ledger['parameter_bytes']==96 and ledger['buffer_bytes']==48
    assert ledger['retained_storage_bytes']==96
    assert ledger['logical_bytes']==144
    model.hidden={'history':torch.ones(100)}
    with pytest.raises(ValueError,match='unregistered|hidden'):
        model_ledger(model)


def test_training_graph_is_reported_and_inference_snapshot_owns_storage():
    from famjet.eval.budgets import state_ledger, require_inference_state
    from famjet.eval.state_io import inference_snapshot
    rates=torch.ones(1,1,requires_grad=True)
    method=JetMemory(rates,1,1)
    s=method.init_state(1,device='cpu',dtype='float32')
    huge=torch.ones(1000,requires_grad=True)
    s=replace(s,payload={**s.payload,'z':(huge*2).sum().reshape(1,1,1,1,1).expand(1,1,1,1,2)})
    assert state_ledger(s)['graph_retention'] is True
    with pytest.raises(ValueError,match='graph'):
        require_inference_state(s)
    clean=inference_snapshot(s)
    assert state_ledger(clean)['graph_retention'] is False
    assert clean.payload['z'].untyped_storage().nbytes()==8
    clean.payload['z'].zero_()
    assert s.payload['z'].sum().item()==4000


def test_static_graph_cannot_be_declared_bounded_inference():
    from famjet.eval.budgets import budget_report
    rates=torch.ones(1,2,requires_grad=True)
    method=JetMemory(rates*2,1,1)
    state=method.init_state(1,device='cpu',dtype='float32')
    report=budget_report(method,state,limit_bytes=10000)
    assert report['static']['graph_retention'] is True
    assert report['eligible'] is False


def test_tensor_attached_cache_is_rejected():
    from famjet.eval.budgets import state_ledger
    method=JetMemory(torch.ones(1,1),1,1)
    state=method.init_state(1,device='cpu',dtype='float32')
    state.payload['z'].hidden_history=torch.ones(100)
    with pytest.raises(ValueError,match='attribute|hidden'):
        state_ledger(state)


def test_external_numpy_view_cannot_hide_owner_allocation():
    import numpy as np
    from famjet.eval.budgets import state_ledger,budget_report
    method=JetMemory(torch.ones(1,1),1,1)
    state=method.init_state(1,device='cpu',dtype='float32')
    owner=np.zeros(10000,np.float32)
    state=replace(state,payload={**state.payload,'z':torch.from_numpy(owner[:2]).reshape(1,1,1,1,2)})
    ledger=state_ledger(state)
    assert ledger['backing_storage_complete'] is False
    assert budget_report(method,state,limit_bytes=1000)['eligible'] is False


def test_packed_and_restored_snapshots_have_accountable_owned_storage(tmp_path):
    from famjet.eval.budgets import state_ledger
    from famjet.eval.state_io import save_state,load_state
    method=PackedHistoryMemory(4,2,'recent',key_dim=1)
    state=method.encode(batches()[0]); path=tmp_path/'state.json'
    assert state_ledger(state)['backing_storage_complete'] is True
    save_state(path,state)
    assert state_ledger(load_state(path,state.parameter_hash))['backing_storage_complete'] is True


def test_leaf_snapshot_gradient_is_training_retention():
    from famjet.eval.budgets import state_ledger,require_inference_state
    m=JetMemory(torch.ones(1,1),1,1); s=m.init_state(1,device='cpu',dtype='float32')
    s.payload['z'].requires_grad_(); s.payload['z'].sum().backward()
    assert s.payload['z'].grad is not None
    assert state_ledger(s)['graph_retention'] is True
    with pytest.raises(ValueError,match='graph'):
        require_inference_state(s)


@pytest.mark.parametrize('device',['cpu','mps'])
def test_native_owned_storage_is_accountable(device):
    from famjet.eval.budgets import state_ledger
    if device=='mps' and not torch.backends.mps.is_available(): pytest.skip('native MPS unavailable')
    method=JetMemory(torch.ones(1,1,device=device),1,1)
    state=method.init_state(1,device=device,dtype='float32')
    ledger=state_ledger(state)
    assert ledger['backing_storage_complete'] is True
    assert ledger['retained_storage_bytes']==105


def test_leaf_static_parameters_are_eligible_for_inference():
    from famjet.eval.budgets import model_ledger
    model=torch.nn.Linear(2,3)
    assert all(p.requires_grad and p.grad_fn is None for p in model.parameters())
    assert model_ledger(model)['graph_retention'] is False


@pytest.mark.parametrize('kind',['packed','jet','bank'])
def test_budget_and_export_are_observational_and_repeatable(kind,tmp_path):
    from famjet.eval.budgets import budget_report,state_ledger
    from famjet.eval.state_io import snapshot_hash,save_state
    from famjet.eval.isolation import export_method,isolated_read,isolated_features
    method={'packed':lambda:PackedHistoryMemory(4,2,'recent',key_dim=1),
            'jet':lambda:JetMemory(torch.ones(1,2,dtype=torch.float64),1,2),
            'bank':lambda:ExpBankMemory(torch.ones(1,2,dtype=torch.float64),1,2)}[kind]()
    events,queries=batches()
    events=replace(events,key_features=events.key_features.double())
    queries=replace(queries,key_features=queries.key_features.double())
    state=method.encode(events)
    all_tensors=[*state.payload.values(),state.last_time,state.valid,state.event_offset]
    if kind!='packed': all_tensors.append(method.rates)
    assert all(t.untyped_storage().resizable() for t in all_tensors)
    original=snapshot_hash(state)
    for operation in (lambda:state_ledger(state),lambda:budget_report(method,state,limit_bytes=10000),
                      lambda:save_state(tmp_path/'state.json',state),lambda:export_method(method),
                      lambda:(isolated_read if kind=='packed' else isolated_features)(method,state,queries)):
        operation()
        assert snapshot_hash(state)==original
        assert all(t.untyped_storage().resizable() for t in all_tensors)
        assert budget_report(method,state,limit_bytes=10000)['eligible'] is True
    assert budget_report(method,state,limit_bytes=10000)==budget_report(method,state,limit_bytes=10000)


def test_retained_base_hidden_history_is_rejected_by_ledger_and_export():
    from famjet.eval.budgets import state_ledger,budget_report
    from famjet.eval.state_io import snapshot_hash
    from famjet.eval.isolation import export_method
    method=PackedHistoryMemory(4,2,'recent',key_dim=1)
    state=method.init_state(1,device='cpu',dtype='float64')
    base=torch.zeros(8,dtype=torch.float64)
    base.hidden_history=torch.ones(10000)
    state=replace(state,payload={**state.payload,'values':base.reshape(1,4,2)})
    for operation in (lambda:state_ledger(state),lambda:budget_report(method,state,limit_bytes=10000),lambda:snapshot_hash(state)):
        with pytest.raises(ValueError,match='hidden|attribute'): operation()
    rates=torch.ones(2)
    rates.hidden_history=torch.ones(10000)
    kernel=JetMemory(torch.ones(1,2),1,1)
    kernel.rates=rates.reshape(1,2)
    with pytest.raises(ValueError,match='hidden|attribute'): export_method(kernel)


def test_retained_base_gradient_is_reported_and_owned_aliases_deduplicate():
    from famjet.eval.budgets import state_ledger,budget_report
    from famjet.eval.state_io import inference_snapshot
    method=JetMemory(torch.ones(1,1),1,1)
    state=method.init_state(1,device='cpu',dtype='float32')
    base=torch.ones(2,requires_grad=True); base.sum().backward()
    with torch.no_grad(): view=base.reshape(1,1,1,1,2)
    assert view.grad_fn is None and view._base is base
    state=replace(state,payload={**state.payload,'z':view,'h':view})
    ledger=state_ledger(state)
    assert ledger['graph_retention'] is True
    assert budget_report(method,state,limit_bytes=10000)['eligible'] is False
    clean=inference_snapshot(state)
    assert state_ledger(clean)['graph_retention'] is False
    base.grad=None
    assert budget_report(method,state,limit_bytes=10000)['eligible'] is True
    assert state_ledger(state)['retained_storage_bytes']==97  # one 8-byte shared allocation +89 metadata


def test_model_dynamic_dict_keys_and_cycles_are_audited():
    from famjet.eval.budgets import model_ledger
    model=torch.nn.Linear(1,1)
    model.cache={torch.ones(10000):None}
    with pytest.raises(ValueError,match='hidden|unregistered'): model_ledger(model)
    model.cache={}; model.cache['cycle']=model.cache
    assert model_ledger(model)['logical_bytes']==8
    model.cache['cycle']['payload']=torch.ones(10000)
    with pytest.raises(ValueError,match='hidden|unregistered'): model_ledger(model)


def test_packed_encode_does_not_change_event_storage_ownership():
    method=PackedHistoryMemory(4,2,'recent',key_dim=1)
    events,_=batches()
    method.encode(events)
    assert events.values.untyped_storage().resizable()
    assert events.observed.untyped_storage().resizable()


def test_registry_rejects_cyclic_extra_state_without_recursion_error():
    from famjet.eval.isolation import export_method
    method=JetMemory(torch.ones(1,1),1,1)
    method.cache={}; method.cache['self']=method.cache
    with pytest.raises(ValueError,match='hidden|unregistered'): export_method(method)
