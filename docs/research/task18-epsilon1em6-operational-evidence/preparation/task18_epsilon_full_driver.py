"""One sealed operational chain; execution requires root allocation, no retries."""
from pathlib import Path
from datetime import datetime,timezone
import argparse,json,os,subprocess,sys,time,shutil
from task18_checked_sequence import run_sequence
from task18_epsilon_full_gate import ROOT,preflight,raw_ok,prepared_ok,cold_ok,fitted_ok,sha

def write_new(path,record):
 with Path(path).open('x') as f:json.dump(record,f,sort_keys=True,allow_nan=False);f.write('\n')
def power():
 r=subprocess.run(['/usr/bin/pmset','-g','batt'],capture_output=True,text=True)
 return {'returncode':r.returncode,'stdout':r.stdout,'stderr':r.stderr,'scope':'read-only; no wake/power override'}
p=argparse.ArgumentParser();p.add_argument('--seal',required=True);p.add_argument('--seal-sha',required=True);a=p.parse_args()
os.environ['TASK18_FULL_SEAL']=a.seal;os.environ['TASK18_FULL_SEAL_SHA']=a.seal_sha;s=preflight();assert not ROOT.exists();out=ROOT/'driver';out.mkdir(parents=True,exist_ok=False);start=time.perf_counter();utc=datetime.now(timezone.utc);rows=[]
steps=[('shared','raw','raw_prepare',ROOT/'raw-preparation/summary.json','complete_shared_strict_raw')]+[(f,phase,helper,ROOT/path/statusfile,status) for f in ('jet','bank') for phase,helper,path,statusfile,status in [('prepare','prepare',f'prepare-{f}','summary.json','prepared_fit_and_features_only'),('cold','cold',f'cold-{f}','development.json','completed'),('fitted','fitted_driver',f'fitted-{f}','summary.json','all24_fitted_checkpoint_cells_passed')]]
write_new(out/'allocation.json',{'source_commit':s['source_commit'],'package_hash':s['package_hash'],'seal_sha256':a.seal_sha,'helper_sha256':sha(__file__),'stage_order':[[f,p] for f,p,*_ in steps],'utc_start':utc.isoformat(),'power_start':power(),'scope':'shared strictRAW6144 thenJetBank each768preparerfit/features+cold768fit96devSTOP2+all12fitted0/2; no scientifictraining','forecast_seconds':[1080,1210],'net_limit':201326592,'minimum_free_bytes':4294967296,'new_stage_reserve_bytes':2500000000,'no_retry':True})
def verify(family,phase):
 if phase=='raw':return raw_ok()
 if phase=='prepare':return prepared_ok(family)
 if phase=='cold':return cold_ok(family)
 return fitted_ok(family)
try:
 for family,phase,helper,summary,status in steps:
  preflight();assert shutil.disk_usage(ROOT).free>=4294967296
  if family=='bank':fitted_ok('jet')
  if phase=='prepare':
   raw_ok();assert not (ROOT/f'features-{family}').exists()
  if phase=='cold':prepared_ok(family)
  if phase=='fitted':cold_ok(family)
  assert not summary.parent.exists(),str(summary.parent)
  if phase=='cold':assert not (ROOT/f'telemetry-{family}').exists()
  cmd=[sys.executable,str(Path(__file__).with_name(f'task18_epsilon_full_{helper}.py'))]+([] if family=='shared' else [family])
  tick=time.perf_counter();u=datetime.now(timezone.utc);power_start=power();attempt={'family':family,'phase':phase,'command':cmd,'utc_start':u.isoformat(),'completed':len(rows)};write_new(out/f'{len(rows):02d}-{family}-{phase}-attempt.json',attempt)
  def execute(command):
   with (out/f'{family}-{phase}.txt').open('x') as log:r=subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,env={**os.environ,'PYTHONPATH':'.:'+str(Path(__file__).parent)})
   if r.returncode==0:verify(family,phase)
   return r.returncode
  run_sequence([{'command':cmd,'summary':str(summary),'expected_status':status}],execute)
  verify(family,phase);power_end=power();end=datetime.now(timezone.utc);elapsed=time.perf_counter()-tick
  row={'family':family,'phase':phase,'status':status,'summary':str(summary),'summary_sha256':sha(summary),'perf_seconds':elapsed,'utc_start':u.isoformat(),'utc_end':end.isoformat(),'utc_seconds':(end-u).total_seconds(),'power_start':power_start,'power_end':power_end};rows.append(row);write_new(out/f'completed-{len(rows):02d}.json',row);print(json.dumps(row),flush=True)
 preflight();end=datetime.now(timezone.utc);elapsed=time.perf_counter()-start;write_new(out/'summary.json',{'status':'both_operational_profiles_and_fitted_checks_complete','source_commit':s['source_commit'],'package_hash':s['package_hash'],'seal_sha256':a.seal_sha,'stages':rows,'perf_seconds':elapsed,'utc_start':utc.isoformat(),'utc_end':end.isoformat(),'utc_seconds':(end-utc).total_seconds(),'scientific_learning':'NOT AUTHORIZED'})
except BaseException as exc:
 end=datetime.now(timezone.utc);elapsed=time.perf_counter()-start;write_new(out/'failure.json',{'status':'interrupted' if isinstance(exc,KeyboardInterrupt) else 'failed','type':type(exc).__name__,'error':str(exc),'source_commit':s['source_commit'],'seal_sha256':a.seal_sha,'completed':rows,'perf_seconds':elapsed,'utc_start':utc.isoformat(),'utc_end':end.isoformat(),'utc_seconds':(end-utc).total_seconds()});raise
