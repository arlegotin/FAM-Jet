import ast,hashlib,json,subprocess
from pathlib import Path
root=Path.cwd(); original=root/'.superpowers/sdd/2026-10-16-famjet/task-18-terminal-lifecycle-native-control.py'
raw=original.read_bytes(); tree=ast.parse(raw)
assignment=next(node for node in tree.body if isinstance(node,ast.Assign) and any(isinstance(target,ast.Name) and target.id=='ROOT_BODY' for target in node.targets))
body=ast.literal_eval(assignment.value)
worker=root/'docs/research/task18-terminal-lifecycle-file-worker.py'
parent=root/'docs/research/task18-terminal-lifecycle-file-control.py'
worker.write_bytes(body.encode())
lines=raw.decode().splitlines(keepends=True)
source=''.join(lines[:assignment.lineno-1]+lines[assignment.end_lineno:])
source=source.replace('"""ONE committed stdlib native control; no science, retries or owning orphan reap."""','"""ONE corrected file-input stdlib control; no science, retries or orphan reap."""')
source=source.replace('import errno\n','import ast\nimport errno\n')
source=source.replace('ROOT=Path(__file__).resolve().parents[3]','ROOT=Path(__file__).resolve().parents[2]')
source=source.replace("    destination=Path(sys.argv[1]).resolve()\n", """    parent_path=Path(__file__).resolve()
    worker_path=(ROOT/'docs/research/task18-terminal-lifecycle-file-worker.py').resolve()
    original_path=ROOT/'.superpowers/sdd/2026-10-16-famjet/task-18-terminal-lifecycle-native-control.py'
    original_tree=ast.parse(original_path.read_bytes())
    original_assignment=next(node for node in original_tree.body if isinstance(node,ast.Assign) and
        any(isinstance(target,ast.Name) and target.id=='ROOT_BODY' for target in node.targets))
    original_body=ast.literal_eval(original_assignment.value).encode()
    parent_bytes=parent_path.read_bytes(); worker_bytes=worker_path.read_bytes()
    ast.parse(parent_bytes); ast.parse(worker_bytes)
    assert worker_bytes==original_body,'worker input differs from the old committed ROOT_BODY'
    inputs=dict(parent_path=str(parent_path),parent_sha256=hashlib.sha256(parent_bytes).hexdigest(),
                parent_bytes=len(parent_bytes),worker_path=str(worker_path),
                worker_sha256=hashlib.sha256(worker_bytes).hexdigest(),worker_bytes=len(worker_bytes),
                original_control_path=str(original_path),original_control_sha256=hashlib.sha256(original_path.read_bytes()).hexdigest(),
                worker_body_byte_equal=True,parent_ast_parse=True,worker_ast_parse=True,
                monitor_path=str(Path(monitor.__file__).resolve()),
                monitor_sha256=hashlib.sha256(Path(monitor.__file__).read_bytes()).hexdigest())
    destination=Path(sys.argv[1]).resolve()
""")
source=source.replace("                source_git=os.environ['TASK18_SOURCE_GIT'],control_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())", "                source_git=os.environ['TASK18_SOURCE_GIT'],control_sha256=inputs['parent_sha256'],inputs=inputs)")
source=source.replace("            vector=[sys.executable,'-I','-S','-c',ROOT_BODY,case,str(peer_path),repr(case_deadline)]", "            vector=[sys.executable,'-I','-B','-S',str(worker_path),case,str(peer_path),repr(case_deadline)]")
source=source.replace("            record.update(vector=vector,vector_sha256=commands.vector_hash(vector))", "            record.update(vector=vector,vector_sha256=commands.vector_hash(vector),inputs=dict(inputs))")
source=source.replace("            assert ends[0]['launch_id']==launches[0]['launch_id'] and ends[0]['reaped'] and type(ends[0]['returncode']) is int", "            assert ends[0]['launch_id']==launches[0]['launch_id'] and ends[0]['reaped'] and type(ends[0]['returncode']) is int\n            assert ends[0]['returncode']==0,'after-exit control requires actual natural root returncode0'")
source=source.replace("                assert signals and all(row['success'] and row['owner_unreaped'] for row in signals)", "                assert not any(row['pid']==root_pid for row in members),'root still present during survivor cleanup query'\n                assert signals and all(row['success'] and row['owner_unreaped'] for row in signals)")
source=source.replace("                assert any(row['pid']==child['pid'] for row in members),'genuine survivor was not queried'", "                queried=[row for row in members if row['pid']==child['pid']]\n                assert len(queried)==1,'genuine survivor was not queried uniquely'\n                assert queried[0]['parent']!=root_pid and queried[0]['pgid']==root_pid,'survivor was not queried after root exit/reparenting'")
parent.write_bytes(source.encode())
ast.parse(parent.read_bytes()); ast.parse(worker.read_bytes())
assert worker.read_bytes()==body.encode()
assert '[sys.executable,\'-I\',\'-B\',\'-S\',str(worker_path),case,str(peer_path),repr(case_deadline)]' in parent.read_text()
print(json.dumps(dict(parent_bytes=parent.stat().st_size,parent_sha256=hashlib.sha256(parent.read_bytes()).hexdigest(),worker_bytes=worker.stat().st_size,worker_sha256=hashlib.sha256(worker.read_bytes()).hexdigest(),original_sha256=hashlib.sha256(raw).hexdigest(),worker_body_byte_equal=True),indent=2))
