"""Deterministic owning-supervisor lifecycle controls; no native/scientific work.

These controls catch early reap, terminal full-RSS admission, missing group
cleanup, invented completion and first-failure erasure at the actual supervisor.
"""
import errno
import json
import os
from pathlib import Path
import subprocess
import sys
import time

import pytest
from validation.kernel_stage_a import authority as a, commands as c, monitor as m
from test_kernel_stage_a_native_process import identity


def exercise(tmp_path,monkeypatch,*,group='empty',failure=None,proof=True,cap=False):
    runtime=identity(); runtime.update(executable=str(Path(sys.executable).resolve()),
                                      executable_sha256=a.file_hash(Path(sys.executable).resolve()))
    monkeypatch.setattr(a,'runtime',lambda:runtime)
    out=tmp_path/'monitor'; vector=[sys.executable,'-c','pass']; order=[]; state={'samples':0}
    pid=470001; member=470002
    class Owner:
        returncode=None
        def poll(self):
            order.append('poll')
            if state['samples']>=2 and failure not in ('poll_none','wait'): self.returncode=0
            return self.returncode
        def wait(self,timeout):
            order.append('wait')
            assert 0<=timeout<=1
            if failure=='wait': raise subprocess.TimeoutExpired(vector,timeout)
            if self.returncode is None: self.returncode=-9 if 'kill' in order else 0
            return self.returncode
    owner=Owner(); owner.pid=pid
    monkeypatch.setattr(m.subprocess,'Popen',lambda *args,**kw:owner)
    monkeypatch.setattr(m.time,'sleep',lambda seconds:None)
    def killpg(group_pid,signum):
        order.append('kill'); assert group_pid==pid and owner.returncode is None
        if failure=='signal': raise PermissionError(errno.EPERM,'controlled denial')
    monkeypatch.setattr(m.os,'killpg',killpg)
    original_end=m.PythonLifetimes.end
    def end(self,event): order.append('end'); return original_end(self,event)
    monkeypatch.setattr(m.PythonLifetimes,'end',end)
    def observe(root,runtime_identity,*,deadline,output_limit):
        order.append('membership'); assert owner.returncode is None
        assert 0<output_limit<=1048576 and deadline<=state['deadline']
        now=time.monotonic(); rows=[]
        if group=='root': rows=[dict(pid=pid,parent=os.getpid(),pgid=pid,rss_bytes=239714304)]
        if group=='survivor': rows=[dict(pid=member,parent=1,pgid=pid,rss_bytes=1024)]
        return dict(start=now,end=time.monotonic(),stdout='',stderr='',rows=rows,helper=None,
                    complete=failure!='query',error='denied numeric query' if failure=='query' else None)
    monkeypatch.setattr(m,'_cleanup_observation',observe,raising=False)
    def sampler(root,**kwargs):
        state['samples']+=1; order.append('sample'); now=time.monotonic()
        assert owner.returncode is None
        if state['samples']==1:
            state['deadline']=kwargs['deadline']+.1
            a.event(out/'monitor-events.jsonl','baseline',pid=pid,rss=226918400)
        if failure=='provenance' and state['samples']==2:
            a.event(out/'monitor-events.jsonl','unrecognized')
        before=time.monotonic(); after=time.monotonic(); image_start=time.monotonic()
        image=(dict(status='ok',**runtime['process_image']) if proof and state['samples']==1 else
               dict(status='error',method='macos.proc_pidpath',reason='native_lookup_failed',errno=errno.ESRCH))
        image.update(lookup_start=image_start,lookup_end=time.monotonic())
        row=dict(pid=pid,parent=os.getpid(),rss_bytes=239714304 if not cap else 500000000,
                 raw_args=c.native_display(vector,runtime),raw_comm='/truncated/Python',
                 sample_start=before,sample_end=after,image=image)
        # Native headers must not reap before retaining even the first proof.
        assert state['samples']<=2,'terminal evidence may not trigger favorable sampling retries'
        return m.ResidentTree({pid:row['rss_bytes']},{pid:row})
    monkeypatch.setattr(m,'process_tree',sampler)
    result=m.supervise(vector,out,sampler=sampler,outer_seconds=.5,free_disk_bytes=0)
    records=[json.loads(line) for line in (out/'monitor-evidence.jsonl').read_text().splitlines()]
    assert json.loads((out/'monitor.json').read_text())==result
    return result,records,order


def test_terminal_high_baseline_esrch_reaps_before_reconciliation(tmp_path,monkeypatch):
    result,records,order=exercise(tmp_path,monkeypatch)
    assert result['status']=='COMPLETED',result
    assert result['incremental_worker_peak_bytes']==12795904
    assert order.index('sample')<order.index('membership')<order.index('poll')<order.index('end')
    assert 'kill' not in order
    ends=[i for i,row in enumerate(records) if row['kind']=='python_root_end']
    terminal=[i for i,row in enumerate(records) if row['kind']=='resolution' and row['sample_id']==2]
    assert len(ends)==1 and ends[0]<terminal[0]
    assert records[terminal[0]]['identities']['470001']['proof']['origin']=='unreaped_owned_root'
    assert len([row for row in records if row['kind']=='sample'])==2


@pytest.mark.parametrize('group',['root','survivor'])
def test_membership_decision_precedes_release_and_survivor_requires_kill(tmp_path,monkeypatch,group):
    result,records,order=exercise(tmp_path,monkeypatch,group=group)
    assert order.index('membership')<order.index('poll' if group=='root' else 'kill')
    if group=='survivor':
        assert order.index('kill')<order.index('wait') and result['status']=='STOPPED'
        assert result['workers']['470002']['absolute_peak_bytes']==1024
    else: assert result['status']=='COMPLETED' and 'kill' not in order
    assert len([row for row in records if row['kind']=='python_root_end'])==1


