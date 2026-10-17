from pathlib import Path
from dataclasses import asdict
import hashlib,json,time,torch
from famjet.config import load_config
from famjet.analysis.development import resolve_policy,execution_shape
from famjet.eval.isolation import source_identity
from famjet.train import identities,_reconstruct
from famjet.checkpoint import load_checkpoint
from famjet.data.development_cache import TrainingDrawCache
from famjet.data.feature_cache import TrainingFeatureCache
from famjet.artifacts import atomic_json
from famjet.provenance import canonical_hash
start=time.perf_counter();expected_package='ad542defda704e06dc9c88819b95afd6f483a882c792e82bf8c85dc27a6f6641';assert source_identity()==expected_package;docs=Path('docs/research');cl=json.loads((docs/'task18-fixed-basis-closure.json').read_text());summary=json.loads((docs/'task18-fixed-basis-operational-summary.json').read_text());mapped=0
for item in cl['promotions']:
 for key in ('source','destination'):assert hashlib.sha256(Path(item[key]).read_bytes()).hexdigest()==item['sha256'],item[key]
 mapped+=1
for p,sha in summary['inventory'].items():assert hashlib.sha256(Path(p).read_bytes()).hexdigest()==sha,p
for p in cl['bundles'][:2]:
 for r in json.loads(Path(p).read_text())['records']:
  raw=Path(r['source']).read_bytes();assert hashlib.sha256(raw).hexdigest()==r['sha256'] and json.loads(raw)==r['record'];mapped+=1
for r in json.loads(Path(cl['bundles'][2]).read_text())['manifests']:
 p=Path(r['source']);m=json.loads(p.read_text());assert hashlib.sha256(p.read_bytes()).hexdigest()==r['sha256'] and canonical_hash(m)==r['canonical_hash'] and len(m['entries'])==r['entry_count'] and {k:v for k,v in m.items() if k!='entries'}==r['record_without_entries'];mapped+=1
rows=[]
def diffs(a,b,p=''):
 if isinstance(a,dict) and isinstance(b,dict):return [z for k in sorted(a.keys()|b.keys()) for z in diffs(a.get(k),b.get(k),p+'.'+k)]
 return [] if a==b else [{'path':p,'before':a,'after':b}]
for f in ('jet','bank','multiscale'):
 path=Path(f'configs/development/{f}_fixed_cpu64_raw128_32768.yaml');c=load_config(path);old=load_config(Path(f'artifacts/task18/fixed-basis-preparation-{f}-r2/calibration.yaml'));delta=diffs(asdict(old),asdict(c));assert {r['path'] for r in delta}=={'.development.mode','.development.calibration_path','.development.calibration_hash'}
 policy=resolve_policy(c);assert policy['development']['mode']=='learning';idn,_=identities(old,resolve_policy(old));ckpath=Path(f'artifacts/task18/calibration-{f}-fixed-basis/training/checkpoint.pt');ck=load_checkpoint(ckpath,{**idn,'source':summary['source']});assert ck['completed_step']==2;model=_reconstruct(ck['model']);raw=TrainingDrawCache(c);raw_verification=raw.verification;del raw
 features=TrainingFeatureCache(c,model);assert len(features.entries)==6144;rows.append({'family':f,'config':str(path),'config_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'exact_config_delta':delta,'resolved_policy_hash':canonical_hash(policy),'raw_verification':raw_verification,'feature_verification':features.verification,'archival_checkpoint_sha256':hashlib.sha256(ckpath.read_bytes()).hexdigest(),'scope':'historical checkpoint inspected with recorded original source, never executable continuation; new real raw/feature guards scan every file; no generation/fit/update/evaluation'});del features,model,ck
record={'status':'promotion_maps_config_delta_real_policy_and_all_cache_file_guards_passed','package_hash':source_identity(),'package_unchanged':source_identity()==expected_package,'exact_copy_and_bundle_records_verified':mapped,'additional_original_inventory_mappings_verified':len(summary['inventory']),'configs':rows,'seconds':time.perf_counter()-start,'scientific_execution':'held for independent review/root release'};atomic_json(docs/'task18-fixed-basis-promotion-verification.json',record);print(json.dumps({k:v for k,v in record.items() if k!='configs'}),flush=True)
