"""ONE bounded nonnumerical sequence. Synchronization seams are TEST ONLY.
Run from repo root with .venv/bin/python; no retry and no numerical input.
"""
import time
START=time.monotonic()
import errno
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import threading

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
from validation.kernel_stage_a import authority as a,commands as c,monitor as m
from validation.kernel_stage_a.production import owned_reader_dispatch

OUT=Path(sys.argv[1]).resolve()
OUT.mkdir(exist_ok=False)
DEADLINE=START+10.
RAW=OUT/'raw.jsonl'
CHILDREN=[]
REAL_IMAGE=a.process_image
REAL_POPEN=subprocess.Popen
RESULT=dict(sequence_start=START,deadline=DEADLINE,import_seconds=time.monotonic()-START,
            source_commit=sys.argv[2],
            allocation_seconds=10,child_watchdog_seconds=5,cases=[],
            factors=0,factorizations=0,model_constructions=0,numerical_requests=0,request_bytes=0,reads=0)


def emit(kind,**fields):
    with RAW.open('a') as stream: stream.write(json.dumps(dict(kind=kind,monotonic=time.monotonic(),**fields))+'\n')


def remaining(deadline=DEADLINE):
    value=min(deadline,DEADLINE)-time.monotonic()
    if value<=0: raise TimeoutError('fixed normal-exit sequence deadline')
    return value


def table(pid,events,deadline):
    tree=m.process_tree(pid,observer_log=events,deadline=min(deadline,DEADLINE),runtime_identity=RUNTIME)
    emit('actual_sample',pid=pid,rss=dict(tree),processes=list(tree.processes.values()),declarations=tree.declarations)
    return tree


def retained_after_reap(pid,events,deadline,release):
    called=[]
    def synchronized(actual_pid):
        if actual_pid==pid:
            called.append(actual_pid)
            emit('ps_row_captured_before_image',pid=pid)
            release()
        image=REAL_IMAGE(actual_pid)
        emit('actual_native_lookup',pid=actual_pid,image=image)
        return image
    a.process_image=synchronized
    try: tree=table(pid,events,deadline)
    finally: a.process_image=REAL_IMAGE
    if called!=[pid]: raise AssertionError('required genuine retained target ps row missing')
    row=tree.processes[pid]
    if row['image'].get('status')!='error' or row['image'].get('errno')!=errno.ESRCH:
        raise AssertionError('real proc_pidpath did not return ESRCH; no retry permitted')
    return row


def root_case():
    folder=OUT/'root'; folder.mkdir(); events=folder/'events.jsonl'; fifo=folder/'seal.fifo'; os.mkfifo(fifo)
    fd=None
    vector=c.stage_command(ROOT,fifo); local_deadline=min(DEADLINE,time.monotonic()+5)
    launch=a.python_launch(vector,RUNTIME,'owned_root')
    try:
        with (folder/'stdout').open('wb') as stdout,(folder/'stderr').open('wb') as stderr:
            child=REAL_POPEN(vector,cwd=folder,stdout=stdout,stderr=stderr,start_new_session=True,close_fds=True)
            CHILDREN.append(child); launch['pid']=child.pid; emit('root_launch',value=launch)
            while fd is None:
                remaining(local_deadline)
                try: fd=os.open(fifo,os.O_WRONLY|os.O_NONBLOCK)
                except OSError as exc:
                    if exc.errno!=errno.ENXIO: raise
                    time.sleep(.002)
            state=m.PythonLifetimes(child.pid,vector,RUNTIME); state.launch(launch,None)
            live=table(child.pid,events,local_deadline).processes[child.pid]
            if child.returncode is not None: raise AssertionError('root owner already reaped')
            state.root_sample(live,owner_unreaped=True)
            def release():
                nonlocal fd
                os.write(fd,b'{}'); os.close(fd); fd=None
                code=child.wait(timeout=remaining(local_deadline))
                end=dict(pid=child.pid,parent=os.getpid(),launch_id=launch['launch_id'],reaped=True,returncode=code,completion_end=time.monotonic())
                state.end(end); emit('root_completion',value=end)
            exited=retained_after_reap(child.pid,events,local_deadline,release)
            exited['identity']=dict(image_evidence='unresolved',launch_evidence=None)
            attribution=state.exited(exited)
            if attribution!='attributed' or child.returncode!=2: raise AssertionError('root control failed')
            emit('root_attribution',row=exited,generation=state.generations[child.pid])
            RESULT['cases'].append(dict(case='root',pid=child.pid,vector=vector,launch_id=launch['launch_id'],returncode=child.returncode,
                                        worker_execution='failed_expected_entry_refusal',identity=attribution,watchdog_kill=False))
    finally:
        if fd is not None: os.close(fd)


