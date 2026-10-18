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
    real_clock=time.monotonic; clock_offset=[0.]
    monkeypatch.setattr(m.time,'monotonic',lambda:real_clock()+clock_offset[0])
    pid=470001; member=470002
    class Owner:
        returncode=None
        def poll(self):
            order.append('poll')
            if state['samples']>=2 and failure not in ('poll_none','wait','wait_value_only'): self.returncode=0
            return self.returncode
        def wait(self,timeout):
            order.append('wait')
            assert 0<=timeout<=1
            if failure=='wait': raise subprocess.TimeoutExpired(vector,timeout)
            if failure=='wait_value_only': return 0
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
    def end(self,event):
        order.append('end')
        return original_end(self,dict(event,launch_id='wrong') if failure=='mismatched_end' else event)
    monkeypatch.setattr(m.PythonLifetimes,'end',end)
    def observe(root,runtime_identity,*,deadline,output_limit):
        order.append('membership'); assert owner.returncode is None
        assert 0<output_limit<=1048576 and deadline<=state['deadline']
        now=time.monotonic(); rows=[]
        if group=='root': rows=[dict(pid=pid,parent=os.getpid(),pgid=pid,rss_bytes=239714304)]
        if group=='survivor': rows=[dict(pid=member,parent=1,pgid=pid,rss_bytes=1024)]
        if failure=='deadline': clock_offset[0]=1.
        return dict(start=now,end=time.monotonic(),stdout='',stderr='',rows=rows,helper=None,
                    complete=failure!='query',error='denied numeric query' if failure=='query' else None)
    monkeypatch.setattr(m,'_cleanup_observation',observe,raising=False)
    if failure in ('output','rootlaunch'):
        original_encode=m._bounded_json
        def encode(value,limit,check=lambda:None):
            if isinstance(value,dict) and value.get('kind')==('python_root_launch' if failure=='rootlaunch' else 'cleanup_membership'):
                raise m._MonitorStop('output cap')
            return original_encode(value,limit,check)
        monkeypatch.setattr(m,'_bounded_json',encode)
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


@pytest.mark.parametrize('failure',['mismatched_end','wait_value_only'])
def test_actual_matching_integer_owner_completion_is_mandatory(tmp_path,monkeypatch,failure):
    result,records,order=exercise(tmp_path,monkeypatch,failure=failure,group='root')
    assert result['status']=='STOPPED'
    assert not any(row['kind']=='python_root_end' for row in records)
    if failure=='wait_value_only': assert result['returncode'] is None


@pytest.mark.parametrize('failure',['output','deadline'])
def test_cleanup_refusal_keeps_known_numeric_cost_and_bounded_wait(tmp_path,monkeypatch,failure):
    result,records,order=exercise(tmp_path,monkeypatch,failure=failure,group='survivor')
    assert result['status']!='COMPLETED' and 'wait' in order
    assert result['evidence']['rejected_observations']==1
    assert result['evidence']['rejected_raw_complete'] is False
    assert result['observed_pid_peak_sum_bytes']>=239715328
    assert result['incremental_worker_peak_bytes']>=239715328
    assert result['reason']==('output cap' if failure=='output' else 'outer timeout')


def test_refused_root_launch_record_still_runs_mandatory_own_wait(tmp_path,monkeypatch):
    result,records,order=exercise(tmp_path,monkeypatch,failure='rootlaunch')
    assert result['status']=='STOPPED' and result['reason']=='output cap'
    assert 'wait' in order
    assert len([row for row in records if row['kind']=='python_root_end'])==1


@pytest.mark.parametrize('raw,error',[(b'1 0 1 2\n','success'),(b'','success'),
    (b'1 0 0 2\n','pgid_zero'),
    (b'1 0 1 2','truncated'),(b'1 0 1 2\n1 0 1 2\n','duplicate'),
    (b'1 0 1 x\n','malformed'),(b'1 0 1 2 3\n','malformed'),(b'1 -1 1 2\n','malformed')])
