from pathlib import Path
from dataclasses import replace,asdict
import json,hashlib,shutil,yaml
from famjet.artifacts import atomic_json
from famjet.provenance import canonical_hash
from famjet.config import load_config
root=Path('artifacts/task18');docs=Path('docs/research');promotions=[]
def copy(a,b):
 a,b=Path(a),Path(b);b.parent.mkdir(parents=True,exist_ok=True);assert not b.exists();shutil.copyfile(a,b);promotions.append({'source':str(a),'destination':str(b),'sha256':hashlib.sha256(a.read_bytes()).hexdigest()});assert a.read_bytes()==b.read_bytes()
def pack(paths,dest):
 records=[]
 for p in paths:
  p=Path(p);records.append({'source':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'record':json.loads(p.read_text())})
 atomic_json(docs/dest,{'scope':'exact parsed records and original-byte SHA; tensors/corpora/checkpoints remain ignored; older accepted memory evidence referenced via original hashes','records':records})
for name in ('source-review','probe-report','operational-report','learning-proposal'):
 copy(f'.superpowers/sdd/2026-10-16-famjet/task-18-structured-fixed-{name}.md',docs/f'task18-structured-fixed-{name}.md')
for stem in ('operational-summary','bounded-summary'):
 copy(root/f'structured-fixed-{stem}.json',docs/f'task18-structured-fixed-{stem}.json')
copy(root/'structured-fixed-operational-calibration.json',docs/'task18-cpu-calibration-structured-fixed.json')
initial=sorted((root/'structured-fixed-initial').glob('*-*/summary.json'));fitted=[p for family in ('jet','bank') for p in sorted((root/f'structured-fixed-fitted-{family}').glob('step*/summary.json'))];assert len(initial)==24 and len(fitted)==48
pack(initial+fitted,'task18-structured-fixed-numerical-evidence.json')
paths=[root/'structured-fixed-initial/procedure.json',root/'structured-fixed-initial/summary.json',root/'structured-fixed-raw-preparation/procedure.json',root/'structured-fixed-raw-preparation/summary.json',root/'structured-fixed-operational/procedure.json',root/'structured-fixed-operational/summary.json']
for family in ('jet','bank'):
 paths += [root/f'structured-fixed-probe/{family}'/n for n in ('procedure.json','summary.json','static-inventory.json','static-after.json','static-comparison.json')]
 paths += [root/f'structured-fixed-preparation-{family}'/n for n in ('procedure.json','summary.json','fit.json')]
 paths += [root/f'telemetry-{family}-structured-fixed'/n for n in ('procedure.json','cost.json')]
 paths += [root/f'calibration-{family}-structured-fixed/development.json',root/f'structured-fixed-fitted-{family}/summary.json',root/f'structured-fixed-fitted-{family}/procedure.json']
paths += [p.parent/'procedure.json' for p in initial+fitted]+[p.parent/'checkpoint-verification.json' for p in fitted]
pack(paths,'task18-structured-fixed-preparation-evidence.json')
manifest_records=[]
for p in [root/'cache-structured-fixed-6144/manifest.json']+[root/f'features-structured-fixed-6144-{f}/manifest.json' for f in ('jet','bank')]:
 m=json.loads(p.read_text());manifest_records.append({'source':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'canonical_hash':canonical_hash(m),'entry_count':len(m['entries']),'record_without_entries':{k:v for k,v in m.items() if k!='entries'}})
atomic_json(docs/'task18-structured-fixed-cache-identities.json',{'scope':'canonical manifest identities/costs; full6144 file records remain at sourcepaths; cold production full-file scans alreadypassed','manifests':manifest_records})
helpers=['task18_structured_fixed_numeric.py','task18_structured_fixed_driver.py','task18_structured_fixed_probe.py','task18_structured_raw_prepare.py','task18_structured_prepare.py','task18_structured_cold.py','task18_structured_fitted.py','task18_structured_fitted_driver.py','task18_structured_operational_driver.py','task18_structured_close.py','task18_structured_learning_drafts.py','task18_structured_promote.py']
for h in helpers:copy('artifacts/task18-evidence/procedure-scripts/'+h,docs/'task18-procedures'/h)
calpath=docs/'task18-cpu-calibration-structured-fixed.json';cal=json.loads(calpath.read_text());configs=[]
for family in ('jet','bank'):
 c=load_config(root/f'structured-fixed-preparation-{family}/calibration.yaml');c=replace(c,development=replace(c.development,mode='learning',calibration_path=str(calpath),calibration_hash=canonical_hash(cal)));p=Path(f'configs/development/{family}_fixed_cpu64_structured_32768.yaml');assert not p.exists();p.write_text(yaml.safe_dump(asdict(c),sort_keys=False));configs.append(str(p))
closure={'scope':'7e0 operational lineage closed after rootacceptance; fresh scientific8192 allocation governed by datedruling, never resume stop2checkpoint','origin_source':json.loads((root/'structured-fixed-operational-summary.json').read_text())['source'],'promotions':promotions,'bundles':['docs/research/task18-structured-fixed-numerical-evidence.json','docs/research/task18-structured-fixed-preparation-evidence.json','docs/research/task18-structured-fixed-cache-identities.json'],'learning_configs':configs,'requested_operational_stop':8192,'potential_horizon':32768,'calibration_hash':canonical_hash(cal),'no_package_source_changes':True,'failures_in_current_stage':0,'all_prior_failures_preserved':True}
atomic_json(docs/'task18-structured-fixed-closure.json',closure);print({'exact_copies':len(promotions),'numeric_records':72,'preparation_records':len(paths),'configs':configs})
