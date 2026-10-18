"""Explicit first-case/remaining23 launcher; execution still requires root allocation."""
from pathlib import Path
from datetime import datetime,timezone
import argparse,hashlib,json,os,subprocess,sys,time,uuid
from task18_checked_sequence import run_sequence

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def canonical(x):return hashlib.sha256(json.dumps(x,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def write_new(p,record):
 with Path(p).open('x') as f:json.dump(record,f,sort_keys=True,allow_nan=False);f.write('\n')
def power():
 r=subprocess.run(['/usr/bin/pmset','-g','batt'],capture_output=True,text=True)
 return {'returncode':r.returncode,'stdout':r.stdout,'stderr':r.stderr,'scope':'read-only snapshot; no wake/power override'}
def frozen(seal):
 assert subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()==seal['source_commit']
 assert not subprocess.check_output(['git','status','--porcelain'],text=True)
 files={str(p):sha(p) for p in sorted(Path('famjet').rglob('*.py'))}
 assert files==seal['package_files'] and canonical(files)==seal['package_hash']
 for name,r in seal['helpers'].items():assert sha(Path(__file__).with_name(name))==r['sha256']
 for path,r in seal['dependencies'].items():assert sha(path)==r['sha256']

def verified_summary(seal,seal_sha,family,ordinal,run_id=None):
 out=Path(seal['output_root'])/f'{family}-{ordinal:02d}';s=json.loads((out/'summary.json').read_text());p=json.loads((out/'procedure.json').read_text());expected=seal['cases'][f'{family}-{ordinal:02d}']
 assert s['status']=='passed' and s['case_count']==1 and s['statistics_module_absent'] is True
 assert s['source']=={'commit':seal['source_commit'],'diff':'','package_hash':seal['package_hash'],'untracked_package_files':{}}
 assert s['family']==family and s['ordinal']==ordinal and s['epsilon']==1e-6 and s['config_hash']==seal['configs'][family]['config_hash']
 assert s['preparation_seal_sha256']==seal_sha and p['preparation_seal_sha256']==seal_sha
 assert s['run_id']==p['run_id'] and (run_id is None or s['run_id']==run_id)
 assert s['history_id']==expected['history_id'] and s['raw_hashes']==expected['raw_hashes'] and s['events_hash']==expected['events_hash']
 assert s['fixed_kernel_hash']==expected['fixed_kernel_hash'] and s['origin_summary_sha256']==expected['origin_summary_sha256']
 assert s['procedure_sha256']==sha(out/'procedure.json') and s['capture_sha256']==sha(out/'new-structured-capture.pt')
 assert p['config_hash']==s['config_hash'] and canonical(p['config'])==s['config_hash'] and p['tolerances']==seal['tolerances']
 assert p['helper_sha256']==seal['helpers']['task18_structured_epsilon_numeric.py']['sha256']
 assert all(m['accepted'] for m in s['metrics'])
 assert all((m.get('atol'),m.get('rtol'))==(1e-12,1e-12) for m in s['metrics'] if m.get('scope')!='inactive_parameter')
 assert s['net_peak_bytes']<=seal['net_limit']
 return {'family':family,'ordinal':ordinal,'summary_sha256':sha(out/'summary.json'),'run_id':s['run_id']}

p=argparse.ArgumentParser();p.add_argument('stage',choices=['first','remaining']);p.add_argument('--seal',required=True);p.add_argument('--seal-sha',required=True);a=p.parse_args()
assert sha(a.seal)==a.seal_sha;seal=json.loads(Path(a.seal).read_text());frozen(seal)
root=Path(seal['output_root']);selected=[seal['first_case']] if a.stage=='first' else seal['remaining_order']
if a.stage=='remaining':
 first=json.loads((root/'driver-first/summary.json').read_text());assert first['status']=='passed' and first['stage']=='first' and first['completed']==1 and first['seal_sha256']==a.seal_sha
 verified_summary(seal,a.seal_sha,'jet',0,first['cases'][0]['run_id'])
else:assert not root.exists()
for f,i in selected:assert not (root/f'{f}-{i:02d}').exists()
run=root/f'driver-{a.stage}';run.mkdir(parents=True,exist_ok=False);tick=time.perf_counter();utc=datetime.now(timezone.utc);completed=[]
allocation={'stage':a.stage,'seal_sha256':a.seal_sha,'source_commit':seal['source_commit'],'package_hash':seal['package_hash'],'helper_sha256':sha(__file__),'cases':selected,'started_utc':utc.isoformat(),'power_before':power(),'scope':'only root-allocated stage; no automatic retry or next stage','previous_required':'fresh first case' if a.stage=='first' else 'verified first-case passing summary and driver','net_limit':seal['net_limit']};write_new(run/'allocation.json',allocation)
try:
 for family,ordinal in selected:
  frozen(seal)
  for prior in completed:verified_summary(seal,a.seal_sha,prior['family'],prior['ordinal'],prior['run_id'])
  out=root/f'{family}-{ordinal:02d}';assert not out.exists();token=uuid.uuid4().hex
  cmd=[sys.executable,str(Path(__file__).with_name('task18_structured_epsilon_numeric.py')),family,str(ordinal),str(out),'--seal',a.seal,'--seal-sha',a.seal_sha,'--run-id',token]
  def execute(command):
   with (run/f'{family}-{ordinal:02d}.txt').open('x') as log:
    result=subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,env={**os.environ,'PYTHONPATH':'.:'+str(Path(__file__).parent)})
   if result.returncode==0:verified_summary(seal,a.seal_sha,family,ordinal,token)
   return result.returncode
  run_sequence([{'command':cmd,'summary':str(out/'summary.json'),'expected_status':'passed'}],execute)
  completed.append(verified_summary(seal,a.seal_sha,family,ordinal,token))
  write_new(run/f'completed-{len(completed):02d}.json',{'completed':len(completed),'cases':completed})
 end=datetime.now(timezone.utc);write_new(run/'summary.json',{'status':'passed','stage':a.stage,'seal_sha256':a.seal_sha,'source_commit':seal['source_commit'],'package_hash':seal['package_hash'],'completed':len(completed),'cases':completed,'perf_seconds':time.perf_counter()-tick,'utc_start':utc.isoformat(),'utc_end':end.isoformat(),'utc_seconds':(end-utc).total_seconds(),'power_after':power(),'next_stage':'held_pending_root_ruling'})
except BaseException as exc:
 end=datetime.now(timezone.utc);write_new(run/'failure.json',{'status':'interrupted' if isinstance(exc,KeyboardInterrupt) else 'failed','type':type(exc).__name__,'message':str(exc),'stage':a.stage,'seal_sha256':a.seal_sha,'completed':len(completed),'cases':completed,'perf_seconds':time.perf_counter()-tick,'utc_start':utc.isoformat(),'utc_end':end.isoformat(),'utc_seconds':(end-utc).total_seconds(),'power_after':power()});raise
