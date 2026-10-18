import hashlib,json,os,shutil,stat,subprocess,sys,tempfile,time
from pathlib import Path
root=Path.cwd(); label=sys.argv[1]; arguments=sys.argv[2:]
base=Path(tempfile.mkdtemp(prefix='task18-owned-root-lifecycle-'+label+'-',dir='/private/tmp'))
archive=root/'docs/research/task18-owned-root-lifecycle-evidence'/base.name
archive.mkdir(); (archive/'source-inputs/validation/kernel_stage_a').mkdir(parents=True); (archive/'source-inputs/tests').mkdir()
for p in list((root/'validation/kernel_stage_a').glob('*.py'))+list((root/'tests').glob('test_kernel_stage_a*.py')):
    shutil.copy2(p,archive/'source-inputs'/p.relative_to(root))
cmd=[str(root/'.venv/bin/python'),'-m','pytest',*arguments,'--basetemp='+str(base/'specimens'),'-ra']
started=time.time()
with (archive/'full-output.log').open('wb') as log:
    result=subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT)
def retain(source,dest):
    if source.is_symlink(): dest.symlink_to(os.readlink(source)); return
    mode=source.lstat().st_mode
    if stat.S_ISDIR(mode):
        dest.mkdir()
        for child in source.iterdir(): retain(child,dest/child.name)
    elif stat.S_ISREG(mode): shutil.copy2(source,dest)
    else:
        (dest.parent/(dest.name+'.special.json')).write_text(json.dumps(dict(mode=mode,not_followed=True)))
if (base/'specimens').exists(): retain(base/'specimens',archive/'specimens')
(archive/'attempt.json').write_text(json.dumps(dict(command=cmd,exit=result.returncode,started_epoch=started,end_epoch=time.time(),owned_base=str(base),source_git=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()),indent=2)+'\n')
manifest={str(p.relative_to(archive)):dict(bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in sorted(archive.rglob('*')) if not p.is_symlink() and p.is_file()}
(archive/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
print(archive); print((archive/'full-output.log').read_text()); sys.exit(result.returncode)
