"""One fresh paired learning allocation; fail closed before every dependent phase."""
from pathlib import Path
from datetime import datetime,timezone
import argparse,json,os,subprocess,sys,time,shutil
from task18_checked_sequence import run_sequence
from task18_epsilon_learning_gate import ROOT,PREP,preflight,config_ok,learning_ok,endpoint_ok,risk_ok,sha

def write_new(path,record):
 with Path(path).open('x') as f:json.dump(record,f,sort_keys=True,allow_nan=False);f.write('\n')
def power():
 r=subprocess.run(['/usr/bin/pmset','-g','batt'],capture_output=True,text=True)
 return {'returncode':r.returncode,'stdout':r.stdout,'stderr':r.stderr,'scope':'read-only; no power override'}
p=argparse.ArgumentParser();p.add_argument('--seal',required=True);p.add_argument('--seal-sha',required=True);a=p.parse_args();os.environ['TASK18_LEARN_SEAL']=a.seal;os.environ['TASK18_LEARN_SEAL_SHA']=a.seal_sha;s=preflight();assert not ROOT.exists();out=ROOT/'driver';out.mkdir(parents=True,exist_ok=False);start=time.perf_counter();utc=datetime.now(timezone.utc);rows=[]
steps=[(f,phase,ROOT/f'{directory}-{f}'/filename,status) for f in ('jet','bank') for phase,directory,filename,status in [('train','learn','development.json','completed'),('endpoint','endpoint','summary.json','all12_trained_endpoint_cells_passed'),('risk','risk','summary.json','completed')]]
write_new(out/'allocation.json',{'source_commit':s['source_commit'],'package_hash':s['package_hash'],'seal_sha256':a.seal_sha,'helper_sha256':sha(__file__),'stage_order':[[f,p] for f,p,*_ in steps],'utc_start':utc.isoformat(),'power_start':power(),'scope':'fresh Jet8192 then12 endpoint thenone6144TRAINrisk, then Bank same; no resume/extension/protected claim','forecast_seconds':[900,1100],'net_limit':201326592,'minimum_free_bytes':4294967296,'whole_group_wallcap_seconds':1800,'no_retry':True})
def verify(f,p):return {'train':learning_ok,'endpoint':endpoint_ok,'risk':risk_ok}[p](f)
try:
 for family,phase,summary,status in steps:
  preflight();assert shutil.disk_usage(ROOT).free>=4294967296;config_ok(family)
  if family=='bank':risk_ok('jet')
  if phase=='endpoint':learning_ok(family)
  if phase=='risk':endpoint_ok(family)
  assert not summary.parent.exists(),str(summary.parent)
  cmd=[sys.executable,str(Path(__file__).with_name(f'task18_epsilon_learning_{phase}.py')),family];tick=time.perf_counter();u=datetime.now(timezone.utc);power_start=power();write_new(out/f'{len(rows):02d}-{family}-{phase}-attempt.json',{'family':family,'phase':phase,'command':cmd,'utc_start':u.isoformat(),'completed':len(rows)})
  def execute(command):
   with (out/f'{family}-{phase}.txt').open('x') as log:r=subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,env={**os.environ,'PYTHONPATH':'.:'+str(Path(__file__).parent)})
   if r.returncode==0:verify(family,phase)
   return r.returncode
  run_sequence([{'command':cmd,'summary':str(summary),'expected_status':status}],execute)
  verify(family,phase);power_end=power();end=datetime.now(timezone.utc);elapsed=time.perf_counter()-tick;row={'family':family,'phase':phase,'status':status,'summary':str(summary),'summary_sha256':sha(summary),'perf_seconds':elapsed,'utc_start':u.isoformat(),'utc_end':end.isoformat(),'utc_seconds':(end-u).total_seconds(),'power_start':power_start,'power_end':power_end};rows.append(row);write_new(out/f'completed-{len(rows):02d}.json',row);print(json.dumps(row),flush=True)
 preflight();end=datetime.now(timezone.utc);write_new(out/'summary.json',{'status':'both_fresh8192_endpoint_and_TRAIN_risks_complete','source_commit':s['source_commit'],'package_hash':s['package_hash'],'seal_sha256':a.seal_sha,'stages':rows,'perf_seconds':time.perf_counter()-start,'utc_start':utc.isoformat(),'utc_end':end.isoformat(),'utc_seconds':(end-utc).total_seconds(),'scope':'exploratory; no convergence or protected acceptance'})
except BaseException as exc:
 end=datetime.now(timezone.utc);write_new(out/'failure.json',{'status':'interrupted' if isinstance(exc,KeyboardInterrupt) else 'failed','type':type(exc).__name__,'error':str(exc),'source_commit':s['source_commit'],'seal_sha256':a.seal_sha,'completed':rows,'perf_seconds':time.perf_counter()-start,'utc_start':utc.isoformat(),'utc_end':end.isoformat(),'utc_seconds':(end-utc).total_seconds()});raise
