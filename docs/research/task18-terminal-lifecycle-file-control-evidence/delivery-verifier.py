import ast,hashlib,json,os,subprocess
from pathlib import Path
root=Path.cwd(); evidence=root/'docs/research/task18-terminal-lifecycle-file-control-evidence'; source='9550cf38f12915ff81a261ff5372febf26d294d4'; base='f31b34bc1ec65a9a9cb1954cc4b0dba731c62579'
archive=evidence/'t18f-ot0owjzs'; checks=[]
for relative,expected in json.loads((archive/'manifest.json').read_text()).items():
    raw=(archive/relative).read_bytes(); assert len(raw)==expected['bytes'] and hashlib.sha256(raw).hexdigest()==expected['sha256'],relative
checks.append(dict(check='complete native attempt manifest',pass_check=True))
for name,relative in [('committed-parent.py','docs/research/task18-terminal-lifecycle-file-control.py'),('committed-worker.py','docs/research/task18-terminal-lifecycle-file-worker.py'),('committed-monitor.py','validation/kernel_stage_a/monitor.py')]:
    raw=subprocess.check_output(['git','show',source+':'+relative]); assert raw==(archive/name).read_bytes()==(root/relative).read_bytes()
    checks.append(dict(check='executed exact committed file',path=relative,bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),pass_check=True))
prior=json.loads((evidence/'prior-artifact-audit.json').read_text())
for relative,expected in prior['files'].items():
    path=root/relative; raw=os.fsencode(os.readlink(path)) if expected['mode']=='120000' else path.read_bytes()
    assert len(raw)==expected['bytes'] and hashlib.sha256(raw).hexdigest()==expected['sha256'],relative
checks.append(dict(check='all prior artifacts remain byte equal',entries=len(prior['files']),bytes=prior['bytes'],pass_check=True))
parent=root/'docs/research/task18-terminal-lifecycle-file-control.py'; worker=root/'docs/research/task18-terminal-lifecycle-file-worker.py'
original=root/'.superpowers/sdd/2026-10-16-famjet/task-18-terminal-lifecycle-native-control.py'
old_tree=ast.parse(original.read_bytes()); assignment=next(node for node in old_tree.body if isinstance(node,ast.Assign) and any(isinstance(target,ast.Name) and target.id=='ROOT_BODY' for target in node.targets))
assert worker.read_bytes()==ast.literal_eval(assignment.value).encode()
checks.append(dict(check='worker exact AST-extracted original bytes',pass_check=True))
report=root/'.superpowers/sdd/2026-10-16-famjet/task-18-terminal-lifecycle-file-control-report.md'; durable=root/'docs/research/task18-kernel-stage-a-terminal-lifecycle-file-control-report.md'
assert report.read_bytes()==durable.read_bytes()
checks.append(dict(check='new report copies byte equal',bytes=report.stat().st_size,sha256=hashlib.sha256(report.read_bytes()).hexdigest(),pass_check=True))
for command in [['git','diff','--check',base,source],['git','diff','--exit-code',base,'--','validation','tests','famjet','requirements.lock']]:
    completed=subprocess.run(command,capture_output=True,text=True); assert completed.returncode==0
    checks.append(dict(check='static source boundary/whitespace',command=command,exit=completed.returncode,stdout=completed.stdout,stderr=completed.stderr))
result=dict(source_git=source,checks=checks,static_delivery_status='PASS',native_diagnostic_compatibility='NEEDS_CONTEXT',native_execution_status='STOPPED',actual_root_returncode=0,survivor='NOT RUN',no_native_or_test_repeat=True)
(evidence/'delivery-verification.json').write_text(json.dumps(result,indent=2)+'\n'); print(json.dumps(result,indent=2))
