"""Reproducible FP32 smoke training; complete run state stays outside TaskModel."""
from dataclasses import asdict, replace
from datetime import datetime, timezone
import hashlib
import math
import os
from pathlib import Path
import platform
import random
import resource
import shutil
import subprocess
import time
import traceback
import numpy as np
import torch
from torch.utils.checkpoint import checkpoint as recompute
from famjet.artifacts import atomic_json, append_jsonl
from famjet.checkpoint import capture_rng, restore_rng, save_checkpoint, load_checkpoint
from famjet.config import RunConfig
from famjet.data.synthetic import generate_episode
from famjet.eval.isolation import export_method, source_identity, _reconstruct
from famjet.eval.oracle import BINARY_TASKS, CATEGORICAL_TASKS
from famjet.memory.delta import DeltaMixer
from famjet.memory.jet import JetMemory
from famjet.memory.hippo import PolynomialMemory
from famjet.memory.multiscale import MultiscaleMemory
from famjet.memory.expbank import ExpBankMemory, BoundedRates
from famjet.models.task_model import TaskModel
from famjet.provenance import canonical_hash
from famjet.readers.structured import make_reader, TASK_ORDER
from famjet.types import Episode

ROOT=Path(__file__).resolve().parents[1]
SMOKE_POLICY={'version':1,'schedule':'constant','gradient_clip_norm':None,'terminal_chunk':32,
              'fit_histories':1,'fit_namespace':'training_preprocessing_v1',
              'draw_namespace':'shared_training_draws_v1','loss':'equal_tasks_then_equal_histories',
              'stream_recompute':True,'missing_labels':'fail_run','scientific_status':'non_scientific_smoke'}


def make_model(config, policy=None):
    policy=SMOKE_POLICY if policy is None else policy
    m,d=config.model,config.data
    device=config.resources.device
    if m.precision != 'float32': raise ValueError('training requires FP32')
    if m.method == 'delta':
        kernel=DeltaMixer(m.K,d.value_dim,heads=m.heads,**asdict(m.delta),device=device)
    elif m.method == 'multiscale':
        p=m.multiscale
        kernel=MultiscaleMemory(p.order,p.scale_order,p.epsilon,p.tau0,m.K,d.value_dim,
            declared_gaps=p.declared_gaps,cache_limit_bytes=config.resources.cache_limit_bytes,
            chunk_size=policy['terminal_chunk'],device=device)
    elif m.method == 'polynomial':
        p=m.polynomial
        kernel=PolynomialMemory(p.orders,p.taus,m.K,d.value_dim,declared_gaps=p.declared_gaps,
            cache_limit_bytes=config.resources.cache_limit_bytes,chunk_size=policy['terminal_chunk'],device=device)
    else:
        if m.method not in {'jet','bank'}: raise ValueError('training comparator not yet registered')
        lo,hi=m.rates.bounds
        if m.rates.mode == 'learned':
            rates=BoundedRates(m.J,math.log(lo),math.log(hi)).to(device)
        else:
            rates=(torch.logspace(math.log10(lo),math.log10(hi),m.J) if m.rates.spacing=='log'
                   else torch.linspace(lo,hi,m.J)).reshape(1,-1).to(device)
        kernel=(JetMemory if m.method=='jet' else ExpBankMemory)(rates,m.K,d.value_dim,
            eps=m.epsilon,support_floor=m.numerical_support_floor,chunk_size=policy['terminal_chunk'])
    from famjet.analysis.development import reader_budget
    reader=make_reader(m.reader.kind,kernel.reader_feature_spec,
        dict(key_dim=m.K),reader_budget(m.reader)).to(device)
    return TaskModel(kernel,reader,config).to(device)


def optimizer_named_groups(model):
    """Canonical registration order within explicit decay/no-decay groups."""
    named=list(model.named_parameters())
    if type(model.kernel) is not DeltaMixer:
        return [named]
    excluded={'kernel.A_log','kernel.dt_bias'}
    return [[(n,p) for n,p in named if n not in excluded],[(n,p) for n,p in named if n in excluded]]


def make_optimizer(model,config):
    groups=optimizer_named_groups(model)
    parameters=[{'params':[p for _,p in group], 'weight_decay':config.training.weight_decay if i==0 else 0.}
                for i,group in enumerate(groups)]
    return torch.optim.AdamW(parameters,lr=config.training.learning_rate,weight_decay=config.training.weight_decay)


