from pathlib import Path
from datetime import datetime,timezone
import subprocess,json,hashlib,time,os
from task18_structured_fixed_numeric import EXPECTED,PACKAGE
from famjet.train import _source
from famjet.artifacts import atomic_json
from famjet.eval.splits import _write_immutable
root=Path('artifacts/task18');out=root/'structured-fixed-operational';out.mkdir(exist_ok=False);source=_source();assert source['commit']==EXPECTED and source['package_hash']==PACKAGE and not source['diff'] and not source['untracked_package_files'];raw=json.loads((root/'structured-fixed-raw-preparation/summary.json').read_text());assert raw['status']=='complete_shared_strict_raw' and raw['all_prior_comparisons']
start=time.perf_counter();utc=datetime.now(timezone.utc);helpers=['task18_structured_prepare.py','task18_structured_cold.py','task18_structured_fitted_driver.py','task18_structured_fitted.py'];procedure={'source':source,'scope':'rootapproved sequential Jet Bank preparer768fit+6144features then cold768/96/stop2 and all12fitted0/2; no scientific learning','helper_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'helpers':{h:hashlib.sha256((Path('/tmp')/h).read_bytes()).hexdigest() for h in helpers},'raw_summary_sha256':hashlib.sha256((root/'structured-fixed-raw-preparation/summary.json').read_bytes()).hexdigest(),'net_limit':201326592,'utc_start':utc.isoformat(),'power_override':False};_write_immutable(out/'procedure.json',procedure);rows=[]
try:
 for family in ('jet','bank'):
  for phase,helper in [('prepare',helpers[0]),('cold',helpers[1]),('fitted',helpers[2])]:
   power_start=subprocess.run(['pmset','-g','batt'],capture_output=True,text=True).stdout;t=time.perf_counter();u=datetime.now(timezone.utc);atomic_json(out/'current.json',{'family':family,'phase':phase,'utc_start':u.isoformat(),'completed':rows});log=out/f'{family}-{phase}.txt'
   with log.open('w') as f:r=subprocess.run(['.venv/bin/python',str(Path('/tmp')/helper),family],stdout=f,stderr=subprocess.STDOUT,env={**os.environ,'PYTHONPATH':'.:/tmp'})
   end=datetime.now(timezone.utc);row={'family':family,'phase':phase,'exit_code':r.returncode,'perf_seconds':time.perf_counter()-t,'utc_start':u.isoformat(),'utc_end':end.isoformat(),'utc_seconds':(end-u).total_seconds(),'log':str(log),'power_start':power_start,'power_end':subprocess.run(['pmset','-g','batt'],capture_output=True,text=True).stdout};rows.append(row);atomic_json(out/'progress.json',{'completed':rows});print(json.dumps(row),flush=True)
   if r.returncode:raise RuntimeError(f'{family} {phase} failed; subsequent families held')
 end=datetime.now(timezone.utc);atomic_json(out/'summary.json',{'status':'both_operational_profiles_and_fitted_checks_complete','source':source,'stages':rows,'perf_seconds':time.perf_counter()-start,'utc_start':utc.isoformat(),'utc_end':end.isoformat(),'utc_seconds':(end-utc).total_seconds(),'scientific_learning':'not authorized'})
except BaseException as exc:
 atomic_json(out/'failure.json',{'source':source,'error':str(exc),'completed':rows,'perf_seconds':time.perf_counter()-start});raise
