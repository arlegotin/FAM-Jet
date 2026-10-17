from pathlib import Path
import subprocess,time,json,hashlib
from famjet.artifacts import atomic_json
from famjet.eval.splits import _write_immutable
from famjet.train import _source
out=Path('artifacts/task18/width128-learned-rate-cpu64-decimal-step2048');out.mkdir(exist_ok=False);start=time.perf_counter();records=[]
_write_immutable(out/'allocation.json',{'source':_source(),'helper_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'scope':'both final2048 learned-rate checkpoints; same12 training fixtures each; original1e-12; uniformDecimal60/80 regardless binary64 result','approved_procedure':'docs/research/task18-width128-learning-procedure.md','captured_gradients':'key,value,gate,logits; no separate captured raw dL/dr/sharedquery certification'})
for family in ('jet','bank'):
 tick=time.perf_counter();log=Path(f'artifacts/task18-evidence/width128-learned-rate-cpu64-fitted-{family}-step2048.txt')
 command=['.venv/bin/python','/tmp/task18_learned_numeric64.py',family,f'artifacts/task18/width128-learned-rate-cpu64-fitted-{family}-step2048','--config',f'configs/development/{family}_learned_cpu64_width128_32768.yaml','--checkpoint',f'artifacts/task18/learning-{family}-cpu64-width128-2048/training/checkpoint.pt','--step','2048']
 with log.open('w') as f:r=subprocess.run(command,stdout=f,stderr=subprocess.STDOUT)
 records.append({'kind':'fitted_binary64','family':family,'returncode':r.returncode,'seconds':time.perf_counter()-tick});atomic_json(out/'driver-progress.json',{'elapsed_seconds':time.perf_counter()-start,'records':records})
 if r.returncode:raise SystemExit(r.returncode)
 print(json.dumps({'family':family,'fitted':json.loads(Path(f'artifacts/task18/width128-learned-rate-cpu64-fitted-{family}-step2048/summary.json').read_text())}),flush=True)
for family in ('jet','bank'):
 for i in range(12):
  tick=time.perf_counter();log=Path(f'artifacts/task18-evidence/width128-learned-rate-cpu64-decimal-step2048-{family}-{i:02d}.txt')
  with log.open('w') as f:r=subprocess.run(['.venv/bin/python','/tmp/task18_decimal_checkpoint.py',family,str(i),'--input-root',f'artifacts/task18/width128-learned-rate-cpu64-fitted-{family}-step2048','--output-root',str(out)],stdout=f,stderr=subprocess.STDOUT)
  records.append({'kind':'decimal60_80','family':family,'ordinal':i,'returncode':r.returncode,'seconds':time.perf_counter()-tick});atomic_json(out/'driver-progress.json',{'elapsed_seconds':time.perf_counter()-start,'records':records})
  if r.returncode:raise SystemExit(r.returncode)
print(json.dumps({'status':'executed_all_cases','seconds':time.perf_counter()-start}),flush=True)
from decimal import Decimal
cases=[json.loads((out/f'{family}-{i:02d}/summary.json').read_text()) for family in ('jet','bank') for i in range(12)]
fitted={}
for family in ('jet','bank'):
 root=Path(f'artifacts/task18/width128-learned-rate-cpu64-fitted-{family}-step2048');rows=[json.loads(x) for x in (root/'cases.jsonl').read_text().splitlines()]
 checks=[{'ordinal':r['ordinal'],**m} for r in rows for m in r['metrics'] if m['name'].startswith(('task_','reader_')) or m['name'] in ('terminal_raw_features','stream_raw_features')]
 fitted[family]={'original_binary64_summary':json.loads((root/'summary.json').read_text()),'task_reader_and_production_features_max_ratio':max(m.get('max_pointwise_ratio',0.) for m in checks),'task_reader_and_production_features_failures':[m for m in checks if not m['accepted']]}
summary={'status':'passed_corrected_reference_and_fitted_task' if all(x['status']=='passed' for x in cases) and all(not f['task_reader_and_production_features_failures'] for f in fitted.values()) else 'failed_applicability','source':_source(),'cases':24,'tolerances':{'rtol':1e-12,'atol':1e-12},'families':{},'fitted':fitted,'driver_wall_seconds':time.perf_counter()-start,'case_compute_seconds':sum(c['total_seconds'] for c in cases),'max_case_rss_additional_bytes':max(c['rss_additional_bytes'] for c in cases),'max60vs80_absolute':str(max(Decimal(v['max_absolute60vs80']) for c in cases for v in c['convergence'].values())),'scope':'captured states/contractions/key/value/gate/logits and fitted task/reader checks; no captured raw dL/dr or independent sharedqueryinputs','artifact_hashes':{str(out/f'{family}-{i:02d}/summary.json'):hashlib.sha256((out/f'{family}-{i:02d}/summary.json').read_bytes()).hexdigest() for family in ('jet','bank') for i in range(12)}}
for family in ('jet','bank'):
 group=[c for c in cases if c['family']==family];summary['families'][family]={'max_pointwise_ratio':max(m['max_pointwise_ratio'] for c in group for m in c['metrics']),'failed_metrics':[{'ordinal':c['ordinal'],**m} for c in group for m in c['metrics'] if not m['accepted']]}
atomic_json(out/'summary.json',summary);print(json.dumps(summary),flush=True)
