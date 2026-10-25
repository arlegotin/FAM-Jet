"""Stdlib subprocess fixtures in disposable miniature Git repositories only."""
from pathlib import Path
import hashlib, json, os, subprocess, sys, tempfile, time

HERE=Path(__file__).resolve().parent
HELPER=HERE.parent/'e2e-resume-witness.py'
RUN=HERE/f'attempt-{time.time_ns()}'
RUN.mkdir()
CONFIGS=('requirements.lock','docs/reporting-requirements.lock','docs/research/e2e-study-config.json','docs/research/e2e-development-resource-policy.json','configs/manifests/beijing_v2_targets.json','docs/research/e2e-inference-qualification.json')
def sha(raw):return hashlib.sha256(raw).hexdigest()
def canonical(value):return json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()
def record(path):
 raw=path.read_bytes();return {'bytes':len(raw),'sha256':sha(raw)}
def dump(path,value):path.write_text(json.dumps(value,sort_keys=True)+'\n')
def invoke(argv,cwd,label):
 start=time.monotonic();epoch=time.time()
 p=subprocess.run(argv,cwd=cwd,capture_output=True,timeout=40)
 raw=p.stdout+b'\n--- STDERR ---\n'+p.stderr
 log=RUN/(label+'.log');log.write_bytes(raw)
 dump(RUN/(label+'.json'),{'argv':argv,'cwd':str(cwd),'exit_code':p.returncode,'start_epoch_seconds':epoch,'elapsed_seconds':time.monotonic()-start,'log_bytes':len(raw),'log_sha256':sha(raw)})
 return p
def git(root,*args):
 return subprocess.check_output(['git',*args],cwd=root,stderr=subprocess.STDOUT,text=True).strip()
def fixture(root):
 git(root,'init','-q')
 for key,value in (('user.email','fixture@example.invalid'),('user.name','Fixture'),('commit.gpgsign','false')):git(root,'config',key,value)
 files={'.gitignore':'artifacts/\n__pycache__/\n','famjet/core.py':'# numeric fixture\n',
        'famjet_poc/__init__.py':'','famjet_poc/report.py':'# old report\n','famjet_poc/report_inputs.py':'# old report adapter\n',
        'famjet_poc/__main__.py':"import argparse,json,os,time\nfrom pathlib import Path\np=argparse.ArgumentParser();p.add_argument('command');p.add_argument('--out');p.add_argument('--resume',action='store_true');a=p.parse_args();out=Path(a.out);out.mkdir(parents=True,exist_ok=True);(out/'child-marker.json').write_text(json.dumps({'pid':os.getpid(),'pgid':os.getpgrp(),'resume':a.resume}));time.sleep(.15)\n"}
 files.update({p:'fixture\n' for p in CONFIGS})
 for name,body in files.items():
  path=root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(body)
 git(root,'add','.');git(root,'commit','-qm','fixture base')
 oldhead=git(root,'rev-parse','HEAD')
 out=root/'artifacts/run';out.mkdir(parents=True)
 (out/'development_k16').mkdir();(out/'development_k16/public.bin').write_bytes(b'p'*8192)
 row={'stage':'development_k16','status':'running','start_epoch_seconds':1234.,'generation':0,'prior_sha256':'0'*64}
 row['entry_sha256']=sha(canonical(row))
 dump(out/'run-ledger.json',{'schema_version':1,'kind':'famjet_e4_stage_ledger','generations':[row]})
 dump(out/'run-policy.json',{'schema_version':1,'start_epoch_seconds':1200.,'global_wall_seconds':21600})
 imm={p:record(root/p) for p in files if p.startswith('famjet/') or (p.startswith('famjet_poc/') and p not in ('famjet_poc/report.py','famjet_poc/report_inputs.py')) or p in CONFIGS}
 baseline={'schema_version':1,'run_root':'artifacts/run','original_revision':oldhead,
           'files':{str(p.relative_to(out)):record(p) for p in out.rglob('*') if p.is_file()},
           'immutable_sources':imm,'original_stage_start_epoch_seconds':1234.}
 return out,baseline,oldhead

