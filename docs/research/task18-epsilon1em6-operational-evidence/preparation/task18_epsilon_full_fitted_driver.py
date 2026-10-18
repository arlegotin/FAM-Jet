from pathlib import Path
from datetime import datetime,timezone
import argparse,subprocess,json,hashlib,time,os
from task18_epsilon_full_gate import ROOT,preflight,raw_ok,prepared_ok,cold_ok,fitted_ok,fitted_case_ok
SEAL=preflight()
from task18_epsilon_full_config import EXPECTED,PACKAGE
from famjet.train import _source
from famjet.artifacts import atomic_json
from famjet.eval.splits import _write_immutable
p=argparse.ArgumentParser();p.add_argument('family',choices=['jet','bank']);a=p.parse_args();source=_source();assert source['commit']==EXPECTED and source['package_hash']==PACKAGE and not source['diff'] and not source['untracked_package_files']
cold_ok(a.family)
out=Path(f'artifacts/task18/epsilon1em6-operational-c715479/fitted-{a.family}');out.mkdir(exist_ok=False);tick=time.perf_counter();utc=datetime.now(timezone.utc)
_write_immutable(out/'procedure.json',{'source':source,'helper_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'case_helper_sha256':hashlib.sha256(Path(str(Path(__file__).with_name('task18_epsilon_full_fitted.py'))).read_bytes()).hexdigest(),'scope':'all12cells atactual0/2; savedfits no rerun; no optimizer; fixedmemory composition via exact initial kernel/terminal/raw replay; original1e-12','utc_start':utc.isoformat(),'power_override':False});rows=[]
try:
 for step in (0,2):
  for ordinal in range(12):
   dest=out/f'step{step}-{ordinal:02d}'
   assert not dest.exists()
   with (out/f'step{step}-{ordinal:02d}.txt').open('x') as f:r=subprocess.run(['.venv/bin/python',str(Path(__file__).with_name('task18_epsilon_full_fitted.py')),a.family,str(ordinal),str(dest),'--step',str(step)],stdout=f,stderr=subprocess.STDOUT,env={**os.environ,'PYTHONPATH':'.:'+str(Path(__file__).parent)})
   assert r.returncode==0,(step,ordinal,r.returncode)
   summary=fitted_case_ok(a.family,step,ordinal);rows.append({'step':step,'ordinal':ordinal,'summary':str(dest/'summary.json'),'sha256':hashlib.sha256((dest/'summary.json').read_bytes()).hexdigest(),'max_ratio':max(m.get('max_pointwise_ratio',0) for m in summary['metrics']),'net_peak_bytes':summary['net_peak_bytes']});atomic_json(out/'progress.json',{'completed':rows})
 end=datetime.now(timezone.utc);record={'status':'all24_fitted_checkpoint_cells_passed','source':source,'family':a.family,'cases':rows,'max_ratio':max(r['max_ratio'] for r in rows),'max_case_net_peak_bytes':max(r['net_peak_bytes'] for r in rows),'perf_seconds':time.perf_counter()-tick,'utc_start':utc.isoformat(),'utc_end':end.isoformat(),'utc_seconds':(end-utc).total_seconds()};atomic_json(out/'summary.json',record);print(json.dumps(record),flush=True)
except BaseException as exc:
 atomic_json(out/'failure.json',{'source':source,'error':str(exc),'completed':len(rows),'perf_seconds':time.perf_counter()-tick});raise
