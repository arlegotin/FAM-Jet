from pathlib import Path
import subprocess,time,json
from famjet.artifacts import atomic_json
start=time.perf_counter();records=[];out=Path('artifacts/task18/learned-rate-cpu64-decimal-step2');out.mkdir(exist_ok=False)
for family in ('jet','bank'):
 for i in range(12):
  tick=time.perf_counter();p=Path(f'artifacts/task18-evidence/learned-rate-cpu64-decimal-step2-{family}-{i:02d}.txt')
  with p.open('w') as f:r=subprocess.run(['.venv/bin/python','/tmp/task18_decimal_checkpoint.py',family,str(i),'--input-root',f'artifacts/task18/learned-rate-cpu64-fitted-{family}-step2','--output-root',str(out)],stdout=f,stderr=subprocess.STDOUT)
  records.append({'family':family,'ordinal':i,'exit_code':r.returncode,'subprocess_wall_seconds':time.perf_counter()-tick});atomic_json(out/'driver-progress.json',{'elapsed_seconds':time.perf_counter()-start,'records':records})
  if r.returncode:raise SystemExit(r.returncode)
print(json.dumps({'driver_seconds':time.perf_counter()-start,'records':records}))
