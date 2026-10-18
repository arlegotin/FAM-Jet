import datetime, hashlib, json, os, pathlib, shutil, subprocess, sys, tempfile, time
root=pathlib.Path('/Users/artemlegotin/Documents/git_alter/FAM-Jet')
ev=root/'docs/research/task18-source-owned-helper-lifecycles-evidence/fix2'; ev.mkdir(exist_ok=True)
if sys.argv[1]=='snapshot':
    paths=['validation/kernel_stage_a/monitor.py','validation/kernel_stage_a/authority.py','validation/kernel_stage_a/production.py','validation/kernel_stage_a/README.md']
    manifest={'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'monotonic':time.monotonic(),'base':'100bf1c900e955d855267ba86d11c94948dcd3dd','files':{}}
    for name in paths:
        target=ev/'pre-edit'/name; target.parent.mkdir(parents=True,exist_ok=True); shutil.copyfile(root/name,target)
        manifest['files'][name]=hashlib.sha256(target.read_bytes()).hexdigest()
    (ev/'pre-edit-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
else:
    label=sys.argv[1]; base=tempfile.mkdtemp(prefix='task18-source-lifecycle-fix2-'+label+'-',dir='/private/tmp')
    cmd=[str(root/'.venv/bin/python'),'-m','pytest',*sys.argv[2:],'--basetemp='+base]
    meta={'command':cmd,'cwd':str(root),'environment':{k:os.environ.get(k) for k in ('PATH','PYTHONPATH','VIRTUAL_ENV','PYTEST_ADDOPTS')},'utc_start':datetime.datetime.now(datetime.timezone.utc).isoformat(),'monotonic_start':time.monotonic(),'basetemp':base}
    (ev/(label+'.json')).write_text(json.dumps(meta,indent=2)+'\n')
    with (ev/(label+'.log')).open('wb') as out: result=subprocess.run(cmd,cwd=root,stdout=out,stderr=subprocess.STDOUT)
    meta.update(exit=result.returncode,utc_end=datetime.datetime.now(datetime.timezone.utc).isoformat(),monotonic_end=time.monotonic())
    meta['duration']=meta['monotonic_end']-meta['monotonic_start']; (ev/(label+'.json')).write_text(json.dumps(meta,indent=2)+'\n')
    print(json.dumps(meta)); print((ev/(label+'.log')).read_text())
