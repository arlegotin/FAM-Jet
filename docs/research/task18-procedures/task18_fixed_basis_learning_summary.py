"""Read-only aggregation of the allocated three-family8192 evidence."""
from pathlib import Path
from collections import defaultdict
import json,hashlib,math,statistics,time
from famjet.train import _source
from famjet.provenance import canonical_hash
from famjet.artifacts import atomic_json
R=Path('artifacts/task18');E=Path('artifacts/task18-evidence');source=_source()
assert source['commit']=='2def54622c5d9a49c84145739792a084494fbbe9' and not source['diff'] and source['package_hash']=='ad542defda704e06dc9c88819b95afd6f483a882c792e82bf8c85dc27a6f6641'
def read(p):return json.loads(Path(p).read_text())
def rows(p):return [json.loads(x) for x in Path(p).read_text().splitlines()]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def mean(x):return math.fsum(x)/len(x)
def grouped(data):
 groups=defaultdict(list)
 for r in data:groups[(r['length'],r['regime'],r['task'],r['history_id'])].append(r['loss'])
 cell=defaultdict(list);histories=defaultdict(list)
 for (n,regime,task,h),losses in groups.items():
  value=mean(losses);cell[(n,regime,task)].append(value);histories[h].append(value)
 return {'cells':[{'length':n,'regime':r,'task':t,'histories':len(v),'loss':mean(v)} for (n,r,t),v in sorted(cell.items())],'loss':mean([mean(v) for v in cell.values()]),'history_losses':{h:mean(v) for h,v in sorted(histories.items())},'weighting':'query within history-task, then equal histories/tasks/regimes/lengths; central losses unchanged'}
s={'status':'three_family8192_complete_exploratory_unconverged','source':source,'helper_sha256':sha(__file__),'target_statistics_hash':'0cebf5f59f3b44f44875b73d582e6cb3c21a0ade54867edfabaebcab220dad21','fit_histories':768,'dev_histories':96,'unique_training_histories':6144,'corpus_passes':4,'updates_each':8192,'configured_horizon':32768,'authorized_further_updates':0,'state_bytes_each':9345,'net_cap_bytes':201326592,'families':{},'artifact_sha256':{},'limitations':['one initialization and one shared finite corpus; all96 histories exposed development','fixed full grids differ from learned interior/endpoints; no freeze-only attribution','scope original1e-12 fitted common-production-reader objective over independent memory features; no independentMLP/query oracle','support calibration unavailable; primary-active parameter counts upper bounds','no convergence/family defeat/protected inference from8192 boundary']}
for family in ('jet','bank','multiscale'):
 p=R/f'learning-{family}-fixed-cpu64-raw128-8192';d=read(p/'development.json');run=read(p/'training/run.json');curve=rows(p/'learning_curve.jsonl');timing=rows(p/'training/timing.jsonl');endpoint=read(R/f'fixed-basis-endpoint8192-{family}/summary.json');risk=read(R/f'fixed-basis-frozen-risk8192-{family}/summary.json');clock=read(E/f'fixed-basis-learning-{family}-8192-clock.json')
 assert d['status']=='completed' and d['source']==source and run['completed_step']==8192 and len(timing)==8192
 assert run['corpus_progress']=={'completed_passes':4,'corpus_histories':6144,'pass_offset':0,'unique_histories':6144}
 assert [r['step'] for r in curve]==[0,128,512,1024,2048,4096,8192]
 assert endpoint['status']=='all12_fitted_checkpoint_cells_passed' and len(endpoint['cases'])==12 and risk['status']=='completed' and risk['histories']==6144
 assert risk['checkpoint_sha256']==sha(p/'training/checkpoint.pt') and risk['target_statistics_hash']==s['target_statistics_hash']
 compact=[];query_hashes=[];final=None;flags={};stage_files=[]
 for row in curve:
  predpath=p/f"predictions-step{row['step']}.jsonl";pred=rows(predpath);g=grouped(pred);assert len(pred)==768 and abs(g['loss']-row['loss'])<1e-14 and row['target_statistics_hash']==s['target_statistics_hash']
  flags[str(row['step'])]={k:sum(bool(x[k]) for x in pred) for k in ('failure','nonfinite','fallback','infinite_loss','quarantined')}
  qhash=canonical_hash([(x['history_id'],x['query_id'],x['task'],x['regime'],x['target'],x['span']) for x in pred]);query_hashes.append(qhash)
  compact.append({'step':row['step'],'loss':row['loss'],'by_length':{n:x['loss'] for n,x in row['by_length'].items()},'observer_seconds':row['evaluation_seconds'],'cells':g['cells']});final=g;stage_files.append(predpath)
 assert len(set(query_hashes))==1
 cases=[read(Path(x['summary']).parent/'checkpoint-verification.json') for x in endpoint['cases']]
 assert all(x['sha256']==risk['checkpoint_sha256'] and x['step']==8192 for x in cases)
 v={'curve':compact,'last_doubling_relative_improvement':1-curve[-1]['loss']/curve[-2]['loss'],'final':final,'flags_by_step':flags,'total_seconds':d['total_seconds'],'net_peak_bytes':d['rss_highwater_additional_bytes'],'clock':clock,'fit_seconds':run['preprocessing_seconds'],'config_hash':run['config_hash'],'policy_hash':run['policy_hash'],'data_hash':run['data_hash'],'manifest_hash':d['manifest_hash'],'lock_hash':run['lock_hash'],'consumed_order_hash':canonical_hash(run['consumed_episode_ids']),'attempted_order_hash':canonical_hash(run['attempted_episode_ids']),'query_target_inventory_hash':query_hashes[0],'checkpoint_sha256':risk['checkpoint_sha256'],'parameters':curve[-1]['parameters'],'model_ledger':cases[0]['ledger'],'endpoint':endpoint,'frozen_train':risk,'cache_verification':run['cache_verification'],'feature_cache_verification':run['feature_cache_verification'],'timing':{'sum_update_seconds':math.fsum(x['seconds'] for x in timing),'median_update_seconds':statistics.median(x['seconds'] for x in timing),'delivery_seconds':math.fsum(x['delivery_seconds'] for x in timing),'forward_loss_seconds':math.fsum(x['forward_loss_seconds'] for x in timing),'backward_seconds':math.fsum(x['backward_seconds'] for x in timing),'actual_encoded_events':sum(x['events'] for x in timing),'source_events':sum(x['source_events'] for x in timing),'boundary':'fixed feature delivery+reader objective+backward+optimizer; excludes enclosing ledger/checkpoint/observers; external upstream preparation separately charged'}}
 draw_ids=[];draw_digest=hashlib.sha256()
 for i,line in enumerate((p/'training/draws.jsonl').open()):
  draw=json.loads(line);assert draw['draw_position']==i and draw['corpus_offset']==i%6144 and draw['corpus_pass']==i//6144 and draw['status']=='ok'
  draw_ids.append(draw['episode_id']);draw_digest.update(json.dumps({k:draw[k] for k in ('draw_position','corpus_offset','corpus_pass','episode_id','hashes')},sort_keys=True,separators=(',',':')).encode())
 assert len(draw_ids)==24576 and len(set(draw_ids))==6144 and all(draw_ids[k*6144:(k+1)*6144]==draw_ids[:6144] for k in range(4))
 v['actual_source_draw_order_hash']=draw_digest.hexdigest();v['unique_source_histories']=len(set(draw_ids));v['actual_source_draw_count']=len(draw_ids)
 v['best_observed_milestone']=min(compact,key=lambda x:x['loss']);s['families'][family]=v
 stage_files += [p/'development.json',p/'manifest.json',p/'training/run.json',p/'training/timing.jsonl',p/'training/draws.jsonl',p/'training/attempts.jsonl',p/'learning_curve.jsonl',R/f'fixed-basis-endpoint8192-{family}/summary.json',R/f'fixed-basis-frozen-risk8192-{family}/summary.json',R/f'fixed-basis-frozen-risk8192-{family}/histories.jsonl',E/f'fixed-basis-learning-{family}-8192-clock.json',E/f'fixed-basis-learning-{family}-8192-allocation.json']
 for c in endpoint['cases']:stage_files += [Path(c['summary']),Path(c['summary']).parent/'checkpoint-verification.json']
 for path in stage_files:s['artifact_sha256'][str(path)]=sha(path)
