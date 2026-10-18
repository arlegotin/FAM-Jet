import hashlib,json,os,pathlib,subprocess,sys,time
ROOT=pathlib.Path('/Users/artemlegotin/Documents/git_alter/FAM-Jet')
WORK=ROOT/'.superpowers/sdd/2026-10-16-famjet'
allocation=json.loads((WORK/'task-18-stage-a-setup04-allocation.json').read_bytes())
parent=pathlib.Path(allocation['parent']['path'])
assert hashlib.sha256(parent.read_bytes()).hexdigest()==allocation['parent']['sha256']
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()==allocation['source_full_git']
assert not subprocess.check_output(['git','status','--porcelain'],cwd=ROOT)
marker=WORK/'task-18-stage-a-setup04-invoked.json'
command=[str(ROOT/'.venv/bin/python'),'-I','-B',str(parent)]
environment=os.environ.copy()
for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','VECLIB_MAXIMUM_THREADS','NUMEXPR_NUM_THREADS'): environment[key]='1'
environment['TASK18_SOURCE_GIT']=allocation['source_full_git']
before=time.monotonic();utc_before=time.time()
with marker.open('x') as stream:
 json.dump(dict(command=command,monotonic_before=before,utc_before=utc_before),stream);stream.flush();os.fsync(stream.fileno())
completed=subprocess.run(command,cwd=ROOT,env=environment)
after=time.monotonic();utc_after=time.time()
preparation=pathlib.Path(allocation['preparation'])
record=dict(command=command,exit=completed.returncode,monotonic_before=before,monotonic_after=after,utc_before=utc_before,utc_after=utc_after,elapsed_seconds=after-before,parent_invocations=1,timing_boundary='before one-use marker through parent exit; wrapper receipt/copy excluded')
path=preparation/'prelaunch/setup-external.json' if preparation.is_dir() else WORK/'task-18-stage-a-setup04-external.json'
with path.open('x') as stream:
 json.dump(record,stream,sort_keys=True);stream.flush();os.fsync(stream.fileno())
if preparation.is_dir():
 original=pathlib.Path(__file__).read_bytes()
 with (preparation/'prelaunch/setup-execute-once.py').open('xb') as stream:
  stream.write(original);stream.flush();os.fsync(stream.fileno())
print(json.dumps(record,sort_keys=True))
raise SystemExit(completed.returncode)
