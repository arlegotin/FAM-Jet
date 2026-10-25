import ast,datetime,hashlib,json,pathlib,shutil,subprocess,sys,time
root=pathlib.Path.cwd(); base='95c9557edda09eea02f3ff3296edd6f87155ef1c'; dst=root/'docs/research/e2e-report-timing-root-acceptance';dst.mkdir(exist_ok=True)
def rec(p):
 raw=p.read_bytes();return {'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}
receipts=[]
for p in (root/'docs/research/e2e-report-timing-fix-evidence').glob('*.json'):
 v=json.loads(p.read_bytes())
 if 'log' in v:
  q=root/v['log']; assert rec(q)=={'bytes':v['bytes'],'sha256':v['sha256']};receipts.append(str(p.relative_to(root)))
paths=subprocess.check_output(['git','ls-tree','-r','--name-only',base],text=True).splitlines(); unchanged=0; changed=[]
changed=sorted(set(paths).intersection(subprocess.check_output(['git','diff','--name-only',base],text=True).splitlines()))
unchanged=len(paths)-len(changed)
assert set(changed)=={'famjet_poc/report.py','famjet_poc/report_inputs.py','tests/test_poc_report_scientific.py'},changed
for name,allowed in [('report.py',{'_science_chart_data','_science_markdown'}),('report_inputs.py',{'_verify_timing'})]:
 old=ast.parse(subprocess.check_output(['git','show',base+':famjet_poc/'+name],text=True));now=ast.parse((root/'famjet_poc'/name).read_text())
 for tree in old,now:tree.body=[n for n in tree.body if not isinstance(n,ast.FunctionDef) or n.name not in allowed]
 assert ast.dump(old)==ast.dump(now)
review=root/'.superpowers/sdd/2026-10-16-famjet/e2e-report-timing-fix-review.md';shutil.copyfile(review,dst/'independent-review.md')
stop=root/'.superpowers/sdd/2026-10-16-famjet/e2e-run03-public-stop.json';shutil.copyfile(stop,dst/'run03-public-stop.json')
for name in ['admission.json','exit-witness.json','stdout.log','stderr.log']:
 p=root/'artifacts/e2e-core-run-03-prep'/name;shutil.copyfile(p,dst/('run03-'+name))
ledger=json.loads((root/'artifacts/e2e-core-run-03/run-ledger.json').read_bytes());first=next(r['start_epoch_seconds'] for r in ledger['generations'] if r['stage']=='development_k16' and r['status']=='running')
files={str(p.relative_to(root/'artifacts/e2e-core-run-03')):rec(p) for p in (root/'artifacts/e2e-core-run-03').rglob('*') if p.is_file()}
index={'schema_version':1,'run_root':'artifacts/e2e-core-run-03','status':'public_interruption_retained_stage_expired_no_resume','files':files,'file_count':len(files),'bytes':sum(r['bytes'] for r in files.values()),'original_stage_start_epoch_seconds':first,'original_stage_deadline_epoch_seconds':first+3600,'observed_epoch_seconds':time.time(),'protected_access':'not_entered'}
(dst/'run03-index.json').write_text(json.dumps(index,indent=2)+'\n')
accept={'schema_version':1,'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'base':base,'reviewed_head':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'unchanged_existing_tracked_files':unchanged,'changed_existing_files':changed,'raw_log_receipts_verified':receipts,'named_function_AST_scope_verified':True,'review':rec(dst/'independent-review.md'),'run03':{'files':len(files),'bytes':index['bytes'],'expired_original_stage_clock':time.time()>first+3600,'no_resume':True},'next':'fresh run04, original absolute six-hour overall deadline retained; no protected outcomes inspected; all earlier failures/interruption/costs retained'}
(dst/'root-acceptance.json').write_text(json.dumps(accept,indent=2)+'\n');print(json.dumps(accept,indent=2))
