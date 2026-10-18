"""Read-only source/static audit; never imports monitored or scientific runtime."""
import ast,hashlib,json,os,stat,subprocess,sys,time
from pathlib import Path
root=Path.cwd(); archive=root/'docs/research/task18-owned-root-lifecycle-evidence'
base='ace9b7cb6b37ab9909f5b07cf5a255dfb3a82dd7'
def sha(raw): return hashlib.sha256(raw).hexdigest()
def meta(path):
    if path.is_symlink():
        raw=os.fsencode(os.readlink(path)); return dict(kind='symlink',bytes=len(raw),sha256=sha(raw),target=os.readlink(path))
    raw=path.read_bytes(); return dict(kind='regular',bytes=len(raw),sha256=sha(raw))
def write(name,value): (archive/name).write_text(json.dumps(value,indent=2)+'\n')
prior={}; mismatches=[]
for line in subprocess.check_output(['git','ls-tree','-r',base],text=True).splitlines():
    head,name=line.split('\t'); mode,kind,blob=head.split()
    if kind!='blob' or not (name.startswith('docs/research/task18') or name.startswith('famjet/') or name.startswith('tests/') or name in ('requirements.lock','validation/kernel_stage_a/authority.py','validation/kernel_stage_a/commands.py')): continue
    path=root/name
    raw=os.fsencode(os.readlink(path)) if mode=='120000' else path.read_bytes()
    actual=hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
    prior[name]=dict(bytes=len(raw),sha256=sha(raw),base_git_blob=blob,actual_git_blob=actual)
    if actual!=blob: mismatches.append(name)
write('unchanged-audit.json',dict(base=base,files=prior,mismatches=mismatches))
package={str(p.relative_to(root)):sha(p.read_bytes()) for p in sorted((root/'famjet').rglob('*.py'))}
package_hash=sha(json.dumps(package,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode())
lock_hash=sha((root/'requirements.lock').read_bytes())
previous=json.loads((root/'docs/research/task18-kernel-projection-source-verification.json').read_bytes())['identities']['memory_components']
memory={name:dict(expected=value['current_sha256'],actual=package[name]) for name,value in previous.items()}
assert not mismatches
assert package_hash=='15cf84c28136d4f5ec34c173316d0db1f2aab1da97c6d68993a5c22bf18ec050'
assert lock_hash=='2b1931e022c8e2555c45a9f9fb5feead7077b9043bfc088fc2db3e811bbe21d1'
assert len(memory)==15 and all(v['actual']==v['expected'] for v in memory.values())
paths=['validation/kernel_stage_a/monitor.py','validation/kernel_stage_a/README.md','tests/test_kernel_stage_a_owned_root_terminal.py','docs/research/task18-owned-root-lifecycle-native-control.py','docs/research/task18-owned-root-lifecycle-native-worker.py']
source={name:meta(root/name) for name in paths}
for name in paths:
    if name.endswith('.py'): ast.parse((root/name).read_bytes(),filename=name)
write('source-audit.json',dict(base=base,source_files=source,package_hash=package_hash,lock_hash=lock_hash,memory_components=memory,unchanged_prior_files=len(prior),ast_parse=True,native_executed=False,scientific_import_executed=False))
worker=root/paths[-1]; parent=root/paths[-2]
worker_tree=ast.parse(worker.read_bytes()); parent_tree=ast.parse(parent.read_bytes())
imports=[alias.name for node in ast.walk(worker_tree) if isinstance(node,ast.Import) for alias in node.names]
assert 'torch' in imports and 'famjet' in imports
assert sum(isinstance(node,ast.Call) and isinstance(node.func,ast.Name) and node.func.id=='record_baseline' for node in ast.walk(worker_tree))==1
vectors=[node.value for node in ast.walk(parent_tree) if isinstance(node,ast.Assign) and any(isinstance(target,ast.Name) and target.id=='vector' for target in node.targets)]
assert len(vectors)==1 and isinstance(vectors[0],ast.List)
assert [ast.literal_eval(node) for node in vectors[0].elts[1:3]]==['-I','-B']
write('native-static-inputs.json',dict(executed=False,parent=meta(parent),worker=meta(worker),parent_path=str(parent),worker_path=str(worker),
    launch_executable=str(root/'.venv/bin/python'),parent_vector=[str(root/'.venv/bin/python'),'-I','-B',str(parent),'<fresh separately allocated destination>'],
    worker_vectors=[[str(root/'.venv/bin/python'),'-I','-B',str(worker),case,'<destination>/'+case+'.socket','<repr(actual case deadline)>'] for case in ('empty','survivor')],
    dynamic_slots='Destination and monotonic deadlines are deliberately unallocated; later root release must freeze concrete values and actual vector hashes.',
    allocation_seconds=10,ordered_cases=['empty','survivor'],case_seconds=4.5,reserve_seconds=.25,incremental_bytes=201326592,output_bytes=67108864,thread_ceiling=4,worker_threads=1,
    static_ast_only=True,real_record_baseline_calls=1,normal_torch_famjet_imports=True))
attempts=[]; preservation={}; failures=[]
for directory in sorted(archive.glob('task18-owned-root-lifecycle-*')):
    attempt=json.loads((directory/'attempt.json').read_text()); attempts.append(dict(path=str(directory.relative_to(archive)),**attempt))
    manifest=json.loads((directory/'manifest.json').read_text())
    for name,value in manifest.items():
        if meta(directory/name)['sha256']!=value['sha256']: failures.append(str(directory/name))
    original=Path(attempt['owned_base'])/'specimens'
    if original.exists():
        for path in original.rglob('*'):
            mode=path.lstat().st_mode
            if stat.S_ISREG(mode) or stat.S_ISLNK(mode):
                target=directory/'specimens'/path.relative_to(original)
                left=meta(path); right=meta(target)
                preservation[str(path)]=dict(archive=str(target.relative_to(root)),original=left,retained=right,equal=left==right)
                if left!=right: failures.append(str(path))
assert not failures
write('attempt-index.json',attempts)
write('specimen-preservation.json',dict(files=preservation,mismatches=failures,originals_retained=True,symlinks='raw payload; not followed',specials='not followed'))
print(json.dumps(dict(attempts=len(attempts),retained_specimen_files=len(preservation),unchanged_files=len(prior),memory_components=len(memory),package_hash=package_hash,lock_hash=lock_hash,source_files=source),indent=2))
