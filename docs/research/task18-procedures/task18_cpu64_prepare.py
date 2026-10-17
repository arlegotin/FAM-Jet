from pathlib import Path
from dataclasses import replace,asdict
import json,hashlib,time,shutil,yaml,torch
from famjet.config import load_config
from famjet.data.development_cache import prepare_cache
from famjet.provenance import canonical_hash
from famjet.train import _source
from famjet.artifacts import atomic_json
from famjet.eval.splits import _write_immutable
root=Path('artifacts/task18');out=root/'learned-rate-cpu64-preparation';out.mkdir(exist_ok=False);torch.set_num_threads(4)
# Gate record is created only after root accepts the reviewed corrected reference.
gate=json.loads((root/'learned-rate-cpu64-decimal-full/accepted-gate.json').read_text());assert gate['status']=='accepted_initial_numerical_and_source_gates' and gate['source']==_source()
c=load_config(Path('configs/development/jet_finite_raw_32768.yaml'));c=replace(c,model=replace(c.model,precision='float64',rates=replace(c.model.rates,mode='learned',bounds=(1/5224,1.))),development=replace(c.development,mode='calibration',fit_histories_per_cell=64,eval_histories_per_cell=8,milestones=(0,128,512,1024,2048,4096,8192,16384,32768),cache_manifest_path=None,cache_manifest_hash=None,feature_cache_manifest_path=None,feature_cache_manifest_hash=None,calibration_path=None,calibration_hash=None))
oldpath=root/'cache-finite6144/manifest.json';old=json.loads(oldpath.read_text());caldirs=[root/f'calibration-{family}-finite-raw' for family in ('jet','bank')];oldoutputs={str(p):sum(f.stat().st_size for f in p.rglob('*') if f.is_file()) for p in caldirs};assert all(oldoutputs.values())
# Four times each measured corresponding cold output: two times panel count,
# two times floating representation, conservative for JSON metadata and copies.
reserve=4*sum(oldoutputs.values());previous=[root/name for name in ('cache-fresh6144','cache-fresh6144-streamfit','cache-finite6144')];retained={str(p):sum(f.stat().st_size for f in p.iterdir() if f.is_file()) for p in previous}
procedure={'source':_source(),'helper_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'config':asdict(c),'gate':gate,'old_manifest':str(oldpath),'old_manifest_hash':canonical_hash(old),'projected_data_bytes':old['total_bytes'],'projection_basis':'same6144 exact generator payload bytes with changed source manifest','measured_prior_cold_output_bytes':oldoutputs,'output_reserve_bytes':reserve,'reserve_basis':'4x sum prior corresponding cold output files (2x panel,2x numeric bytes)','retained_old_cache_actual_bytes':retained,'free_disk_bytes':shutil.disk_usage(root).free,'cost':'full preparation charged once campaign aggregate, any later amortization explicit'}
_write_immutable(out/'procedure.json',procedure);tick=time.perf_counter();path=prepare_cache(c,root/'cache-learned-cpu64-6144',projected_data_bytes=old['total_bytes'],output_reserve_bytes=reserve);m=json.loads(path.read_text());keys=('ordinal','episode_id','length','regime','sha256','hashes','bytes');assert len(m['entries'])==len(old['entries'])==6144
same=all(all(a[k]==b[k] for k in keys) for a,b in zip(old['entries'],m['entries']));assert same
configs={}
for family in ('jet','bank'):
 cc=replace(c,model=replace(c.model,method=family,J=4 if family=='jet' else 8),development=replace(c.development,cache_manifest_path=str(path),cache_manifest_hash=canonical_hash(m)))
 p=out/f'calibration-{family}.yaml';p.write_text(yaml.safe_dump(asdict(cc),sort_keys=False));configs[family]={'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
record={'source':_source(),'status':'complete','helper_total_seconds':time.perf_counter()-tick,'cache_manifest':str(path),'cache_manifest_hash':canonical_hash(m),'same6144_ordered_content_and_file_hashes':same,'compared_fields':keys,'cache_total_seconds':m['total_seconds'],'cache_total_bytes':m['total_bytes'],'configs':configs};atomic_json(out/'summary.json',record);print(json.dumps(record),flush=True)
