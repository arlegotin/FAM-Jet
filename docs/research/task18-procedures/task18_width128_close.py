from pathlib import Path
import json,hashlib
from famjet.train import _source
from famjet.artifacts import atomic_json
out=Path('artifacts/task18/width128-profile-closure');out.mkdir(exist_ok=False)
files={}
def read(p):
 p=Path(p);files[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest();return json.loads(p.read_text())
def rows(p):
 p=Path(p);files[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest();return [json.loads(x) for x in p.read_text().splitlines()]
source=_source();assert source['commit']=='321b01b4059469375c11f63b021800465b85defa' and source['diff']==''
summary={'source':source,'scope':'operational width128 CPU64 learned-rate profile only; no sustained quality evidence','state_bytes_each':9345,'net_cap_bytes':201326592,'families':{},'preparation':read('artifacts/task18/width128-preparation/summary.json'),'initial_uniform':read('artifacts/task18/width128-initial-gate/summary.json'),'initial_small_reader':read('artifacts/task18/width128-initial-reader/summary.json'),'step2_uniform':read('artifacts/task18/width128-decimal-step2/summary.json'),'helper_recovery':read('artifacts/task18-evidence/width128-fitted-helper-recovery.json')}
for f in ['jet','bank']:
 d=read(f'artifacts/task18/calibration-{f}-width128/development.json');v=read(f'artifacts/task18/width128-verification-{f}-r2/summary.json');t=rows(f'artifacts/task18/calibration-{f}-width128/training/timing.jsonl');st=rows(f'artifacts/task18/telemetry-{f}-width128/stages.jsonl');clock=read(f'artifacts/task18-evidence/width128-cold-{f}-time-boundary.json')
 assert d['source']==source and d['status']=='completed' and d['training_run']['completed_step']==2 and d['rss_highwater_additional_bytes']<=201326592
 assert all(c['accepted'] for c in v['checks'].values())
 summary['families'][f]={'configured_horizon':32768,'executed_steps':2,'cold_profile_perf_seconds':d['total_seconds'],'external_clock':clock,'net_peak_bytes':d['rss_highwater_additional_bytes'],'profile_recorded_disk_boundary_bytes':d['disk_bytes'],'fit_provenance':d['training_run']['preprocessing']['fit_provenance'],'preprocessing_seconds':d['training_run']['preprocessing_seconds'],'cache_verification':d['training_run']['cache_verification'],'update_timings':t,'telemetry':st,'verified_checkpoints':v['verified'],'fitted_checks':{k:{'accepted':x['accepted'],'max_ratio':x['max_ratio'],'binary64_memory_status':x['original_binary64_summary']['status']} for k,x in v['checks'].items()},'fitted_verification_perf_seconds':v['seconds']}
 read(f'artifacts/task18/width128-verification-{f}-r2/step0-reference-composition.json')
for p in ['artifacts/task18-evidence/width128-fitted-jet-time-boundary.json','artifacts/task18-evidence/width128-fitted-jet-r2-time-boundary.json','artifacts/task18-evidence/width128-fitted-bank-r2-time-boundary.json','artifacts/task18-evidence/width128-decimal2-time-boundary.json']:read(p)
assert summary['step2_uniform']['status']=='passed'
summary['status']='all_profile_and_applicable_numerical_gates_passed_no_scientific_allocation'
summary['scope_limits']=['two updates do not demonstrate sustained resource stability or convergence','memory reference scope captured states/contractions/key/value/gate/logit gradients; no separately captured raw dL/dr or independent shared query_inputs oracle','small initial reader and actual fitted step0/2 checks are separate','original binary64 reference misses retained beside uniformly applied Decimal60/80','target scale residual uncertainty remains; all96 development exposed','performance timers and UTC kept separate; no power override; current conditions not thermal guarantee']
atomic_json(out/'summary.json',summary);atomic_json(out/'inventory.json',{'source':source,'files':files,'summary_sha256':hashlib.sha256((out/'summary.json').read_bytes()).hexdigest()})
print(json.dumps({'status':summary['status'],'summary':str(out/'summary.json'),'summary_sha256':hashlib.sha256((out/'summary.json').read_bytes()).hexdigest(),'files':len(files)}))
