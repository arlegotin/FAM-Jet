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
