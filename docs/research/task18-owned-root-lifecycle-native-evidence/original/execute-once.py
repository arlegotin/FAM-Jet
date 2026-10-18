"""Single allocated parent invocation; no native observation outside frozen parent."""
import ast
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import time

ROOT=Path('/Users/artemlegotin/Documents/git_alter/FAM-Jet')
BASE=Path('/private/tmp/t18o-3cipo8u0')
ALLOCATION=ROOT/'.superpowers/sdd/2026-10-16-famjet/task-18-owned-root-lifecycle-native-allocation.json'
allocation=json.loads(ALLOCATION.read_bytes())
command=allocation['command']; destination=Path(allocation['destination'])
paths=dict(monitor=ROOT/'validation/kernel_stage_a/monitor.py',
           parent=ROOT/'docs/research/task18-owned-root-lifecycle-native-control.py',
           worker=ROOT/'docs/research/task18-owned-root-lifecycle-native-worker.py')
def digest(raw): return hashlib.sha256(raw).hexdigest()
def save(name,value):
    with (BASE/name).open('x') as stream: stream.write(json.dumps(value,indent=2)+'\n')
head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
status=subprocess.check_output(['git','status','--porcelain'],cwd=ROOT,text=True)
package={str(path.relative_to(ROOT)):digest(path.read_bytes()) for path in sorted((ROOT/'famjet').rglob('*.py'))}
package_hash=digest(json.dumps(package,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode())
lock_hash=digest((ROOT/'requirements.lock').read_bytes())
source_hashes={key:digest(path.read_bytes()) for key,path in paths.items()}
free=shutil.disk_usage(BASE).free
thread_environment={key:'1' for key in ('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS','VECLIB_MAXIMUM_THREADS','NUMEXPR_NUM_THREADS')}
environment=dict(os.environ,**thread_environment,TASK18_SOURCE_GIT=allocation['source_full_git'])
checks=dict(head=head==allocation['source_full_git'],clean_tree=not status,base=BASE.is_dir(),
    fresh_destination=not destination.exists(),one_invocation=not (BASE/'invocation-started.json').exists(),
    exact_command=command==[str(ROOT/'.venv/bin/python'),'-I','-B',str(paths['parent']),str(BASE/'native')],
    package=package_hash=='15cf84c28136d4f5ec34c173316d0db1f2aab1da97c6d68993a5c22bf18ec050',
    lock=lock_hash=='2b1931e022c8e2555c45a9f9fb5feead7077b9043bfc088fc2db3e811bbe21d1',
    source_hashes=all(source_hashes[key]==allocation[key+'_sha256'] for key in paths),
    free_disk=free>=4294967296)
for path in paths.values(): ast.parse(path.read_bytes(),filename=str(path))
save('precheck.json',dict(utc_epoch=time.time(),monotonic=time.monotonic(),checks=checks,head=head,status=status,
    command=command,source_hashes=source_hashes,package_hash=package_hash,lock_hash=lock_hash,
    free_disk_bytes=free,allocation=allocation,allocation_sha256=digest(ALLOCATION.read_bytes()),
    wrapper_sha256=digest(Path(__file__).read_bytes()),environment_overrides=dict(thread_environment,TASK18_SOURCE_GIT=allocation['source_full_git']),
    inherited_environment_keys=sorted(os.environ),ast_parse=True))
if not all(checks.values()): raise SystemExit('PRECHECK FAILED; parent not invoked')
save('invocation-started.json',dict(monotonic=time.monotonic(),utc_epoch=time.time(),command=command))
with (BASE/'parent-stdout.log').open('xb') as stdout,(BASE/'parent-stderr.log').open('xb') as stderr:
    before=time.monotonic(); utc_before=time.time()
    result=subprocess.run(command,cwd=ROOT,env=environment,stdout=stdout,stderr=stderr)
    after=time.monotonic(); utc_after=time.time()
save('external-result.json',dict(command=command,exit=result.returncode,monotonic_before=before,monotonic_after=after,
    utc_before=utc_before,utc_after=utc_after,elapsed_seconds=after-before,
    timer_boundary='immediately before subprocess.run through actual parent exit, including parent artifact write; wrapper final JSON/copy/commit excluded',
    parent_invocations=1))
print(json.dumps(dict(exit=result.returncode,external_elapsed=after-before,base=str(BASE))))
raise SystemExit(result.returncode)
