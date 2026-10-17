from pathlib import Path
from datetime import datetime,timezone
from decimal import Decimal
import subprocess,time,json,hashlib
from famjet.artifacts import atomic_json
from famjet.train import _source
from famjet.eval.splits import _write_immutable
start=time.perf_counter();utc=datetime.now(timezone.utc);records=[];out=Path('artifacts/task18/width128-decimal-step2');out.mkdir(exist_ok=False)
_write_immutable(out/'procedure.json',{'source':_source(),'helper_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'oracle_helper_sha256':hashlib.sha256(Path('/tmp/task18_decimal_checkpoint.py').read_bytes()).hexdigest(),'scope':'uniform60/80 Decimal all24 actualstep2 represented-rate captures, regardless binary64 outcome; original1e-12; no rawdLdr or sharedquery certification','checkpoint_sha256':{f:hashlib.sha256(Path(f'artifacts/task18/calibration-{f}-width128/training/checkpoint.pt').read_bytes()).hexdigest() for f in ('jet','bank')},'start_utc':utc.isoformat(),'power_override':False})
for family in ('jet','bank'):
 for i in range(12):
  tick=time.perf_counter();p=Path(f'artifacts/task18-evidence/width128-decimal-step2-{family}-{i:02d}.txt')
  with p.open('w') as target:r=subprocess.run(['.venv/bin/python','/tmp/task18_decimal_checkpoint.py',family,str(i),'--input-root',f'artifacts/task18/width128-fitted-{family}-step2','--output-root',str(out)],stdout=target,stderr=subprocess.STDOUT)
  records.append({'family':family,'ordinal':i,'exit_code':r.returncode,'subprocess_perf_seconds':time.perf_counter()-tick});atomic_json(out/'driver-progress.json',{'elapsed_seconds':time.perf_counter()-start,'records':records})
  if r.returncode:raise SystemExit(r.returncode)
cases=[json.loads((out/f'{f}-{i:02d}'/'summary.json').read_text()) for f in ('jet','bank') for i in range(12)];end=datetime.now(timezone.utc)
summary={'status':'passed' if all(c['status']=='passed' for c in cases) else 'failed','source':_source(),'cases':24,'families':{f:{'max_ratio':max(m['max_pointwise_ratio'] for c in cases if c['family']==f for m in c['metrics']),'failures':[m for c in cases if c['family']==f for m in c['metrics'] if not m['accepted']]} for f in ('jet','bank')},'max60vs80_absolute':str(max(Decimal(v['max_absolute60vs80']) for c in cases for v in c['convergence'].values())),'max_case_rss_additional_bytes':max(c['rss_additional_bytes'] for c in cases),'perf_counter_seconds':time.perf_counter()-start,'start_utc':utc.isoformat(),'end_utc':end.isoformat(),'utc_interval_seconds':(end-utc).total_seconds(),'case_summary_sha256':{str(out/f'{f}-{i:02d}'/'summary.json'):hashlib.sha256((out/f'{f}-{i:02d}'/'summary.json').read_bytes()).hexdigest() for f in ('jet','bank') for i in range(12)}};atomic_json(out/'summary.json',summary);print(json.dumps(summary),flush=True)