def test_numeric_cleanup_requires_complete_unique_four_integer_parse(raw,error):
    if error in ('success','pgid_zero'):
        rows=m._parse_cleanup_numeric(raw)
        assert rows==([] if not raw else [dict(pid=1,parent=0,pgid=0 if error=='pgid_zero' else 1,rss_bytes=2048)])
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
                dict(status='ok',method='macos.proc_pidpath',path='/wrong' if case=='contradiction' else '/bin/ps',sha256='c'*64))
        return dict(result,lookup_start=now,lookup_end=time.monotonic())
    monkeypatch.setattr(a,'process_image',image)
    class Probe:
        returncode=None
        def __init__(self):
            self.pid=pid
            data=b'470002 1 470001 3\n480001 '+str(os.getpid()).encode()+b' 999 2\n'
            if case=='malformed': data+=b'1 nope 3 4\n'
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
        assert observed['helper']['image_evidence']==('image_unavailable' if case=='esrch' else 'kernel_image')
    else: assert observed['error']
    if case=='malformed':
        assert observed['rows'][0]==dict(pid=470002,parent=1,pgid=470001,rss_bytes=3072)
    assert observed['helper']['launch']['reaped'] is False
    assert observed['helper']['completion']['reaped'] is True


def test_worker_cannot_admit_numeric_cleanup_vector_as_an_observer(tmp_path):
    pid=12; vector=['/bin/ps','-axo','pid=,ppid=,pgid=,rss=']
    entry=dict(pid=pid,parent=os.getpid(),executable='/bin/ps',argv=vector)
    roles=m.classify(10,{pid:entry},{},{pid:dict(entry)})
    assert roles[pid]=='unaccounted'


@pytest.mark.parametrize('case',['remaining','exhausted','kill_denied','reap_failed','already_reaped','read_error'])
def test_helper_eof_wait_failure_terminates_and_reaps_only_with_original_remainder(tmp_path,monkeypatch,case):
    """EOF cannot waive owning termination/reap after its first wait fails."""
    runtime=identity(); clock=[100.]; calls=[]; pid=480001
    monkeypatch.setattr(m.time,'monotonic',lambda:clock[0])
    monkeypatch.setattr(a,'helper_artifact',lambda path:runtime['helpers']['ps'])
    monkeypatch.setattr(a,'process_image',lambda queried:dict(status='ok',path='/bin/ps',sha256='c'*64,
        lookup_start=100.,lookup_end=100.))
    class Probe:
        returncode=None
        def __init__(self):
            self.pid=pid
            for name,raw in [('stdout',b'480001 '+str(os.getpid()).encode()+b' 999 2\n'),('stderr',b'')]:
                read,write=os.pipe(); os.write(write,raw); os.close(write)
                setattr(self,name,os.fdopen(read,'rb',buffering=0))
        def kill(self):
            assert self.returncode is None,'never signal an already-reaped numeric PID'
            calls.append(dict(operation='kill',time=clock[0]))
            if case=='kill_denied': raise PermissionError(errno.EPERM,'controlled helper kill denial')
        def wait(self,timeout):
            calls.append(dict(operation='wait',time=clock[0],timeout=timeout))
            assert 0<=timeout<=max(0,100.5-clock[0])
            if len([row for row in calls if row['operation']=='wait'])==1:
                clock[0]=100.5 if case=='exhausted' else 100.1
                if case=='already_reaped': self.returncode=0
                raise subprocess.TimeoutExpired('initial helper wait',timeout)
            clock[0]+=.01
            if case in ('exhausted','reap_failed'): raise TimeoutError('controlled helper reap failure')
            self.returncode=0 if case in ('kill_denied','already_reaped') else -9
            return self.returncode
    probe=Probe(); monkeypatch.setattr(m.subprocess,'Popen',lambda *args,**kw:probe)
    if case=='read_error':
        def denied_read(fd,count): raise OSError('controlled helper read failure')
        monkeypatch.setattr(m.os,'read',denied_read)
    observed=m._cleanup_observation(470001,runtime,deadline=100.5,output_limit=1024)
    (tmp_path/'helper-outcome.json').write_text(json.dumps(dict(case=case,calls=calls,observation=observed),indent=2)+'\n')
    assert observed['complete'] is False and 'initial helper wait' in observed['error']
    assert len([row for row in calls if row['operation']=='wait'])==2
    assert len([row for row in calls if row['operation']=='kill'])==(0 if case=='already_reaped' else 1)
    assert observed['helper']['witness']['reaped'] is (case not in ('exhausted','reap_failed'))
    assert observed['helper']['witness']['returncode']==probe.returncode
    if case=='exhausted':
        assert calls[-1]['timeout']==0 and observed['end']>=100.5
        assert observed['helper']['witness']['returncode'] is None
    if case=='kill_denied': assert 'controlled helper kill denial' in observed['error']
    if case=='reap_failed': assert 'controlled helper reap failure' in observed['error']
    if case=='read_error': assert 'controlled helper read failure' in observed['error']


