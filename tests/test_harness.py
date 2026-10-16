import numpy as np
import pytest


def test_deterministic_controls_and_unexecuted_training_gate():
    from famjet.eval.controls import run_controls
    from famjet.config import load_config
    from pathlib import Path
    r=run_controls(load_config(Path('configs/smoke.yaml')))
    assert r['aa']['effect']==0 and r['aa_swapped']['effect']==0
    assert r['exact_vs_ring']['effect']>0
    assert r['wrong_moment_sign']['status']=='detected'
    assert r['reversed_temporal_labels']['status']=='detected'
    assert r['leaked_writer']['status']=='rejected'
    assert r['independent_retraining']['status']=='pending_task18'


def test_mid_episode_state_quarantine_retains_all_queries_and_trigger(monkeypatch):
    import torch
    from famjet.train import make_model,move_episode,_prediction_records
    from famjet.data.synthetic import generate_episode
    from test_training import tiny
    c=tiny(); model=make_model(c)
    fit=[move_episode(generate_episode(c,c.seed,x),'cpu') for x in ['fit','fit2']]; model.fit_statistics(fit)
    ep=move_episode(generate_episode(c,c.seed,'read'),'cpu')
    encode=model.encode; calls=[]; byte_counts=[]
    def injected(events,state=None,*,mode='stream'):
        result=encode(events,state,mode=mode); calls.append(mode)
        byte_counts.append(model.persistent_nbytes(result))
        if len(calls)==3:
            next(v for v in result.payload.values() if v.is_floating_point() and v.ndim>1).fill_(float('nan'))
        return result
    monkeypatch.setattr(model,'encode',injected)
    rows=list(_prediction_records(model,ep,'run','development_fit'))
    assert len(rows)==2 and all(r['eligible'] and r['fallback'] and r['quarantined'] for r in rows)
    assert all(r['loss'] is not None for r in rows)
    assert rows[0]['quarantine_trigger']['event_offset']==3
    assert rows[0]['quarantine_trigger']['input']['event_id']==2
    assert calls==['stream']*3
    assert rows[0]['payload_bytes']==byte_counts[2]
    assert rows[0]['evaluation_boundary']=='causal_stream_with_host_state_inspection'


def test_adversarial_load_and_span_are_independent_and_reads_are_immutable():
    from famjet.eval.controls import adversarial_events
    from famjet.memory.exact_store import PackedHistoryMemory
    from famjet.types import QueryBatch
    from famjet.eval.state_io import snapshot_hash
    import torch
    for load,span in [(2,10.),(8,10.),(2,1e6)]:
        e=adversarial_events(load=load,span=span)
        assert len(set(e.key_ids[0].tolist()))==load and float(e.timestamps.max())==span
        m=PackedHistoryMemory(None,1,'exact',key_dim=1); state=m.encode(e); before=snapshot_hash(state)
        q=QueryBatch(e.history_ids,torch.tensor([[0,1]]),torch.full((1,2),span,dtype=torch.float64),torch.tensor([[0,load-1]]),
                     torch.ones(1,2,1),(('mean','mean'),),torch.zeros(1,2,dtype=torch.float64),torch.full((1,2),span+1,dtype=torch.float64),torch.ones(1,2,dtype=torch.bool),torch.tensor([2]))
        assert m.read(state,q).prediction[0,0,0]==pytest.approx(2/3)
        assert snapshot_hash(state)==before


def test_new_training_rejects_legacy_targets_before_optimization(tmp_path):
    from dataclasses import replace
    from famjet.train import train_model
    from test_training import tiny
    c=tiny(); c=replace(c,data=replace(c.data,generator_version='initial_spec_v1'))
    with pytest.raises(ValueError,match='legacy target'): train_model(c,tmp_path/'legacy')
