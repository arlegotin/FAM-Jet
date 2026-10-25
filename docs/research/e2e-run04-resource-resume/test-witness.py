"""Stdlib subprocess fixtures in disposable miniature Git repositories only."""
from pathlib import Path
import ast
import hashlib, json, os, subprocess, sys, tempfile, time

HERE=Path(__file__).resolve().parent
HELPER=HERE/'e2e-run04-resume-witness.py'
RUN=Path(os.environ.get('FAMJET_E6_EVIDENCE_ROOT',
                        str(HERE/'e2e-cache-memory-resume-evidence')))/f'attempt-{time.time_ns()}'
RUN.mkdir(parents=True)
function=next(node for node in ast.parse(HELPER.read_text()).body
              if isinstance(node,ast.FunctionDef) and node.name=='accepted_exit')
namespace={}
exec(compile(ast.Module(body=[function],type_ignores=[]),str(HELPER),'exec'),namespace)
accepted_exit=namespace['accepted_exit']
boundary={'actual_returncode':0,'guard_failure':None,'source_after':'clean-head',
          'source_head':'clean-head','source_after_clean':True,'end_monotonic':19.,
          'deadline':20.,'original_global_deadline_epoch_seconds':1000.,
          'end_epoch_seconds':999.999}
assert accepted_exit(boundary)
assert not accepted_exit({**boundary,'end_epoch_seconds':1000.})
assert not accepted_exit({**boundary,'end_epoch_seconds':1000.001})
assert accepted_exit({**boundary,'original_global_deadline_epoch_seconds':None,
                      'end_epoch_seconds':1000.001})
(RUN/'final-exit-boundary.json').write_text(json.dumps(
    {'helper_sha256':hashlib.sha256(HELPER.read_bytes()).hexdigest(),
     'original_global_deadline_epoch_seconds':1000.,
     'accepted_before':999.999,'rejected_at':1000.,'rejected_after':1000.001,
     'fresh_mode_without_original_deadline_accepted':True},indent=2)+'\n')
CONFIGS=('requirements.lock','docs/reporting-requirements.lock','docs/research/e2e-study-config.json','docs/research/e2e-development-resource-policy.json','configs/manifests/beijing_v2_targets.json','docs/research/e2e-inference-qualification.json')
def sha(raw):return hashlib.sha256(raw).hexdigest()
def canonical(value):return json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()
def record(path):
 raw=path.read_bytes();return {'bytes':len(raw),'sha256':sha(raw)}
def dump(path,value):path.write_text(json.dumps(value,sort_keys=True)+'\n')
def invoke(argv,cwd,label):
 start=time.monotonic();epoch=time.time()
 p=subprocess.run(argv,cwd=cwd,capture_output=True,timeout=40,
                  env={**os.environ,'PATH':str(cwd/'bin')+os.pathsep+os.environ['PATH']})
 raw=p.stdout+b'\n--- STDERR ---\n'+p.stderr
 log=RUN/(label+'.log');log.write_bytes(raw)
 dump(RUN/(label+'.json'),{'argv':argv,'cwd':str(cwd),'exit_code':p.returncode,'start_epoch_seconds':epoch,'elapsed_seconds':time.monotonic()-start,'log_bytes':len(raw),'log_sha256':sha(raw)})
 return p
def git(root,*args):
 return subprocess.check_output(['git',*args],cwd=root,stderr=subprocess.STDOUT,text=True).strip()
