from pathlib import Path
from datetime import datetime,timezone
import json,hashlib,subprocess,time
from famjet.train import _source
from famjet.artifacts import atomic_json
from famjet.eval.splits import _write_immutable
root=Path('artifacts/task18/fixed-basis-initial');source=_source();start=time.perf_counter();utc=datetime.now(timezone.utc)
_write_immutable(root/'allocation.json',{'source':source,'helper_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'numeric_helper_sha256':hashlib.sha256(Path('/tmp/task18_fixed_basis_numeric.py').read_bytes()).hexdigest(),'scope':'approved12cells each Jet/Bank/logHiPPO; no fit or quality; source reviewed e756515; all original bounds','retained_jet00_sha256':hashlib.sha256((root/'jet-00/summary.json').read_bytes()).hexdigest(),'power_override':False,'utc_start':utc.isoformat()})
records=[]
for family in ('jet','bank','multiscale'):
 for i in range(12):
  out=root/f'{family}-{i:02d}'
  if family=='jet' and i==0:
   record=json.loads((out/'summary.json').read_text());assert record['source']==source
  else:
   tick=time.perf_counter()
   with Path(f'artifacts/task18-evidence/fixed-basis-initial-{family}-{i:02d}.txt').open('w') as log:
    r=subprocess.run(['.venv/bin/python','-u','/tmp/task18_fixed_basis_numeric.py',family,str(i),str(out)],stdout=log,stderr=subprocess.STDOUT)
   if r.returncode:
    atomic_json(root/'driver-failure.json',{'family':family,'ordinal':i,'returncode':r.returncode,'completed':records,'seconds':time.perf_counter()-start});raise SystemExit(r.returncode)
   record=json.loads((out/'summary.json').read_text())
  assert record['source']==source
  records.append({'family':family,'ordinal':i,'status':record['status'],'summary_sha256':hashlib.sha256((out/'summary.json').read_bytes()).hexdigest(),'seconds':record['perf_seconds'],'net_peak_bytes':record['net_peak_bytes']});atomic_json(root/'progress.json',{'records':records})
 # Report bounded family failure without changing candidate/reference or consuming probe allocation.
 family_rows=[x for x in records if x['family']==family]
 atomic_json(root/f'{family}-summary.json',{'family':family,'status':'passed' if all(x['status']=='passed' for x in family_rows) else 'failed_original_tolerance','cases':family_rows,'source':source})
end=datetime.now(timezone.utc)
summary={'status':'passed' if all(x['status']=='passed' for x in records) else 'failed_original_tolerance','cases':records,'source':source,'perf_seconds':time.perf_counter()-start,'utc_start':utc.isoformat(),'utc_end':end.isoformat(),'utc_seconds':(end-utc).total_seconds(),'scope':'initial numerical gate only; original fixed upstream memory + applicable fresh unfitted ordinal0 reader/task; no independent shared query-input/MLP oracle claim','authorized_after_pass':'bounded12record per family cost probe only; no full6144/768cold/scientific training'};atomic_json(root/'summary.json',summary);print(json.dumps(summary),flush=True)