@pytest.mark.parametrize('failure',['signal','wait','query','poll_none','provenance'])
def test_cleanup_failure_is_unsuccessful_and_wait_end_are_independent(tmp_path,monkeypatch,failure):
    group='survivor' if failure=='signal' else 'root'
    result,records,order=exercise(tmp_path,monkeypatch,group=group,failure=failure)
    assert result['status']!='COMPLETED',result
    assert 'wait' in order
    ends=[row for row in records if row['kind']=='python_root_end']
    assert len(ends)==(0 if failure=='wait' else 1)
    if failure=='wait': assert result['returncode'] is None
    if failure=='poll_none': assert result['incremental_worker_peak_bytes']>=239714304 and 'kill' in order
    if failure=='signal': assert any(d['operation']=='signal' for d in result['cleanup_diagnostics'])


def test_real_prior_cap_cannot_be_cleared_by_cleanup_reap(tmp_path,monkeypatch):
    result,records,order=exercise(tmp_path,monkeypatch,cap=True,failure='signal',group='survivor')
    assert result['reason']=='incremental worker memory cap',result
    assert result['incremental_worker_peak_bytes']>=273081600
    assert 'wait' in order and len([r for r in records if r['kind']=='python_root_end'])==1
    assert any(d['operation']=='signal' for d in result['cleanup_diagnostics'])


def test_never_proved_root_cannot_gain_identity_from_numeric_membership(tmp_path,monkeypatch):
    result,records,order=exercise(tmp_path,monkeypatch,proof=False)
    assert result['status']=='STOPPED' and result['incremental_worker_peak_bytes']>=239714304
    assert all('proof' not in row.get('identities',{}).get('470001',{}) for row in records)


@pytest.mark.parametrize('raw,error',[(b'1 0 1 2\n','success'),(b'','success'),
    (b'1 0 1 2','truncated'),(b'1 0 1 2\n1 0 1 2\n','duplicate'),
    (b'1 0 1 x\n','malformed'),(b'1 0 1 2 3\n','malformed'),(b'1 -1 1 2\n','malformed')])
def test_numeric_cleanup_requires_complete_unique_four_integer_parse(raw,error):
    if error=='success':
        rows=m._parse_cleanup_numeric(raw)
        assert rows==([] if not raw else [dict(pid=1,parent=0,pgid=1,rss_bytes=2048)])
    else:
        with pytest.raises(ValueError,match=error): m._parse_cleanup_numeric(raw)


@pytest.mark.parametrize('case',['success','esrch','contradiction','denied','nonzero','malformed','truncated','overflow','timeout'])
def test_cleanup_query_bounded_capture_uses_actual_helper_image_and_reap(tmp_path,monkeypatch,case):
    runtime=identity(); pid=480001; launched=[]; writers=[]
    monkeypatch.setattr(a,'helper_artifact',lambda path:runtime['helpers']['ps'])
    def image(queried):
        assert queried==pid; now=time.monotonic()
        result=(dict(status='error',method='macos.proc_pidpath',reason='native_lookup_failed',errno=errno.ESRCH)
                if case=='esrch' else dict(status='error',errno=errno.EPERM) if case=='denied' else
                dict(status='ok',path='/wrong' if case=='contradiction' else '/bin/ps',sha256='c'*64))
        return dict(result,lookup_start=now,lookup_end=time.monotonic())
    monkeypatch.setattr(a,'process_image',image)
    class Probe:
        returncode=None
        def __init__(self):
            self.pid=pid
            data=b'470002 1 470001 3\n480001 '+str(os.getpid()).encode()+b' 999 2\n'
            if case=='malformed': data=b'1 nope 3 4\n'
            if case=='truncated': data=b'1 2 3 4'
            if case=='overflow': data=b'1 2 3 4\n'*20
            for name,raw in [('stdout',data),('stderr',b'controlled denial' if case=='nonzero' else b'')]:
                read,write=os.pipe(); os.write(write,raw)
                if case=='timeout' and name=='stdout': writers.append(write)
                else: os.close(write)
                setattr(self,name,os.fdopen(read,'rb',buffering=0))
        def kill(self): self.returncode=-9
        def wait(self,timeout):
            assert 0<=timeout<=1
            if self.returncode is None: self.returncode=1 if case=='nonzero' else 0
            return self.returncode
    def popen(argv,**kw):
        assert argv==['/bin/ps','-axo','pid=,ppid=,pgid=,rss=']
        assert kw['stdout']==subprocess.PIPE and kw['stderr']==subprocess.PIPE
        launched.append(Probe()); return launched[-1]
    monkeypatch.setattr(m.subprocess,'Popen',popen)
    try:
        observed=m._cleanup_observation(470001,runtime,deadline=time.monotonic()+.01,output_limit=64)
    finally:
        for writer in writers: os.close(writer)
    assert len(launched)==1 and type(launched[0].returncode) is int
    assert observed['helper']['witness']['reaped'] is True
    assert observed['helper']['witness']['returncode']==launched[0].returncode
    assert observed['helper']['image']['lookup_start']<=observed['helper']['image']['lookup_end']
    assert len(observed['stdout'].encode('latin1'))+len(observed['stderr'].encode('latin1'))<=64
    assert observed['complete'] is (case in ('success','esrch'))
    if observed['complete']:
        assert observed['rows']==[dict(pid=470002,parent=1,pgid=470001,rss_bytes=3072),
                                  dict(pid=480001,parent=os.getpid(),pgid=999,rss_bytes=2048)]
        assert observed['helper']['image_evidence']==('unavailable_exited' if case=='esrch' else 'kernel_image')
    else: assert observed['error']
