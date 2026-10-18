import sys,os,signal,subprocess,time,json,traceback,pathlib,select
ROOT=pathlib.Path('/Users/artemlegotin/Documents/git_alter/FAM-Jet');sys.path.insert(0,str(ROOT))
from validation.kernel_stage_a.authority import process_image
OUT=pathlib.Path(__file__).resolve().parent
start=time.monotonic();deadline=start+10
report=dict(scope='NEW nonnumerical owned-group exit syscall diagnosis only',start=start,deadline=deadline,cases=[],numerical_work=0)
def record(path,value):
 raw=json.dumps(value,sort_keys=True,indent=2).encode();assert len(raw)<1048576
 with path.open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
def attempt(row,name,fn):
 t=time.monotonic()
 try:
  value=fn();row['operations'].append(dict(name=name,status='ok',value=value,start=t,end=time.monotonic()));return value
 except BaseException as e:
  row['operations'].append(dict(name=name,status='error',type=type(e).__name__,errno=getattr(e,'errno',None),message=str(e),traceback=traceback.format_exc(),start=t,end=time.monotonic()));return None
try:
 for name,body in [('live','import sys;sys.stdout.buffer.write(bytes([82,69,65,68,89,10]));sys.stdout.buffer.flush();sys.stdin.buffer.read(1)'),('natural_exit_unreaped','pass')]:
  assert time.monotonic()<deadline-2
  vector=[sys.executable,'-I','-B','-c',body]
  row=dict(name=name,vector=vector,operations=[],images=[]);report['cases'].append(row)
  p=subprocess.Popen(vector,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,start_new_session=True,close_fds=True)
  row.update(pid=p.pid,parent=os.getpid(),parent_pgid=os.getpgrp(),launch=time.monotonic())
  try:
   if name=='live':
    ready=select.select([p.stdout],[],[],min(2,deadline-time.monotonic()))[0];assert ready and p.stdout.readline()==b'READY\n'
    row['ready']=True
    group=attempt(row,'getpgid_owned_live',lambda:os.getpgid(p.pid));assert group==p.pid and group!=row['parent_pgid']
   else:
    # Observe termination without reaping. The exact child PID remains reserved
    # by our own unreaped Popen, so its group identifier cannot be reused.
    ready=select.select([p.stdout],[],[],min(2,deadline-time.monotonic()))[0];assert ready and p.stdout.read()==b''
    bound=min(deadline-2,time.monotonic()+2)
    while True:
     image=process_image(p.pid);row['images'].append(image)
     if image.get('status')=='error':
      assert image.get('errno')==3 and image.get('reason')=='native_lookup_failed';break
     assert time.monotonic()<bound;time.sleep(.001)
    assert p.returncode is None
    attempt(row,'getpgid_owned_exited_unreaped',lambda:os.getpgid(p.pid))
   row['cached_returncode_before_signal']=p.returncode
   attempt(row,'killpg_owned_unreaped',lambda:os.killpg(p.pid,signal.SIGKILL))
  finally:
   # Close the fixed live child's input even if group signaling was denied.
   # It can then finish naturally. A bounded PID-only cleanup targets this own
   # still-unreaped child if required; never signal an arbitrary/reused PID.
   if p.stdin is not None:p.stdin.close()
   try:
    rc=p.wait(timeout=max(.01,min(1,deadline-time.monotonic())));row['operations'].append(dict(name='wait_owned',status='ok',value=rc,end=time.monotonic()))
   except BaseException as e:
    row['operations'].append(dict(name='wait_owned',status='error',type=type(e).__name__,message=str(e),traceback=traceback.format_exc()))
    if p.returncode is None:attempt(row,'kill_owned_PID_cleanup',p.kill)
    attempt(row,'wait_owned_cleanup',lambda:p.wait(timeout=max(.01,min(1,deadline-time.monotonic()))))
   row.update(returncode=p.returncode,completed=time.monotonic(),stdout_remaining=p.stdout.read().decode(errors='replace'),stderr=p.stderr.read().decode(errors='replace'))
   p.stdout.close();p.stderr.close()
  record(OUT/(name+'.json'),row)
 report['status']='CONTROL_COMPLETED_ALL_OUTCOMES_RETAINED'
except BaseException as e:
 report.update(status='CONTROL_FAILED_NO_RETRY',error=dict(type=type(e).__name__,message=str(e),traceback=traceback.format_exc()))
finally:
 report.update(end=time.monotonic(),seconds=time.monotonic()-start)
 record(OUT/'result.json',report)
 print(json.dumps({k:report[k] for k in ['status','seconds','numerical_work']}))
