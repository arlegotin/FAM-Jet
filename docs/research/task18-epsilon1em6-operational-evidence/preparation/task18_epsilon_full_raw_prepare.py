from pathlib import Path
from dataclasses import asdict
from datetime import datetime,timezone
import hashlib,json,time,shutil,torch,subprocess
from task18_epsilon_full_gate import ROOT,preflight,raw_ok,prepared_ok,cold_ok,fitted_ok,fitted_case_ok
SEAL=preflight()
from task18_epsilon_full_config import config,EXPECTED,PACKAGE,sha
from famjet.train import _source,check_smoke_memory
from famjet.data.development_cache import prepare_cache
from famjet.provenance import canonical_hash
from famjet.artifacts import atomic_json
from famjet.eval.splits import _write_immutable
root=ROOT;out=root/'raw-preparation';assert not out.exists()
source=_source();assert source['commit']==EXPECTED and source['package_hash']==PACKAGE and not source['diff'] and not source['untracked_package_files']
torch.set_num_threads(4);c=config('jet');oldpath=Path(SEAL['prior_raw_manifests'][0]['path']);old=json.loads(oldpath.read_text());free=shutil.disk_usage(root).free;assert free>=4*1024**3
reserve_total=2500000000;extra=reserve_total-old['total_bytes']-6144*2048;assert extra>0
out.mkdir();power_start=subprocess.run(['pmset','-g','batt'],capture_output=True,text=True).stdout;utc=datetime.now(timezone.utc);tick=time.perf_counter()
procedure={'allocation':'root2026-10-18 approved strict sharedraw then sequential JetBank768preparerfit/features+cold768/96stop2+all12fitted0/2; scientificlearningHELD','source':source,'helper_sha256':sha(__file__),'seal_sha256':__import__('os').environ['TASK18_FULL_SEAL_SHA'],'config_helper_sha256':sha(str(Path(__file__).with_name('task18_epsilon_full_config.py'))),'config':asdict(c),'old_manifest':str(oldpath),'old_manifest_hash':canonical_hash(old),'free_disk_bytes':free,'minimum_free_bytes':4*1024**3,'reserved_total_new_bytes':reserve_total,'raw_projection_bytes':old['total_bytes'],'additional_output_reserve_bytes':extra,'feature_caps':[193044480,196190208],'cost':'one shared raw generation, all prior costs/caches retained; both necessary fits per family charged','utc_start':utc.isoformat(),'power_override':False,'power_start':power_start};_write_immutable(out/'procedure.json',procedure)
try:
 path=prepare_cache(c,root/'raw-cache',projected_data_bytes=old['total_bytes'],output_reserve_bytes=extra)
 m=json.loads(path.read_text());prep=json.loads((path.parent/'preparation.json').read_text());keys=('ordinal','episode_id','length','regime','sha256','hashes','bytes');assert len(m['entries'])==6144;comparisons=[]
 for prior_record in SEAL['prior_raw_manifests']:
  priorpath=Path(prior_record['path']);assert sha(priorpath)==prior_record['sha256']
  if priorpath==path:continue
  prior=json.loads(priorpath.read_text())
  assert prior.get('status')=='complete' and len(prior.get('entries',[]))==6144
  assert all(all(a[k]==b[k] for k in keys) for a,b in zip(prior['entries'],m['entries'])),str(priorpath)
  comparisons.append({'path':str(priorpath),'manifest_hash':canonical_hash(prior),'all6144_ordered_ids_content_query_oracle_file_bytes_sha_equal':True})
 assert len(comparisons)==len(SEAL['prior_raw_manifests']);check_smoke_memory(c,prep['rss_highwater_additional_bytes']);power_end=subprocess.run(['pmset','-g','batt'],capture_output=True,text=True).stdout;elapsed=time.perf_counter()-tick;end=datetime.now(timezone.utc)
 record={'status':'complete_shared_strict_raw','source':source,'cache_manifest':str(path),'cache_manifest_hash':canonical_hash(m),'all_prior_comparisons':comparisons,'compared_fields':keys,'cache_total_bytes':m['total_bytes'],'cache_total_seconds':m['total_seconds'],'preparation':prep|{'entries':'omitted; actualpreparation.json retainsfullentries'},'perf_seconds':elapsed,'utc_start':utc.isoformat(),'utc_end':end.isoformat(),'utc_seconds':(end-utc).total_seconds(),'power_end':power_end,'next':'authorized Jet then Bank prepare/cold/fitted; learningheld'};atomic_json(out/'summary.json',record);print(json.dumps(record),flush=True)
except BaseException as exc:
 atomic_json(out/'failure.json',{'source':source,'error':str(exc),'type':type(exc).__name__,'perf_seconds':time.perf_counter()-tick,'utc_end':datetime.now(timezone.utc).isoformat()});raise
