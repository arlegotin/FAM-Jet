from pathlib import Path
from dataclasses import replace,asdict
import json,hashlib,yaml
from famjet.config import load_config
from famjet.analysis.development import resolve_policy,execution_shape
from famjet.provenance import canonical_hash
from famjet.artifacts import atomic_json
root=Path('artifacts/task18');calpath=root/'structured-fixed-operational-calibration.json';cal=json.loads(calpath.read_text());assert cal['status']=='passed';out=root/'structured-fixed-learning-drafts';out.mkdir(exist_ok=False);rows=[]
for family in ('jet','bank'):
 oldpath=root/f'structured-fixed-preparation-{family}/calibration.yaml';old=load_config(oldpath);new=replace(old,development=replace(old.development,mode='learning',calibration_path=str(calpath),calibration_hash=canonical_hash(cal)));p=out/f'{family}_fixed_cpu64_structured_32768.yaml';p.write_text(yaml.safe_dump(asdict(new),sort_keys=False));loaded=load_config(p);policy=resolve_policy(loaded);assert canonical_hash(execution_shape(old))==canonical_hash(execution_shape(loaded));a,b=asdict(old),asdict(loaded)
 def diff(x,y,path=''):
  if isinstance(x,dict):return [z for k in x for z in diff(x[k],y[k],path+'.'+k)]
  return [] if x==y else [{'path':path,'old':x,'new':y}]
 changes=diff(a,b);assert {x['path'] for x in changes}=={'.development.mode','.development.calibration_path','.development.calibration_hash'}
 rows.append({'family':family,'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'exact_delta':changes,'real_resolve_policy_passed':True,'policy':policy,'same_execution_shape':True,'configured_steps':loaded.training.optimizer_steps,'requested_operational_stop':8192,'scope':'draft only; no learning allocated or executed'})
atomic_json(out/'verification.json',{'calibration_hash':canonical_hash(cal),'configs':rows,'scientific_learning':'HELD pendingrootruling'})
