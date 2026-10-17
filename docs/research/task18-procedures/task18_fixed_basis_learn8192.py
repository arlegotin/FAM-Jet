from pathlib import Path
from datetime import datetime,timezone
import argparse,json,time,hashlib,subprocess
from famjet.config import load_config
from famjet.analysis.development import run_development
from famjet.eval.splits import _write_immutable
from famjet.artifacts import atomic_json
from famjet.train import _source
p=argparse.ArgumentParser();p.add_argument('family',choices=['jet','bank','multiscale']);a=p.parse_args();f=a.family
source=_source();assert source['commit']=='2def54622c5d9a49c84145739792a084494fbbe9' and not source['diff'] and not source['untracked_package_files'] and source['package_hash']=='ad542defda704e06dc9c88819b95afd6f483a882c792e82bf8c85dc27a6f6641'
cpath=Path(f'configs/development/{f}_fixed_cpu64_raw128_32768.yaml');c=load_config(cpath);assert c.training.optimizer_steps==32768 and c.development.mode=='learning'
out=Path(f'artifacts/task18/learning-{f}-fixed-cpu64-raw128-8192');procedure=Path('docs/research/task18-fixed-basis-procedure.md');allocation=Path(f'artifacts/task18-evidence/fixed-basis-learning-{f}-8192-allocation.json');clock=Path(f'artifacts/task18-evidence/fixed-basis-learning-{f}-8192-clock.json');utc=datetime.now(timezone.utc)
if out.exists():raise FileExistsError(f'fresh output directory already exists: {out}')
_write_immutable(allocation,{'source':source,'helper_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'procedure_sha256':hashlib.sha256(procedure.read_bytes()).hexdigest(),'config_sha256':hashlib.sha256(cpath.read_bytes()).hexdigest(),'configured_horizon':32768,'execution_stop':8192,'fresh':True,'no_resume':True,'net_limit_bytes':201326592,'power_override':False,'scope':'approved single three-family fixed-basis empirical-corpus comparison; no convergence/protected claim','utc_start':utc.isoformat(),'power_start':subprocess.run(['pmset','-g','batt'],capture_output=True,text=True).stdout})
start=time.perf_counter();status='running';exception_type=None
try:
 r=run_development(c,out,stop_at=8192);assert source==_source() and r['training_run']['completed_step']==8192;status='completed'
 print(json.dumps({'family':f,'status':r['status'],'step':8192,'loss':r['last_evaluation']['loss'],'run_seconds':r['total_seconds'],'external_perf_seconds':time.perf_counter()-start,'net_peak_bytes':r['rss_highwater_additional_bytes'],'checkpoint':r['checkpoint']}),flush=True)
except BaseException as exc:
 status='interrupted' if isinstance(exc,(KeyboardInterrupt,SystemExit)) else 'failed';exception_type=type(exc).__name__;raise
finally:
 end=datetime.now(timezone.utc);atomic_json(clock,{'source':source,'status':status,'exception_type':exception_type,'perf_seconds':time.perf_counter()-start,'utc_start':utc.isoformat(),'utc_end':end.isoformat(),'utc_seconds':(end-utc).total_seconds(),'power_end':subprocess.run(['pmset','-g','batt'],capture_output=True,text=True).stdout,'power_override':False})