def reader_case():
    folder=OUT/'reader'; folder.mkdir(); events=folder/'events.jsonl'; local_deadline=min(DEADLINE,time.monotonic()+5)
    vector=c.reader_command(ROOT,events,local_deadline); gate=threading.Event(); created=threading.Event(); holder={}; errors=[]
    env={'OMP_NUM_THREADS':'1','MKL_NUM_THREADS':'1','OPENBLAS_NUM_THREADS':'1','VECLIB_MAXIMUM_THREADS':'1',
         'NUMEXPR_NUM_THREADS':'1','PYTORCH_ENABLE_MPS_FALLBACK':'0','PYTORCH_MPS_FAST_MATH':'0'}
    class HeldInput:
        def __init__(self,child): self.child=child; self.first=True
        def __getattr__(self,key): return getattr(self.child,key)
        def communicate(self,*args,**kwargs):
            if self.first:
                self.first=False
                if not gate.wait(remaining(local_deadline)): raise subprocess.TimeoutExpired(vector,0)
                kwargs['timeout']=min(kwargs.get('timeout',remaining(local_deadline)),remaining(local_deadline))
            return self.child.communicate(*args,**kwargs)
    def synchronized_popen(command,*args,**kwargs):
        child=REAL_POPEN(command,*args,**kwargs)
        if command==vector:
            CHILDREN.append(child); holder['child']=child; created.set(); return HeldInput(child)
        return child
    def operation():
        try:
            with (folder/'stdout').open('wb') as stdout,(folder/'stderr').open('wb') as stderr:
                holder['result']=owned_reader_dispatch(vector,input=b'',stdout=stdout,stderr=stderr,cwd=folder,env=env,
                    deadline=local_deadline,event_path=events,runtime_identity=RUNTIME)
        except BaseException as exc: errors.append(repr(exc))
    subprocess.Popen=synchronized_popen
    thread=threading.Thread(target=operation)
    try:
        thread.start()
        if not created.wait(remaining(local_deadline)): raise TimeoutError('reader PID unavailable')
        child=holder['child']
        while True:
            remaining(local_deadline)
            rows=[json.loads(line) for line in events.read_text().splitlines() if line.endswith('}')] if events.exists() else []
            if any(row.get('event')=='baseline' for row in rows): break
            if errors: raise RuntimeError(errors)
            time.sleep(.002)
        context=dict(root=ROOT,event_path=events,deadline=local_deadline)
        state=m.PythonLifetimes(os.getpid(),['unused-control-root'],RUNTIME)
        launch=next(row for row in rows if row['event']=='python_worker_launch')
        state.launch(launch,context)
        own=next(row for row in rows if row['event']=='observer_sample')
        if own['emitter_pid']!=child.pid or own['self_pid']!=child.pid: raise AssertionError('reader emitter mismatch')
        state.self_sample(own['emitter_pid'],own['processes'])
        baseline=next(row for row in rows if row['event']=='baseline'); state.baseline(baseline)
        def release():
            gate.set(); thread.join(timeout=remaining(local_deadline))
            if thread.is_alive() or errors: raise RuntimeError('reader natural completion failed: '+repr(errors))
            completed=[json.loads(line) for line in events.read_text().splitlines()]
            end=next(row for row in completed if row['event']=='python_worker_end'); state.end(end)
            emit('reader_completion',value=end)
        exited=retained_after_reap(child.pid,events,local_deadline,release)
        exited['identity']=dict(image_evidence='unresolved',launch_evidence=None)
        attribution=state.exited(exited)
        if attribution!='attributed' or holder['result'].returncode==0 or child.returncode<=0:
            raise AssertionError('reader control failed')
        if (folder/'stdout').read_bytes(): raise AssertionError('unexpected reader profile/read output')
        emit('reader_attribution',row=exited,generation=state.generations[child.pid])
        RESULT['cases'].append(dict(case='reader',pid=child.pid,vector=vector,launch_id=launch['launch_id'],returncode=child.returncode,
                                    worker_execution='failed_expected_empty_json',identity=attribution,watchdog_kill=False,
                                    baseline_bytes=state.generations[child.pid]['baseline']))
    finally:
        gate.set()
        if thread.is_alive():
            if 'child' in holder and holder['child'].poll() is None: holder['child'].kill()
            thread.join(timeout=max(.01,min(1.,DEADLINE-time.monotonic())))
        subprocess.Popen=REAL_POPEN


try:
    RUNTIME=a.runtime(); RESULT['runtime']=RUNTIME
    paths=[ROOT/'validation/kernel_stage_a'/name for name in ('authority.py','monitor.py','production.py','commands.py','reader_worker.py','__main__.py')]
    paths += [Path(__file__).resolve()]
    RESULT['executed_source_hashes']={str(p):a.file_hash(p) for p in paths}
    package={str(p.relative_to(ROOT)):a.file_hash(p) for p in sorted((ROOT/'famjet').rglob('*.py'))}
    RESULT['package_hash']=a.digest(package)
    root_case(); reader_case(); remaining()
    RESULT['status']='PASS_IDENTITY_ONLY_EXPECTED_WORKER_FAILURES'
except BaseException as exc:
    RESULT.update(status='FAILED',error=repr(exc))
    raise
finally:
    a.process_image=REAL_IMAGE; subprocess.Popen=REAL_POPEN
    for child in CHILDREN:
        if child.poll() is None:
            emit('watchdog_cleanup_kill',pid=child.pid)
            child.kill()
        child.wait(timeout=1)
    RESULT['seconds']=time.monotonic()-START
    RESULT['output_bytes_before_result']=sum(p.stat().st_size for p in OUT.rglob('*') if p.is_file())
    (OUT/'result.json').write_text(json.dumps(RESULT,indent=2)+'\n')
