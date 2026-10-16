"""Exploratory development orchestration and conservative comparator selection."""
import math
from collections import defaultdict

_TRIAL_FIELDS={'config_hash','family','split','loss','total_cost_seconds','status','convergence',
               'positive_control','numerical_gate','padding_parameters','allocated_parameters',
               'objective_active_parameters','reader_input_width','claim_scope'}


def validate_baseline_acceptance(record: dict, claim_scope: str) -> None:
    if set(record)!=_TRIAL_FIELDS:
        raise ValueError('unknown or missing trial fields; protected outcomes forbidden')
    if record['split']!='development_fit': raise ValueError('selection requires development split')
    if record['claim_scope']!=claim_scope: raise ValueError('baseline claim scope mismatch')
    for field,want in [('status','completed'),('convergence','accepted'),('positive_control','passed'),('numerical_gate','passed')]:
        if record[field]!=want: raise ValueError(f'baseline {field} is not accepted')
    if record['padding_parameters']!=0: raise ValueError('padding parameters forbidden')
    for field in ('loss','total_cost_seconds','allocated_parameters','objective_active_parameters','reader_input_width'):
        if type(record[field]) not in (int,float) or not math.isfinite(record[field]) or record[field]<0:
            raise ValueError(f'invalid trial {field}')
    if record['objective_active_parameters']>record['allocated_parameters']:
        raise ValueError('active parameters exceed allocation')


def select_family(trials: list[dict], policy: dict) -> dict:
    if set(policy)!={'claim_scope','max_total_cost_seconds','max_active_parameters','tie_tolerance'}:
        raise ValueError('unknown selection policy')
    accepted=[]; excluded=[]
    for r in trials:
        if set(r)!=_TRIAL_FIELDS or r.get('split')!='development_fit':
            raise ValueError('protected or unknown fields cannot enter development selection')
        try: validate_baseline_acceptance(r,policy['claim_scope'])
        except ValueError as exc:
            excluded.append({'config_hash':r['config_hash'],'reason':str(exc)}); continue
        if r['total_cost_seconds']>policy['max_total_cost_seconds'] or r['objective_active_parameters']>policy['max_active_parameters']:
            excluded.append({'config_hash':r['config_hash'],'reason':'outside declared cost/parameter envelope'}); continue
        accepted.append(r)
    if not accepted: return {'selected':None,'accepted':[],'excluded':excluded}
    best=min(r['loss'] for r in accepted)
    tied=[r for r in accepted if r['loss']<=best+policy['tie_tolerance']]
    return {'selected':min(tied,key=lambda r:(r['total_cost_seconds'],r['config_hash'])),
            'accepted':accepted,'excluded':excluded}


def reader_match(left, right):
    return all(left[k]==right[k] for k in ('reader_input_width','allocated_parameters','objective_active_parameters')) and left['padding_parameters']==right['padding_parameters']==0


def validation_loss(rows,regime_weights,task_weights):
    """Equal histories within regime, equal declared tasks, queries within cells."""
    cells=defaultdict(list); histories=defaultdict(set)
    for row in rows:
        cells[row['regime'],row['history_id'],row['task']].append(row['loss'])
        histories[row['regime']].add(row['history_id'])
    if set(histories)!=set(regime_weights): raise ValueError('incomplete regime inventory')
    total=0.
    for regime,rw in regime_weights.items():
        for history in histories[regime]:
            for task,tw in task_weights.items():
                values=cells[regime,history,task]
                if not values: raise ValueError('incomplete task/history inventory')
                total+=rw*tw*math.fsum(values)/len(values)/len(histories[regime])
    return total


def parameter_accounting(model):
    allocated=sum(p.numel() for p in model.parameters())
    inactive=sum(p.numel() for p in model.reader.support.parameters())
    return {'allocated_parameters':allocated,'objective_active_parameters':allocated-inactive,
            'reader_input_width':model.reader.input_dim,'padding_parameters':0,
            'macs_per_query':model.reader.cost()['macs_per_query'],
            'support_calibration':'untrained_unavailable'}


def reader_budget(reader):
    return {'width':reader.width,'hidden_layers':reader.layers,
            **{k:getattr(reader,k) for k in ('rank','max_parameters','max_macs') if getattr(reader,k) is not None}}