@pytest.mark.parametrize('final_failure',['encoding','commit','output'])
@pytest.mark.parametrize('prior_cap',[True,False])
def test_emergency_preserves_first_cap_and_separate_finalization_failure(tmp_path,monkeypatch,final_failure,prior_cap):
    message='later "encoded"\\\n\t\x00故障🙂'
    if final_failure=='commit':
        def commit(*args): raise OSError(message)
        monkeypatch.setattr(m,'_commit_monitor',commit)
    else:
        original=json.JSONEncoder.iterencode
        def encode(self,value,*args,**kwargs):
            if isinstance(value,dict) and 'stage_launch_vector_sha256' in value:
                if final_failure=='output': raise m._MonitorStop(message)
                raise OSError(message)
            return original(self,value,*args,**kwargs)
        monkeypatch.setattr(json.JSONEncoder,'iterencode',encode)
    result,records,order=exercise(tmp_path,monkeypatch,cap=prior_cap,
        failure='signal' if prior_cap else None,group='survivor' if prior_cap else 'empty')
    assert result['status']=='STOPPED' and result['returncode'] is not None
    assert result['reason']==('incremental worker memory cap' if prior_cap else
                             message if final_failure=='output' else 'monitor serialization/write failure')
    assert message in result['finalization_failure']
    if prior_cap:
        assert result['incremental_worker_peak_bytes']>=500000000
        assert result['cleanup_failure_count']>=1
    assert (tmp_path/'monitor/monitor.json').stat().st_size==8192
    assert len([row for row in records if row['kind']=='python_root_end'])==1


def test_emergency_quoted_primary_and_long_secondary_fit_minimum_reservation(tmp_path,monkeypatch):
    primary='primary "quoted"\\\n\t\x00故障🙂\ud800'; out=tmp_path/'minimum-emergency'
    class Owner:
        pid=490001; returncode=None
        def poll(self): return self.returncode
        def wait(self,timeout): self.returncode=0; return 0
    monkeypatch.setattr(m.subprocess,'Popen',lambda *args,**kwargs:Owner())
    monkeypatch.setattr(m.os,'killpg',lambda *args:None)
    def sampler(pid): raise m._MonitorStop(primary)
    original=json.JSONEncoder.iterencode
    def encode(self,value,*args,**kwargs):
        if isinstance(value,dict) and 'stage_launch_vector_sha256' in value:
            raise OSError('secondary "escaped"\\\n\x00故障🙂'*100)
        return original(self,value,*args,**kwargs)
    monkeypatch.setattr(json.JSONEncoder,'iterencode',encode)
    result=m.supervise([sys.executable,'-c','pass'],out,sampler=sampler,outer_seconds=.5,
                       output_bytes=1024,free_disk_bytes=0)
    assert result['status']=='STOPPED' and result['reason']==primary
    assert result['finalization_failure'].startswith('OSError: secondary')
    assert json.loads((out/'monitor.json').read_text())==result
    assert (out/'monitor.json').stat().st_size==512
    assert m.directory_bytes(out)<=1024
