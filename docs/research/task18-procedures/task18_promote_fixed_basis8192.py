from pathlib import Path
import hashlib,json,shutil
from famjet.artifacts import atomic_json
from famjet.train import _source
from famjet.eval.isolation import source_identity
source=_source();assert source['commit']=='2def54622c5d9a49c84145739792a084494fbbe9' and source['package_hash']=='ad542defda704e06dc9c88819b95afd6f483a882c792e82bf8c85dc27a6f6641' and not source['diff']
D=Path('docs/research');R=Path('artifacts/task18');E=Path('artifacts/task18-evidence');copies=[]
def copy(a,b):
 a,b=Path(a),Path(b);shutil.copyfile(a,b);assert a.read_bytes()==b.read_bytes();copies.append({'source':str(a),'promoted':str(b),'sha256':hashlib.sha256(a.read_bytes()).hexdigest()})
copy(R/'fixed-basis-learning8192-summary.json',D/'task18-fixed-basis-learning8192-summary.json')
copy('.superpowers/sdd/2026-10-16-famjet/task-18-fixed-basis-learning8192-report.md',D/'task18-fixed-basis-learning8192-report.md')
copy('.superpowers/sdd/2026-10-16-famjet/task-18-fixed-basis-operational-review.md',D/'task18-fixed-basis-operational-review.md')
for n in ('task18_fixed_basis_learn8192.py','task18_fixed_basis_endpoint8192_case.py','task18_fixed_basis_endpoint8192_driver.py','task18_fixed_basis_frozen_risk8192.py','task18_fixed_basis_learning_summary.py','task18_fixed_basis_launcher_clock_test.py'):
 copy(E/'procedure-scripts'/n,D/'task18-procedures'/n)
for n in ('fixed-basis-launch-clock-red.txt','fixed-basis-launch-clock-green.txt','fixed-basis-launch-clock-verification.json'):
 copy(E/n,D/('task18-'+n))
records=[]
def record(p):
 p=Path(p);records.append({'source':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'value':json.loads(p.read_text())})
for f in ('jet','bank','multiscale'):
 p=R/f'fixed-basis-endpoint8192-{f}';record(p/'summary.json');record(p/'procedure.json')
 for i in range(12):
  for n in ('summary.json','procedure.json','checkpoint-verification.json'):record(p/f'step8192-{i:02d}'/n)
 p=R/f'fixed-basis-frozen-risk8192-{f}';record(p/'summary.json');record(p/'procedure.json')
 for kind in ('allocation','clock'):record(E/f'fixed-basis-learning-{f}-8192-{kind}.json')
atomic_json(D/'task18-fixed-basis-learning8192-evidence.json',{'scope':'complete endpoint/risk/procedure/clock metadata; binary gradients/checkpoints and full training/dev rows remain ignored with retained hashes','records':records})
atomic_json(D/'task18-fixed-basis-learning8192-closure.json',{'source':source,'status':'root_accepted_exploratory_unconverged_allocation_closed','package_hash':source_identity(),'exact_copies':copies,'bundled_records':len(records),'bundle_sha256':hashlib.sha256((D/'task18-fixed-basis-learning8192-evidence.json').read_bytes()).hexdigest(),'no_binaries_or_corpora_promoted':True,'current_stage_execution_seconds':1467.8430695819552,'prior_setup_seconds':1975.089738041,'full_task18_acceptance':'pending','next_source_stage':'only exact full structured Jet125/Bank122 predicate and focused lifecycle TDD; numerical/prep/cold/science not released'})
print({'copies':len(copies),'records':len(records),'package':source_identity()})
