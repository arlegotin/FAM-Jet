import pathlib,json,subprocess,os,time,sys
ROOT=pathlib.Path('/Users/artemlegotin/Documents/git_alter/FAM-Jet')
PRE=pathlib.Path(__file__).parent
seal=PRE/'stage-a-seal.json'
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()=='81204796ade55ce9e7202bc9253b1b61db6a65a3'
assert not subprocess.check_output(['git','status','--porcelain'],cwd=ROOT)
command=[str(ROOT/'.venv/bin/python'),'-B','-m','validation.kernel_stage_a','--seal',str(seal)]
environment=os.environ.copy()
for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','VECLIB_MAXIMUM_THREADS','NUMEXPR_NUM_THREADS'): environment[k]='1'
environment['TASK18_SOURCE_GIT']='81204796ade55ce9e7202bc9253b1b61db6a65a3'
before=time.monotonic();utc_before=time.time()
with (PRE/'stage-a-invoked.json').open('x') as s:
 json.dump(dict(command=command,monotonic_before=before,utc_before=utc_before),s);s.flush();os.fsync(s.fileno())
with (PRE/'stage-a-outer-stdout.log').open('xb') as out,(PRE/'stage-a-outer-stderr.log').open('xb') as err:
 completed=subprocess.run(command,cwd=ROOT,env=environment,stdout=out,stderr=err)
after=time.monotonic();utc_after=time.time()
record=dict(command=command,exit=completed.returncode,monotonic_before=before,monotonic_after=after,utc_before=utc_before,utc_after=utc_after,elapsed_seconds=after-before,parent_invocations=1,timing_boundary='before one-use marker through stage parent exit; receipt excluded')
with (PRE/'stage-a-external.json').open('x') as s: json.dump(record,s,sort_keys=True);s.flush();os.fsync(s.fileno())
print(json.dumps(record,sort_keys=True))
raise SystemExit(completed.returncode)
