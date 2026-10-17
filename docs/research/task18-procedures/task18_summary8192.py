from pathlib import Path
from collections import defaultdict
from datetime import datetime
import json,hashlib,math,statistics
from famjet.train import _source
from famjet.provenance import canonical_hash
from famjet.artifacts import atomic_json
R=Path('artifacts/task18')
def read(p):return json.loads(Path(p).read_text())
def rows(p):return [json.loads(x) for x in Path(p).read_text().splitlines()]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def mean(v):return math.fsum(v)/len(v)
def grouped(data):
 groups=defaultdict(list)
 for r in data:groups[r['length'],r['regime'],r['task'],r['history_id']].append(r['loss'])
 cells=defaultdict(list)
 for (n,g,t,h),v in groups.items():cells[n,g,t].append((h,mean(v)))
 slices={name:mean([mean([v for h,v in cell if test(h)]) for cell in cells.values()]) for name,test in [('full96',lambda h:True),('old48',lambda h:int(h.rsplit('-',1)[1])<4),('new48',lambda h:int(h.rsplit('-',1)[1])>=4)]}
 return {'slices':slices,'cells':[{'length':n,'regime':g,'task':t,'histories':len(v),'loss':mean([x[1] for x in v])} for (n,g,t),v in sorted(cells.items())]}
old=read(R/'learned-rate-cpu64-2048-summary.json');s={'status':'matched8192_exploratory_unconverged','source':_source(),'configured_horizon':32768,'actual_step':8192,'completed_passes':4,'corpus_unique_histories':6144,'development_histories':96,'fit_histories':768,'target_statistics_hash':old['target_statistics_hash'],'state_bytes_each':9345,'families':{},'artifact_sha256':{},'simple_scores_reused_from':str(R/'simple-cpu64-frontier9345-r2/summary.json'),'numerical_endpoint':read(R/'learned-rate-cpu64-decimal-step8192/summary.json'),'limitations':old['limitations']+['Civil elapsed and perf_counter differ materially during host sleep; perf_counter is not CPU time.','No automatic continuation beyond8192 allocated.']}
for f in ('jet','bank'):
 p=R/f'learning-{f}-cpu64-8192';d=read(p/'development.json');r=read(p/'training/run.json');curve=rows(p/'learning_curve.jsonl');t=rows(p/'training/timing.jsonl');num=read(R/f'learned-rate-cpu64-fitted-{f}-step8192/summary.json');risk=read(R/f'learned-cpu64-frozen-risk8192-{f}/summary.json');prior=read(R/f'learned-cpu64-frozen-risk2048-{f}/summary.json');assert d['status']=='completed' and r['completed_step']==8192 and d['source']==s['source'];assert r['corpus_progress']=={'completed_passes':4,'corpus_histories':6144,'pass_offset':0,'unique_histories':6144};assert len(t)==6144
 g=grouped(rows(p/'predictions-step8192.jsonl'));assert abs(g['slices']['full96']-curve[-1]['loss'])<1e-14
 pred=rows(p/'predictions-step8192.jsonl');check=sha(p/'training/checkpoint.pt');assert check==num['checkpoint_sha256']==risk['checkpoint_sha256'];assert risk['target_statistics_hash']==s['target_statistics_hash']
 fullcurve=old['families'][f]['curve']+[{'step':v['step'],'loss':v['loss'],'by_length':{n:a['loss'] for n,a in v['by_length'].items()},'observer_seconds':v['evaluation_seconds']} for v in curve if v['step']>2048]
 s['families'][f]={'curve':fullcurve,'final_grouped':g,'grouped4096':grouped(rows(p/'predictions-step4096.jsonl')),'last_doubling_relative_improvement':1-curve[-1]['loss']/curve[-2]['loss'],'frozen_training_risk':risk,'frozen_risk2048':prior['objective'],'frozen_risk_relative_improvement':1-risk['objective']/prior['objective'],'rates':num['rates'][0],'logits':num['logits'][0],'rates2048':old['families'][f]['final_rates'],'max_logit_change_since2048':max(abs(x-y) for x,y in zip(num['logits'][0],old['families'][f]['final_logits'])),'checkpoint_sha256':check,'parameters':curve[-1]['parameters'],'actual_budgets':r['actual_budgets'],'net_peak_bytes':d['rss_highwater_additional_bytes'],'development_perf_counter_seconds':d['total_seconds'],'training_perf_counter_seconds':r['total_seconds'],'training_start_utc':r['start_utc'],'training_end_utc':r['end_utc'],'training_utc_interval_seconds':(datetime.fromisoformat(r['end_utc'])-datetime.fromisoformat(r['start_utc'])).total_seconds(),'timing':{'steps':len(t),'median_update_seconds':statistics.median(v['seconds'] for v in t),'sum_update_seconds':sum(v['seconds'] for v in t),'delivery_seconds':sum(v['delivery_seconds'] for v in t),'forward_loss_seconds':sum(v['forward_loss_seconds'] for v in t),'backward_seconds':sum(v['backward_seconds'] for v in t),'actual_events':sum(v['events'] for v in t)},'data_hash':r['data_hash'],'policy_hash':r['policy_hash'],'config_hash':r['config_hash'],'consumed_order_hash':canonical_hash(r['consumed_episode_ids']),'manifest_hash':d['manifest_hash'],'failure_count':sum(v['failure'] for v in pred),'fallback_count':sum(v['fallback'] for v in pred),'nonfinite_count':sum(v['nonfinite'] for v in pred)}
 for a in [p/'development.json',p/'training/run.json',p/'training/timing.jsonl',p/'learning_curve.jsonl',p/'predictions-step8192.jsonl',R/f'learned-cpu64-frozen-risk8192-{f}/summary.json',R/f'learned-rate-cpu64-fitted-{f}-step8192/summary.json']:s['artifact_sha256'][str(a)]=sha(a)
for key in ('data_hash','consumed_order_hash','manifest_hash'):assert s['families']['jet'][key]==s['families']['bank'][key]
s['paired_loss_difference_jet_minus_bank']=s['families']['jet']['curve'][-1]['loss']-s['families']['bank']['curve'][-1]['loss'];s['performance_boundary_notice']='Historical fields named total_seconds or driver_wall_seconds use perf_counter. They are execution-clock intervals, not CPU seconds, and are not civil wall time when host sleeps. Original records preserved.'
s['external_time_boundaries']={p.name:read(p) for p in Path('artifacts/task18-evidence').glob('*8192*time-boundary.json')};s['sleep_evidence_sha256']=sha('artifacts/task18-evidence/learned-cpu64-8192-sleep-wake.txt')
atomic_json(R/'learned-rate-cpu64-8192-summary.json',s)
print(json.dumps({f:{'loss':v['curve'][-1]['loss'],'slices':v['final_grouped']['slices'],'last_doubling':v['last_doubling_relative_improvement'],'trainrisk':v['frozen_training_risk']['objective'],'trainrisk_improvement':v['frozen_risk_relative_improvement'],'perf_seconds':v['development_perf_counter_seconds'],'utc_seconds':v['training_utc_interval_seconds'],'rates':v['rates']} for f,v in s['families'].items()}))