def move_episode(ep, device):
    e,q=ep.events,ep.queries
    e=replace(e,key_features=e.key_features.to(device=device,dtype=torch.float32),
        values=e.values.to(device=device,dtype=torch.float32),present=e.present.to(device),observed=e.observed.to(device),
        auxiliary={k:v.to(device=device,dtype=torch.float32) for k,v in e.auxiliary.items()})
    q=replace(q,key_features=q.key_features.to(device=device,dtype=torch.float32),present=q.present.to(device))
    return replace(ep,events=e,queries=q)


def _batch(episodes):
    def join(field,objects): return torch.cat([getattr(o,field) for o in objects],0)
    events=[ep.events for ep in episodes]; queries=[ep.queries for ep in episodes]
    e=replace(events[0],history_ids=tuple(h for e in events for h in e.history_ids),
        **{k:join(k,events) for k in ['event_ids','timestamps','key_ids','key_features','values','lengths','present','observed']},
        auxiliary={k:torch.cat([e.auxiliary[k] for e in events],0) for k in events[0].auxiliary})
    q=replace(queries[0],history_ids=e.history_ids,tasks=tuple(row for q in queries for row in q.tasks),
        **{k:join(k,queries) for k in ['query_ids','T','key_ids','key_features','age_start','age_end','present','lengths']})
    return Episode(e,q,torch.cat([ep.labels for ep in episodes]),torch.cat([ep.supported for ep in episodes]))


def history_loss(model, result, episode):
    """Equal task means per history, equal history means; never filter predictions."""
    q=episode.queries
    if bool(result.failure[q.present].any()): raise FloatingPointError('failed model prediction')
    rows=[]
    for b,tasks in enumerate(q.tasks):
        terms=[]
        active={t for t,yes in zip(tasks,q.present[b].cpu().tolist()) if yes}
        if not active: raise ValueError('missing training queries/labels')
        if 'change_sign' in active: raise ValueError('sign training requires continuous contrast arm')
        for task in sorted(active):
            mask=q.present[b] & torch.tensor([t==task for t in tasks],device=q.present.device)
            labels=episode.labels[b].to(device=q.present.device,dtype=torch.float32)[mask]
            if not bool(torch.isfinite(labels).all()): raise ValueError('missing/nonfinite training labels')
            if task in BINARY_TASKS:
                loss=torch.nn.functional.binary_cross_entropy_with_logits(result.diagnostics['support_logit'][b,mask],labels.flatten().float())
            else:
                if not bool(episode.supported[b].to(mask.device)[mask].all()):
                    raise ValueError('missing valid training labels')
                if task in CATEGORICAL_TASKS:
                    loss=torch.nn.functional.cross_entropy(result.logits[b,mask],labels.long())
                else:
                    scale=model.target_scale[TASK_ORDER.index(task)]
                    loss=((result.prediction[b,mask]-labels.float())/scale).square().mean()
            terms.append(loss)
        rows.append(torch.stack(terms).mean())
    loss=torch.stack(rows).mean()
    if not bool(torch.isfinite(loss)): raise FloatingPointError('nonfinite training objective')
    return loss


def forward_training(model, episode, encode_mode, *, recompute=True):
    # Non-reentrant checkpoint preserves the entire recurrent gradient; no detach,
    # truncation, retained snapshots, or stale writer/rate state crosses an update.
    def forward(values):
        return model(replace(episode.events,values=values),episode.queries,encode_mode=encode_mode)
    if encode_mode=='stream' and recompute:
        return globals()['recompute'](forward,episode.events.values,use_reentrant=False,preserve_rng_state=True)
    return forward(episode.events.values)


def _sync(device):
    if device=='mps': torch.mps.synchronize()


def _now(): return datetime.now(timezone.utc).isoformat()


def _source():
    def git(*args):
        return subprocess.check_output(['git',*args],cwd=ROOT,text=True)
    return {'commit':git('rev-parse','HEAD').strip(),'diff':git('diff','HEAD','--'),
            'untracked_package_files':{name:(ROOT/name).read_text() for name in git('ls-files','--others','--exclude-standard','famjet').splitlines() if name.endswith('.py')},
            'package_hash':source_identity()}


