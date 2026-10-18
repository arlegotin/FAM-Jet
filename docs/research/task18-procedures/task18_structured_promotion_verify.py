from pathlib import Path
from dataclasses import asdict
import hashlib,json,subprocess,time
from famjet.train import _source
from famjet.analysis.development import resolve_policy,execution_shape
from famjet.config import load_config
from famjet.provenance import canonical_hash
from famjet.artifacts import atomic_json
start=time.perf_counter();root=Path('artifacts/task18');docs=Path('docs/research');source=_source();assert source['package_hash']=='18785561574bfb4d246f703bc1e2caff9f7764ff0b0d8d7f641bef978f4957e0'
closure=json.loads((docs/'task18-structured-fixed-closure.json').read_text());copies=0;bundles=0
for row in closure['promotions']:
 a,b=Path(row['source']),Path(row['destination']);assert hashlib.sha256(a.read_bytes()).hexdigest()==row['sha256'] and a.read_bytes()==b.read_bytes();copies+=1
for path in closure['bundles']:
 b=json.loads(Path(path).read_text())
 for row in b.get('records',[]):
  p=Path(row['source']);assert hashlib.sha256(p.read_bytes()).hexdigest()==row['sha256'] and json.loads(p.read_text())==row['record'];bundles+=1
 for row in b.get('manifests',[]):
  p=Path(row['source']);m=json.loads(p.read_text());assert hashlib.sha256(p.read_bytes()).hexdigest()==row['sha256'] and canonical_hash(m)==row['canonical_hash'] and len(m['entries'])==row['entry_count'];bundles+=1
summary=json.loads((docs/'task18-structured-fixed-operational-summary.json').read_text())
for p,h in summary['inventory'].items():assert hashlib.sha256(Path(p).read_bytes()).hexdigest()==h
cal=json.loads((docs/'task18-cpu-calibration-structured-fixed.json').read_text());assert canonical_hash(cal)==closure['calibration_hash'];checks=[]
for family,path in zip(('jet','bank'),closure['learning_configs']):
 c=load_config(path);old=load_config(root/f'structured-fixed-preparation-{family}/calibration.yaml');policy=resolve_policy(c);assert canonical_hash(execution_shape(c))==canonical_hash(execution_shape(old))
 def diffs(a,b,path=''):
  if isinstance(a,dict):return [z for k in a for z in diffs(a[k],b[k],path+'.'+k)]
  return [] if a==b else [{'path':path,'before':a,'after':b}]
 delta=diffs(asdict(old),asdict(c));assert {r['path'] for r in delta}=={'.development.mode','.development.calibration_path','.development.calibration_hash'}
 for p,h in ((c.development.cache_manifest_path,c.development.cache_manifest_hash),(c.development.feature_cache_manifest_path,c.development.feature_cache_manifest_hash)):assert canonical_hash(json.loads(Path(p).read_text()))==h
 checks.append({'family':family,'config':path,'config_sha256':hashlib.sha256(Path(path).read_bytes()).hexdigest(),'exact_delta':delta,'real_resolve_policy_passed':True,'execution_shape_equal':True,'canonical_cache_identities_passed':True,'fullfile_scan_scope':'actual cold production scans retained; no redundant promotion corpus rescan; freshlearning guards unchanged'})
changed=subprocess.check_output(['git','diff','--name-only'],text=True).splitlines();assert not any(p.startswith('famjet/') or p in ('requirements.lock','pyproject.toml') for p in changed)
r={'status':'passed','package_hash':source['package_hash'],'origin_source_commit':closure['origin_source']['commit'],'exact_copies':copies,'bundled_records':bundles,'original_inventory_sha_matches':len(summary['inventory']),'calibration_hash':canonical_hash(cal),'configs':checks,'helper_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'verification_seconds':time.perf_counter()-start,'no_tests_training_evaluation_or_corpus_scan':True};atomic_json(docs/'task18-structured-fixed-promotion-verification.json',r);print(json.dumps({k:v for k,v in r.items() if k!='configs'}))
