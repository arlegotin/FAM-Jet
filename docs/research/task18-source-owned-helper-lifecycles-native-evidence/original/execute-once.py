"""One allocated native parent; static checks and whole-base output postcondition."""
import ast
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import time

ROOT=Path('/Users/artemlegotin/Documents/git_alter/FAM-Jet')
BASE=Path('/private/tmp/t18s-xqsxzfxl')
ALLOCATION=ROOT/'.superpowers/sdd/2026-10-16-famjet/task-18-source-owned-helper-lifecycles-native-allocation.json'
allocation=json.loads(ALLOCATION.read_bytes())
command=allocation['vector']; destination=Path(allocation['destination'])
def digest(raw): return hashlib.sha256(raw).hexdigest()
def save(name,value):
    with (BASE/name).open('x') as stream: stream.write(json.dumps(value,indent=2)+'\n')
head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
status=subprocess.check_output(['git','status','--porcelain'],cwd=ROOT,text=True)
package={str(path.relative_to(ROOT)):digest(path.read_bytes()) for path in sorted((ROOT/'famjet').rglob('*.py'))}
package_hash=digest(json.dumps(package,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode())
lock_hash=digest((ROOT/'requirements.lock').read_bytes())
inputs={item['path']:dict(bytes=(ROOT/item['path']).stat().st_size,sha256=digest((ROOT/item['path']).read_bytes())) for item in allocation['inputs']}
for item in allocation['inputs']: ast.parse((ROOT/item['path']).read_bytes(),filename=item['path'])
environment=dict(os.environ,**allocation['environment'])
free=shutil.disk_usage(BASE).free
checks=dict(source_label=head==allocation['source_git']==environment['TASK18_SOURCE_GIT'],clean_tree=not status,
    base=BASE.is_dir() and str(BASE)==allocation['base'],fresh_destination=not destination.exists(),
    one_invocation=not (BASE/'invocation-started.json').exists(),
    exact_vector=command==[str(ROOT/'.venv/bin/python'),'-I','-B',str(ROOT/'docs/research/task18-source-owned-helper-native-control.py'),str(BASE/'native')],
    input_count=len(inputs)==8,input_hashes=all(inputs[item['path']]==dict(bytes=item['bytes'],sha256=item['sha256']) for item in allocation['inputs']),
    package=package_hash=='15cf84c28136d4f5ec34c173316d0db1f2aab1da97c6d68993a5c22bf18ec050',
    lock=lock_hash=='2b1931e022c8e2555c45a9f9fb5feead7077b9043bfc088fc2db3e811bbe21d1',
    thread_variables=all(environment[key]=='1' for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','VECLIB_MAXIMUM_THREADS','NUMEXPR_NUM_THREADS')),
    free_disk=free>=allocation['free_disk_bytes'])
save('precheck.json',dict(utc_epoch=time.time(),monotonic=time.monotonic(),checks=checks,head=head,status=status,
    command=command,inputs=inputs,package_hash=package_hash,lock_hash=lock_hash,free_disk_bytes=free,
    allocation=allocation,allocation_sha256=digest(ALLOCATION.read_bytes()),wrapper_sha256=digest(Path(__file__).read_bytes()),
    environment_overrides=allocation['environment'],inherited_environment_keys=sorted(os.environ),ast_parse=True))
if not all(checks.values()): raise SystemExit('PRECHECK FAILED; parent not invoked')
reserve=2048
with (BASE/'aggregate-postcondition.json').open('xb') as stream:
    initial=b'{"status":"NEEDS_CONTEXT","reason":"external postcondition incomplete"}\n'
    stream.write(initial+b' '*(reserve-len(initial)))
save('invocation-started.json',dict(monotonic=time.monotonic(),utc_epoch=time.time(),command=command))
with (BASE/'parent-stdout.log').open('xb') as stdout,(BASE/'parent-stderr.log').open('xb') as stderr:
    before=time.monotonic(); utc_before=time.time()
    result=subprocess.run(command,cwd=ROOT,env=environment,stdout=stdout,stderr=stderr)
    after=time.monotonic(); utc_after=time.time()
save('external-result.json',dict(command=command,exit=result.returncode,monotonic_before=before,monotonic_after=after,
    utc_before=utc_before,utc_after=utc_after,elapsed_seconds=after-before,parent_invocations=1,
    timer_boundary='immediately before subprocess.run through parent exit including all parent artifact writes/stdout; wrapper final JSON/postcondition/copy/commit excluded'))
regular_bytes=sum(path.lstat().st_size for path in BASE.rglob('*') if stat.S_ISREG(path.lstat().st_mode))
within=regular_bytes<=allocation['aggregate_output_bytes']
post=dict(status='PASS' if within else 'NEEDS_CONTEXT',aggregate_regular_bytes=regular_bytes,
    aggregate_cap_bytes=allocation['aggregate_output_bytes'],includes_wrapper_precheck_external_logs_and_this_reserved_receipt=True,
    receipt_reserved_bytes=reserve,checked_monotonic=time.monotonic(),checked_utc_epoch=time.time(),
    parent_exit=result.returncode,scope='every regular file under allocated base after external-result write; no socket/special-file reads')
payload=(json.dumps(post,indent=2)+'\n').encode()
assert len(payload)<=reserve
with (BASE/'aggregate-postcondition.json').open('r+b') as stream:
    stream.write(payload+b' '*(reserve-len(payload))); stream.flush()
print(json.dumps(dict(exit=result.returncode,external_elapsed=after-before,aggregate_regular_bytes=regular_bytes,aggregate_within_cap=within,base=str(BASE))))
raise SystemExit(result.returncode if result.returncode else (0 if within else 1))
