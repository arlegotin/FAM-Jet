"""Causal evaluation and quarantine; audit state lives outside bounded methods."""
from dataclasses import replace
import time
import torch
from famjet.types import PredictionBatch
from famjet.eval.metrics import score_predictions,TARGET_SEMANTICS
from famjet.eval.oracle import BINARY_TASKS,CATEGORICAL_TASKS
from famjet.data.synthetic import batch_hash
from famjet.provenance import canonical_hash


def episode_policy(episodes):
    inventory=[]; tasks=set(); regimes=set()
    for ep in episodes:
        for b,h in enumerate(ep.queries.history_ids):
            cell={}
            for j,t in enumerate(ep.queries.tasks[b]):
                if ep.queries.present[b,j]: cell.setdefault(t,[]).append(int(ep.queries.query_ids[b,j]))
            inventory.append({'history_id':h,'replicate':0,'regime':ep.metadata['regime'],'tasks':cell})
            tasks.update(cell); regimes.add(ep.metadata['regime'])
    if not tasks: raise ValueError('missing query inventory')
    primary=sorted(tasks & {'mean','contrast'}) if all(ep.metadata.get('population','primary')=='primary' for ep in episodes) else []
    return {'version':2,'primary_tasks':primary,'support_calibration':None,'expected_inventory':inventory,
            'task_weights':{t:1/len(tasks) for t in sorted(tasks)},'regime_weights':{r:1/len(regimes) for r in sorted(regimes)}}


def score_episode(model,ep,*,method,policy=None,manifest_hash=None,replicate=0):
    """Stream each history once, inspect every saved field after each event.

    All queries are deferred until after the recorded history. Host inspections
    synchronize devices and are evaluation overhead, not asynchronous kernel time.
    Contract/infrastructure exceptions propagate. Nonfinite state is quarantined
    before any further encode/read; finite unsupported reads only affect a query.
    """
    if ep.metadata.get('target_semantics')!=TARGET_SEMANTICS: raise ValueError('legacy target semantics cannot be scored')
    from famjet.data.schema import validate_events,validate_queries
    validate_events(ep.events); validate_queries(ep.queries)
    policy=episode_policy([ep]) if policy is None else policy
    stats=model.target_statistics
    if stats is None: raise ValueError('frozen training statistics required')
    rows=[]
    for b,h in enumerate(ep.events.history_ids):
        e=ep.events; q=ep.queries
        events=replace(e,history_ids=(h,),**{k:getattr(e,k)[b:b+1] for k in ('event_ids','timestamps','key_ids','key_features','values','lengths','present','observed')},auxiliary={k:v[b:b+1] for k,v in e.auxiliary.items()})
        queries=replace(q,history_ids=(h,),tasks=(q.tasks[b],),**{k:getattr(q,k)[b:b+1] for k in ('query_ids','T','key_ids','key_features','age_start','age_end','present','lengths')})
        if queries.present.any() and int(events.lengths[0]) and bool((queries.T[queries.present.cpu()]<events.timestamps[0,int(events.lengths[0])-1]).any()):
            raise ValueError('evaluation requires deferred queries at/after entire history')
        state=None; trigger=None; inspection_seconds=0.; started=time.perf_counter()
        with torch.no_grad():
            for i in range(int(events.lengths[0])):
                event=replace(events,**{k:getattr(events,k)[:,i:i+1] for k in ('event_ids','timestamps','key_ids','key_features','values','present','observed')},lengths=torch.ones_like(events.lengths),auxiliary={k:v[:,i:i+1] for k,v in events.auxiliary.items()})
                state=model.encode(event,state,mode='stream')
                inspected=time.perf_counter()
                fields={**state.payload,'last_time':state.last_time}
                bad=[name for name,v in fields.items() if v.is_floating_point() and not bool(torch.isfinite(v).all())]
                inspection_seconds+=time.perf_counter()-inspected
                if bad:
                    trigger={'reason':'nonfinite_stored_state','fields':bad,'event_offset':i+1,
                             'parameter_hash':state.parameter_hash,'input_hash':batch_hash(event),
                             'state_hash':batch_hash(state),
                             'input':{'event_id':int(events.event_ids[0,i]),'timestamp':events.timestamps[0,i].item(),
                                      'key_id':int(events.key_ids[0,i]),'values':events.values[0,i].cpu().tolist(),
                                      'observed':events.observed[0,i].cpu().tolist(),'key_features':events.key_features[0,i].cpu().tolist(),
                                      'auxiliary':{k:v[0,i].cpu().tolist() for k,v in events.auxiliary.items()}},'history_id':h}
                    break
            if state is None:
                state=model.encode(events,mode='stream')
            if trigger is None:
                result=model.read(state,queries)
                payload_bytes=model.persistent_nbytes(state)
            else:
                result=None
                # Generic ledger permits failed numerical payloads and counts
                # the same logical metadata as every registered method.
                from famjet.eval.budgets import state_ledger
                payload_bytes=state_ledger(state)['logical_bytes']
        labels=ep.labels[b:b+1].cpu(); shape=queries.T.shape
        active={t for t,present in zip(queries.tasks[0],queries.present[0].cpu().tolist()) if present}
        categorical=bool(active & CATEGORICAL_TASKS); binary=bool(active & BINARY_TASKS)
        if result is None:
            raw=torch.full((*shape,32 if categorical else 1 if binary else ep.events.values.shape[-1]),float('nan'))
            valid=torch.zeros(shape,dtype=torch.bool); numeric=valid; failure=torch.ones(shape,dtype=torch.bool)
        else:
            raw=(result.logits if categorical else result.diagnostics['support_logit'][...,None] if binary else result.prediction).detach().cpu()
            valid=result.diagnostics['prediction_valid'].cpu(); numeric=result.diagnostics.get('numeric_supported',valid).cpu(); failure=result.failure.cpu()
        context={'version':2,'present':queries.present.cpu().tolist(),'tasks':queries.tasks,
                 'target_valid':ep.metadata['target_valid'][b:b+1], 'numeric_supported':numeric.tolist(),
                 'prediction_valid':valid.tolist(),'quarantined':torch.full(shape,trigger is not None).tolist(),
                 'quarantine_trigger':trigger,'method':method,'replicate':replicate,'regime':ep.metadata['regime'],
                 'target_semantics':TARGET_SEMANTICS,'manifest_hash':manifest_hash or canonical_hash(ep.metadata['hashes']),
                 'statistics_hash':canonical_hash(stats),'output_convention':'categorical_logits' if categorical else 'binary_logit' if binary else 'numeric'}
        batch=PredictionBatch((h,),queries.query_ids.cpu(),raw,labels,ep.supported[b:b+1].cpu(),failure,
                              torch.zeros(shape,dtype=torch.bool),{'scoring_v2':context})
        for row in score_predictions(batch,stats,policy):
            row.update(payload_bytes=payload_bytes,evaluation_boundary='causal_stream_with_host_state_inspection',
                       state_inspection_seconds=inspection_seconds,episode_evaluation_seconds=time.perf_counter()-started,
                       state_inspection_timing='host_wall_includes_device_synchronization',
                       event_count=int(events.lengths[0]),time_unit=events.time_unit,
                       load=len(set(events.key_ids[0,:int(events.lengths[0])].tolist())),
                       span=float(events.timestamps[0,int(events.lengths[0])-1]-events.timestamps[0,0]) if int(events.lengths[0]) else 0.)
            rows.append(row)
    return rows
