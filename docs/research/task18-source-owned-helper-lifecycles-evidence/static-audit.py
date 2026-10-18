import ast,datetime,hashlib,json,pathlib,shutil,subprocess,time
root=pathlib.Path('/Users/artemlegotin/Documents/git_alter/FAM-Jet'); ev=root/'docs/research/task18-source-owned-helper-lifecycles-evidence'
started=time.monotonic(); utc=datetime.datetime.now(datetime.timezone.utc).isoformat()
paths=['validation/kernel_stage_a/monitor.py','validation/kernel_stage_a/source_lifecycles.py','validation/kernel_stage_a/authority.py','validation/kernel_stage_a/production.py','validation/kernel_stage_a/README.md','tests/test_kernel_stage_a_source_lifecycles.py','docs/research/task18-source-owned-helper-native-control.py','docs/research/task18-source-owned-helper-native-worker.py']
manifest={}
for name in paths:
 p=root/name; raw=p.read_bytes()
 if p.suffix=='.py':ast.parse(raw)
 manifest[name]={'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw),'AST':p.suffix=='.py'}
package={str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((root/'famjet').rglob('*.py'))}
package_hash=hashlib.sha256(json.dumps(package,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()).hexdigest()
lock_hash=hashlib.sha256((root/'requirements.lock').read_bytes()).hexdigest()
checks={}
for label,cmd in [('diff_check',['git','diff','--check']),('protected_diff',['git','diff','--name-only','100bf1c900e955d855267ba86d11c94948dcd3dd','--','famjet','requirements.lock','validation/kernel_stage_a/authority.py','validation/kernel_stage_a/production.py','validation/kernel_stage_a/commands.py','validation/kernel_stage_a/reader_worker.py','validation/kernel_stage_a/fixture-descriptors.json','validation/kernel_stage_a/frozen-training-metadata.json','tests/test_kernel_stage_a_owned_root_terminal.py','tests/test_kernel_stage_a_native_process_fix2.py'])]:
 r=subprocess.run(cmd,cwd=root,capture_output=True,text=True); checks[label]={'command':cmd,'exit':r.returncode,'stdout':r.stdout,'stderr':r.stderr}
base=subprocess.run(['git','show','100bf1c900e955d855267ba86d11c94948dcd3dd:validation/kernel_stage_a/monitor.py'],cwd=root,capture_output=True,text=True,check=True).stdout
current=(root/'validation/kernel_stage_a/monitor.py').read_text()
methods=['owned_baseline_event','owned_candidate','qualify_owned_root','owned_terminal','root_sample']
def nodes(source):
 cls=next(n for n in ast.parse(source).body if isinstance(n,ast.ClassDef) and n.name=='PythonLifetimes')
 return {n.name:ast.dump(n,include_attributes=False) for n in cls.body if isinstance(n,ast.FunctionDef)}
x,y=nodes(base),nodes(current); same={name:x[name]==y[name] for name in methods}
result={'utc_start':utc,'monotonic_start':started,'source_base':'100bf1c900e955d855267ba86d11c94948dcd3dd','files':manifest,'package_hash':package_hash,'lock_sha256':lock_hash,'checks':checks,'root_receipt_methods_AST_unchanged':same,'native_execution':False}
result.update(utc_end=datetime.datetime.now(datetime.timezone.utc).isoformat(),monotonic_end=time.monotonic())
(ev/'static-audit.json').write_text(json.dumps(result,indent=2)+'\n')
shutil.copyfile('/private/tmp/task18-source-lifecycle-capture.py',ev/'capture.py')
shutil.copyfile(__file__,ev/'static-audit.py')
print(json.dumps(result,indent=2))
