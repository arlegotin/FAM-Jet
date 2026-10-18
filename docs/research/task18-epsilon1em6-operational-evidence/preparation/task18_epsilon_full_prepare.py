from pathlib import Path
from dataclasses import replace,asdict
from datetime import datetime,timezone
import argparse,json,hashlib,time,shutil,resource,platform,subprocess,torch,yaml
from task18_epsilon_full_gate import ROOT,preflight,raw_ok,prepared_ok,cold_ok,fitted_ok,fitted_case_ok
SEAL=preflight()
from task18_epsilon_full_config import config,EXPECTED,PACKAGE,static_inventory
from famjet.train import _source,make_model,move_episode,check_smoke_memory
from famjet.analysis.development import iter_fit_panel
from famjet.data.feature_cache import prepare_feature_cache,feature_identity
from famjet.provenance import canonical_hash
from famjet.artifacts import atomic_json
from famjet.eval.splits import _write_immutable
p=argparse.ArgumentParser();p.add_argument('family',choices=['jet','bank']);a=p.parse_args();family=a.family
raw_ok()
if family=='bank':fitted_ok('jet')
root=ROOT;out=root/f'prepare-{family}';out.mkdir(exist_ok=False);source=_source();assert source['commit']==EXPECTED and source['package_hash']==PACKAGE and not source['diff'] and not source['untracked_package_files']
torch.set_num_threads(4);rawpath=root/'raw-cache/manifest.json';raw=json.loads(rawpath.read_text());assert raw['status']=='complete';c=config(family);c=replace(c,development=replace(c.development,cache_manifest_path=str(rawpath),cache_manifest_hash=canonical_hash(raw)))
utc=datetime.now(timezone.utc);tick=time.perf_counter();factor=1 if platform.system()=='Darwin' else 1024;base=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*factor
assert shutil.disk_usage(root).free>=4*1024**3
feature_cap=193044480 if family=='jet' else 196190208
procedure={'bounded_probe_summary_sha256':hashlib.sha256(Path('artifacts/task18-evidence/epsilon1em6-probe-execution-9aca1b/complete-summary.json').read_bytes()).hexdigest(),'size_audit_summary_sha256':hashlib.sha256(Path('artifacts/task18/fixed-basis-feature-size-audit/summary.json').read_bytes()).hexdigest(),'retained_historical_failed_attempt':'artifacts/task18/fixed-basis-preparation-jet','source':source,'helper_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'config':asdict(c),'raw_manifest_hash':canonical_hash(raw),'scope':'approved768 training-only fit then6144 fixed-upstream features; no optimizer/dev fit','projected_feature_bytes':feature_cap,'output_reserve_bytes':1500000000,'free_disk_bytes':shutil.disk_usage(root).free,'utc_start':utc.isoformat(),'power_override':False,'power_start':subprocess.run(['pmset','-g','batt'],capture_output=True,text=True).stdout};_write_immutable(out/'procedure.json',procedure)
def peak():return max(0,resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*factor-base)
try:
 torch.manual_seed(c.seed);t=time.perf_counter();model=make_model(c);construction=time.perf_counter()-t;t=time.perf_counter();model.fit_statistics(lambda:(move_episode(ep,'cpu',dtype=torch.float64) for ep in iter_fit_panel(c)));fit=time.perf_counter()-t;check_smoke_memory(c,peak())
 assert canonical_hash(model.target_statistics)=='0cebf5f59f3b44f44875b73d582e6cb3c21a0ade54867edfabaebcab220dad21' and model.kernel.t_ref==1. and model.fit_provenance['history_count']==768
 actual_identity=feature_identity(c,model);assert actual_identity['version']==2 and actual_identity['read_policy']=={'epsilon':1e-6,'numerical_support_floor':1e-8};atomic_json(out/'feature-identity.json',actual_identity)
 fitrecord={'actual_constructor_executions':1,'construction_seconds':construction,'fit_seconds':fit,'target_statistics_hash':canonical_hash(model.target_statistics),'fit_provenance':model.fit_provenance,'target_statistics':model.target_statistics,'net_peak_bytes':peak(),'static_inventory':static_inventory(model,c)};atomic_json(out/'fit.json',fitrecord);print(json.dumps({'family':family,'stage':'fit_complete','seconds':fit,'net_peak_bytes':peak()}),flush=True)
 fp=prepare_feature_cache(c,model,root/f'features-{family}',projected_data_bytes=feature_cap,output_reserve_bytes=1500000000);fm=json.loads(fp.read_text());assert canonical_hash(fm['identity'])==canonical_hash(actual_identity);check_smoke_memory(c,peak());cc=replace(c,development=replace(c.development,feature_cache_manifest_path=str(fp),feature_cache_manifest_hash=canonical_hash(fm)))
 configpath=out/'calibration.yaml';assert not configpath.exists();configpath.open('x').write(yaml.safe_dump(asdict(cc),sort_keys=False));end=datetime.now(timezone.utc)
 record={'status':'prepared_fit_and_features_only','source':source,'family':family,'config_path':str(configpath),'config_sha256':hashlib.sha256(configpath.read_bytes()).hexdigest(),'raw_manifest_hash':canonical_hash(raw),'feature_manifest':str(fp),'feature_manifest_hash':canonical_hash(fm),'feature_bytes':fm['total_bytes'],'feature_seconds':fm['total_seconds'],'upstream_preparation_totals':fm['upstream_preparation_totals'],'fit_seconds':fit,'construction_seconds':construction,'net_peak_bytes':peak(),'perf_seconds':time.perf_counter()-tick,'utc_start':utc.isoformat(),'utc_end':end.isoformat(),'utc_seconds':(end-utc).total_seconds(),'free_disk_after_bytes':shutil.disk_usage(root).free,'power_end':subprocess.run(['pmset','-g','batt'],capture_output=True,text=True).stdout};atomic_json(out/'summary.json',record);print(json.dumps(record),flush=True)
except BaseException as exc:
 atomic_json(out/'failure.json',{'source':source,'error':str(exc),'type':type(exc).__name__,'perf_seconds':time.perf_counter()-tick,'net_peak_bytes':peak()});raise
