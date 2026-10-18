"""Bounded two-family probe sequencing; no fitted-cache authorization."""
from pathlib import Path
from datetime import datetime,timezone
import argparse,hashlib,json,os,subprocess,sys,time,uuid
from task18_checked_sequence import run_sequence

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def canonical(x):return hashlib.sha256(json.dumps(x,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def write_new(p,x):
 with Path(p).open('x') as f:json.dump(x,f,sort_keys=True,allow_nan=False);f.write('\n')
def power():
 r=subprocess.run(['/usr/bin/pmset','-g','batt'],capture_output=True,text=True)
 return {'returncode':r.returncode,'stdout':r.stdout,'stderr':r.stderr,'scope':'read-only; no override'}
def preflight(seal):
 assert subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()==seal['source_commit']
 assert not subprocess.check_output(['git','status','--porcelain'],text=True)
 files={str(p):sha(p) for p in sorted(Path('famjet').rglob('*.py'))};assert files==seal['package_files'] and canonical(files)==seal['package_hash']
 for n,r in seal['helpers'].items():assert sha(Path(__file__).with_name(n))==r['sha256']
 for p,r in seal['dependencies'].items():assert sha(p)==r['sha256']
 for family,c in seal['configs'].items():assert sha(c['source_path'])==c['source_sha256'] and canonical(c['config'])==c['config_hash']
 for key,r in seal['cases'].items():
  assert sha(r['summary_path'])==r['summary_sha256'];s=json.loads(Path(r['summary_path']).read_text())
  assert s['status']=='passed' and s['source']['commit']==seal['source_commit'] and s['source']['package_hash']==seal['package_hash']
  assert s['epsilon']==1e-6 and s['config_hash']==seal['configs'][s['family']]['config_hash'] and s['statistics_module_absent']
  assert s['history_id']==r['history_id'] and s['raw_hashes']==r['raw_hashes'] and all(m['accepted'] for m in s['metrics'])
 assert 'famjet.analysis.statistics' not in sys.modules

def verified(seal,seal_sha,family,run_id=None):
 out=Path(seal['output_root'])/family;s=json.loads((out/'summary.json').read_text());p=json.loads((out/'procedure.json').read_text())
 assert s['status']=='completed_bounded_structured_cost_probe_only' and s['family']==family and s['records']==12 and s['actual_constructor_executions']==1
 assert s['source']=={'commit':seal['source_commit'],'diff':'','package_hash':seal['package_hash'],'untracked_package_files':{}}
 assert s['seal_sha256']==seal_sha and p['seal_sha256']==seal_sha and s['run_id']==p['run_id'] and (run_id is None or s['run_id']==run_id)
 assert s['config_hash']==seal['configs'][family]['config_hash']==canonical(p['config']) and s['epsilon']==1e-6
 assert s['transport_read_policy']=={'epsilon':1e-6,'numerical_support_floor':1e-8} and s['fitted_cache_identity'] is None and s['statistics_module_absent']
 assert s['input_width']==(105 if family=='jet' else 113) and s['net_peak_bytes']<=seal['net_limit']
 assert s['procedure_sha256']==sha(out/'procedure.json') and s['records_sha256']==sha(out/'records.jsonl')
 for name in ('static-inventory','static-after','static-comparison'):assert s['artifact_hashes'][name]==sha(out/f'{name}.json')
 assert s['static_comparison']['semantic_owned_objects_equal'] and s['static_comparison']['tensor_storage_export_config_equal']
 rows=[json.loads(line) for line in (out/'records.jsonl').read_text().splitlines()];assert len(rows)==12
 for i,row in enumerate(rows):
  expected=seal['cases'][f'{family}-{i:02d}'];assert row['ordinal']==i and row['history_id']==expected['history_id'] and row['raw_hashes']==expected['raw_hashes']
  file=out/f'{i:02d}.pt';assert file.stat().st_size==row['bytes'] and sha(file)==row['sha256']
  assert row['values_shape']==[1,8,s['input_width']] and row['values_dtype']=='torch.float64' and row['net_peak_bytes']<=seal['net_limit']
 assert sum(r['bytes'] for r in rows)==s['actual_probe_bytes']
 return {'family':family,'summary_sha256':sha(out/'summary.json'),'run_id':s['run_id']}

def main():
 p=argparse.ArgumentParser();p.add_argument('--seal',required=True);p.add_argument('--seal-sha',required=True);a=p.parse_args();assert sha(a.seal)==a.seal_sha;seal=json.loads(Path(a.seal).read_text());preflight(seal)
 root=Path(seal['output_root']);assert not root.exists();run=root/'driver';run.mkdir(parents=True,exist_ok=False);tick=time.perf_counter();utc=datetime.now(timezone.utc);completed=[]
 write_new(run/'allocation.json',{'seal_sha256':a.seal_sha,'source_commit':seal['source_commit'],'package_hash':seal['package_hash'],'order':['jet','bank'],'power_before':power(),'utc_start':utc.isoformat(),'scope':'UNFITTED12 records/family only; no retry or later preparation','net_limit':seal['net_limit']})
 try:
  for family in ('jet','bank'):
   preflight(seal)
   for prior in completed:verified(seal,a.seal_sha,prior['family'],prior['run_id'])
   out=root/family;assert not out.exists();token=uuid.uuid4().hex
   cmd=[sys.executable,str(Path(__file__).with_name('task18_structured_epsilon_probe.py')),family,'--seal',a.seal,'--seal-sha',a.seal_sha,'--run-id',token]
   def execute(command):
    with (run/f'{family}.txt').open('x') as log:r=subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,env={**os.environ,'PYTHONPATH':'.:'+str(Path(__file__).parent)})
    if r.returncode==0:verified(seal,a.seal_sha,family,token)
    return r.returncode
   run_sequence([{'command':cmd,'summary':str(out/'summary.json'),'expected_status':'completed_bounded_structured_cost_probe_only'}],execute)
   completed.append(verified(seal,a.seal_sha,family,token));write_new(run/f'completed-{len(completed)}.json',{'completed':completed})
  after=power();end=datetime.now(timezone.utc);elapsed=time.perf_counter()-tick
  write_new(run/'summary.json',{'status':'passed','seal_sha256':a.seal_sha,'source_commit':seal['source_commit'],'package_hash':seal['package_hash'],'completed':completed,'perf_seconds':elapsed,'utc_start':utc.isoformat(),'utc_end':end.isoformat(),'utc_seconds':(end-utc).total_seconds(),'power_after':after,'next':'HELD; no full preparation or profiles'})
 except BaseException as exc:
  end=datetime.now(timezone.utc);elapsed=time.perf_counter()-tick
  write_new(run/'failure.json',{'status':'interrupted' if isinstance(exc,KeyboardInterrupt) else 'failed','type':type(exc).__name__,'error':str(exc),'completed':completed,'seal_sha256':a.seal_sha,'perf_seconds':elapsed,'utc_start':utc.isoformat(),'utc_end':end.isoformat(),'utc_seconds':(end-utc).total_seconds()});raise
if __name__=='__main__':main()
