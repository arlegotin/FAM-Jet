"""Preserve each authorized synthetic pytest attempt before starting another."""
import hashlib
import json
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tarfile

ROOT=Path(__file__).resolve().parents[3]
EVIDENCE=Path(__file__).resolve().parent
def sha(data): return hashlib.sha256(data).hexdigest()
def write(path,value): path.write_text(json.dumps(value,indent=2,sort_keys=True)+'\n')

attempt=sys.argv[1]
assert attempt in ('red','green','cover')
base=Path('/tmp/task18-native-fix4')/('pytest-'+attempt)
dest=EVIDENCE/attempt
assert not base.exists() and not dest.exists(), 'never overwrite an attempt'
dest.mkdir()
command=sys.argv[2:]+['--basetemp='+str(base)]
inputs={}
paths=list((ROOT/'validation/kernel_stage_a').glob('*.py'))+list((ROOT/'tests').glob('test_kernel_stage_a*.py'))
for path in sorted(paths):
    target=dest/'inputs'/path.relative_to(ROOT)
    target.parent.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(path,target)
    data=target.read_bytes()
    inputs[str(path.relative_to(ROOT))]=dict(sha256=sha(data),bytes=len(data))
record=dict(command=command,shell_command=shlex.join(command),cwd=str(ROOT),basetemp=str(base),
            source_HEAD=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),inputs=inputs)
write(dest/'command.json',record)
with (dest/'output.txt').open('wb') as stream:
    result=subprocess.run(command,cwd=ROOT,stdout=stream,stderr=subprocess.STDOUT)
record['exit_code']=result.returncode
write(dest/'command.json',record)
mappings=[]
if base.exists():
    archive=dest/'all-specimens.tar.gz'
    with tarfile.open(archive,'w:gz',dereference=False) as tar: tar.add(base,arcname=base.name)
    for path in sorted(base.rglob('*')):
        if path.is_file() and not path.is_symlink():
            data=path.read_bytes()
            mappings.append(dict(original=str(path),archive=str(archive.relative_to(ROOT)),
                                 member=str(Path(base.name)/path.relative_to(base)),sha256=sha(data),bytes=len(data)))
    for verdict in sorted(base.rglob('monitor.json')):
        if verdict.is_symlink(): continue
        out=verdict.parent
        target=dest/'specimens'/out.relative_to(base)
        shutil.copytree(out,target)
        for path in sorted(out.rglob('*')):
            if path.is_file() and not path.is_symlink():
                data=path.read_bytes()
                mappings.append(dict(original=str(path),durable=str((target/path.relative_to(out)).relative_to(ROOT)),
                                     sha256=sha(data),bytes=len(data)))
write(dest/'mappings.json',mappings)
print((dest/'output.txt').read_text(),end='')
print('Preserved attempt:',attempt,'exit:',result.returncode,'mapped files:',len(mappings))
sys.exit(result.returncode)
