from pathlib import Path
import json,time,hashlib,resource,platform,math,torch
from famjet.config import load_config
from famjet.analysis.development import development_inventory,simple_memories,_ScoredMemory
from famjet.eval.runner import episode_policy,score_episode
from famjet.eval.metrics import score_predictions,aggregate_scores
from famjet.eval.splits import _write_immutable
from famjet.types import PredictionBatch
from famjet.artifacts import append_jsonl,atomic_json
from famjet.provenance import canonical_hash
from famjet.train import _source,check_smoke_memory
from famjet.memory.buckets import TemporalBucketsMemory
from famjet.memory.exact_store import PackedHistoryMemory
out=Path('artifacts/task18/simple-cpu64-frontier9345-r2');out.mkdir(exist_ok=False)
start=time.perf_counter();factor=1 if platform.system()=='Darwin' else 1024;base=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*factor;torch.set_num_threads(4)
c=load_config(Path('configs/development/jet_learned_cpu64_raw_32768.yaml'));source=_source();statpath=Path('artifacts/task18/telemetry-jet-learned-cpu64/stages.jsonl');stats=next(json.loads(x)['target_statistics'] for x in statpath.read_text().splitlines() if json.loads(x)['stage']=='fit_end');assert canonical_hash(stats)=='0cebf5f59f3b44f44875b73d582e6cb3c21a0ade54867edfabaebcab220dad21'
procedure={'date':'2026-10-17','retained_previous_failure':'artifacts/task18/simple-cpu64-frontier9345/summary.json','correction':'UInt64 max unsupported; inspect exact Python integers from tolist, no float or signed narrowing','source':source,'helper_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'approval':'docs/research/task18-next-learning-procedure.md','budget_bytes':9345,'common_training_fit_histories':768,'statistics_source':str(statpath),'statistics_source_sha256':hashlib.sha256(statpath.read_bytes()).hexdigest(),'target_statistics_hash':canonical_hash(stats),'development_histories':96,'weights':'equal3lengths_4regimes_2tasks_then_equalhistories','precision':'packed records FP32 inputs; buckets FP64 sums; exact growing oracle FP64; shared and independent count variants explicit','net_limit_bytes':201326592,'scope':'exposed development headroom; no fitting or protected outputs','latest16_proof':'DataConfig public one-hot key space16 and key_load16; with capacity>=16 no latest-LRU key eviction is possible. Compare all scored outputs against maximal capacity on same96 histories.','storage_boundary':'actual persistent snapshot, no ignored history; oracle grows and is not bounded competitor'}
_write_immutable(out/'procedure.json',procedure);atomic_json(out/'statistics.json',stats)
def memory():return max(0,resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*factor-base)
def guard():check_smoke_memory(c,memory())
results={};allrows={}
def finish(status,**extra):atomic_json(out/'summary.json',{'status':status,'source':source,'procedure_hash':canonical_hash(procedure),'target_statistics_hash':canonical_hash(stats),'results':results,'total_seconds':time.perf_counter()-start,'rss_additional_bytes':memory(),'limit':201326592,**extra})
def summarize(rows):
 by={str(n):aggregate_scores([r for r in rows if r['length']==n]) for n in (128,512,2048)}
 return {'loss':math.fsum(v['loss'] for v in by.values())/3,'by_length':by,'failure_count':sum(r['failure'] for r in rows),'nonfinite_count':sum(r['nonfinite'] for r in rows),'fallback_count':sum(r['fallback'] for r in rows),'max_persistent_bytes':max(r['payload_bytes'] for r in rows)}
try:
 tick=time.perf_counter();episodes,manifest=development_inventory(c,out);gen=time.perf_counter()-tick;guard()
 assert all(max(ep.events.key_ids.flatten().tolist())<16 for ep in episodes)
 assert all(bool((ep.events.observed==ep.events.observed[...,:1]).all()) for ep in episodes)
 neural=json.loads(Path('artifacts/task18/learning-jet-cpu64-2048/manifest.json').read_text());assert manifest==neural
 memories=simple_memories(c,9345)
 capacity=1
 while True:
  m=TemporalBucketsMemory(capacity,8,key_dim=16,value_dtype='float32',accumulation_dtype='float64',normalization='shared');state=m.init_state(1,device='cpu',dtype='float32')
  if m.persistent_nbytes(state)>9345:break
  memories['buckets_shared_fp64']=m;capacity+=1
 memories['latest_lru_16']=PackedHistoryMemory(16,8,'latest_lru',key_dim=16,value_dtype='float32')
 policies={n:episode_policy([ep for ep in episodes if int(ep.events.lengths[0])==n]) for n in (128,512,2048)}
 # Prior is central scoring of the frozen train-only mean; no causal ingestion/state claim.
 tick=time.perf_counter();prior=[]
 for ep in episodes:
  n=int(ep.events.lengths[0]);q=ep.queries;shape=q.T.shape
  raw=torch.tensor([[stats['tasks'][task]['mean'] for task in q.tasks[0]]],dtype=torch.float64)
  context={'version':2,'output_convention':'numeric','present':q.present.tolist(),'tasks':q.tasks,'target_valid':ep.metadata['target_valid'],'numeric_supported':torch.ones(shape,dtype=torch.bool).tolist(),'prediction_valid':torch.ones(shape,dtype=torch.bool).tolist(),'quarantined':torch.zeros(shape,dtype=torch.bool).tolist(),'quarantine_trigger':None,'method':'training_prior_no_memory','replicate':0,'regime':ep.metadata['regime'],'target_semantics':'observed_event_targets_v2','manifest_hash':manifest['manifest_hash'],'statistics_hash':canonical_hash(stats)}
  batch=PredictionBatch(q.history_ids,q.query_ids,raw,ep.labels,ep.supported,torch.zeros(shape,dtype=torch.bool),torch.zeros(shape,dtype=torch.bool),{'scoring_v2':context})
  for row in score_predictions(batch,stats,policies[n]):row.update(length=n,payload_bytes=0,evaluation_boundary='static_training_prior_scoring_no_ingestion');prior.append(row);append_jsonl(out/'prior-predictions.jsonl',row)
 results['training_prior_no_memory']={**summarize(prior),'seconds':time.perf_counter()-tick,'capacity':0,'growing_storage':False};finish('running',generation_seconds=gen)
 for name in ['reservoir','buckets_shared_fp64','exact_unbounded_fp64','recent','latest_lru','latest_lru_16','hybrid','buckets']:
  tick=time.perf_counter();m=memories[name];rows=[];scored=_ScoredMemory(m,stats)
  for ep in episodes:
   n=int(ep.events.lengths[0]);current=score_episode(scored,ep,method=name,policy=policies[n],manifest_hash=manifest['manifest_hash'])
   for row in current:row['length']=n;rows.append(row);append_jsonl(out/f'{name}.jsonl',row)
   guard()
  results[name]={**summarize(rows),'seconds':time.perf_counter()-tick,'capacity':m.capacity,'growing_storage':name=='exact_unbounded_fp64'}
  if name in ('latest_lru','latest_lru_16'):allrows[name]=rows
  if name!='exact_unbounded_fp64':assert results[name]['max_persistent_bytes']<=9345
  if name=='exact_unbounded_fp64':assert results[name]['loss']==0
  finish('running',generation_seconds=gen);print(json.dumps({'method':name,**{k:results[name][k] for k in ('loss','seconds','max_persistent_bytes','capacity')}}),flush=True)
 fields=['history_id','query_id','prediction','raw_prediction','target','loss','failure','fallback','nonfinite','prediction_valid','numeric_supported','quarantined']
 assert len(allrows['latest_lru'])==len(allrows['latest_lru_16'])==768
 assert all(all(a[k]==b[k] for k in fields) for a,b in zip(allrows['latest_lru'],allrows['latest_lru_16']))
 assert source==_source();finish('completed',generation_seconds=gen,latest16_equivalence={'rows':768,'fields':fields,'status':'exact'},manifest_hash=manifest['manifest_hash']);print(json.dumps({'status':'completed','total_seconds':time.perf_counter()-start,'net_peak':memory()}),flush=True)
except BaseException as exc:
 finish('failed',error={'type':type(exc).__name__,'message':str(exc)});raise