def identities(config,policy):
    data={'generator':asdict(config.data),'split':'training','seed':config.seed if config.development is None else config.development.data_seed,
          'draw_namespace':policy['draw_namespace'],'fit_namespace':policy['fit_namespace']}
    if config.development is not None:
        data.update(length_weights=policy['length_weights'],regime_weights=policy['regime_weights'],
            task_weights={'mean':.5,'contrast':.5},
            cell_identity_namespace='task18-{fit|train}-N{length}-{regime}-{ordinal:012d}',
            fit_histories_per_cell=config.development.fit_histories_per_cell)
    return {'config_hash':canonical_hash(asdict(config)),'policy_hash':canonical_hash(policy),
        'source_hash':source_identity(),'lock_hash':hashlib.sha256((ROOT/'requirements.lock').read_bytes()).hexdigest(),
        'data_hash':canonical_hash(data)},data


def _context(config,policy,identity,data,source,model,optimizer,step,ids):
    wire=export_method(model)
    return {'schema_version':1,'config':asdict(config),'execution_policy':dict(policy),**identity,
        'source':source,'data_identity':data,'model':wire,'model_hash':canonical_hash(wire),
        'writer_hash':model._parameter_hash(),'model_state':{k:v.detach().cpu().clone() for k,v in model.state_dict().items()},
        'optimizer':optimizer.state_dict(),
        'optimizer_active_parameters':[n for n,p in model.named_parameters() if p in optimizer.state],
        'scheduler':{'kind':'constant','last_step':step},'scaler':None,
        'rng':capture_rng(config.resources.device),'sampler':{'namespace':policy['draw_namespace'],'seed':data['seed'],'position':len(ids)},
        'completed_step':step,'accumulation_position':0,'consumed_episode_ids':list(ids),'restarted_accumulation':False}


def check_smoke_memory(config, additional_bytes):
    # Discovery already applies the reserved fraction to this net ceiling.
    if additional_bytes > config.resources.smoke_additional_allocation_limit_bytes:
        raise MemoryError('smoke additional allocation exceeds reserved envelope')


def _check_smoke_dimensions(config):
    """Pure preallocation bound shared with raw checkpoint descriptor checks."""
    if config.training.optimizer_steps>4 or config.training.effective_batch>4 or config.training.microbatch>2 or config.data.length>128 or config.data.queries_per_history>8 or config.model.heads!=1 or ((config.model.delta.dim>32 or config.model.delta.head_key_dim>8 or config.model.delta.head_value_dim>8 or config.model.delta.conv_length>4) if config.model.method=='delta' else config.model.multiscale.order*config.model.multiscale.scale_order>8 if config.model.method=='multiscale' else sum(config.model.polynomial.orders)>8 if config.model.method=='polynomial' else config.model.J>4) or config.model.K>16 or config.data.value_dim>32 or config.model.reader.width>128 or config.model.reader.layers>2:
        raise ValueError('outside tiny smoke envelope; sustained calibration required')


def _resource_check(config, policy):
    if config.phase=='development':
        from famjet.analysis.development import resolve_policy
        if policy!=resolve_policy(config): raise ValueError('development policy mismatch')
    elif config.phase != 'smoke':
        raise ValueError('non-smoke training requires Task18/20 explicit policy and sustained resource calibration')
    if config.phase=='smoke' and policy != SMOKE_POLICY: raise ValueError('unregistered smoke execution policy')
    if config.data.generator.namespace != 'training' or config.data.beijing is not None:
        raise ValueError('training requires exploratory synthetic training namespace')
    if config.phase=='smoke': _check_smoke_dimensions(config)
    if config.resources.checkpoint_retention<2: raise ValueError('two checkpoints required for atomic recovery')
    provenance_path=ROOT/config.resources.resource_provenance
    if not provenance_path.is_file(): raise ValueError('missing resource provenance')
    import json
    discovered=json.loads(provenance_path.read_text()).get('resource_policy',{})
    ceiling=discovered.get('smoke_additional_allocation_limit_bytes')
    if type(ceiling) is not int or config.resources.smoke_additional_allocation_limit_bytes>ceiling:
        raise ValueError('configured smoke ceiling exceeds discovered resource provenance')
    if config.resources.device=='mps' and (os.environ.get('PYTORCH_ENABLE_MPS_FALLBACK')!='0' or os.environ.get('PYTORCH_MPS_FAST_MATH')!='0' or not torch.backends.mps.is_available()):
        raise ValueError('native MPS requires availability, fallback=0 and fast-math=0 before torch import')
    if shutil.disk_usage(ROOT).free < 64*1024**2: raise OSError('insufficient checkpoint/log disk reserve')


