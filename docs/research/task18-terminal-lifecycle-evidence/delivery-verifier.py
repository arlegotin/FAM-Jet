import hashlib,json,os,subprocess
from pathlib import Path
root=Path.cwd(); evidence=root/'docs/research/task18-terminal-lifecycle-evidence'
source='3044f3ca0cd935b4e3e53863cbe259fdcacd4c38'; base='1bc005abe7b323c7cc76358adecc6e71346296d2'
checks=[]
for path in sorted(evidence.glob('*/manifest.json')):
    manifest=json.loads(path.read_text())
    for relative,expected in manifest.items():
        target=path.parent/relative; raw=target.read_bytes()
        assert len(raw)==expected['bytes'] and hashlib.sha256(raw).hexdigest()==expected['sha256'],str(target)
    checks.append(dict(check='archived attempt byte hashes',path=str(path.relative_to(root)),entries=len(manifest),pass_check=True))
for archived,committed in [('committed-native-control.py','.superpowers/sdd/2026-10-16-famjet/task-18-terminal-lifecycle-native-control.py'),('committed-monitor.py','validation/kernel_stage_a/monitor.py')]:
    original=subprocess.check_output(['git','show',source+':'+committed])
    assert (evidence/'t18n-0zr5z837'/archived).read_bytes()==original
    assert (root/committed).read_bytes()==original
    checks.append(dict(check='native executed exact source commit blob',path=committed,sha256=hashlib.sha256(original).hexdigest(),pass_check=True))
report=root/'.superpowers/sdd/2026-10-16-famjet/task-18-terminal-lifecycle-report.md'
durable=root/'docs/research/task18-kernel-stage-a-terminal-lifecycle-report.md'
assert report.read_bytes()==durable.read_bytes()
checks.append(dict(check='report copies byte equal',bytes=report.stat().st_size,sha256=hashlib.sha256(report.read_bytes()).hexdigest(),pass_check=True))
assert not json.loads((evidence/'prior-artifacts-audit.json').read_text())['mismatches']
assert json.loads((evidence/'source-audit.json').read_text())['package_unchanged']
for command in [['git','diff','--check',base,source],['.venv/bin/python','-m','py_compile','validation/kernel_stage_a/monitor.py','.superpowers/sdd/2026-10-16-famjet/task-18-terminal-lifecycle-native-control.py']]:
    execution=subprocess.run(command,capture_output=True,text=True)
    checks.append(dict(check='source verification',command=command,exit=execution.returncode,stdout=execution.stdout,stderr=execution.stderr))
    assert execution.returncode==0
result=dict(source_git=source,checks=checks,status='byte/hash/whitespace/compile verification PASS; native compatibility remains NEEDS_CONTEXT')
(evidence/'delivery-verification.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
