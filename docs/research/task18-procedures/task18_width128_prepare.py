from pathlib import Path
from dataclasses import replace,asdict
from datetime import datetime,timezone
import json,hashlib,time,shutil,yaml,torch,math
from famjet.config import load_config
from famjet.data.development_cache import prepare_cache
from famjet.provenance import canonical_hash
from famjet.train import _source
from famjet.artifacts import atomic_json
from famjet.eval.splits import _write_immutable
root=Path('artifacts/task18');out=root/'width128-preparation';out.mkdir(exist_ok=False);torch.set_num_threads(4)
gate=json.loads((root/'width128-initial-gate/accepted-gate.json').read_text());assert gate['status']=='accepted_initial_numerical_and_source_gates' and gate['source']==_source()
c=load_config(Path('configs/development/jet_learned_cpu64_raw_32768.yaml'));c=replace(c,model=replace(c.model,reader=replace(c.model.reader,width=128)),development=replace(c.development,mode='calibration',cache_manifest_path=None,cache_manifest_hash=None,feature_cache_manifest_path=None,feature_cache_manifest_hash=None,calibration_path=None,calibration_hash=None))
oldpath=root/'cache-learned-cpu64-6144/manifest.json';old=json.loads(oldpath.read_text());caldirs=[root/f'calibration-{family}-learned-cpu64' for family in ('jet','bank')];oldoutputs={str(p):sum(f.stat().st_size for f in p.rglob('*') if f.is_file()) for p in caldirs};assert all(oldoutputs.values());reserve=math.ceil(30225/11025)*sum(oldoutputs.values());previous=[root/name for name in ('cache-fresh6144','cache-fresh6144-streamfit','cache-finite6144','cache-learned-cpu64-6144')];retained={str(p):sum(f.stat().st_size for f in p.iterdir() if f.is_file()) for p in previous}
procedure={'source':_source(),'helper_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'config':asdict(c),'gate':gate,'old_manifest':str(oldpath),'old_manifest_hash':canonical_hash(old),'projected_data_bytes':old['total_bytes'],'projection_basis':'same6144 exact generator payload bytes, source identity changes only; all prior copies retained','measured_prior_cold_output_bytes':oldoutputs,'output_reserve_bytes':reserve,'reserve_basis':'ceil(30225/11025)=3 times sum measured prior corresponding fullcold output bytes; conservative reader parameter growth','retained_old_cache_actual_bytes':retained,'free_disk_bytes':shutil.disk_usage(root).free,'cost':'full source-specific preparation separately charged, no hidden amortization','start_utc':datetime.now(timezone.utc).isoformat(),'power_override':False}
_write_immutable(out/'procedure.json',procedure);tick=time.perf_counter();path=prepare_cache(c,root/'cache-width128-6144',projected_data_bytes=old['total_bytes'],output_reserve_bytes=reserve);m=json.loads(path.read_text());keys=('ordinal','episode_id','length','regime','sha256','hashes','bytes');assert len(m['entries'])==len(old['entries'])==6144;same=all(all(a[k]==b[k] for k in keys) for a,b in zip(old['entries'],m['entries']));assert same
configs={}
for family in ('jet','bank'):
 cc=replace(c,model=replace(c.model,method=family,J=4 if family=='jet' else 8),development=replace(c.development,cache_manifest_path=str(path),cache_manifest_hash=canonical_hash(m)));p=out/f'calibration-{family}.yaml';p.write_text(yaml.safe_dump(asdict(cc),sort_keys=False));configs[family]={'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
record={'source':_source(),'status':'complete','helper_total_perf_counter_seconds':time.perf_counter()-tick,'start_utc':procedure['start_utc'],'end_utc':datetime.now(timezone.utc).isoformat(),'cache_manifest':str(path),'cache_manifest_hash':canonical_hash(m),'same6144_ordered_content_and_file_hashes':same,'compared_fields':keys,'cache_total_seconds':m['total_seconds'],'cache_total_bytes':m['total_bytes'],'configs':configs};atomic_json(out/'summary.json',record);print(json.dumps(record),flush=True)
