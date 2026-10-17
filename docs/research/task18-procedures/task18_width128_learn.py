from pathlib import Path
import argparse,json,time,hashlib
from famjet.config import load_config
from famjet.analysis.development import run_development
from famjet.eval.splits import _write_immutable
from famjet.train import _source
p=argparse.ArgumentParser();p.add_argument('family',choices=['jet','bank']);a=p.parse_args();f=a.family
source=_source();assert source['commit']=='ddb55b7748e1a55dcfb1535bada6175156ae7fc7' and source['diff']=='' and source['package_hash']=='3a54cb7201bd8a0a888dcfa4ee09c9de581fcbab720882815a243f4c389f7bf8'
cpath=Path(f'configs/development/{f}_learned_cpu64_width128_32768.yaml');c=load_config(cpath);out=Path(f'artifacts/task18/learning-{f}-cpu64-width128-2048');procedure=Path('docs/research/task18-width128-learning-procedure.md')
_write_immutable(Path(f'artifacts/task18-evidence/width128-learning-{f}-allocation.json'),{'source':source,'helper_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'procedure_sha256':hashlib.sha256(procedure.read_bytes()).hexdigest(),'config_sha256':hashlib.sha256(cpath.read_bytes()).hexdigest(),'configured_horizon':32768,'execution_stop':2048,'fresh':True,'no_resume':True,'net_limit_bytes':201326592,'power_override':False,'scope':'single approved paired reader-width frontier, not convergence or protected inference'})
start=time.perf_counter();r=run_development(c,out,stop_at=2048);assert source==_source();assert r['training_run']['completed_step']==2048
print(json.dumps({'family':f,'status':r['status'],'step':2048,'loss':r['last_evaluation']['loss'],'profile_seconds':r['total_seconds'],'external_perf_seconds':time.perf_counter()-start,'net_peak_bytes':r['rss_highwater_additional_bytes'],'checkpoint':r['checkpoint']}),flush=True)
