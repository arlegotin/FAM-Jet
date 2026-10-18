import hashlib,json,os,shutil,subprocess,sys,tempfile,time
from pathlib import Path
root=Path.cwd(); base=Path(tempfile.mkdtemp(prefix='t18a-',dir='/private/tmp'))
archive=root/'docs/research/task18-terminal-attribution-native-evidence'/base.name
archive.mkdir(); source_git=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
assert source_git=='037b04484c6afe1b163c330cd10e1b593f43de62'
inputs={}
for relative,name in [('docs/research/task18-terminal-attribution-native-control.py','committed-parent.py'),('docs/research/task18-terminal-lifecycle-file-worker.py','committed-worker.py'),('validation/kernel_stage_a/monitor.py','committed-monitor.py')]:
    raw=(root/relative).read_bytes(); assert raw==subprocess.check_output(['git','show',source_git+':'+relative])
    (archive/name).write_bytes(raw)
    inputs[relative]=dict(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
environment=dict(os.environ,TASK18_SOURCE_GIT=source_git)
keys=('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS','VECLIB_MAXIMUM_THREADS','NUMEXPR_NUM_THREADS')
for key in keys: environment[key]='4'
command=[str(root/'.venv/bin/python'),'-B',str(root/'docs/research/task18-terminal-attribution-native-control.py'),str(base/'native')]
prior_seconds=.3026611660607159
before=dict(command=command,source_git=source_git,owned_base=str(base),inputs=inputs,thread_limits={key:environment[key] for key in keys},cpu_count=os.cpu_count(),prior_failed_native_command_seconds=prior_seconds,scope='one separately authorized terminal-attribution invocation; no retry or science')
(archive/'attempt-before.json').write_text(json.dumps(before,indent=2)+'\n')
started=time.monotonic()
with (archive/'full-output.log').open('wb') as log:
    result=subprocess.run(command,env=environment,stdout=log,stderr=subprocess.STDOUT)
elapsed=time.monotonic()-started
if (base/'native').exists(): shutil.copytree(base/'native',archive/'native',symlinks=True)
(archive/'attempt.json').write_text(json.dumps(dict(before,exit=result.returncode,command_elapsed_including_interpreter_start=elapsed,cumulative_native_command_seconds=prior_seconds+elapsed),indent=2)+'\n')
manifest={str(path.relative_to(archive)):dict(bytes=path.stat().st_size,sha256=hashlib.sha256(path.read_bytes()).hexdigest()) for path in sorted(archive.rglob('*')) if path.is_file()}
(archive/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
print(archive); print((archive/'full-output.log').read_text()); sys.exit(result.returncode)