def execution_shape(config):
    from dataclasses import asdict
    return {'method':config.model.method,'model':asdict(config.model),
            'key_dim':config.data.key_dim,'value_dim':config.data.value_dim,
            'queries':config.data.queries_per_history,'threads':config.resources.cpu_threads,
            'device':config.resources.device,'microbatch':config.training.microbatch,
            'lengths':list(config.development.lengths),
            'fit_histories_per_cell':config.development.fit_histories_per_cell,
            'eval_histories_per_cell':config.development.eval_histories_per_cell}


def resolve_policy(config):
    from dataclasses import asdict
    from famjet.train import SMOKE_POLICY,ROOT
    from famjet.provenance import canonical_hash
    from famjet.eval.isolation import source_identity
    import json
    d=config.development
    if config.phase!='development' or d is None: raise ValueError('explicit development calibration policy required')
    if config.resources.device!='cpu' or config.model.precision!='float32':
        raise ValueError('development initially calibrated only for CPU FP32')
    if config.data.generator.namespace!='training' or config.data.generator_version!='initial_spec_v2_targets':
        raise ValueError('development requires current training-only target generation')
    if config.training.microbatch!=1: raise ValueError('ragged development uses microbatch1')
    if d.mode=='calibration':
        # Prospective staged permission, not general removal of smoke bounds.
        if (any(n not in (128,512,2048) for n in d.lengths) or config.model.method not in {'jet','bank'}
            or config.model.J>(4 if config.model.method=='jet' else 8) or config.model.K!=16
            or config.data.value_dim!=8 or config.model.reader.width!=64 or config.model.reader.layers!=2
            or config.model.writer!='fixed' or config.model.rates.mode!='fixed'
            or config.training.optimizer_steps>4 or d.fit_histories_per_cell>4
            or config.data.queries_per_history>8 or d.eval_histories_per_cell>1):
            raise ValueError('outside authorized initial CPU calibration shape')
    else:
        if d.calibration_path is None: raise ValueError('measured calibration required')
        evidence=json.loads((ROOT/d.calibration_path).read_text())
        if canonical_hash(evidence)!=d.calibration_hash: raise ValueError('calibration hash mismatch')
        if (evidence.get('status')!='passed' or evidence.get('source_hash')!=source_identity()
                or execution_shape(config) not in evidence.get('shapes',[])):
            raise ValueError('calibration is not applicable to source/device/shape/policy')
        if config.resources.smoke_additional_allocation_limit_bytes>evidence['net_allocation_limit_bytes']:
            raise ValueError('development exceeds calibrated net allocation limit')
    return {**SMOKE_POLICY,'version':2,'scientific_status':'exploratory_development',
            'fit_histories':4*len(d.lengths)*d.fit_histories_per_cell,
            'fit_namespace':'task18_training_preprocessing_v2','draw_namespace':'task18_shared_training_draws_v2',
            'gradient_clip_norm':d.gradient_clip_norm,'development':asdict(d),
            'length_weights':{str(n):1/len(d.lengths) for n in d.lengths},
            'regime_weights':{r:.25 for r in REGIMES}}


from famjet.data._processes import REGIMES