def _historical_prediction_records(model,ep,run_id,split):
    with torch.no_grad():
        state=model.encode(ep.events,mode='terminal')
        result=model.read(state,ep.queries)
        payload_bytes=model.persistent_nbytes(state)
    q,e=ep.queries,ep.events
    for b,row in enumerate(q.tasks):
        for j,task in enumerate(row):
            if not bool(q.present[b,j]): continue
            pred=(result.logits if result.logits is not None else result.prediction)[b,j].detach().cpu()
            label=ep.labels[b,j].cpu()
            finite=bool(torch.isfinite(pred).all())
            label_valid=bool(torch.isfinite(label).all()) and (task in BINARY_TASKS or bool(ep.supported[b,j]))
            numeric=task not in CATEGORICAL_TASKS
            mse=float((pred-label).square().mean()) if finite and label_valid and numeric else None
            scale=model.target_statistics['tasks'].get(task,{}).get('scale') if model.target_statistics else None
            yield {'schema_version':1,'run_id':run_id,'replicate':0,'history_id':e.history_ids[b],
                'cluster_id':e.history_ids[b],'query_id':int(q.query_ids[b,j]),'split':split,
                'regime':ep.metadata.get('regime'),'task':task,'load':len(set(e.key_ids[b].tolist())),
                'event_count':int(e.lengths[b]),'span':float(e.timestamps[b,-1]-e.timestamps[b,0]),
                'time_unit':e.time_unit,'window':[float(q.age_start[b,j]),float(q.age_end[b,j])],
                'target':label.tolist() if label_valid else None,'prediction':pred.tolist() if finite else None,
                'support':float(result.support[b,j]) if torch.isfinite(result.support[b,j]) else None,
                'normalized_error':mse/scale**2 if mse is not None and scale else None,'native_mse':mse,
                'nonfinite':not finite,'abstained':False,'failure':bool(result.failure[b,j]),
                'status':('ok' if bool(result.diagnostics['prediction_valid'][b,j]) else 'unsupported_prediction') if finite and label_valid and not bool(result.failure[b,j]) else 'missing_or_failed',
                'payload_bytes':payload_bytes,
                'diagnostics':{'prediction_valid':bool(result.diagnostics['prediction_valid'][b,j]),
                               'scientific_scoring':'historical_unscored_v1'}}


def _prediction_records(model,ep,run_id,split,*,policy=None,manifest_hash=None,scientific=True):
    from famjet.eval.runner import score_episode,episode_policy
    if not scientific and policy is None:
        policy=episode_policy([ep]); policy['primary_tasks']=[]
    for row in score_episode(model,ep,method=model.kernel.reader_feature_spec['family'],policy=policy,manifest_hash=manifest_hash):
        row.update(run_id=run_id,split=split,cluster_id=row['history_id'])
        b=ep.queries.history_ids.index(row['history_id'])
        j=ep.queries.query_ids[b].tolist().index(row['query_id'])
        row['window']=[float(ep.queries.age_start[b,j]),float(ep.queries.age_end[b,j])]
        yield row


