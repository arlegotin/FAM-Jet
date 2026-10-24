"""Root byte/provenance custody only; no scientific imports or tests."""
from pathlib import Path
import datetime,hashlib,json,subprocess
R=Path('/Users/artemlegotin/Documents/git_alter/FAM-Jet');W=R/'.superpowers/sdd/2026-10-16-famjet'
BASE='38093b1ec1d0489a5d3d6247f76ce8baa07d6e74';HEAD='9c4b4b3017ddaa97267b9e8c35b68991bc1bc6db'
def git(*a):return subprocess.check_output(['git',*a],cwd=R)
def sha(b):return hashlib.sha256(b).hexdigest()
def load(p):return json.loads(p.read_bytes())
assert git('rev-parse','HEAD').decode().strip()==HEAD and not git('status','--porcelain')
paths=[s for s in git('diff','--name-only','-z',BASE,HEAD).decode().split('\0') if s]
for name in paths:assert (R/name).read_bytes()==git('show',HEAD+':'+name),name
protected=['famjet','requirements.lock','validation/kernel_stage_a','configs/development/jet_finite_raw_32768.yaml','docs/research/task18-kernel-stage-a06-evidence','docs/research/task18-kernel-stage-b-binding01-evidence','docs/research/task18-kernel-stage-b-binding02-evidence','docs/research/task18-kernel-stage-b-panel02-evidence','docs/research/task18-kernel-stage-b-binding03-evidence','docs/research/task18-kernel-stage-b-panel03-evidence','docs/research/task18-kernel-stage-b-binding01-witness.py','docs/research/task18-kernel-stage-b-binding02-witness.py','docs/research/task18-kernel-stage-b-panel01-witness.py','docs/research/task18-kernel-stage-b-panel02-witness.py','docs/research/task18-kernel-stage-b-binding03-witness.py','docs/research/task18-kernel-stage-b-panel03-witness.py']
assert not git('diff','--name-only',BASE,HEAD,'--',*protected)
mp=R/'docs/research/task18-kernel-stage-b-source-evidence/source-manifest.json';rows=load(mp)
assert len(rows)==88 and rows==sorted(rows,key=lambda x:x['path']) and len({x['path'] for x in rows})==88
for row in rows:
 raw=(R/row['path']).read_bytes();assert len(raw)==row['bytes'] and sha(raw)==row['sha256'],row['path']
old={x['path']:x for x in json.loads(git('show',BASE+':'+str(mp.relative_to(R))))};current={x['path']:x for x in rows}
assert sorted(k for k in old.keys()|current.keys() if old.get(k)!=current.get(k))==['validation/kernel_stage_b/production.py']
historical=load(R/'docs/research/task18-kernel-stage-b-source-review/historical-material-manifest.json')
assert len(historical)==79 and all(current[x['path']]==x for x in historical)
package={str(p.relative_to(R)):sha(p.read_bytes()) for p in sorted((R/'famjet').rglob('*.py'))}
ph=sha(json.dumps(package,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode())
assert len(package)==53 and ph=='15cf84c28136d4f5ec34c173316d0db1f2aab1da97c6d68993a5c22bf18ec050'
assert sha((R/'requirements.lock').read_bytes())=='2b1931e022c8e2555c45a9f9fb5feead7077b9043bfc088fc2db3e811bbe21d1'
afiles=git('ls-tree','-r','--name-only',BASE,'validation/kernel_stage_a').decode().splitlines();assert len(afiles)==15
for name in afiles:assert (R/name).read_bytes()==git('show',BASE+':'+name),name
E=R/'docs/research/task18-kernel-stage-b-reader-launcher-source-evidence';idx=load(E/'run-index.json');assert len(idx['invocations'])==3
failed=[]
for i,row in enumerate(idx['invocations'],1):
 for ref in row['raw'].values():
  raw=(R/ref['path']).read_bytes();assert len(raw)==ref['bytes'] and sha(raw)==ref['sha256']
 metadata=load((R/row['raw']['stdout']['path']).with_suffix('.json'))
 assert all(metadata[k]==row[k] for k in ('argv','elapsed_seconds','exit_code'))
 if row['exit_code']!=0:failed.append(i)
assert failed==[1] and idx['invocations'][-1]['exit_code']==0
assert b'67 passed in 9.63s' in (R/idx['invocations'][-1]['raw']['stdout']['path']).read_bytes()
assert all(x['raw']['stderr']['bytes']==0 for x in idx['invocations'])
ref=idx['custody_proof'];raw=(R/ref['path']).read_bytes();assert len(raw)==ref['bytes'] and sha(raw)==ref['sha256']
report=R/'docs/research/task18-kernel-stage-b-reader-launcher-source-report.md';assert report.read_bytes()==(W/'task-18-reader-launcher-source-report.md').read_bytes()
plan=load(R/'validation/kernel_stage_b/prospective-plan.json');assert all(plan[x] is None for x in ('approval','execution','release'))
assert plan['evidence']['source']['sha256']==sha(mp.read_bytes()) and plan['evidence']['source']['bytes']==mp.stat().st_size
proof=dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),base=BASE,head=HEAD,delivered_git_files=len(paths),material_rows=88,changed_material_rows=['validation/kernel_stage_b/production.py'],material_sha256=sha(mp.read_bytes()),historical_rows_equal=79,package_files=53,package_sha256=ph,stage_a_unchanged=15,protected_diff_empty=True,raw_invocations=3,failed_invocations_retained=failed,final_test_result='67 passed in 9.63s',final_log_sha256=idx['invocations'][-1]['raw']['stdout']['sha256'],report_sha256=sha(report.read_bytes()),report_mirror_equal=True,prospective_authority_null=True,experiment_executed=False)
(W/'task-18-reader-launcher-root-custody.json').write_text(json.dumps(proof,indent=2)+'\n');print(json.dumps(proof,indent=2))
