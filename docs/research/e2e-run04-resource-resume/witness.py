"""Root execution witness. Monitors only its newly created process group."""
from pathlib import Path
import datetime, hashlib, json, math, os, re, resource, shutil, signal, stat, subprocess, sys, time
ROOT=Path(subprocess.check_output(['git','rev-parse','--show-toplevel'],text=True).strip()).resolve()
allocation_path=Path(sys.argv[1]).resolve(); allocation=json.loads(allocation_path.read_bytes())
required={'expected_head','argv','out','prep','total_seconds','finalization_reserve_seconds','rss_cap_bytes','output_cap_bytes'}
if set(allocation) not in (required,required|{'resume_baseline_ref'}):raise ValueError('exact allocation fields required')
head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
if head!=allocation['expected_head'] or subprocess.check_output(['git','status','--porcelain'],cwd=ROOT):raise RuntimeError('requires clean exact source')
for key in ('total_seconds','finalization_reserve_seconds','rss_cap_bytes','output_cap_bytes'):
 if type(allocation[key]) not in (int,float) or not math.isfinite(allocation[key]) or allocation[key]<=0:raise ValueError(key)
if allocation['total_seconds']<=allocation['finalization_reserve_seconds']:raise ValueError('reserve exceeds allocation')
out=(ROOT/allocation['out']).resolve();prep=(ROOT/allocation['prep']).resolve()
if not out.is_relative_to(ROOT/'artifacts') or not prep.is_relative_to(ROOT/'artifacts') or prep.exists():raise ValueError('artifact output and fresh prep required')
if out==prep or out.is_relative_to(prep) or prep.is_relative_to(out):raise ValueError('distinct nonnested output/prep required')
for candidate in (Path(allocation['out']),Path(allocation['prep'])):
 path=candidate if candidate.is_absolute() else ROOT/candidate
 if '..' in path.parts or any(p.is_symlink() for p in (path,*path.parents)):raise ValueError('no output/prep symlinks or traversal')
resume_binding=None
def _sha(raw):return hashlib.sha256(raw).hexdigest()
def _safe(base,name):
 if type(name) is not str or not name or Path(name).is_absolute() or any(p in ('..','.') for p in name.split('/')):raise ValueError('unsafe baseline path')
 path=base/name
 if not path.resolve().is_relative_to(base.resolve()) or any(p.is_symlink() for p in (path,*path.parents)):raise ValueError('baseline symlink/traversal')
 return path
def _record(path):
 raw=path.read_bytes();return {'bytes':len(raw),'sha256':_sha(raw)}
def _check_record(path,record):
 if type(record) is not dict or set(record)!={'bytes','sha256'} or type(record['bytes']) is not int or record['bytes']<0 or type(record['sha256']) is not str or re.fullmatch('[0-9a-f]{64}',record['sha256']) is None or _record(path)!=record:raise ValueError('baseline byte/hash mismatch: '+str(path))
def _files(root):
 if not root.is_dir() or root.is_symlink():raise ValueError('existing plain output directory required')
 result={}
 for path in root.rglob('*'):
  if path.is_symlink():raise ValueError('symlink inside baseline output')
  if path.is_file():result[str(path.relative_to(root))]=_record(path)
  elif not path.is_dir():raise ValueError('nonregular baseline output')
 return result
def _immutable_paths():
 paths={str(p.relative_to(ROOT)) for p in (ROOT/'famjet').rglob('*.py')}
 paths|={str(p.relative_to(ROOT)) for p in (ROOT/'famjet_poc').glob('*.py') if p.name!='pipeline.py'}
 paths|={'requirements.lock','docs/reporting-requirements.lock','docs/research/e2e-study-config.json','docs/research/e2e-development-resource-policy.json','configs/manifests/beijing_v2_targets.json','docs/research/e2e-inference-qualification.json'}
 return paths