for key in ('data_hash','manifest_hash','consumed_order_hash','attempted_order_hash','query_target_inventory_hash','actual_source_draw_order_hash'):
 assert len({v[key] for v in s['families'].values()})==1,key
controls=read(R/'simple-cpu64-frontier9345-r2/summary.json');assert controls['status']=='completed' and controls['target_statistics_hash']==s['target_statistics_hash'];s['simple_controls_reused']=controls
s['operational_setup_origin']='e7565155c07638ff0367e9a12062c5c69be95ad5';s['retained_setup_seconds']=1975.089738041;s['setup_summary']='docs/research/task18-fixed-basis-operational-summary.json'
s['current_allocated_stage_seconds']=math.fsum(v['total_seconds']+v['endpoint']['perf_seconds']+v['frozen_train']['seconds'] for v in s['families'].values());s['cost_boundary']='three actual fresh8192 learning runs including fit/observer/ledger/checkpoint,12endpoint cases each, one6144frozenTRAINrisk each; prior setup1975.089738 separately retained; all earlier tests/numerics/probes/campaigns/simple suite additional, not repeated or erased'
for path in (R/'simple-cpu64-frontier9345-r2/summary.json',Path(s['setup_summary'])):s['artifact_sha256'][str(path)]=sha(path)
atomic_json(R/'fixed-basis-learning8192-summary.json',s)
print(json.dumps({'families':{f:{'loss':v['curve'][-1]['loss'],'by_length':v['curve'][-1]['by_length'],'last_doubling':v['last_doubling_relative_improvement'],'train':v['frozen_train']['objective'],'seconds':v['total_seconds'],'endpoint_max':v['endpoint']['max_ratio']} for f,v in s['families'].items()},'current_allocated_stage_seconds':s['current_allocated_stage_seconds']}),flush=True)
