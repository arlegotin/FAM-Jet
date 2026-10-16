"""Numeric-only, identity-checked snapshots and crash-safe replacement."""
from dataclasses import replace
import json
import pytest
import torch
from famjet.memory.exact_store import PackedHistoryMemory
from famjet.memory.jet import JetMemory
from test_exact_store import batches


def test_roundtrip_uint64_owned_storage_and_previous(tmp_path):
    from famjet.eval.state_io import save_state,load_state,snapshot_hash
    method=PackedHistoryMemory(4,2,'recent',key_dim=1)
    events,_=batches(); state=method.encode(events); path=tmp_path/'state.json'
    save_state(path,state)
    loaded=load_state(path,state.parameter_hash)
    assert snapshot_hash(loaded)==snapshot_hash(state)
    assert loaded.payload['key_ids'].tolist()==[[2**64-1]*4]
    newer=method.advance_copy(state,9)
    save_state(path,newer)
    assert snapshot_hash(load_state(path.with_suffix('.json.previous'),state.parameter_hash))==snapshot_hash(state)
    loaded.payload['values'].zero_()
    assert state.payload['values'].sum()>0
    assert load_state(path,state.parameter_hash).last_time.item()==9


def test_checksum_and_schema_rejected(tmp_path):
    from famjet.eval.state_io import save_state,load_state
    from famjet.provenance import canonical_hash
    m=JetMemory(torch.ones(1,1),1,1); s=m.init_state(1,device='cpu',dtype='float32')
    p=tmp_path/'state.json'; save_state(p,s); original=p.read_text()
    obj=json.loads(original); obj['body']['schema_version']=999; p.write_text(json.dumps(obj))
    with pytest.raises(ValueError,match='checksum'): load_state(p,s.parameter_hash)
    obj['checksum']=canonical_hash(obj['body']); p.write_text(json.dumps(obj))
    with pytest.raises(ValueError,match='schema'): load_state(p,s.parameter_hash)
    p.write_text(original)
    with pytest.raises(ValueError,match='parameter'): load_state(p,'a'*64)


def test_failed_replace_keeps_last_good(tmp_path,monkeypatch):
    from famjet.eval import state_io
    m=JetMemory(torch.ones(1,1),1,1); s=m.init_state(1,device='cpu',dtype='float32')
    p=tmp_path/'state.json'; state_io.save_state(p,s); original=p.read_bytes()
    real_replace=state_io.os.replace
    def fail_primary(src,dst):
        if dst==p: raise OSError('interrupted replacement')
        return real_replace(src,dst)
    monkeypatch.setattr(state_io.os,'replace',fail_primary)
    with pytest.raises(OSError): state_io.save_state(p,s)
    assert p.read_bytes()==original
    assert p.with_suffix('.json.previous').read_bytes()==original
    assert not list(tmp_path.glob('*.tmp'))


def test_corrupt_primary_cannot_destroy_previous(tmp_path):
    from famjet.eval.state_io import save_state,load_state,snapshot_hash
    m=JetMemory(torch.ones(1,1),1,1); s=m.init_state(1,device='cpu',dtype='float32')
    p=tmp_path/'state.json'; save_state(p,s); save_state(p,s)
    p.write_text('truncated')
    with pytest.raises(ValueError): save_state(p,s)
    assert snapshot_hash(load_state(p.with_suffix('.json.previous'),s.parameter_hash))==snapshot_hash(s)


def test_alias_roundtrip_packs_values_not_oversized_allocation(tmp_path):
    from famjet.eval.state_io import save_state,load_state
    m=JetMemory(torch.ones(1,1),1,1); s=m.init_state(1,device='cpu',dtype='float32')
    a=torch.arange(100,dtype=torch.float32)
    s=replace(s,payload={**s.payload,'z':a[::10],'h':a[::10]})
    p=tmp_path/'state.json'; save_state(p,s); loaded=load_state(p,s.parameter_hash)
    assert torch.equal(loaded.payload['z'],a[::10])
    assert loaded.payload['z'].untyped_storage().nbytes()==40
    loaded.payload['z'].zero_()
    assert loaded.payload['h'].sum().item()==450


def test_malformed_metadata_rejected_before_io(tmp_path):
    from famjet.eval.state_io import save_state
    m=JetMemory(torch.ones(1,1),1,1); s=m.init_state(1,device='cpu',dtype='float32')
    with pytest.raises(ValueError,match='event_offset'):
        save_state(tmp_path/'state.json',replace(s,event_offset=torch.tensor([-1])))