def draw_config(config,index,*,fit=False,length=None,regime=None):
    """Independent across length/regime cells and paired across methods."""
    from dataclasses import replace
    d=config.development
    n=length or d.lengths[index%len(d.lengths)]
    r=regime or REGIMES[(index//len(d.lengths))%len(REGIMES)]
    g=replace(config.data.generator,namespace='training',regime=r)
    return replace(config,data=replace(config.data,length=n,generator=g)), f'task18-{"fit" if fit else "train"}-N{n}-{r}-{index:012d}'


def fit_panel(config):
    from famjet.data.synthetic import generate_episode
    panel=[]
    for n in config.development.lengths:
        for r in REGIMES:
            for i in range(config.development.fit_histories_per_cell):
                c,identity=draw_config(config,i,fit=True,length=n,regime=r)
                panel.append(generate_episode(c,config.development.data_seed,identity))
    return panel


def development_inventory(config,out):
    """Seal fresh independent length/regime histories; protected roots stay empty."""
    from dataclasses import asdict,replace
    from famjet.data.synthetic import generate_episode,SEED_VERSION,FEATURE_VERSION
    from famjet.eval.splits import _seal,_write_immutable,_split_roots
    from famjet.provenance import derive_seed
    roots=_split_roots(replace(config,seed=config.development.data_seed)); episodes=[]; entries=[]
    for n in config.development.lengths:
        for r in REGIMES:
            for i in range(config.development.eval_histories_per_cell):
                g=replace(config.data.generator,namespace='development_fit',regime=r)
                c=replace(config,data=replace(config.data,length=n,generator=g))
                identity=f'task18-dev-N{n}-{r}-{i:012d}'
                # Data root is shared across model/training seeds and disjoint
                # from all training preprocessing/optimization draws.
                seed=derive_seed(config.development.data_seed,'task18_development_v2','shared')
                ep=generate_episode(c,seed,identity); episodes.append(ep)
                entries.append({'length':n,'regime':r,'episode_id':identity,'seed':seed,'hashes':ep.metadata['hashes']})
    roots['development_fit'].update(root=seed,episodes=entries)
    manifest=_seal({'manifest_version':1,'generator_version':config.data.generator_version,
        'target_semantics':'observed_event_targets_v2','seed_version':SEED_VERSION,'feature_version':FEATURE_VERSION,
        'artifact_kind':'task18_pooled_development_inventory','data':asdict(config.data),
        'length_weights':{str(n):1/len(config.development.lengths) for n in config.development.lengths},
        'regime_weights':{r:.25 for r in REGIMES},'splits':roots})
    _write_immutable(out/'manifest.json',manifest)
    return episodes,manifest


def evaluate_development(model,episodes,manifest_hash,method):
    from famjet.eval.runner import episode_policy,score_episode
    from famjet.eval.metrics import aggregate_scores
    rows=[]; per_length={}
    for n in sorted({int(ep.events.lengths[0]) for ep in episodes}):
        subset=[ep for ep in episodes if int(ep.events.lengths[0])==n]
        policy=episode_policy(subset)
        current=[]
        for ep in subset:
            scored=score_episode(model,ep,method=method,policy=policy,manifest_hash=manifest_hash)
            for row in scored: row['length']=n
            current.extend(scored)
        per_length[str(n)]=aggregate_scores(current); rows.extend(current)
    return rows,{'loss':sum(v['loss'] for v in per_length.values())/len(per_length),
                 'by_length':per_length,'length_weighting':'equal_lengths_then_task_history_regime'}


class _ScoredMemory:
    """Runner-side training-prior attachment, never serialized into a memory."""
    def __init__(self,memory,statistics): self.memory,self.target_statistics=memory,statistics
    def encode(self,*a,**k): return self.memory.encode(*a,**k)
    def read(self,*a,**k): return self.memory.read(*a,**k)
    def persistent_nbytes(self,*a,**k): return self.memory.persistent_nbytes(*a,**k)


def simple_memories(config,budget):
    from famjet.memory.exact_store import PackedHistoryMemory
    from famjet.memory.reservoir import ReservoirMemory,HybridMemory
    from famjet.memory.buckets import TemporalBucketsMemory
    k,v=config.model.K,config.data.value_dim
    factories={
        'recent':lambda c:PackedHistoryMemory(c,v,'recent',key_dim=k,value_dtype='float32'),
        'latest_lru':lambda c:PackedHistoryMemory(c,v,'latest_lru',key_dim=k,value_dtype='float32'),
        'reservoir':lambda c:ReservoirMemory(c,v,config.development.data_seed,key_dim=k,value_dtype='float32'),
        'hybrid':lambda c:HybridMemory(max(1,c//2),max(1,c-c//2),v,config.development.data_seed,key_dim=k,value_dtype='float32'),
        'buckets':lambda c:TemporalBucketsMemory(c,v,key_dim=k,value_dtype='float32')}
    result={'exact_unbounded_fp64':PackedHistoryMemory(None,v,'exact',key_dim=k)}
    for name,factory in factories.items():
        capacity=1
        while True:
            memory=factory(capacity)
            state=memory.init_state(1,device='cpu',dtype='float32')
            if memory.persistent_nbytes(state)>budget: break
            result[name]=memory; capacity+=1
    return result


def host_observation():
    import subprocess,shutil
    from famjet.train import ROOT
    result={'disk_free_bytes':shutil.disk_usage(ROOT).free}
    for name,cmd in [('memory_pressure',['memory_pressure','-Q']),('vm_stat',['vm_stat']),
                     ('swap',['sysctl','-n','vm.swapusage']),('thermal',['pmset','-g','therm'])]:
        p=subprocess.run(cmd,capture_output=True,text=True)
        result[name]={'returncode':p.returncode,'output':p.stdout,'error':p.stderr}
    return result


def run_development(config,out):
    from pathlib import Path
    from dataclasses import asdict
    import time,json,hashlib,resource,platform
    import torch
    from famjet.train import train_model,make_model,move_episode,ROOT,_source
    from famjet.artifacts import atomic_json,append_jsonl
    from famjet.eval.metrics import fit_target_statistics
    from famjet.provenance import canonical_hash
    from famjet.eval.isolation import source_identity
    out=Path(out); out.mkdir(parents=True,exist_ok=False)
    started=time.perf_counter()
    rss_factor=1 if platform.system()=='Darwin' else 1024
    baseline=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*rss_factor
    record={'status':'initializing','phase':'development','claim_scope':'exploratory_no_confirmatory_claim',
            'config':asdict(config),'source':_source(),'source_hash':source_identity(),
            'expected_budgets':asdict(config.resources),'host_before':host_observation(),
            'plan_hash':hashlib.sha256((ROOT/'docs/superpowers/specs/2026-10-16-famjet-design.md').read_bytes()).hexdigest(),
            'amendments':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((ROOT/'docs/amendments').glob('*.md'))},
            'lock_hash':hashlib.sha256((ROOT/'requirements.lock').read_bytes()).hexdigest()}
    atomic_json(out/'development.json',record)
    try:
        policy=resolve_policy(config); record['execution_policy']=policy
        from famjet.train import _resource_check,check_smoke_memory
        _resource_check(config,policy)
        torch.set_num_threads(config.resources.cpu_threads)
        episodes,manifest=development_inventory(config,out)
        record['manifest_hash']=manifest['manifest_hash']
        if config.development.mode=='simple':
            fits=fit_panel(config); stats=fit_target_statistics(fits)
            atomic_json(out/'statistics.json',stats)
            model=make_model(config,policy)
            state=model.encode(move_episode(episodes[0],'cpu').events,mode='terminal')
            budget=model.persistent_nbytes(state); result={}
            for name,memory in simple_memories(config,budget).items():
                tick=time.perf_counter()
                rows,summary=evaluate_development(_ScoredMemory(memory,stats),episodes,manifest['manifest_hash'],name)
                for row in rows: append_jsonl(out/'predictions.jsonl',row)
                result[name]={**summary,'seconds':time.perf_counter()-tick,
                              'max_persistent_bytes':max(r['payload_bytes'] for r in rows),
                              'capacity':memory.capacity,'growing_storage':name=='exact_unbounded_fp64'}
                check_smoke_memory(config,max(0,resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*rss_factor-baseline))
                atomic_json(out/'headroom.json',{'budget_bytes':budget,'methods':result})
            oracle=result['exact_unbounded_fp64']
            for name,v in result.items():
                v['headroom']=v['loss']-oracle['loss']
            record.update(results=result,state_budget_bytes=budget)
        else:
            def observe(model,step,run_dir):
                tick=time.perf_counter()
                rows,summary=evaluate_development(model,[move_episode(ep,'cpu') for ep in episodes],manifest['manifest_hash'],config.model.method)
                for row in rows: append_jsonl(out/f'predictions-step{step}.jsonl',row)
                entry={'step':step,**summary,'evaluation_seconds':time.perf_counter()-tick,
                       'parameters':parameter_accounting(model),'target_statistics_hash':canonical_hash(model.target_statistics),
                       'fit_provenance':model.fit_provenance}
                append_jsonl(out/'learning_curve.jsonl',entry)
                record['last_evaluation']=entry
                check_smoke_memory(config,max(0,resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*rss_factor-baseline))
                atomic_json(out/'development.json',record)
            checkpoint=train_model(config,out/'training',observer=observe)
            record['checkpoint']=str(checkpoint)
            record['training_run']=json.loads((out/'training/run.json').read_text())
        record['status']='completed'
    except BaseException as exc:
        record.update(status='failed',error={'type':type(exc).__name__,'message':str(exc)})
        raise
    finally:
        peak=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*rss_factor
        record.update(total_seconds=time.perf_counter()-started,host_after=host_observation(),
                      rss_highwater_baseline_bytes=baseline,rss_highwater_peak_bytes=peak,
                      rss_highwater_additional_bytes=max(0,peak-baseline),
                      disk_bytes=sum(p.stat().st_size for p in out.rglob('*') if p.is_file()))
        atomic_json(out/'development.json',record)
    return record