def train_model(config: RunConfig, run_dir: Path, *, resume: Path | None = None, observer=None, stop_at=None) -> Path:
    run_dir=Path(run_dir)
    run_dir.mkdir(parents=True,exist_ok=False)
    from famjet.analysis.development import resolve_policy,fit_panel,draw_config
    policy=dict(SMOKE_POLICY)
    if stop_at is not None and not 0<=stop_at<=config.training.optimizer_steps: raise ValueError('invalid stop boundary')
    start=time.perf_counter(); baseline=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    record={'schema_version':1,'id':run_dir.name,'phase':config.phase,'status':'initializing',
        'scientific_status':policy['scientific_status'],'start_utc':_now(),'end_utc':None,'failure_category':None,
        'completed_step':0,'consumed_episode_ids':[],'attempted_episode_ids':[],'checkpoints':[],
        'resume':str(resume) if resume else None,'seeds':{'training':config.seed},'execution_policy':policy,
        'machine':{'platform':platform.platform(),'python':platform.python_version(),'torch':str(torch.__version__),
            'deterministic_algorithms':torch.are_deterministic_algorithms_enabled(),
            'mps_environment':{k:os.environ.get(k) for k in ['PYTORCH_ENABLE_MPS_FALLBACK','PYTORCH_MPS_FAST_MATH','PYTORCH_MPS_HIGH_WATERMARK_RATIO','PYTORCH_MPS_LOW_WATERMARK_RATIO']}},
        'expected_budgets':asdict(config.resources),'actual_budgets':{}}
    atomic_json(run_dir/'run.json',record)
    checkpoint_path=run_dir/'checkpoint.pt'
    try:
        policy=dict(SMOKE_POLICY) if config.phase=='smoke' else resolve_policy(config)
        record.update(execution_policy=policy,scientific_status=policy['scientific_status'])
        if config.data.generator_version!='initial_spec_v2_targets':
            raise ValueError('legacy target semantics forbidden for new training')
        _resource_check(config,policy)
        torch.set_num_threads(config.resources.cpu_threads)
        identity,data=identities(config,policy); source=_source()
        record.update(identity,source=source,data_identity=data,plan_hash=hashlib.sha256((ROOT/'docs/superpowers/specs/2026-10-16-famjet-design.md').read_bytes()).hexdigest(),
            amendments={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((ROOT/'docs/amendments').glob('*.md'))})
        atomic_json(run_dir/'resolved_config.json',{'config':asdict(config),'execution_policy':policy,**identity})
        random.seed(config.seed); np.random.seed(config.seed % 2**32); torch.manual_seed(config.seed)
        if config.resources.device=='mps': torch.mps.manual_seed(config.seed)
        construction_start=time.perf_counter()
        model=make_model(config,policy)
        if config.model.method in {'polynomial','multiscale'}:
            record[config.model.method+'_construction']={**model.kernel.preparation_cost([]),
                'seconds':time.perf_counter()-construction_start,'boundary':'complete_model_construction_including_cpu_fp64_matrices'}
        record['construction_seconds']=time.perf_counter()-construction_start
        optimizer=make_optimizer(model,config)
        step,consumed=0,[]
        if resume is not None:
            context=load_checkpoint(resume,identity)
            model=_reconstruct(context['model']).to(config.resources.device)
            optimizer=make_optimizer(model,config)
            optimizer.load_state_dict(context['optimizer'])
            step=context['completed_step']; consumed=list(context['consumed_episode_ids'])
            restore_rng(context['rng'],config.resources.device)
        else:
            fit_start=time.perf_counter()
            fits=fit_panel(config) if config.phase=='development' else [generate_episode(config,config.seed,'training_preprocessing_v1-000000000000')]
            for fit in fits:
                append_jsonl(run_dir/'preprocessing.jsonl',{'episode_ids':list(fit.events.history_ids),
                    'hashes':fit.metadata['hashes'],'split':'training','purpose':'frozen_statistics'})
            generation_seconds=time.perf_counter()-fit_start
            model.fit_statistics([move_episode(fit,config.resources.device) for fit in fits])
            record['preprocessing_seconds']={'generation':generation_seconds,'total':time.perf_counter()-fit_start}
            if config.development is not None and config.development.fit_histories_per_cell>=4:
                from famjet.eval.metrics import fit_target_statistics
                nested=fit_target_statistics([ep for i,ep in enumerate(fits) if i%config.development.fit_histories_per_cell<config.development.fit_histories_per_cell//2])
                record['statistics_stability']={t:{'nested_scale':nested['tasks'][t]['scale'],'full_scale':v['scale'],
                    'relative_scale_change':abs(v['scale']/nested['tasks'][t]['scale']-1)} for t,v in model.target_statistics['tasks'].items()}
            record['preprocessing']={'target_statistics':model.target_statistics,'fit_provenance':model.fit_provenance}
            del fits,fit
        draw_cache=None
        if config.development is not None and config.development.cache_manifest_path is not None:
            from famjet.data.development_cache import TrainingDrawCache
            draw_cache=TrainingDrawCache(config,start_ordinal=len(consumed))
            record['cache_verification']=draw_cache.verification
        record.update(status='running',completed_step=step,consumed_episode_ids=consumed)
        save_checkpoint(checkpoint_path,_context(config,policy,identity,data,source,model,optimizer,step,consumed))
        record['checkpoints']=[str(checkpoint_path),str(checkpoint_path.with_suffix('.pt.previous'))]
        atomic_json(run_dir/'run.json',record)
        if observer is not None: observer(model,step,run_dir)
        for step_index in range(step,config.training.optimizer_steps if stop_at is None else stop_at):
            optimizer.zero_grad(set_to_none=True)
            preparation=[]; consumed_lengths=[]; query_count=0
            step_ids=[]; loss_sum=0.; generation_seconds=0.; forward_seconds=0.; backward_seconds=0.; before=model._parameter_hash()
            _sync(config.resources.device); tick=time.perf_counter()
            for offset in range(0,config.training.effective_batch,config.training.microbatch):
                ids=[f'train-{len(consumed)+offset+i:012d}' for i in range(config.training.microbatch)]
                record['attempted_episode_ids'].extend(ids); step_ids.extend(ids)
                atomic_json(run_dir/'run.json',record)
                generation_start=time.perf_counter()
                if config.phase=='development':
                    episodes=[]
                    for ordinal in range(len(consumed)+offset,len(consumed)+offset+config.training.microbatch):
                        dc,draw_id=draw_config(config,ordinal)
                        episodes.append(draw_cache.read(ordinal) if draw_cache is not None else generate_episode(dc,config.development.data_seed,draw_id))
                else:
                    episodes=[generate_episode(config,config.seed,i) for i in ids]
                generation_seconds+=time.perf_counter()-generation_start
                for ep in episodes:
                    consumed_lengths.extend(int(n) for n in ep.events.lengths)
                    query_count+=int(ep.queries.present.sum())
                    append_jsonl(run_dir/'draws.jsonl',{'step':step_index+1,'episode_id':ep.events.history_ids[0],
                        'regime':ep.metadata['regime'],'hashes':ep.metadata['hashes'],'status':ep.metadata['status']})
                ep=move_episode(_batch(episodes),config.resources.device)
                if config.model.method in {'polynomial','multiscale'}:
                    preparation.append(model.kernel.call_preparation_cost(ep.events,ep.queries,
                        mode=config.model.encode,reader_kind=config.model.reader.kind))
                forward_start=time.perf_counter()
                result=forward_training(model,ep,config.model.encode,recompute=policy['stream_recompute'])
                loss=history_loss(model,result,ep)*config.training.microbatch/config.training.effective_batch
                forward_seconds+=time.perf_counter()-forward_start
                backward_start=time.perf_counter(); loss.backward(); backward_seconds+=time.perf_counter()-backward_start
                loss_sum+=float(loss.detach())
                del result,loss,ep,episodes
            norm=torch.linalg.vector_norm(torch.stack([torch.linalg.vector_norm(p.grad) for p in model.parameters() if p.grad is not None]))
            if not bool(torch.isfinite(norm)): raise FloatingPointError('nonfinite gradients')
            if policy['gradient_clip_norm'] is not None:
                torch.nn.utils.clip_grad_norm_(model.parameters(),policy['gradient_clip_norm'],error_if_nonfinite=True)
            optimizer.step(); optimizer.zero_grad(set_to_none=True)
            if not all(bool(torch.isfinite(p).all()) for p in model.parameters()): raise FloatingPointError('nonfinite updated parameters')
            consumed.extend(step_ids); step=step_index+1
            _sync(config.resources.device)
            elapsed=time.perf_counter()-tick
            record.update(completed_step=step,consumed_episode_ids=list(consumed))
            append_jsonl(run_dir/'training.jsonl',{'step':step,'episode_ids':step_ids,'loss':loss_sum,
                'learning_rate':optimizer.param_groups[0]['lr'],'gradient_norm':float(norm),
                'gradient_clip_norm':policy['gradient_clip_norm'],'writer_hash_before':before,'writer_hash_after':model._parameter_hash()})
            if config.phase=='smoke' or step in config.development.milestones or step==stop_at:
                save_checkpoint(checkpoint_path,_context(config,policy,identity,data,source,model,optimizer,step,consumed))
            if observer is not None and step in config.development.milestones:
                observer(model,step,run_dir)
            peak=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
            additional=max(0,peak-baseline)*(1 if platform.system()=='Darwin' else 1024)
            record['actual_budgets']={'rss_highwater_additional_bytes':additional,
                'rss_highwater_baseline_bytes':baseline*(1 if platform.system()=='Darwin' else 1024),
                'rss_highwater_peak_bytes':peak*(1 if platform.system()=='Darwin' else 1024),
                'measurement_limit':'lifetime highwater delta; fresh process required for cold allocation',
                'mps_current_bytes':torch.mps.current_allocated_memory() if config.resources.device=='mps' else None,
                'mps_driver_bytes':torch.mps.driver_allocated_memory() if config.resources.device=='mps' else None}
            append_jsonl(run_dir/'timing.jsonl',{'step':step,'shape':{'microbatch':config.training.microbatch,'lengths':consumed_lengths,'J':config.model.J,'K':config.model.K,'V':config.data.value_dim},
                'device':config.resources.device,'precision':'float32','boundary':'training_generate_forward_backward_optimizer',
                'cold_warm':'cold' if step_index==0 else 'warm','block':step_index,'order':0,'repetitions':1,
                'seconds':elapsed,'generation_seconds':generation_seconds,'forward_loss_seconds':forward_seconds,'backward_seconds':backward_seconds,('multiscale_preparation' if config.model.method=='multiscale' else 'polynomial_preparation'):preparation,
                'polynomial_allocation':asdict(config.model.polynomial) if config.model.polynomial is not None else None,
                'multiscale_allocation':asdict(config.model.multiscale) if config.model.multiscale is not None else None,
                'delta_allocation':asdict(config.model.delta) if config.model.delta is not None else None,
                'sync_policy':'before_after' if config.resources.device=='mps' else 'synchronous_cpu',
                'events':sum(consumed_lengths),'queries':query_count,
                'memory':record['actual_budgets'],'pressure':None,'power':None,'status':policy['scientific_status']})
            check_smoke_memory(config,additional)
            atomic_json(run_dir/'run.json',record)
        model.eval()
        probe=move_episode(generate_episode(config,config.seed if config.development is None else config.development.data_seed,'train-000000000000'),config.resources.device)
        for prediction in _prediction_records(model,probe,record['id'],'training',scientific=False):
            append_jsonl(run_dir/'predictions.jsonl',prediction)
        record.update(status='completed',parameter_hash=canonical_hash(export_method(model)))
        return checkpoint_path
    except BaseException as exc:
        category=('interrupted' if isinstance(exc,(KeyboardInterrupt,SystemExit)) else
                  'numerical_model_failure' if isinstance(exc,FloatingPointError) else 'infrastructure_or_contract_failure')
        record.update(status='failed',failure_category=category,error={'type':type(exc).__name__,'message':str(exc),'traceback':traceback.format_exc()})
        append_jsonl(run_dir/'failures.jsonl',{'utc':_now(),'category':category,'completed_step':record['completed_step'],
            'attempted_episode_ids':record['attempted_episode_ids'],**record['error']})
        raise
    finally:
        record.update(end_utc=_now(),total_seconds=time.perf_counter()-start)
        atomic_json(run_dir/'run.json',record)


def evaluate_model(checkpoint: Path, manifest: Path, out: Path) -> Path:
    """Failure-complete development diagnostics from a sealed current inventory.

    Protected splits remain reservation-only. Smoke checkpoints cannot claim
    scientific primary selection; undefined normalized scales remain explicit.
    """
    import json
    from famjet.config import _parse
    from famjet.eval.splits import _check_seal, _verify_splits
    out=Path(out); out.mkdir(parents=True,exist_ok=False)
    record={'schema_version':1,'id':out.name,'status':'running','phase':'development_fit',
        'split':'development_fit','scientific_status':'development_failure_complete_diagnostics','start_utc':_now(),
        'checkpoint':str(checkpoint),'manifest':str(manifest),'failure_category':None}
    atomic_json(out/'run.json',record)
    try:
        ctx=load_checkpoint(checkpoint,{'source_hash':source_identity(),
            'lock_hash':hashlib.sha256((ROOT/'requirements.lock').read_bytes()).hexdigest()})
        config=_parse(ctx['config'],RunConfig,'checkpoint.config')
        payload=json.loads(Path(manifest).read_text())
        _check_seal(payload); _verify_splits(payload['splits'])
        root_hash=payload['manifest_hash']
        if 'populations' in payload:
            selected=config.data.generator.population
            if selected=='delayed': selected=f'delayed_{config.data.generator.delay_multiplier:g}'
            if config.data.generator.robustness!='standard': selected=f'robustness_{config.data.generator.robustness}'
            if config.data.key_features=='dense' and selected in {'primary','presence','corrected_categorical','random_binding'}:
                selected=f'dense_{config.data.generator.key_load}_{selected}'
            entry=payload['populations'][selected]
            relative=Path(entry['path'])
            if relative.is_absolute() or '..' in relative.parts: raise ValueError('manifest path must be relative')
            payload=json.loads((Path(manifest).parent/relative).read_text())
            _check_seal(payload); _verify_splits(payload['splits'])
            if payload['manifest_hash']!=entry['manifest_hash']: raise ValueError('population manifest hash mismatch')
        if payload.get('artifact_kind')!='exploratory_population_inventory': raise ValueError('expected exploratory population manifest')
        eval_config=_parse(payload['config'],RunConfig,'manifest.config')
        a,b=asdict(config.data),asdict(eval_config.data)
        # Registered OOD lengths are explicit in the sealed workload; feature/
        # target population and every remaining data definition must agree.
        a.pop('length'); b.pop('length')
        if a!=b: raise ValueError('manifest/checkpoint data schema/population mismatch')
        if eval_config.phase not in {'smoke','development'}: raise ValueError('protected manifest evaluation forbidden')
        if eval_config.data.generator_version!='initial_spec_v2_targets': raise ValueError('legacy target semantics forbidden for new evaluation')
        split=payload['splits']['development_fit']
        record.update(manifest_hash=root_hash,population_manifest_hash=payload['manifest_hash'],
            config=ctx['config'],evaluation_config=payload['config'],model_hash=ctx['model_hash'],
            config_hash=ctx['config_hash'],data_hash=ctx['data_hash'],source_hash=ctx['source_hash'],lock_hash=ctx['lock_hash'])
        atomic_json(out/'run.json',record)
        model=_reconstruct(ctx['model']).to(config.resources.device).eval()
        from famjet.eval.runner import episode_policy
        inventory=[]
        for entry in split['episodes']:
            g=replace(eval_config.data.generator,namespace='development_fit',regime=entry['regime'])
            inventory.append(generate_episode(replace(eval_config,data=replace(eval_config.data,generator=g)),split['root'],entry['episode_id']))
        scoring_policy=episode_policy(inventory)
        scoring_policy['regime_weights']=payload['regime_weights']
        if ctx['execution_policy'].get('scientific_status')=='non_scientific_smoke':
            scoring_policy['primary_tasks']=[]
        del inventory
        atomic_json(out/'scoring_policy.json',scoring_policy)
        path=out/'predictions.jsonl'
        for entry in split['episodes']:
            g=replace(eval_config.data.generator,namespace='development_fit',regime=entry['regime'])
            c=replace(eval_config,data=replace(eval_config.data,generator=g))
            episode=generate_episode(c,split['root'],entry['episode_id'])
            if episode.metadata['hashes']!=entry['hashes']: raise ValueError('regenerated manifest episode hash mismatch')
            ep=move_episode(episode,config.resources.device)
            for row in _prediction_records(model,ep,out.name,'development_fit',policy=scoring_policy,manifest_hash=root_hash):
                append_jsonl(path,row)
            if not bool(ep.queries.present.any()):
                append_jsonl(path,{'run_id':out.name,'history_id':ep.events.history_ids[0],
                    'split':'development_fit','query_id':None,'status':'missing_queries','prediction':None,
                    'target':None,'native_mse':None,'normalized_error':None,'diagnostics':ep.metadata['diagnostics']})
        record['status']='completed'
        return path
    except BaseException as exc:
        record.update(status='failed',failure_category='infrastructure_or_contract_failure',
            error={'type':type(exc).__name__,'message':str(exc)})
        raise
    finally:
        record['end_utc']=_now(); atomic_json(out/'run.json',record)
