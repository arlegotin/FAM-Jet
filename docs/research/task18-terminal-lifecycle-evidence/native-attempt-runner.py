import hashlib,json,os,shutil,subprocess,sys,tempfile,time
from pathlib import Path
root=Path.cwd(); stamp=Path(tempfile.mkdtemp(prefix='t18n-',dir='/private/tmp'))
archive=root/'docs/research/task18-terminal-lifecycle-evidence'/stamp.name
archive.mkdir(); control=root/'.superpowers/sdd/2026-10-16-famjet/task-18-terminal-lifecycle-native-control.py'
source_git=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
shutil.copy2(control,archive/'committed-native-control.py')
shutil.copy2(root/'validation/kernel_stage_a/monitor.py',archive/'committed-monitor.py')
environment=dict(os.environ,TASK18_SOURCE_GIT=source_git)
for key in ('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS','VECLIB_MAXIMUM_THREADS','NUMEXPR_NUM_THREADS'): environment[key]='4'
command=[str(root/'.venv/bin/python'),str(control),str(stamp/'native')]
started=time.monotonic()
with (archive/'full-output.log').open('wb') as log:
    result=subprocess.run(command,env=environment,stdout=log,stderr=subprocess.STDOUT)
elapsed=time.monotonic()-started
if (stamp/'native').exists(): shutil.copytree(stamp/'native',archive/'native',symlinks=True)
(archive/'attempt.json').write_text(json.dumps(dict(command=command,exit=result.returncode,owned_base=str(stamp),source_git=source_git,command_elapsed_including_interpreter_start=elapsed,control_sha256=hashlib.sha256(control.read_bytes()).hexdigest(),thread_limits={key:environment[key] for key in ('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS','VECLIB_MAXIMUM_THREADS','NUMEXPR_NUM_THREADS')},cpu_count=os.cpu_count()),indent=2)+'\n')
manifest={str(path.relative_to(archive)):dict(bytes=path.stat().st_size,sha256=hashlib.sha256(path.read_bytes()).hexdigest()) for path in sorted(archive.rglob('*')) if path.is_file()}
(archive/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
print(archive);print((archive/'full-output.log').read_text());sys.exit(result.returncode)
