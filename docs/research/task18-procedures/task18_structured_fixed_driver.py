from pathlib import Path
from datetime import datetime,timezone
import subprocess,json,hashlib,time,os
from task18_structured_fixed_numeric import EXPECTED,PACKAGE,sha
from famjet.train import _source
from famjet.artifacts import atomic_json
from famjet.eval.splits import _write_immutable
source=_source();assert source['commit']==EXPECTED and source['package_hash']==PACKAGE and not source['diff'] and not source['untracked_package_files']
out=Path('artifacts/task18/structured-fixed-initial');tick=time.perf_counter();utc=datetime.now(timezone.utc)
first=out/'jet-00/summary.json';assert json.loads(first.read_text())['status']=='passed'
_write_immutable(out/'procedure.json',{'source':source,'helper_sha256':sha(__file__),'case_helper_sha256':sha('/tmp/task18_structured_fixed_numeric.py'),'scope':'all12cells each Jet and Bank NEW full structured feature/input/task/common-reader gradients; original pointwise1e-12; accepted old memory exact component/kernel/terminal/raw replay; no stream/Decimal/fullfit rerun','existing_first_case':{'file':str(first),'sha256':sha(first)},'utc_start':utc.isoformat(),'power_override':False});rows=[]
try:
 for family in ('jet','bank'):
  for ordinal in range(12):
   dest=out/f'{family}-{ordinal:02d}'
   if (family,ordinal)!=('jet',0):
    with (out/f'{family}-{ordinal:02d}.txt').open('w') as f:r=subprocess.run(['.venv/bin/python','/tmp/task18_structured_fixed_numeric.py',family,str(ordinal),str(dest)],stdout=f,stderr=subprocess.STDOUT,env={**os.environ,'PYTHONPATH':'.:/tmp'})
    assert r.returncode==0,(family,ordinal,r.returncode)
   summary=json.loads((dest/'summary.json').read_text());assert summary['status']=='passed',(family,ordinal,summary['status']);rows.append({'family':family,'ordinal':ordinal,'summary':str(dest/'summary.json'),'sha256':sha(dest/'summary.json'),'max_ratio':summary['max_ratio'],'net_peak_bytes':summary['net_peak_bytes'],'case_perf_seconds':summary['perf_seconds']});atomic_json(out/'progress.json',{'completed':rows})
 end=datetime.now(timezone.utc);record={'status':'all24_new_structured_cases_passed','source':source,'cases':rows,'max_ratio':max(r['max_ratio'] for r in rows),'max_case_net_peak_bytes':max(r['net_peak_bytes'] for r in rows),'driver_perf_seconds_excluding_prior_first_case':time.perf_counter()-tick,'all_case_perf_seconds':sum(r['case_perf_seconds'] for r in rows),'utc_start':utc.isoformat(),'utc_end':end.isoformat(),'utc_seconds':(end-utc).total_seconds()};atomic_json(out/'summary.json',record);print(json.dumps(record),flush=True)
except BaseException as exc:
 end=datetime.now(timezone.utc);atomic_json(out/'failure.json',{'source':source,'status':'interrupted' if isinstance(exc,KeyboardInterrupt) else 'failed','exception_type':type(exc).__name__,'error':str(exc),'completed':rows,'perf_seconds':time.perf_counter()-tick,'utc_start':utc.isoformat(),'utc_end':end.isoformat()});raise