def fixture(root, child_sleep=.15):
 git(root,'init','-q')
 for key,value in (('user.email','fixture@example.invalid'),('user.name','Fixture'),('commit.gpgsign','false')):git(root,'config',key,value)
 files={'.gitignore':'artifacts/\nbin/\n__pycache__/\n','famjet/core.py':'# numeric fixture\n',
        'famjet_poc/__init__.py':'','famjet_poc/pipeline.py':'# old observer\n','famjet_poc/report.py':'# old report\n','famjet_poc/report_inputs.py':'# old report adapter\n',
        'famjet_poc/__main__.py':f"import argparse,json,os,time\nfrom pathlib import Path\np=argparse.ArgumentParser();p.add_argument('command');p.add_argument('--out');p.add_argument('--resume',action='store_true');a=p.parse_args();out=Path(a.out);out.mkdir(parents=True,exist_ok=True);(out/'child-marker.json').write_text(json.dumps({{'pid':os.getpid(),'pgid':os.getpgrp(),'resume':a.resume}}));time.sleep({child_sleep!r})\n"}
 files.update({p:'fixture\n' for p in CONFIGS})
 for name,body in files.items():
  path=root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(body)
 git(root,'add','.');git(root,'commit','-qm','fixture base')
 oldhead=git(root,'rev-parse','HEAD')
 bindir=root/'bin';bindir.mkdir()
 for name,body in {'vm_stat': '#!/bin/sh\nprintf "Mach Virtual Memory Statistics: (page size of 16384 bytes)\\nPages free: 50000.\\nPages speculative: 10000.\\nPages inactive: 400000.\\nFile-backed pages: 400000.\\n"\n',
                   'sysctl': '#!/bin/sh\necho 1\n',
                   'ps': '#!/bin/sh\nexit 0\n'}.items():
  path=bindir/name;path.write_text(body);path.chmod(0o755)
 out=root/'artifacts/run';out.mkdir(parents=True)
 (out/'development_k16').mkdir();(out/'development_k16/public.bin').write_bytes(b'p'*8192)
 now=time.time()
 rows=[]
 def append(stage,status,start):
  row={'stage':stage,'status':status,'start_epoch_seconds':start,
       'generation':len(rows),'prior_sha256':rows[-1]['entry_sha256'] if rows else '0'*64}
  row['entry_sha256']=sha(canonical(row));rows.append(row)
 append('development_k16','completed',now-600)
 append('timing_k16','running',now-120)
 append('timing_k16','failed',now-120)
 dump(out/'run-ledger.json',{'schema_version':1,'kind':'famjet_e4_stage_ledger','generations':rows})
 dump(out/'run-policy.json',{'schema_version':1,'start_epoch_seconds':now-600,'global_wall_seconds':21600})
 imm={p:record(root/p) for p in files if p.startswith('famjet/') or (p.startswith('famjet_poc/') and p!='famjet_poc/pipeline.py') or p in CONFIGS}
 baseline={'schema_version':1,'run_root':'artifacts/run','original_revision':'27dc49a0f61a12e9cf319d20c6cc9aeefe2a84dc',
           'files':{str(p.relative_to(out)):record(p) for p in out.rglob('*') if p.is_file()},
           'immutable_sources':imm,'original_stage_start_epoch_seconds':now-120}
 return out,baseline,oldhead

cases=('existing_without_baseline','valid_resume_pipeline_commit','valid_stage_transition','changed_output','changed_numeric','invalid_baseline_sha','protected_ledger','wrong_out','missing_resume','fresh_mode','clock_changed','extra_output','symlink_output','immutable_set_missing','existing_prep','expired_stage','expired_global','wrong_executable','warning_pressure','missing_cache_stat','global_expiry_during_poll')
if os.environ.get('FAMJET_E6_ONLY_CASE'):
 cases=(os.environ['FAMJET_E6_ONLY_CASE'],)
