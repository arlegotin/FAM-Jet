from pathlib import Path
from datetime import datetime,timezone
import json,hashlib,subprocess,time
from famjet.train import _source
from famjet.artifacts import atomic_json
from famjet.eval.splits import _write_immutable
root=Path('artifacts/task18/fixed-basis-task-supplement');source=_source();start=time.perf_counter();utc=datetime.now(timezone.utc)
_write_immutable(root/'allocation.json',{'source':source,'helper_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'numeric_helper_sha256':hashlib.sha256(Path('/tmp/task18_fixed_basis_task_supplement.py').read_bytes()).hexdigest(),'scope':'root-approved supplemental fresh-reader/task composition ordinals1–11 each family at original1e-12; originalordinal0 retained; exact terminal/reference replay; no stream/Decimal/768fit','retained_jet01_sha256':hashlib.sha256((root/'jet-01/summary.json').read_bytes()).hexdigest(),'power_override':False,'utc_start':utc.isoformat()})
records=[]
for family in ('jet','bank','multiscale'):
 for i in range(1,12):
  out=root/f'{family}-{i:02d}'
  if family=='jet' and i==1:record=json.loads((out/'summary.json').read_text())
  else:
   with Path(f'artifacts/task18-evidence/fixed-basis-task-{family}-{i:02d}.txt').open('w') as log:r=subprocess.run(['.venv/bin/python','-u','/tmp/task18_fixed_basis_task_supplement.py',family,str(i),str(out)],stdout=log,stderr=subprocess.STDOUT)
   if r.returncode:
    atomic_json(root/'driver-failure.json',{'family':family,'ordinal':i,'returncode':r.returncode,'completed':records,'seconds':time.perf_counter()-start});raise SystemExit(r.returncode)
   record=json.loads((out/'summary.json').read_text())
  assert record['source']==source
  records.append({'family':family,'ordinal':i,'status':record['status'],'summary_sha256':hashlib.sha256((out/'summary.json').read_bytes()).hexdigest(),'seconds':record['perf_seconds'],'net_peak_bytes':record['net_peak_bytes'],'max_pointwise_ratio':max(m.get('max_pointwise_ratio',0) for m in record['metrics'])});atomic_json(root/'progress.json',{'records':records})
end=datetime.now(timezone.utc)
summary={'status':'passed' if all(x['status']=='passed' for x in records) else 'failed_original_tolerance','cases':records,'source':source,'perf_seconds':time.perf_counter()-start,'utc_start':utc.isoformat(),'utc_end':end.isoformat(),'utc_seconds':(end-utc).total_seconds(),'scope':'supplement33task/reader cases plus original3ordinal0 covers12cells per family; sharedproductionreader over independent memory features, not an independent MLP/query-input oracle'};atomic_json(root/'summary.json',summary);print(json.dumps(summary),flush=True)
