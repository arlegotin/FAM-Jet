"""Root custody only: no scientific imports, tests or experiment launch."""
from pathlib import Path
import datetime, hashlib, json, subprocess
ROOT=Path('/Users/artemlegotin/Documents/git_alter/FAM-Jet')
BASE='08ba541aa32cc8f1ea83833cccb9962291f0d625'
HEAD='c4bee4bee52114427bfb07ab9d4a04d5280e20dc'
E=ROOT/'docs/research/task18-kernel-stage-b-launcher-source-evidence'
def sha(x): return hashlib.sha256(x).hexdigest()
def git(*x): return subprocess.check_output(['git',*x],cwd=ROOT)
def load(p): return json.loads(p.read_bytes())
assert git('rev-parse','HEAD').decode().strip()==HEAD
assert not git('status','--porcelain')
changed=[p for p in git('diff','--name-only','-z',BASE,HEAD).decode().split('\0') if p]
for name in changed:
 p=ROOT/name
 assert p.is_file() and not p.is_symlink(),name
 assert p.read_bytes()==git('show',f'{HEAD}:{name}'),name
protected=['famjet','requirements.lock','validation/kernel_stage_a','docs/research/task18-kernel-stage-a06-evidence','docs/research/task18-kernel-stage-b-binding01-evidence','docs/research/task18-kernel-stage-b-binding01-witness.py','configs/development/jet_finite_raw_32768.yaml']
assert not git('diff','--name-only',BASE,HEAD,'--',*protected)
manifest_path=ROOT/'docs/research/task18-kernel-stage-b-source-evidence/source-manifest.json'
rows=load(manifest_path)
assert len(rows)==88 and rows==sorted(rows,key=lambda r:r['path'])
assert len({r['path'] for r in rows})==88
mapping={r['path']:r for r in rows}
for row in rows:
 raw=(ROOT/row['path']).read_bytes()
 assert set(row)=={'path','bytes','sha256'} and len(raw)==row['bytes'] and sha(raw)==row['sha256'],row['path']
historical=load(ROOT/'docs/research/task18-kernel-stage-b-source-review/historical-material-manifest.json')
assert len(historical)==79 and all(mapping[r['path']]==r for r in historical)
assert len(set(mapping)-{r['path'] for r in historical})==9
package={str(p.relative_to(ROOT)):sha(p.read_bytes()) for p in sorted((ROOT/'famjet').rglob('*.py'))}
package_hash=sha(json.dumps(package,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode())
assert len(package)==53 and package_hash=='15cf84c28136d4f5ec34c173316d0db1f2aab1da97c6d68993a5c22bf18ec050'
assert sha((ROOT/'requirements.lock').read_bytes())=='2b1931e022c8e2555c45a9f9fb5feead7077b9043bfc088fc2db3e811bbe21d1'
stage_a=git('ls-tree','-r','--name-only',BASE,'validation/kernel_stage_a').decode().splitlines()
assert len(stage_a)==15
for name in stage_a: assert (ROOT/name).read_bytes()==git('show',f'{BASE}:{name}'),name
index=load(E/'index.json')
assert len(index['invocations'])==10
failed=[]
for i,r in enumerate(index['invocations'],1):
 raw=(E/r['log']).read_bytes()
 assert len(raw)==r['log_bytes'] and sha(raw)==r['log_sha256'],r['log']
 if r['exit_code']: failed.append(i)
assert failed==index['failed_invocation_ids']==[1,2,4,5,8]
assert index['invocations'][-1]['exit_code']==0
assert b'58 passed in 9.36s' in (E/index['invocations'][-1]['log']).read_bytes()
pr=index['protected_material_proof']; raw=(E/pr['path']).read_bytes()
assert len(raw)==pr['bytes'] and sha(raw)==pr['sha256']
report=ROOT/'docs/research/task18-kernel-stage-b-launcher-source-report.md'
assert report.read_bytes()==(ROOT/'.superpowers/sdd/2026-10-16-famjet/task-18-runtime-launcher-source-report.md').read_bytes()
plan=load(ROOT/'validation/kernel_stage_b/prospective-plan.json')
assert all(plan[k] is None for k in ('approval','execution','release'))
# Existing nested material Ref remains source data, not runtime authority.
def walk(v):
 if isinstance(v,dict):
  if v.get('path')==str(manifest_path.relative_to(ROOT)):
   assert v['bytes']==manifest_path.stat().st_size and v['sha256']==sha(manifest_path.read_bytes())
   yield v
  for x in v.values(): yield from walk(x)
 elif isinstance(v,list):
  for x in v: yield from walk(x)
refs=list(walk(plan)); assert refs
proof=dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),base=BASE,head=HEAD,delivered_git_paths_verified=len(changed),material_rows=88,historical_rows_unchanged=79,package_files=53,package_sha256=package_hash,stage_a_files_unchanged=15,protected_diff_empty=True,failed_binding01_unchanged=True,test_invocations=10,failed_invocations_retained=failed,final_test_log_sha256=index['invocations'][-1]['log_sha256'],final_test_result='58 passed in 9.36s',manifest_sha256=sha(manifest_path.read_bytes()),prospective_material_refs=len(refs),prospective_authority_null=True,report_sha256=sha(report.read_bytes()),report_mirror_equal=True,scientific_imports=False,experiment_launched=False)
output=ROOT/'.superpowers/sdd/2026-10-16-famjet/task-18-runtime-launcher-root-custody.json'
output.write_text(json.dumps(proof,indent=2)+'\n')
print(json.dumps(proof,indent=2))
