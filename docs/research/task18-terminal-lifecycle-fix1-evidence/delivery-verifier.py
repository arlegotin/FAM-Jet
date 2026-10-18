import hashlib,json,os,subprocess
from pathlib import Path
root=Path.cwd(); evidence=root/'docs/research/task18-terminal-lifecycle-fix1-evidence'
source='75c0d0f4913388668e71444156ae3e63bee032db'; base='4815000fef3060f88518a8577713a0085aebb1f4'
checks=[]
for path in sorted(evidence.glob('*/manifest.json')):
    manifest=json.loads(path.read_text())
    for relative,expected in manifest.items():
        target=path.parent/relative; raw=target.read_bytes()
        assert len(raw)==expected['bytes'] and hashlib.sha256(raw).hexdigest()==expected['sha256'],str(target)
    checks.append(dict(check='archived attempt byte hashes',path=str(path.relative_to(root)),entries=len(manifest),pass_check=True))
for committed in ['validation/kernel_stage_a/monitor.py','tests/test_kernel_stage_a_terminal_lifecycle.py','tests/test_kernel_stage_a_native_process_fix1.py']:
    original=subprocess.check_output(['git','show',source+':'+committed])
    assert (evidence/'task18-terminal-fix1-scoped-cover-evy_hhso/source-inputs'/committed).read_bytes()==original
    assert (root/committed).read_bytes()==original
    checks.append(dict(check='final covering inputs equal source commit',path=committed,sha256=hashlib.sha256(original).hexdigest(),pass_check=True))
report=root/'.superpowers/sdd/2026-10-16-famjet/task-18-terminal-lifecycle-fix1-report.md'
durable=root/'docs/research/task18-kernel-stage-a-terminal-lifecycle-fix1-report.md'
assert report.read_bytes()==durable.read_bytes()
checks.append(dict(check='report copies byte equal',bytes=report.stat().st_size,sha256=hashlib.sha256(report.read_bytes()).hexdigest(),pass_check=True))
assert not json.loads((evidence/'prior-artifacts-audit.json').read_text())['mismatches']
assert json.loads((evidence/'source-audit.json').read_text())['package_unchanged']
for command in [['git','diff','--check',base,source]]:
    execution=subprocess.run(command,capture_output=True,text=True)
    checks.append(dict(check='source verification',command=command,exit=execution.returncode,stdout=execution.stdout,stderr=execution.stderr))
    assert execution.returncode==0
result=dict(source_git=source,checks=checks,status='byte/hash/whitespace verification PASS; earlier compile/source audit retained; no new tests/native; native gate remains NEEDS_CONTEXT')
(evidence/'delivery-verification.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
