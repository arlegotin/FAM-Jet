"""Root execution witness. Monitors only its newly created process group."""
from pathlib import Path
import datetime, hashlib, json, math, os, re, resource, shutil, signal, subprocess, sys, time
ROOT=Path(__file__).resolve().parents[3]
allocation_path=Path(sys.argv[1]).resolve(); allocation=json.loads(allocation_path.read_bytes())
required={'expected_head','argv','out','prep','total_seconds','finalization_reserve_seconds','rss_cap_bytes','output_cap_bytes'}
if set(allocation)!=required:raise ValueError('exact allocation fields required')
head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
if head!=allocation['expected_head'] or subprocess.check_output(['git','status','--porcelain'],cwd=ROOT):raise RuntimeError('requires clean exact source')
for key in ('total_seconds','finalization_reserve_seconds','rss_cap_bytes','output_cap_bytes'):
 if type(allocation[key]) not in (int,float) or not math.isfinite(allocation[key]) or allocation[key]<=0:raise ValueError(key)
if allocation['total_seconds']<=allocation['finalization_reserve_seconds']:raise ValueError('reserve exceeds allocation')
out=(ROOT/allocation['out']).resolve();prep=(ROOT/allocation['prep']).resolve()
if not out.is_relative_to(ROOT/'artifacts') or not prep.is_relative_to(ROOT/'artifacts') or out.exists() or prep.exists():raise ValueError('fresh artifact directories required')
vm=subprocess.check_output(['vm_stat'],text=True);page=int(re.search(r'page size of (\d+)',vm)[1]);num=lambda n:int(re.search(rf'{n}:\s+(\d+)',vm)[1]);free=(num('Pages free')+num('Pages speculative'))*page
if free<2*2**30 or .75*free<allocation['rss_cap_bytes'] or shutil.disk_usage(ROOT).free<allocation['output_cap_bytes']+4*2**30:raise RuntimeError('fresh admission refused')
prep.mkdir(parents=True)
def save(name,value):
 p=prep/name;t=p.with_suffix(p.suffix+'.tmp');t.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n');t.replace(p)
start=time.monotonic();deadline=start+allocation['total_seconds'];work_deadline=deadline-allocation['finalization_reserve_seconds']
rec={'schema':1,'utc_start':datetime.datetime.now(datetime.timezone.utc).isoformat(),'source_head':head,'allocation':allocation,'allocation_sha256':hashlib.sha256(allocation_path.read_bytes()).hexdigest(),'witness_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'start_monotonic':start,'work_deadline':work_deadline,'deadline':deadline,'free_plus_speculative':free,'free_disk_bytes':shutil.disk_usage(ROOT).free,'measurement':'sum of current RSS for this wrapper and the owned process group; conservative on shared pages','status':'starting'}
save('admission.json',rec);samples=[];guard=None;actual=None;child=None;output_bytes=0;last_disk=-math.inf
try:
 env=dict(os.environ,OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',VECLIB_MAXIMUM_THREADS='1')
 with (prep/'stdout.log').open('wb') as stdout,(prep/'stderr.log').open('wb') as stderr:
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
    output_bytes=sum(p.stat().st_size for d in (out,prep) if d.exists() for p in d.rglob('*') if p.is_file());last_disk=now
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
 end=time.monotonic();after=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
 rec.update(status='returned',actual_returncode=actual,guard_failure=guard,end_monotonic=end,elapsed_seconds=end-start,utc_end=datetime.datetime.now(datetime.timezone.utc).isoformat(),source_after=after,samples=samples,maximum_sampled_rss_sum_bytes=max((s['rss_sum_bytes'] for s in samples),default=None),child_lifetime_peak_rss_bytes=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,output_bytes=sum(p.stat().st_size for d in (out,prep) if d.exists() for p in d.rglob('*') if p.is_file()))
 save('exit-witness.json',rec)
print(json.dumps({k:rec[k] for k in ('actual_returncode','guard_failure','elapsed_seconds','maximum_sampled_rss_sum_bytes','output_bytes')}))
raise SystemExit(0 if actual==0 and guard is None and after==head and end<deadline else 1)