overall=time.monotonic();results=[]
for case in cases:
 with tempfile.TemporaryDirectory(prefix='famjet-witness-fixture-') as temp:
  root=Path(temp);out,baseline,oldhead=fixture(root,child_sleep=2.5 if case=='valid_stage_transition' else 2.5 if case=='global_expiry_during_poll' else .15)
  alloc={'expected_head':oldhead,'argv':[sys.executable,'-m','famjet_poc','run','--out','artifacts/run','--resume'],
         'out':'artifacts/run','prep':'artifacts/prep','total_seconds':15,'finalization_reserve_seconds':2,
         'rss_cap_bytes':512*1024**2,'output_cap_bytes':4*1024**2}
  if case=='valid_resume_pipeline_commit':
   (root/'famjet_poc/pipeline.py').write_text('# changed observer only\n');git(root,'add','famjet_poc/pipeline.py');git(root,'commit','-qm','observer only');alloc['expected_head']=git(root,'rev-parse','HEAD')
  if case=='changed_output':(out/'development_k16/public.bin').write_bytes(b'changed')
  if case=='changed_numeric':
   (root/'famjet/core.py').write_text('# changed numeric\n');git(root,'add','famjet/core.py');git(root,'commit','-qm','numeric change');alloc['expected_head']=git(root,'rev-parse','HEAD')
  if case=='protected_ledger':
   ledger=json.loads((out/'run-ledger.json').read_bytes());row=ledger['generations'][0];row['stage']='freeze';row['entry_sha256']=sha(canonical({k:v for k,v in row.items() if k!='entry_sha256'}));dump(out/'run-ledger.json',ledger);baseline['files']['run-ledger.json']=record(out/'run-ledger.json')
  if case=='wrong_out':alloc['argv'][5]='artifacts/wrong'
  if case=='missing_resume':alloc['argv'].remove('--resume')
  if case=='clock_changed':baseline['original_stage_start_epoch_seconds']=1235.
  if case=='valid_stage_transition':
   ledger=json.loads((out/'run-ledger.json').read_bytes());ledger['generations'][1]['start_epoch_seconds']=time.time()-1798
   for index,row in enumerate(ledger['generations']):
    row['prior_sha256']=ledger['generations'][index-1]['entry_sha256'] if index else '0'*64
    row['entry_sha256']=sha(canonical({k:v for k,v in row.items() if k!='entry_sha256'}))
   dump(out/'run-ledger.json',ledger);baseline['files']['run-ledger.json']=record(out/'run-ledger.json')
   baseline['original_stage_start_epoch_seconds']=ledger['generations'][1]['start_epoch_seconds']
  if case=='expired_stage':
   ledger=json.loads((out/'run-ledger.json').read_bytes());ledger['generations'][1]['start_epoch_seconds']=time.time()-1801
   for index,row in enumerate(ledger['generations']):
    row['prior_sha256']=ledger['generations'][index-1]['entry_sha256'] if index else '0'*64
    row['entry_sha256']=sha(canonical({k:v for k,v in row.items() if k!='entry_sha256'}))
   dump(out/'run-ledger.json',ledger);baseline['files']['run-ledger.json']=record(out/'run-ledger.json')
   baseline['original_stage_start_epoch_seconds']=ledger['generations'][1]['start_epoch_seconds']
  if case=='expired_global':
   policy=json.loads((out/'run-policy.json').read_bytes());policy['start_epoch_seconds']=time.time()-21601
   dump(out/'run-policy.json',policy);baseline['files']['run-policy.json']=record(out/'run-policy.json')
  if case=='global_expiry_during_poll':
   policy=json.loads((out/'run-policy.json').read_bytes());policy['start_epoch_seconds']=time.time()-21600+1.5
   dump(out/'run-policy.json',policy);baseline['files']['run-policy.json']=record(out/'run-policy.json')
   (root/'bin/ps').write_text('#!/bin/sh\nsleep 3.5\n')
  if case=='wrong_executable':alloc['argv'][0]='/usr/bin/true'
  if case=='warning_pressure':(root/'bin/sysctl').write_text('#!/bin/sh\necho 2\n')
  if case=='missing_cache_stat':(root/'bin/vm_stat').write_text('#!/bin/sh\nprintf "Mach Virtual Memory Statistics: (page size of 16384 bytes)\\nPages free: 50000.\\nPages speculative: 10000.\\n"\n')
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
  expected_pass=case in ('valid_resume_pipeline_commit','valid_stage_transition','fresh_mode')
  monitored=root/alloc['out'];marker=monitored/'child-marker.json'
  assert (p.returncode==0)==expected_pass,(case,p.returncode,p.stderr.decode(),p.stdout.decode())
  assert marker.exists()==(expected_pass or case=='global_expiry_during_poll'),(case,'unexpected child execution')
  if case=='global_expiry_during_poll':
   witness=json.loads((root/'artifacts/prep/exit-witness.json').read_bytes())
   assert witness['actual_returncode']==0 and witness['guard_failure']=='original_global_deadline'
   assert witness['end_epoch_seconds']>=witness['original_global_deadline_epoch_seconds']
   assert witness['source_after_clean']
   dump(RUN/(case+'-witness.json'),witness)
  if expected_pass:
   witness=json.loads((root/'artifacts/prep/exit-witness.json').read_bytes());child=json.loads(marker.read_bytes())
   assert child['pid']==child['pgid']==witness['child_pid']
   assert witness['actual_returncode']==0 and witness['guard_failure'] is None and witness['source_after_clean']
   if case in ('valid_resume_pipeline_commit','valid_stage_transition'):
    assert witness['initial_output_bytes']>=sum(v['bytes'] for v in baseline['files'].values())
    assert witness['resume_baseline']['original_revision']==baseline['original_revision']
    if case=='valid_resume_pipeline_commit':assert witness['source_head']!=oldhead
    assert witness['resume_baseline']['original_stage_start_epoch_seconds']==baseline['original_stage_start_epoch_seconds']
    assert witness['resume_baseline']['original_global_start_epoch_seconds']<time.time()
    assert witness['cache_credit_bytes']==195000*16384
    assert witness['raw_free_ram_bytes']==60000*16384
    if case=='valid_stage_transition':
     assert witness['elapsed_seconds']>2.0 and witness['work_deadline']-witness['start_monotonic']>10
   else:assert witness['resume_baseline'] is None
   # Preserve the witness evidence after the disposable fixture is removed.
   dump(RUN/(case+'-witness.json'),witness)
  for name,commitment in old_output.items():assert record(out/name)==commitment,(case,'old bytes mutated',name)
  results.append({'case':case,'status':'passed','witness_returncode':p.returncode})
  print(case,'PASS',flush=True)
dump(RUN/'test-summary.json',{'helper_sha256':sha(HELPER.read_bytes()),'cases':results,'elapsed_seconds':time.monotonic()-overall,'scientific_imports':False,'actual_run_data_accessed':False})
print(f'{len(results)} fixture cases passed',flush=True)
