from pathlib import Path
from dataclasses import asdict
from datetime import datetime,timezone
import hashlib,json,time,shutil,torch,subprocess
from task18_fixed_basis_numeric import config,EXPECTED,PACKAGE
from famjet.train import _source,check_smoke_memory
from famjet.data.development_cache import prepare_cache
from famjet.provenance import canonical_hash
from famjet.artifacts import atomic_json
from famjet.eval.splits import _write_immutable
root=Path('artifacts/task18');out=root/'fixed-basis-raw-preparation';out.mkdir(exist_ok=False)
source=_source();assert source['commit']==EXPECTED and source['package_hash']==PACKAGE and not source['diff'] and not source['untracked_package_files']
torch.set_num_threads(4);c=config('jet');oldpath=root/'cache-width128-6144/manifest.json';old=json.loads(oldpath.read_text());free=shutil.disk_usage(root).free;assert free>=4*1024**3
reserve_total=2500000000;extra=reserve_total-old['total_bytes']-6144*2048;assert extra>0
utc=datetime.now(timezone.utc);tick=time.perf_counter()
procedure={'allocation':'root RAW ONLY release 2026-10-18; full family fit/features/profiles/learning held','source':source,'helper_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'config_helper_sha256':hashlib.sha256(Path('/tmp/task18_fixed_basis_numeric.py').read_bytes()).hexdigest(),'config':asdict(c),'old_manifest':str(oldpath),'old_manifest_hash':canonical_hash(old),'free_disk_bytes':free,'minimum_free_bytes':4*1024**3,'reserved_total_new_bytes':reserve_total,'raw_projection_bytes':old['total_bytes'],'additional_output_reserve_bytes':extra,'cost':'shared raw generation counted once, all historical preparations retained','utc_start':utc.isoformat(),'power_override':False,'power_start':subprocess.run(['pmset','-g','batt'],capture_output=True,text=True).stdout}
_write_immutable(out/'procedure.json',procedure)
try:
 path=prepare_cache(c,root/'cache-fixed-basis-6144',projected_data_bytes=old['total_bytes'],output_reserve_bytes=extra)
 m=json.loads(path.read_text());prep=json.loads((path.parent/'preparation.json').read_text());keys=('ordinal','episode_id','length','regime','sha256','hashes','bytes');assert len(m['entries'])==len(old['entries'])==6144
 same=all(all(a[k]==b[k] for k in keys) for a,b in zip(old['entries'],m['entries']));assert same
 check_smoke_memory(c,prep['rss_highwater_additional_bytes']);end=datetime.now(timezone.utc)
 record={'status':'complete_raw_only','source':source,'cache_manifest':str(path),'cache_manifest_hash':canonical_hash(m),'same6144_ordered_content_and_file_hashes':same,'compared_fields':keys,'cache_total_bytes':m['total_bytes'],'cache_total_seconds':m['total_seconds'],'preparation':prep | {'entries':'omitted; retained in actual preparation.json'},'perf_seconds':time.perf_counter()-tick,'utc_start':utc.isoformat(),'utc_end':end.isoformat(),'utc_seconds':(end-utc).total_seconds(),'power_end':subprocess.run(['pmset','-g','batt'],capture_output=True,text=True).stdout,'next':'family fits/features/profiles remain held pending root ruling'}
 atomic_json(out/'summary.json',record);print(json.dumps(record),flush=True)
except BaseException as exc:
 atomic_json(out/'failure.json',{'source':source,'error':str(exc),'type':type(exc).__name__,'perf_seconds':time.perf_counter()-tick,'utc_end':datetime.now(timezone.utc).isoformat()});raise