def validate_resume(ref):
 if type(ref) is not dict or set(ref)!={'path','bytes','sha256'}:raise ValueError('exact baseline ref required')
 baseline_path=_safe(ROOT,ref['path']);_check_record(baseline_path,{k:ref[k] for k in ('bytes','sha256')})
 baseline=json.loads(baseline_path.read_bytes())
 if type(baseline) is not dict or set(baseline)!={'schema_version','run_root','original_revision','files','immutable_sources','original_stage_start_epoch_seconds'} or baseline['schema_version']!=1:raise ValueError('baseline schema')
 if _safe(ROOT,baseline['run_root']).resolve()!=out or not out.is_dir():raise ValueError('baseline output mismatch')
 if baseline['original_revision']!='27dc49a0f61a12e9cf319d20c6cc9aeefe2a84dc':raise ValueError('original run04 revision mismatch')
 argv=allocation['argv']
 if type(argv) is not list or not all(type(v) is str for v in argv) or len(argv)!=7 or Path(argv[0]).resolve()!=Path(sys.executable).resolve() or argv[1:3]!=['-m','famjet_poc'] or argv.count('--resume')!=1 or argv.count('--out')!=1:raise ValueError('exact Python public CLI --resume argv required')
 # The actual CLI is python -m famjet_poc run --out PATH --resume.
 if argv[3]!='run' or argv[4]!='--out' or argv[6]!='--resume' or (ROOT/argv[5]).resolve()!=out:raise ValueError('resume CLI monitored --out mismatch')
 if type(baseline['files']) is not dict or not baseline['files']:raise ValueError('nonempty exact baseline file set required')
 for name,record in baseline['files'].items():_check_record(_safe(out,name),record)
 if _files(out)!=baseline['files']:raise ValueError('baseline output file set mismatch')
 immutable=baseline['immutable_sources']
 if type(immutable) is not dict or set(immutable)!=_immutable_paths():raise ValueError('exact immutable source/config set required')
 for name,record in immutable.items():_check_record(_safe(ROOT,name),record)
 ledger=json.loads(_safe(out,'run-ledger.json').read_bytes())
 if type(ledger) is not dict or set(ledger)!={'schema_version','kind','generations'} or ledger['schema_version']!=1 or ledger['kind']!='famjet_e4_stage_ledger' or type(ledger['generations']) is not list or not ledger['generations']:raise ValueError('public stage ledger schema')
 allowed={'preflight','probe_k16','development_k16','timing_k16','probe_k12','development_k12','probe_beijing_fit','transfer_fit'}
 previous='0'*64
 for index,row in enumerate(ledger['generations']):
  if type(row) is not dict or row.get('stage') not in allowed or row.get('status') not in {'running','completed','failed'}:raise ValueError('nonpublic/protected stage ledger rejected')
  payload={k:v for k,v in row.items() if k!='entry_sha256'}
  if row.get('generation')!=index or row.get('prior_sha256')!=previous or row.get('entry_sha256')!=_sha(json.dumps(payload,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()):raise ValueError('stage hash chain mismatch')
  previous=row['entry_sha256']
 last=ledger['generations'][-1]
 if last['stage']!='timing_k16' or last['status']!='failed':raise ValueError('failed public timing stage required')
 if not any(r['stage']=='development_k16' and r['status']=='completed' for r in ledger['generations']):raise ValueError('completed K16 development required')
 starts=[r['start_epoch_seconds'] for r in ledger['generations'] if r['stage']=='timing_k16' and r['status']=='running']
 clock=baseline['original_stage_start_epoch_seconds']
 if type(clock) not in (int,float) or not math.isfinite(clock) or clock<=0 or not starts or starts[0]!=clock:raise ValueError('original stage clock mismatch')
 for name in baseline['files']:
  if len(Path(name).parts)>1 and Path(name).parts[0] not in allowed:raise ValueError('nonpublic output directory rejected')
  if len(Path(name).parts)==1 and name not in {'run-ledger.json','run-policy.json'}:raise ValueError('unknown root output rejected')
 policy=json.loads(_safe(out,'run-policy.json').read_bytes())
 global_start=policy.get('start_epoch_seconds');global_seconds=policy.get('global_wall_seconds')
 if policy.get('schema_version')!=1 or any(type(v) not in (int,float) or not math.isfinite(v) or v<=0 for v in (global_start,global_seconds)):raise ValueError('original global clock required')
 return {'ref':ref,'baseline_sha256':ref['sha256'],'original_revision':baseline['original_revision'],'current_revision':head,'original_stage_start_epoch_seconds':clock,'original_stage_wall_seconds':1800,'original_global_start_epoch_seconds':global_start,'original_global_wall_seconds':global_seconds,'original_global_deadline_epoch_seconds':global_start+global_seconds,'output_file_count':len(baseline['files']),'immutable_source_count':len(immutable),'old_output_bytes':sum(v['bytes'] for v in baseline['files'].values()),'run_root':baseline['run_root']}
def remaining_original_seconds(binding):
 now=time.time()
 stage=binding['original_stage_start_epoch_seconds']+binding['original_stage_wall_seconds']-now
 overall=binding['original_global_start_epoch_seconds']+binding['original_global_wall_seconds']-now
 if stage<=0:raise RuntimeError('original timing stage deadline expired before launch')
 if overall<=0:raise RuntimeError('original global deadline expired before launch')
 return {'stage':stage,'global':overall}
if 'resume_baseline_ref' in allocation:
 resume_binding=validate_resume(allocation['resume_baseline_ref'])
 remaining_original_seconds(resume_binding)
elif out.exists():raise ValueError('fresh artifact directories required; existing output needs resume baseline')
vm=subprocess.check_output(['vm_stat'],text=True);page=int(re.search(r'page size of (\d+)',vm)[1])
vm_pages={key.strip():int(value.strip()[:-1]) for line in vm.splitlines() if ':' in line
          for key,value in [line.split(':',1)] if re.fullmatch(r'[0-9]+\.',value.strip())}
def num(name):return vm_pages[name]
if page<=0:raise ValueError('positive vm_stat page size required')
raw_free=(num('Pages free')+num('Pages speculative'))*page
try:pressure=subprocess.check_output(['sysctl','-n','kern.memorystatus_vm_pressure_level'],text=True).strip()
except (OSError,subprocess.CalledProcessError):pressure=''
try:cached_pages=max(0,min(num('Pages inactive'),num('File-backed pages'))-num('Pages speculative'))
except KeyError:cached_pages=0
cache_credit=(cached_pages*page)//2 if pressure=='1' else 0
free=raw_free+cache_credit
if free<2*2**30 or .75*free<allocation['rss_cap_bytes'] or shutil.disk_usage(ROOT).free<allocation['output_cap_bytes']+4*2**30:raise RuntimeError('fresh admission refused')
prep.mkdir(parents=True)
def save(name,value):
 p=prep/name;t=p.with_suffix(p.suffix+'.tmp');t.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n');t.replace(p)
def _count_output_bytes(roots):
 def scan_error(error):
  if not isinstance(error,(FileNotFoundError,NotADirectoryError)):raise error
 total=0
 for root in roots:
  try:root_info=Path(root).stat()
  except FileNotFoundError:continue
  if not stat.S_ISDIR(root_info.st_mode):raise NotADirectoryError(root)
  for directory,_,filenames in os.walk(root,onerror=scan_error):
   for filename in filenames:
    try:info=os.stat(os.path.join(directory,filename))
    except (FileNotFoundError,NotADirectoryError):continue
    if stat.S_ISREG(info.st_mode):total+=info.st_size
 return total
def accepted_exit(value):
 original=value['original_global_deadline_epoch_seconds']
 return (value['actual_returncode']==0 and value['guard_failure'] is None and
         value['source_after']==value['source_head'] and value['source_after_clean'] and
         value['end_monotonic']<value['deadline'] and
         (original is None or value['end_epoch_seconds']<original))
initial_output_bytes=_count_output_bytes((out,prep))
if initial_output_bytes>allocation['output_cap_bytes']:raise RuntimeError('existing output exceeds cap')
original_remaining=remaining_original_seconds(resume_binding) if resume_binding else None
start=time.monotonic();deadline=start+allocation['total_seconds'];work_deadline=deadline-allocation['finalization_reserve_seconds']
if original_remaining is not None:work_deadline=min(work_deadline,start+original_remaining['global'])
original_global_deadline=resume_binding['original_global_deadline_epoch_seconds'] if resume_binding else None
rec={'schema':1,'utc_start':datetime.datetime.now(datetime.timezone.utc).isoformat(),'source_head':head,'allocation':allocation,'allocation_sha256':hashlib.sha256(allocation_path.read_bytes()).hexdigest(),'witness_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'start_monotonic':start,'work_deadline':work_deadline,'deadline':deadline,'original_global_deadline_epoch_seconds':original_global_deadline,'vm_page_size_bytes':page,'vm_pages':vm_pages,'raw_free_ram_bytes':raw_free,'cache_credit_bytes':cache_credit,'vm_pressure_level':pressure,'free_ram_bytes':free,'ram_estimate_policy':'raw_free_plus_half_non_speculative_filebacked_inactive_when_pressure_1','free_disk_bytes':shutil.disk_usage(ROOT).free,'measurement':'sum of current RSS for this wrapper and the owned process group; conservative on shared pages','status':'starting'}
rec.update(resume_baseline=resume_binding,initial_output_bytes=initial_output_bytes,monitored_out=str(out),fresh_prep=str(prep))
save('admission.json',rec);samples=[];guard=None;actual=None;child=None;output_bytes=0;last_disk=-math.inf
try:
 env=dict(os.environ,OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',VECLIB_MAXIMUM_THREADS='1')
 with (prep/'stdout.log').open('wb') as stdout,(prep/'stderr.log').open('wb') as stderr:
  if resume_binding:remaining_original_seconds(resume_binding)
  child=subprocess.Popen(allocation['argv'],cwd=ROOT,env=env,stdin=subprocess.DEVNULL,stdout=stdout,stderr=stderr,start_new_session=True)
  rec['child_pid']=child.pid;rec['status']='running';save('admission.json',rec)
  while child.poll() is None:
   now=time.monotonic()
   if now>=work_deadline:guard='work_deadline';break
   result=subprocess.run(['ps','-axo','pid=,ppid=,pgid=,rss='],capture_output=True,text=True,timeout=5)
   if result.returncode:guard='rss_monitor_failed';break
   processes=[tuple(map(int,line.split())) for line in result.stdout.splitlines() if line.strip()]
   owned=[r for r in processes if r[0]==os.getpid() or r[2]==child.pid]
   rss=sum(r[3]*1024 for r in owned)
   if now-last_disk>=5:
    output_bytes=_count_output_bytes((out,prep));last_disk=now
   samples.append({'monotonic':now,'rss_sum_bytes':rss,'owned_pids':[r[0] for r in owned],'output_bytes_last_sample':output_bytes})
   if rss>allocation['rss_cap_bytes'] or output_bytes>allocation['output_cap_bytes']:guard='resource_cap';break
   time.sleep(.5)
  if guard:
   try:os.killpg(child.pid,signal.SIGTERM)
   except ProcessLookupError:pass
   try:child.wait(timeout=2)
   except subprocess.TimeoutExpired:
    try:os.killpg(child.pid,signal.SIGKILL)
    except ProcessLookupError:pass
  actual=child.wait(timeout=5)
except BaseException as exc:
 guard=guard or type(exc).__name__+': '+str(exc)
 if child is not None:
  try:os.killpg(child.pid,signal.SIGKILL)
  except ProcessLookupError:pass
  try:actual=child.wait(timeout=5)
  except subprocess.TimeoutExpired:pass
finally:
 end=time.monotonic();end_epoch=time.time();after=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip();after_clean=not subprocess.check_output(['git','status','--porcelain'],cwd=ROOT)
 if original_global_deadline is not None and end_epoch>=original_global_deadline:guard=guard or 'original_global_deadline'
 rec.update(status='returned',actual_returncode=actual,guard_failure=guard,end_monotonic=end,end_epoch_seconds=end_epoch,elapsed_seconds=end-start,utc_end=datetime.datetime.now(datetime.timezone.utc).isoformat(),source_after=after,source_after_clean=after_clean,samples=samples,maximum_sampled_rss_sum_bytes=max((s['rss_sum_bytes'] for s in samples),default=None),child_lifetime_peak_rss_bytes=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,output_bytes=_count_output_bytes((out,prep)))
 save('exit-witness.json',rec)
print(json.dumps({k:rec[k] for k in ('actual_returncode','guard_failure','elapsed_seconds','maximum_sampled_rss_sum_bytes','output_bytes')}))
raise SystemExit(0 if accepted_exit(rec) else 1)
