"""One-shot <=30s NONNUMERICAL native compatibility check; no sealed verdict."""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import threading
import time

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
from validation.kernel_stage_a import authority as a, commands as c, monitor as m


def main():
    started=time.monotonic(); deadline=started+30
    report=dict(scope='NONNUMERICAL native compatibility only',allowance_seconds=30,attempts=[])
    # Source identity is supplied by the launcher, avoiding an extra Git vector.
    report['source_commit']=os.environ['TASK18_SOURCE_COMMIT']
    report['source_diff_sha256']=os.environ['TASK18_SOURCE_DIFF_SHA256']
    report['runtime']=a.runtime(); runtime=report['runtime']
    output=Path(sys.argv[1]); children=[]
    def remaining():
        left=deadline-time.monotonic()
        if left<=0: raise TimeoutError('aggregate native allowance exhausted')
        return left
    def launch(vector,**kwargs):
        before=time.monotonic(); process=subprocess.Popen(vector,start_new_session=True,close_fds=True,**kwargs)
        children.append(process)
        timer=threading.Timer(min(10,remaining()),lambda:os.killpg(process.pid,signal.SIGKILL) if process.poll() is None else None)
        timer.start()
        attempt=dict(vector=vector,vector_sha256=c.vector_hash(vector),pid=process.pid,started=before)
        report['attempts'].append(attempt)
        return process,timer,attempt
    def cleanup(process,timer,attempt):
        if process.poll() is None: os.killpg(process.pid,signal.SIGKILL)
        process.wait(timeout=min(1,remaining())); timer.cancel(); timer.join()
        attempt.update(returncode=process.returncode,reaped=True,seconds=time.monotonic()-attempt['started'])
    def check_tree(tree,root_pid,**kwargs):
        roles=m.classify(root_pid,tree.processes,{},tree.declarations,runtime_identity=runtime,**kwargs)
        assert all(role in ('pending_baseline','observer_helper') for role in roles.values()),roles
        return dict(readings=dict(tree),samples=list(tree.processes.values()),witnesses=list(tree.declarations.values()),roles=roles)
    try:
        with tempfile.TemporaryDirectory(prefix='task18-native-') as scratch:
            scratch=Path(scratch); fifo=scratch/'incomplete-seal'; os.mkfifo(fifo)
            keeper=os.open(fifo,os.O_RDWR|os.O_NONBLOCK); os.write(keeper,b'{')
            stage=c.stage_command(ROOT,fifo)
            process,timer,attempt=launch(stage,cwd=scratch,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
            try:
                time.sleep(.1)
                tree=m.process_tree(process.pid,deadline=min(deadline,attempt['started']+9),runtime_identity=runtime)
                assert process.pid in tree and process.poll() is None
                attempt.update(kind='stage held at incomplete FIFO',observation=check_tree(tree,process.pid,stage_vector=stage))
            finally:
                cleanup(process,timer,attempt)
                os.close(keeper)
                attempt['stdout']=process.stdout.read().decode(); attempt['stderr']=process.stderr.read().decode()
                process.stdout.close(); process.stderr.close()
            assert not attempt['stdout'] and not attempt['stderr']
            events=scratch/'reader-events.jsonl'; reader_deadline=min(deadline,time.monotonic()+9)
            reader=c.reader_command(ROOT,events,reader_deadline)
            process,timer,attempt=launch(reader,cwd=scratch,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
            try:
                while True:
                    remaining()
                    if process.poll() is not None: raise AssertionError('reader exited before input boundary')
                    if events.exists():
                        records=[json.loads(line) for line in events.read_text().splitlines()]
                        if any(row['event']=='baseline' for row in records): break
                    if time.monotonic()>=reader_deadline: raise TimeoutError('reader import/baseline boundary')
                    time.sleep(.01)
                context=dict(root=ROOT,event_path=events,deadline=reader_deadline)
                tree=m.process_tree(process.pid,deadline=reader_deadline,runtime_identity=runtime)
                assert process.pid in tree and process.poll() is None
                attempt.update(kind='reader held with ZERO request bytes',request_bytes=0,
                               observation=check_tree(tree,os.getpid(),reader_context=context),events=records)
                declarations={row['pid']:{k:v for k,v in row.items() if k not in ('event','monotonic')} for row in records if row['event']=='observer_helper'}
                for row in records:
                    if row['event']=='observer_helper_end': declarations[row['pid']].update(reaped=row['reaped'],completion_end=row['completion_end'])
                samples=next(row['processes'] for row in records if row['event']=='observer_sample')
                roles=m.classify(os.getpid(),{row['pid']:row for row in samples},{},declarations,
                                 reader_context=context,runtime_identity=runtime)
                assert all(role in ('pending_baseline','observer_helper') for role in roles.values()),roles
                attempt['inner_roles']=roles; attempt['inner_samples']=samples
            finally:
                cleanup(process,timer,attempt)  # kill/reap BEFORE closing stdin
                process.stdin.close()
                attempt['stdout']=process.stdout.read().decode(); attempt['stderr']=process.stderr.read().decode()
                process.stdout.close(); process.stderr.close()
            assert not attempt['stdout'] and not attempt['stderr']
            git_events=scratch/'git-events.jsonl'; original_event=a.event
            def observed_event(path,kind,**fields):
                original_event(path,kind,**fields)
                if kind=='authority_helper':
                    report['attempts'].append(dict(kind='exact readonly Git',witness=fields.copy(),
                                                   image_at_launch=a.process_image(fields['pid'])))
            a.event=observed_event
            try:
                for args in (('rev-parse','HEAD'),('status','--porcelain')):
                    before=time.monotonic()
                    result=a.git(ROOT,*args,deadline=min(deadline,before+5),event_path=git_events)
                    report['attempts'][-1].update(seconds=time.monotonic()-before,output=result)
            finally: a.event=original_event
            report['git_events']=[json.loads(line) for line in git_events.read_text().splitlines()]
            for attempt in report['attempts']:
                if attempt.get('kind')=='exact readonly Git':
                    image=attempt['image_at_launch']
                    if image['status']=='ok': assert all(image[k]==runtime['helpers']['git'][k] for k in ('path','sha256'))
                    attempt['raw_display']='not sampled: short exact source-owned Git may exit before ps lookup'
            report['status']='PASS'
    except BaseException as exc:
        report.update(status='FAILED',failure=dict(type=type(exc).__name__,message=str(exc)))
        raise
    finally:
        for process in children:
            if process.poll() is None:
                os.killpg(process.pid,signal.SIGKILL); process.wait(timeout=1)
        report.update(seconds=time.monotonic()-started,all_owned_children_reaped=all(process.poll() is not None for process in children))
        output.write_text(json.dumps(report,indent=2)+'\n')
        print(json.dumps(dict(status=report.get('status'),seconds=report['seconds'],report=str(output))))


if __name__=='__main__': main()
