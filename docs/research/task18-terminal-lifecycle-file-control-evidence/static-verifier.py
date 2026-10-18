import ast,hashlib,json,os,subprocess
from pathlib import Path
root=Path.cwd(); evidence=root/'docs/research/task18-terminal-lifecycle-file-control-evidence'
base='f31b34bc1ec65a9a9cb1954cc4b0dba731c62579'
original=root/'.superpowers/sdd/2026-10-16-famjet/task-18-terminal-lifecycle-native-control.py'
parent=root/'docs/research/task18-terminal-lifecycle-file-control.py'; worker=root/'docs/research/task18-terminal-lifecycle-file-worker.py'
original_tree=ast.parse(original.read_bytes())
assignment=next(node for node in original_tree.body if isinstance(node,ast.Assign) and any(isinstance(target,ast.Name) and target.id=='ROOT_BODY' for target in node.targets))
assert worker.read_bytes()==ast.literal_eval(assignment.value).encode()
parent_tree=ast.parse(parent.read_bytes()); ast.parse(worker.read_bytes())
compile(parent.read_bytes(),str(parent),'exec'); compile(worker.read_bytes(),str(worker),'exec')
vectors=[node.value for node in ast.walk(parent_tree) if isinstance(node,ast.Assign) and any(isinstance(target,ast.Name) and target.id=='vector' for target in node.targets)]
assert len(vectors)==1
assert ast.unparse(vectors[0])=="[sys.executable, '-I', '-B', '-S', str(worker_path), case, str(peer_path), repr(case_deadline)]"
for path in ['validation/kernel_stage_a/monitor.py','validation/kernel_stage_a/authority.py','validation/kernel_stage_a/commands.py','.superpowers/sdd/2026-10-16-famjet/task-18-terminal-lifecycle-native-control.py','.superpowers/sdd/2026-10-16-famjet/task-18-terminal-lifecycle-report.md','docs/research/task18-kernel-stage-a-terminal-lifecycle-report.md']:
    assert (root/path).read_bytes()==subprocess.check_output(['git','show',base+':'+path])
unchanged=subprocess.run(['git','diff','--exit-code',base,'--','validation','tests','famjet','requirements.lock'],capture_output=True,text=True)
assert unchanged.returncode==0
tracked={}; mismatches=[]
for line in subprocess.check_output(['git','ls-tree','-r',base],text=True).splitlines():
    header,path=line.split('\t'); mode,kind,blob=header.split()
    if kind!='blob' or not (path.startswith('docs/research/task18') or path.startswith('.superpowers/sdd/2026-10-16-famjet/task-18-terminal-lifecycle')): continue
    file=root/path
    raw=os.fsencode(os.readlink(file)) if mode=='120000' else file.read_bytes()
    current=hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
    tracked[path]=dict(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),mode=mode,base_git_blob=blob,current_git_blob=current,byte_equal=current==blob)
    if current!=blob: mismatches.append(path)
assert not mismatches
(evidence/'prior-artifact-audit.json').write_text(json.dumps(dict(base_git=base,files=tracked,file_count=len(tracked),bytes=sum(row['bytes'] for row in tracked.values()),mismatches=mismatches),indent=2)+'\n')
inputs={str(path.relative_to(root)):dict(bytes=path.stat().st_size,sha256=hashlib.sha256(path.read_bytes()).hexdigest()) for path in [parent,worker,original,root/'validation/kernel_stage_a/monitor.py']}
result=dict(base_git=base,inputs=inputs,worker_body_byte_equal=True,parent_ast_parse=True,worker_ast_parse=True,parent_compile=True,worker_compile=True,vector_ast=ast.unparse(vectors[0]),worker_case_semantics='exact original body bytes; no execution',unchanged_production_tests_package=dict(command=unchanged.args,exit=unchanged.returncode,stdout=unchanged.stdout,stderr=unchanged.stderr),prior_artifact_count=len(tracked),prior_artifact_bytes=sum(row['bytes'] for row in tracked.values()),prior_artifact_mismatches=mismatches,status='PASS static only; native not yet attempted')
(evidence/'static-verification.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