cases=('existing_without_baseline','valid_resume_report_commit','changed_output','changed_numeric','invalid_baseline_sha','protected_ledger','wrong_out','missing_resume','fresh_mode','clock_changed','extra_output','symlink_output','immutable_set_missing','existing_prep')
overall=time.monotonic();results=[]
for case in cases:
 with tempfile.TemporaryDirectory(prefix='famjet-witness-fixture-') as temp:
  root=Path(temp);out,baseline,oldhead=fixture(root)
  alloc={'expected_head':oldhead,'argv':[sys.executable,'-m','famjet_poc','run','--out','artifacts/run','--resume'],
         'out':'artifacts/run','prep':'artifacts/prep','total_seconds':15,'finalization_reserve_seconds':2,
         'rss_cap_bytes':512*1024**2,'output_cap_bytes':4*1024**2}
  if case=='valid_resume_report_commit':
   (root/'famjet_poc/report.py').write_text('# changed report only\n');git(root,'add','famjet_poc/report.py');git(root,'commit','-qm','report only');alloc['expected_head']=git(root,'rev-parse','HEAD')
  if case=='changed_output':(out/'development_k16/public.bin').write_bytes(b'changed')
  if case=='changed_numeric':
   (root/'famjet/core.py').write_text('# changed numeric\n');git(root,'add','famjet/core.py');git(root,'commit','-qm','numeric change');alloc['expected_head']=git(root,'rev-parse','HEAD')
  if case=='protected_ledger':
   ledger=json.loads((out/'run-ledger.json').read_bytes());row=ledger['generations'][0];row['stage']='freeze';row['entry_sha256']=sha(canonical({k:v for k,v in row.items() if k!='entry_sha256'}));dump(out/'run-ledger.json',ledger);baseline['files']['run-ledger.json']=record(out/'run-ledger.json')
  if case=='wrong_out':alloc['argv'][5]='artifacts/wrong'
  if case=='missing_resume':alloc['argv'].remove('--resume')
  if case=='clock_changed':baseline['original_stage_start_epoch_seconds']=1235.
  if case=='extra_output':(out/'development_k16/extra').write_text('extra')
  if case=='symlink_output':(out/'development_k16/link').symlink_to(out/'development_k16/public.bin')
  if case=='immutable_set_missing':baseline['immutable_sources'].pop('requirements.lock')
  if case=='existing_prep':(root/'artifacts/prep').mkdir()
  baseline_path=root/'artifacts/baseline.json';dump(baseline_path,baseline)
  if case not in ('existing_without_baseline','fresh_mode'):
   alloc['resume_baseline_ref']={'path':'artifacts/baseline.json',**record(baseline_path)}
  if case=='invalid_baseline_sha':alloc['resume_baseline_ref']['sha256']='0'*64
  if case=='fresh_mode':
   alloc['out']='artifacts/fresh';alloc['argv'][5]='artifacts/fresh';alloc['argv'].remove('--resume')
  allocation_path=root/'artifacts/allocation.json';dump(allocation_path,alloc)
  old_output={str(p.relative_to(out)):record(p) for p in out.rglob('*') if p.is_file() and not p.is_symlink()}
  p=invoke([sys.executable,str(HELPER),str(allocation_path)],root,case)
  expected_pass=case in ('valid_resume_report_commit','fresh_mode')
  monitored=root/alloc['out'];marker=monitored/'child-marker.json'
  assert (p.returncode==0)==expected_pass,(case,p.returncode,p.stderr.decode(),p.stdout.decode())
  assert marker.exists()==expected_pass,(case,'unexpected child execution')
  if expected_pass:
   witness=json.loads((root/'artifacts/prep/exit-witness.json').read_bytes());child=json.loads(marker.read_bytes())
   assert child['pid']==child['pgid']==witness['child_pid']
   assert witness['actual_returncode']==0 and witness['guard_failure'] is None and witness['source_after_clean']
   if case=='valid_resume_report_commit':
    assert witness['initial_output_bytes']>=sum(v['bytes'] for v in baseline['files'].values())
    assert witness['resume_baseline']['original_revision']==oldhead and witness['source_head']!=oldhead
    assert witness['resume_baseline']['original_stage_start_epoch_seconds']==1234.
    assert witness['resume_baseline']['original_global_start_epoch_seconds']==1200.
   else:assert witness['resume_baseline'] is None
   # Preserve the witness evidence after the disposable fixture is removed.
   dump(RUN/(case+'-witness.json'),witness)
  for name,commitment in old_output.items():assert record(out/name)==commitment,(case,'old bytes mutated',name)
  results.append({'case':case,'status':'passed','witness_returncode':p.returncode})
  print(case,'PASS',flush=True)
dump(RUN/'test-summary.json',{'helper_sha256':sha(HELPER.read_bytes()),'cases':results,'elapsed_seconds':time.monotonic()-overall,'scientific_imports':False,'actual_run_data_accessed':False})
print(f'{len(results)} fixture cases passed',flush=True)
