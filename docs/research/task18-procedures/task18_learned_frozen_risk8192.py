from pathlib import Path
import argparse,json,time,hashlib,math,resource,platform,collections,torch
from famjet.config import load_config
from famjet.checkpoint import load_checkpoint
from famjet.train import _reconstruct,history_loss,identities,_source,check_smoke_memory,move_episode
from famjet.analysis.development import resolve_policy
from famjet.data.development_cache import TrainingDrawCache
from famjet.provenance import canonical_hash
from famjet.artifacts import atomic_json,append_jsonl
from famjet.eval.splits import _write_immutable
P=argparse.ArgumentParser();P.add_argument('family',choices=['jet','bank']);args=P.parse_args();family=args.family
out=Path(f'artifacts/task18/learned-cpu64-frozen-risk8192-{family}');out.mkdir(exist_ok=False);torch.set_num_threads(4)
started=time.perf_counter();factor=1 if platform.system()=='Darwin' else 1024;base=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*factor;source=_source();configpath=Path(f'configs/development/{family}_learned_cpu64_raw_32768.yaml');c=load_config(configpath);p=Path(f'artifacts/task18/learning-{family}-cpu64-8192/training/checkpoint.pt')
procedure={'date':'2026-10-17','family':family,'source':source,'approval':'root explicit frozen6144 risk ruling after full simple suite, no updates','helper_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'checkpoint':str(p),'checkpoint_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'config_sha256':hashlib.sha256(configpath.read_bytes()).hexdigest(),'cache_manifest_hash':c.development.cache_manifest_hash,'target_statistics_hash':'0cebf5f59f3b44f44875b73d582e6cb3c21a0ade54867edfabaebcab220dad21','histories':6144,'actual_checkpoint_step':8192,'precision':'CPU64 computation; exact existing FP32 input and training-label presentation before promotion','objective':'existing history_loss equal_tasks_then_equal_histories; no support-based filtering or evaluation fallback substitution','scope':'frozen empirical TRAIN risk; not central development loss or independent evidence','upstream':'raw histories recomputed at saved learned rates; no feature cache or fitting','net_limit_bytes':201326592,'forecast_paired_seconds':[120,160]};_write_immutable(out/'procedure.json',procedure)
def memory():return max(0,resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*factor-base)
def guard():check_smoke_memory(c,memory())
losses=[];cells=collections.defaultdict(list);counts={'failed_histories':0,'model_failure_queries':0,'prediction_invalid_queries':0,'numeric_unsupported_queries':0,'fallback_substitution_queries':0};timing={'delivery_seconds':0.,'forward_loss_seconds':0.,'row_write_seconds':0.}
try:
 identity,_=identities(c,resolve_policy(c));ck=load_checkpoint(p,{**identity,'source':source});assert ck['completed_step']==8192
 m=_reconstruct(ck['model']).to('cpu');m.eval();assert canonical_hash(m.target_statistics)==procedure['target_statistics_hash'];cache=TrainingDrawCache(c);guard()
 with torch.no_grad():
  for i in range(6144):
   tick=time.perf_counter();raw=cache.read(i);ep=move_episode(raw,'cpu',dtype=torch.float64);timing['delivery_seconds']+=time.perf_counter()-tick;tick=time.perf_counter();error=None;value=None
   result=m.read(m.encode(ep.events,mode='terminal'),ep.queries)
   q=ep.queries.present;flags={'model_failure_queries':int(result.failure[q].sum()),'prediction_invalid_queries':int((~result.diagnostics['prediction_valid'][q]).sum()),'numeric_unsupported_queries':int((~result.diagnostics['numeric_supported'][q]).sum())}
   for k,v in flags.items():counts[k]+=v
   try:
    value=float(history_loss(m,result,ep))
    if not math.isfinite(value):raise FloatingPointError('nonfinite empirical objective')
   except (ValueError,FloatingPointError) as exc:error={'type':type(exc).__name__,'message':str(exc)};value=None;counts['failed_histories']+=1
   timing['forward_loss_seconds']+=time.perf_counter()-tick
   row={'ordinal':i,'history_id':ep.events.history_ids[0],'length':int(ep.events.lengths[0]),'regime':ep.metadata['regime'],'objective':value,'status':'ok' if error is None else 'failed','error':error,'query_flags':flags,'fallback_substitution_applied':False,'raw_hashes':ep.metadata['hashes']};tick=time.perf_counter();append_jsonl(out/'histories.jsonl',row);timing['row_write_seconds']+=time.perf_counter()-tick
   if value is not None:losses.append(value);cells[f"{row['length']}/{row['regime']}"].append(value)
   guard()
 assert source==_source();assert len(losses)+counts['failed_histories']==6144
 record={'status':'completed' if counts['failed_histories']==0 else 'failed_objective','family':family,'checkpoint_step':8192,'histories':6144,'objective':math.fsum(losses)/6144 if not counts['failed_histories'] else None,'cell_means':{k:math.fsum(v)/len(v) for k,v in cells.items()} if not counts['failed_histories'] else None,'cell_counts':{k:len(v) for k,v in cells.items()},'counts':counts,'training_fallback_semantics':'No substitution in history_loss; invalid/support flags retained, model failure makes whole diagnostic failed rather than dropping histories.','timing':timing,'seconds':time.perf_counter()-started,'rss_additional_bytes':memory(),'source':source,'procedure_hash':canonical_hash(procedure),'checkpoint_sha256':procedure['checkpoint_sha256'],'target_statistics_hash':procedure['target_statistics_hash'],'cache_manifest_hash':c.development.cache_manifest_hash,'cache_verification':cache.verification,'rows_sha256':hashlib.sha256((out/'histories.jsonl').read_bytes()).hexdigest()};atomic_json(out/'summary.json',record);print(json.dumps(record),flush=True)
except BaseException as exc:
 atomic_json(out/'failure.json',{'type':type(exc).__name__,'message':str(exc),'recorded_histories':len(losses)+counts['failed_histories'],'seconds':time.perf_counter()-started,'rss_additional_bytes':memory(),'source':source});raise
