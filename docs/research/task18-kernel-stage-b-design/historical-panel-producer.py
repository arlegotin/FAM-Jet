from pathlib import Path
from dataclasses import replace
import json,time,hashlib,resource,platform,math,collections,torch
from famjet.config import load_config
from famjet.analysis.development import development_inventory,_ScoredMemory
from famjet.train import identities,_source,_reconstruct,move_episode,check_smoke_memory
from famjet.checkpoint import load_checkpoint
from famjet.analysis.development import resolve_policy
from famjet.eval.runner import episode_policy,score_episode
from famjet.eval.metrics import aggregate_scores
from famjet.eval.splits import _write_immutable
from famjet.memory.reservoir import ReservoirMemory
from famjet.provenance import canonical_hash
from famjet.artifacts import atomic_json,append_jsonl
out=Path('artifacts/task18/finite-nested96');out.mkdir(exist_ok=False)
start=time.perf_counter();factor=1 if platform.system()=='Darwin' else 1024;baseline=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*factor;torch.set_num_threads(4)
configs={f:load_config(Path(f'configs/development/{f}_finite_raw_32768.yaml')) for f in ('jet','bank')}
c=configs['jet'];source=_source();checkpoints={f'{f}-{s}':Path(f'artifacts/task18/{f}_finite_raw_8192/training/checkpoint.pt'+('.previous' if s==4096 else '')) for f in configs for s in (4096,8192)}
procedure={'date':'2026-10-17','kind':'prospective_evaluation_only_nested_development','source':source,'helper_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'checkpoint_sha256':{k:hashlib.sha256(p.read_bytes()).hexdigest() for k,p in checkpoints.items()},'histories_per_length_regime':8,'lengths':[128,512,2048],'old_ordinals':[0,1,2,3],'new_ordinals':[4,5,6,7],'weights':'equal3lengths_4regimes_2tasks_equal_histories','frozen_fit_histories':384,'target_statistics_hash':'76333b9d6ffdf7de73ea627a8c30158897cc7e37dac89dbc14e2498920e1692e','reservoir_capacity':61,'reservoir_bytes':4709,'net_allocation_limit_bytes':201326592,'protected_namespaces':'closed','claim':'diagnostic_not_primary_inference','tracked_amendment_deferred_reason':'preserve exact checkpoint Git source identity until lineage closes','calibration':'fresh_process_retained96_inventory_each_current_family_and_reservoir_one_maxlength_history_before_full_evaluation','slices':'full96_old48_new48; raw rows unchanged, derived slice policy narrows expected inventory only'}
_write_immutable(out/'procedure.json',procedure);ph=canonical_hash(procedure)
tick=time.perf_counter();episodes,manifest=development_inventory(replace(c,development=replace(c.development,eval_histories_per_cell=8)),out);episodes=[move_episode(ep,'cpu') for ep in episodes];generation_seconds=time.perf_counter()-tick
old=json.loads(Path('artifacts/task18/jet_finite_raw_8192/manifest.json').read_text())['splits']['development_fit']['episodes'];entries=manifest['splits']['development_fit']['episodes'];assert all(x in entries for x in old)
cal=[];results={};common_stats=None

def memory():return max(0,resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*factor-baseline)
def guard():check_smoke_memory(c,memory())
def model_at(name):
 global common_stats
 family,step=name.split('-');cc=configs[family];identity,_=identities(cc,resolve_policy(cc));ck=load_checkpoint(checkpoints[name],identity)
 assert ck['source']==source and ck['completed_step']==int(step)
 m=_reconstruct(ck['model']).to('cpu');m.eval();assert canonical_hash(m.target_statistics)==procedure['target_statistics_hash'];common_stats=m.target_statistics
 return m

def slices(rows):
 summary={}
 for tag,predicate in [('full96',lambda i:True),('old48',lambda i:i<4),('new48',lambda i:i>=4)]:
  lengths={}
  for n in (128,512,2048):
   eps=[ep for ep in episodes if int(ep.events.lengths[0])==n and predicate(int(ep.events.history_ids[0].rsplit('-',1)[1]))]
   ids={ep.events.history_ids[0] for ep in eps};policy=episode_policy(eps)
   selected=[{**r,'policy':policy,'policy_hash':canonical_hash(policy)} for r in rows if r['history_id'] in ids]
   lengths[str(n)]=aggregate_scores(selected)
  summary[tag]={'loss':math.fsum(x['loss'] for x in lengths.values())/3,'by_length':lengths}
 return summary

def evaluate(m,name):
 tick=time.perf_counter();rows=[]
 for n in (128,512,2048):
  eps=[ep for ep in episodes if int(ep.events.lengths[0])==n];policy=episode_policy(eps)
  for ep in eps:
   values=score_episode(m,ep,method=name,policy=policy,manifest_hash=manifest['manifest_hash'])
   for row in values:row['length']=n;append_jsonl(out/f'{name}.jsonl',row)
   rows.extend(values);guard()
 return {'seconds':time.perf_counter()-tick,'slices':slices(rows),'fallback_count':sum(r['fallback'] for r in rows),'failure_count':sum(r['failure'] for r in rows),'nonfinite_count':sum(r['nonfinite'] for r in rows)}

try:
 guard();probe=next(ep for ep in episodes if int(ep.events.lengths[0])==2048 and ep.metadata['regime']=='trend_reset')
 for name in ('jet-8192','bank-8192','reservoir'):
  m=model_at(name) if name!='reservoir' else _ScoredMemory(ReservoirMemory(61,8,c.development.data_seed,key_dim=16,value_dtype='float32'),common_stats)
  tick=time.perf_counter();rows=score_episode(m,probe,method=name,policy=episode_policy([probe]),manifest_hash=manifest['manifest_hash'])
  for row in rows:append_jsonl(out/'calibration-predictions.jsonl',row)
  guard();cal.append({'method':name,'executed_histories':1,'length':2048,'seconds':time.perf_counter()-tick,'rss_additional_bytes':memory()});del m,rows
 atomic_json(out/'calibration.json',{'status':'passed','procedure_hash':ph,'manifest_hash':manifest['manifest_hash'],'retained_histories':96,'records':cal,'rss_additional_bytes':memory(),'limit':201326592,'generation_seconds':generation_seconds})
 for name in checkpoints:
  m=model_at(name);results[name]=evaluate(m,name);del m
  atomic_json(out/'summary.json',{'status':'running','procedure_hash':ph,'manifest_hash':manifest['manifest_hash'],'source':source,'results':results})
  print(json.dumps({'method':name,'seconds':results[name]['seconds'],'losses':{k:v['loss'] for k,v in results[name]['slices'].items()}}),flush=True)
 m=_ScoredMemory(ReservoirMemory(61,8,c.development.data_seed,key_dim=16,value_dtype='float32'),common_stats);results['reservoir']=evaluate(m,'reservoir');del m
 print(json.dumps({'method':'reservoir','seconds':results['reservoir']['seconds'],'losses':{k:v['loss'] for k,v in results['reservoir']['slices'].items()}}),flush=True)
 atomic_json(out/'summary.json',{'status':'completed','procedure_hash':ph,'manifest_hash':manifest['manifest_hash'],'source':source,'results':results,'generation_seconds':generation_seconds,'total_seconds':time.perf_counter()-start,'rss_additional_bytes':memory(),'limit':201326592})
except BaseException as exc:
 atomic_json(out/'failure.json',{'error':str(exc),'type':type(exc).__name__,'procedure_hash':ph,'results':results,'total_seconds':time.perf_counter()-start,'rss_additional_bytes':memory()});raise
