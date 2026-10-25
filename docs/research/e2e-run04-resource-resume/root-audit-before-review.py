from pathlib import Path
import ast,datetime,hashlib,json,shutil,subprocess,time
w=Path('.superpowers/sdd/2026-10-16-famjet'); d=Path('docs/research/e2e-run04-resource-resume');d.mkdir(exist_ok=False);base='27dc49a0f61a12e9cf319d20c6cc9aeefe2a84dc'
def rec(p):
 b=p.read_bytes();return {'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}
e=Path('docs/research/e2e-cache-memory-resume-evidence');v=json.loads((e/'verification.json').read_bytes());n=0
for q in v['checks']:
 for stream in ['stdout','stderr']:
  p=e/(q['label']+'.'+stream+'.log'); assert rec(p)=={'bytes':q[stream+'_bytes'],'sha256':q[stream+'_sha256']};n+=1
for p in (e/'fake-repo').rglob('*.json'):
 q=json.loads(p.read_bytes())
 if 'log_sha256' in q:
  assert rec(p.with_suffix('.log'))=={'bytes':q['log_bytes'],'sha256':q['log_sha256']};n+=1
old=ast.parse(subprocess.check_output(['git','show',base+':famjet_poc/pipeline.py'],text=True));now=ast.parse(Path('famjet_poc/pipeline.py').read_text())
old.body=[x for x in old.body if not isinstance(x,ast.FunctionDef) or x.name!='observe_resources'];now.body=[x for x in now.body if not isinstance(x,ast.FunctionDef) or x.name!='observe_resources'];now.body=[x for x in now.body if not isinstance(x,ast.Import) or not any(a.name=='re' for a in x.names)]
calls=[x for x in ast.walk(now) if isinstance(x,ast.Call) and isinstance(x.func,ast.Attribute) and x.func.attr=='stage' and x.args and isinstance(x.args[0],ast.Constant) and x.args[0].value=='timing_k16'];assert len(calls)==1
k=[x for x in calls[0].keywords if x.arg=='retryable'];assert len(k)==1 and isinstance(k[0].value,ast.Constant) and k[0].value.value is True;calls[0].keywords.remove(k[0]);assert ast.dump(old)==ast.dump(now)
b=json.loads((w/'e2e-run04-resume-baseline.json').read_bytes());out=Path(b['run_root']);assert {str(p.relative_to(out)):rec(p) for p in out.rglob('*') if p.is_file()}==b['files']
for name,r in b['immutable_sources'].items():
 assert rec(Path(name))==r
 assert Path(name).read_bytes()==subprocess.check_output(['git','show',base+':'+name])
helper=w/'e2e-run04-resume-witness.py';assert rec(helper)['sha256']=='d1fb1fdb48e9aa5ded8a1fb851698ddf027eed80230e8dc00b506e69d78a78e6'
shutil.copyfile(helper,d/'witness.py');shutil.copyfile(w/'e2e-cache-memory-resume-test-witness.py',d/'test-witness.py');shutil.copyfile(w/'e2e-run04-resume-baseline.json',d/'baseline.json');shutil.copyfile(w/'e2e-run04-failed-public-index.json',d/'failed-public-index.json')
for name in ['host.json','host.log']:shutil.copyfile(Path('artifacts/e2e-run04-memory-diagnosis')/name,d/name)
for name in ['admission.json','exit-witness.json','stdout.log','stderr.log']:shutil.copyfile(Path('artifacts/e2e-core-run-04-prep')/name,d/('initial-'+name))
r={'schema_version':1,'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'base':base,'source_head':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'verified_raw_log_pairs':n,'pipeline_scope':'observer+re_import+only_timing_k16_retryable_keyword_AST_verified','unchanged_original_immutable_files':len(b['immutable_sources']),'unchanged_original_output_files':len(b['files']),'unchanged_output_bytes':sum(x['bytes'] for x in b['files'].values()),'baseline':rec(d/'baseline.json'),'helper':rec(d/'witness.py'),'original_timing_start_epoch_seconds':b['original_stage_start_epoch_seconds'],'original_timing_deadline_epoch_seconds':b['original_stage_start_epoch_seconds']+1800,'timing_remaining_seconds':b['original_stage_start_epoch_seconds']+1800-time.time(),'review_status':'pending_independent','actual_resume':'not_entered'}
(d/'root-audit.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2))
