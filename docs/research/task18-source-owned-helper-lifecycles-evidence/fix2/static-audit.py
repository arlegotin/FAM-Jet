import ast,datetime,hashlib,json,pathlib,subprocess,time
root=pathlib.Path.cwd(); ev=root/'docs/research/task18-source-owned-helper-lifecycles-evidence/fix2'; base='f02a432cdd63359be7d1938e7d62a3ec57c48df0'
started=time.monotonic(); utc=datetime.datetime.now(datetime.timezone.utc).isoformat()
paths=['validation/kernel_stage_a/monitor.py','validation/kernel_stage_a/source_lifecycles.py','tests/test_kernel_stage_a_source_lifecycles.py','docs/research/task18-source-owned-helper-native-control.py','docs/research/task18-source-owned-helper-native-worker.py']
files={}
for name in paths:
 raw=(root/name).read_bytes(); ast.parse(raw); files[name]=dict(sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw),AST=True)
package={str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((root/'famjet').rglob('*.py'))}
package_hash=hashlib.sha256(json.dumps(package,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()).hexdigest(); lock=hashlib.sha256((root/'requirements.lock').read_bytes()).hexdigest()
checks={}
protected=['famjet','requirements.lock','validation/kernel_stage_a/authority.py','validation/kernel_stage_a/production.py','validation/kernel_stage_a/commands.py','validation/kernel_stage_a/reader_worker.py','validation/kernel_stage_a/fixture-descriptors.json','validation/kernel_stage_a/frozen-training-metadata.json','tests/test_kernel_stage_a_owned_root_terminal.py','tests/test_kernel_stage_a_native_process_fix2.py',*paths[1:2],*paths[3:]]
for label,cmd in [('diff_check',['git','diff','--check']),('protected_diff',['git','diff','--name-only',base,'--',*protected])]:
 r=subprocess.run(cmd,capture_output=True,text=True,check=True); assert not r.stdout; checks[label]=dict(command=cmd,exit=r.returncode,stdout=r.stdout,stderr=r.stderr)
def methods(source): return {n.name:ast.dump(n,include_attributes=False) for n in ast.walk(ast.parse(source)) if isinstance(n,ast.FunctionDef)}
a=methods(subprocess.run(['git','show',base+':validation/kernel_stage_a/monitor.py'],capture_output=True,text=True,check=True).stdout); b=methods((root/paths[0]).read_text())
same={k:a[k]==b[k] for k in ['owned_baseline_event','owned_candidate','qualify_owned_root','owned_terminal','root_sample','root_end','_git_phase_valid']}; assert all(same.values())
index=[]
for label in ('red01','red02','green01','cover01','cover02'):
 metadata=json.loads((ev/(label+'.json')).read_text()); lines=(ev/(label+'.log')).read_text().splitlines()
 metadata.update(label=label,summary=next(line for line in reversed(lines) if ' in ' in line and ('passed' in line or 'failed' in line)),failures=[line for line in lines if line.startswith('FAILED ')]); index.append(metadata)
(ev/'attempt-index.json').write_text(json.dumps(index,indent=2)+'\n')
manifest=json.loads((ev/'specimen-manifest.json').read_text())
for relative in ('test_unrecoverable_source_jour1/partial','test_unsampled_git_still_requi2/monitor'):
 directory=pathlib.Path(index[-1]['basetemp'])/relative
 for name in ('monitor.json','monitor-evidence.jsonl','monitor-events.jsonl','stdout.log','stderr.log'):
  source=directory/name; data=source.read_bytes(); target=ev/'specimens/cover02'/relative/name; target.parent.mkdir(parents=True,exist_ok=True); target.write_bytes(data)
  manifest.append(dict(original=str(source),archive=str(target.relative_to(root)),bytes=len(data),sha256=hashlib.sha256(data).hexdigest()))
for item in manifest:
 assert hashlib.sha256(pathlib.Path(item['original']).read_bytes()).hexdigest()==item['sha256']==hashlib.sha256((root/item['archive']).read_bytes()).hexdigest()
(ev/'specimen-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
result=dict(base=base,utc_start=utc,monotonic_start=started,files=files,package_hash=package_hash,lock_sha256=lock,checks=checks,protected_methods_AST_unchanged=same,native_input_execution=False,utc_end=datetime.datetime.now(datetime.timezone.utc).isoformat(),monotonic_end=time.monotonic(),stdlib_wait_source_sha256=hashlib.sha256((ev/'posix-popen-wait.txt').read_bytes()).hexdigest(),specimens=len(manifest),specimen_bytes=sum(item['bytes'] for item in manifest))
(ev/'static-audit.json').write_text(json.dumps(result,indent=2)+'\n'); (ev/'static-audit.py').write_text(pathlib.Path(__file__).read_text()); print(json.dumps(result,indent=2))
