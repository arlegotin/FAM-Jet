from pathlib import Path
from dataclasses import replace,asdict
from datetime import datetime,timezone
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
 atomic_json(docs/dest,{'scope':'exact parsed records with original byte SHA; bulk tensor/corpus files remain ignored','records':records})
for name in ('source-review','probe-report','operational-report','learning-proposal'):
 copy(f'.superpowers/sdd/2026-10-16-famjet/task-18-fixed-basis-{name}.md',docs/f'task18-fixed-basis-{name}.md')
copy(root/'fixed-basis-operational-summary.json',docs/'task18-fixed-basis-operational-summary.json')
copy(root/'fixed-basis-operational-calibration.json',docs/'task18-cpu-calibration-fixed-basis.json')
copy(root/'fixed-basis-probe-summary.json',docs/'task18-fixed-basis-probe-summary.json')
initial=sorted((root/'fixed-basis-initial').glob('*-*/summary.json'));supp=sorted((root/'fixed-basis-task-supplement').glob('*-*/summary.json'));fitted=[p for f in ('jet','bank','multiscale') for p in sorted((root/f'fixed-basis-fitted-{f}').glob('step*/summary.json'))];assert len(initial)==36 and len(supp)==33 and len(fitted)==72
pack(initial+supp+fitted,'task18-fixed-basis-numerical-evidence.json')
paths=[root/'fixed-basis-raw-preparation/procedure.json',root/'fixed-basis-raw-preparation/summary.json',root/'fixed-basis-raw-preparation/all-prior-equivalence.json',root/'fixed-basis-operational/failure.json',root/'fixed-basis-preparation-jet/failure.json',root/'fixed-basis-preparation-jet/projection-diagnosis.json',root/'fixed-basis-feature-size-audit/procedure.json',root/'fixed-basis-feature-size-audit/summary.json',root/'fixed-basis-feature-size-audit/restart-allocation.json',root/'fixed-basis-operational-r2/procedure.json',root/'fixed-basis-operational-r2/summary.json',root/'fixed-basis-preparation-bank-r2/clock-audit.json',root/'fixed-basis-probe/jet/failure.json',root/'fixed-basis-probe/jet/static-comparison.json']
for f in ('jet','bank','multiscale'):
 paths += [root/f'fixed-basis-preparation-{f}-r2'/n for n in ('procedure.json','summary.json','fit.json')]+[root/f'telemetry-{f}-fixed-basis'/n for n in ('procedure.json','cost.json')]+[root/f'calibration-{f}-fixed-basis/development.json',root/f'fixed-basis-fitted-{f}/summary.json']
pack(paths,'task18-fixed-basis-preparation-evidence.json')
manifest_records=[]
for p in [root/'cache-fixed-basis-6144/manifest.json']+[root/f'features-fixed-basis-6144-{f}-r2/manifest.json' for f in ('jet','bank','multiscale')]:
 m=json.loads(p.read_text());manifest_records.append({'source':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'canonical_hash':canonical_hash(m),'entry_count':len(m['entries']),'record_without_entries':{k:v for k,v in m.items() if k!='entries'}})
atomic_json(docs/'task18-fixed-basis-cache-identities.json',{'scope':'complete manifest identities and costs, full per-file corpus manifests retained at sourcepaths','manifests':manifest_records})
copy('artifacts/task18-evidence/fixed-basis-bank-preparation-sleep-wake.txt',docs/'task18-fixed-basis-bank-sleep-wake.txt')
helpers=['numeric','initial_driver','task_supplement','supplement_driver','probe_r2','probe_r3','raw_prepare','prepare','cold','fitted','fitted_driver','operational_driver','size_audit','prepare_r2','cold_r2','fitted_r2','fitted_driver_r2','operational_driver_r2','close']
for h in helpers:copy(f'artifacts/task18-evidence/procedure-scripts/task18_fixed_basis_{h}.py',docs/f'task18-procedures/task18_fixed_basis_{h}.py')
for name in ('task18_static_compare.py','task18_recover_jet_probe.py'):
 copy('artifacts/task18-evidence/procedure-scripts/'+name,docs/'task18-procedures'/name)
calpath=docs/'task18-cpu-calibration-fixed-basis.json';cal=json.loads(calpath.read_text());configs=[]
for f in ('jet','bank','multiscale'):
 c=load_config(root/f'fixed-basis-preparation-{f}-r2/calibration.yaml');c=replace(c,development=replace(c.development,mode='learning',calibration_path=str(calpath),calibration_hash=canonical_hash(cal)));p=Path(f'configs/development/{f}_fixed_cpu64_raw128_32768.yaml');assert not p.exists();p.write_text(yaml.safe_dump(asdict(c),sort_keys=False));configs.append(str(p))
closure={'scope':'source-frozen e756 operational lineage closed; scientific8192 execution held for independent operational/config review','origin_source':json.loads((root/'fixed-basis-operational-summary.json').read_text())['source'],'promotions':promotions,'bundles':['docs/research/task18-fixed-basis-numerical-evidence.json','docs/research/task18-fixed-basis-preparation-evidence.json','docs/research/task18-fixed-basis-cache-identities.json'],'learning_configs':configs,'operational_stop':8192,'potential_horizon':32768,'calibration_hash':canonical_hash(cal),'no_package_source_changes':True}
atomic_json(docs/'task18-fixed-basis-closure.json',closure)
print({'exact_copies':len(promotions),'numeric_records':len(initial+supp+fitted),'preparation_records':len(paths),'configs':configs})
