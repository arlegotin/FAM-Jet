"""Bounded external monitor evidence/finalization; controlled samplers only."""
import errno
import json
import os
from pathlib import Path
import sys
import time

import pytest
from validation.kernel_stage_a import authority as a, monitor as m
from test_kernel_stage_a_native_process import identity, sample, witness


COMMAND=[sys.executable,'-c','from pathlib import Path; import time\nwhile not Path("finish").exists(): time.sleep(.005)']


def rows(out):
    return [json.loads(line) for line in (out/'monitor-evidence.jsonl').read_text().splitlines()]


def test_small_budget_retains_accepted_raw_and_charges_rejected_oversize(tmp_path,monkeypatch):
    monkeypatch.setattr(a,'runtime',identity); out=tmp_path/'bounded'; polls=[]
    def sampler(pid):
        polls.append(pid); now=time.monotonic()
        entry=sample(pid,os.getpid(),COMMAND,start=now,end=now+.001)
        if len(polls)==3: entry['raw_args']='x'*20000; entry['rss_bytes']=500
        a.event(out/'monitor-events.jsonl','baseline',pid=pid,rss=10)
        if len(polls)==3: return m.ResidentTree({pid:500},{pid:entry})
        helper=pid+100000+len(polls)
        observer=sample(helper,os.getpid(),m.PS_ARGV,image=dict(status='error',errno=errno.ESRCH),start=now,end=now+.001)
        observer['raw_args']=' '.join(m.PS_ARGV)
        declared=witness(helper,os.getpid(),m.PS_ARGV); declared.update(launch_id=str(helper),launch_start=now-.01,completion_end=now+.002)
        return m.ResidentTree({pid:70,helper:70},{pid:entry,helper:observer},{helper:declared})
    result=m.supervise(COMMAND,out,sampler=sampler,outer_seconds=.5,output_bytes=16384,free_disk_bytes=0)
    assert result['status']=='STOPPED' and 'output cap' in result['reason']
    assert m.directory_bytes(out)<=16384
    assert json.loads((out/'monitor.json').read_text())==result
    records=rows(out)
    assert sum(row['kind']=='sample' for row in records)==2
    assert sum(row['kind']=='witness' for row in records)==2
    assert result['evidence']['rejected_observations']>=1
    assert result['evidence']['rejected_raw_complete'] is False
    assert result['absolute_process_tree_peak_bytes']==500
    assert result['incremental_worker_peak_bytes']>=500
    assert result['evidence']['rejected_rss_bytes']==500
    assert all('x'*20000 not in json.dumps(row) for row in records)


def test_settled_native_samples_are_not_reclassified_each_poll(tmp_path,monkeypatch):
    monkeypatch.setattr(a,'runtime',identity); out=tmp_path/'linear'; polls=[]; classified=[]
    real_classify=m.classify; real_sleep=time.sleep
    def classify(*args,**kwargs):
        classified.append(len(args[1])); return real_classify(*args,**kwargs)
    monkeypatch.setattr(m,'classify',classify)
    def sampler(pid):
        polls.append(pid); now=time.monotonic(); helper=pid+100000+len(polls)
        root=sample(pid,os.getpid(),COMMAND,start=now,end=now+.001)
        entry=sample(helper,os.getpid(),m.PS_ARGV,image=dict(status='error',errno=errno.ESRCH),start=now,end=now+.001)
        entry['raw_args']=' '.join(m.PS_ARGV)
        declared=witness(helper,os.getpid(),m.PS_ARGV); declared.update(launch_id=str(helper),launch_start=now-.01,completion_end=now+.002)
        if len(polls)==1: a.event(out/'monitor-events.jsonl','baseline',pid=pid,rss=10)
        return m.ResidentTree({pid:70,helper:70},{pid:root,helper:entry},{helper:declared})
    def sleep(seconds):
        if seconds==.02 and len(polls)>=8: (out/'finish').touch(); real_sleep(.08)
        elif seconds!=.02: real_sleep(seconds)
    monkeypatch.setattr(m.time,'sleep',sleep)
    result=m.supervise(COMMAND,out,sampler=sampler,outer_seconds=.5,free_disk_bytes=0)
    assert result['status']=='COMPLETED',result
    assert len(polls)==8
    assert sum(classified)<=len(polls)*4
    assert sum(row['kind']=='sample' for row in rows(out))==8


def test_deadline_crossed_during_classification_stops_and_counts_work(tmp_path,monkeypatch):
    monkeypatch.setattr(a,'runtime',identity); clock=[100.]; out=tmp_path/'deadline'; real_classify=m.classify
    monkeypatch.setattr(m.time,'monotonic',lambda:clock[0])
    def classify(*args,**kwargs):
        result=real_classify(*args,**kwargs)
        if args[1]: clock[0]+=2
        return result
    monkeypatch.setattr(m,'classify',classify)
    def sampler(pid): return m.ResidentTree({pid:70},{pid:sample(pid,os.getpid(),COMMAND,start=100.,end=100.)})
    result=m.supervise(COMMAND,out,sampler=sampler,outer_seconds=1,free_disk_bytes=0)
    assert result['status']=='STOPPED' and result['reason']=='outer timeout'
    assert result['outer_seconds']>=2
    assert result['absolute_process_tree_peak_bytes']==70
    assert result['returncode'] is not None
    assert json.loads((out/'monitor.json').read_text())==result


@pytest.mark.parametrize('failure',['serialization','write'])
def test_finalization_failure_returns_bounded_durable_failure_and_reaps(tmp_path,monkeypatch,failure):
    monkeypatch.setattr(a,'runtime',identity); out=tmp_path/failure
    assert hasattr(m,'_commit_monitor')
    if failure=='serialization':
        original=json.JSONEncoder.iterencode
        def encode(self,value,*args,**kwargs):
            if isinstance(value,dict) and 'stage_launch_vector_sha256' in value: raise OSError('controlled final encoding failure')
            return original(self,value,*args,**kwargs)
        monkeypatch.setattr(json.JSONEncoder,'iterencode',encode)
    else:
        original=m._commit_monitor
        def write(path,payload,reserve):
            if b'stage_launch_vector_sha256' in payload: raise OSError('controlled final write failure')
            return original(path,payload,reserve)
        monkeypatch.setattr(m,'_commit_monitor',write)
    def sampler(pid):
        now=time.monotonic(); (out/'finish').touch()
        return m.ResidentTree({pid:70},{pid:sample(pid,os.getpid(),COMMAND,start=now,end=now+.001)})
    result=m.supervise(COMMAND,out,sampler=sampler,outer_seconds=.3,output_bytes=8192,free_disk_bytes=0)
    assert result['status']=='STOPPED' and result['reason']=='monitor serialization/write failure'
    assert result['returncode'] is not None
    assert result['absolute_process_tree_peak_bytes']==70 and result['incremental_worker_peak_bytes']>=70
    assert json.loads((out/'monitor.json').read_text())==result
    assert m.directory_bytes(out)<=8192 and rows(out)


def test_initialized_authority_inventory_is_closed_over_exact_monitor_files(tmp_path):
    assert hasattr(a,'_check_initialized_output')
    for name in ('stdout.log','stderr.log','monitor-events.jsonl','monitor-evidence.jsonl','monitor.json'): (tmp_path/name).touch()
    a._check_initialized_output(tmp_path)
    extra=tmp_path/'arbitrary-evidence'; extra.touch()
    with pytest.raises(a.AuthorityError,match='initialized'): a._check_initialized_output(tmp_path)
    extra.unlink(); (tmp_path/'monitor.json').unlink()
    with pytest.raises(a.AuthorityError,match='initialized'): a._check_initialized_output(tmp_path)


def test_deadline_crossed_in_final_encoding_is_not_completed_or_timed_before_work(tmp_path,monkeypatch):
    monkeypatch.setattr(a,'runtime',identity); out=tmp_path/'final-time'; clock=[100.]; real_sleep=time.sleep
    monkeypatch.setattr(m.time,'monotonic',lambda:clock[0]); original=json.JSONEncoder.iterencode
    def encode(self,value,*args,**kwargs):
        if isinstance(value,dict) and 'stage_launch_vector_sha256' in value: clock[0]+=2
        return original(self,value,*args,**kwargs)
    monkeypatch.setattr(json.JSONEncoder,'iterencode',encode)
    def sampler(pid):
        a.event(out/'monitor-events.jsonl','baseline',pid=pid,rss=10)
        (out/'finish').touch(); real_sleep(.08)
        return m.ResidentTree({pid:70},{pid:sample(pid,os.getpid(),COMMAND,start=100.,end=100.)})
    result=m.supervise(COMMAND,out,sampler=sampler,outer_seconds=1,free_disk_bytes=0)
    assert result['status']=='STOPPED' and result['reason']=='outer timeout'
    assert result['outer_seconds']>=2
    assert 'commit' in result['timing_boundary']
    assert json.loads((out/'monitor.json').read_text())==result


def test_settled_helper_late_contradictory_end_invalidates_without_history_scan(tmp_path,monkeypatch):
    monkeypatch.setattr(a,'runtime',identity); out=tmp_path/'end-conflict'; real_sleep=time.sleep; launches=[]
    def sampler(pid):
        now=time.monotonic(); helper=pid+100000
        declared=witness(helper,os.getpid(),m.PS_ARGV); declared.update(launch_start=now-.01,reaped=False); declared.pop('completion_end')
        launches.append(declared)
        root=sample(pid,os.getpid(),COMMAND,start=now,end=now+.001)
        entry=sample(helper,os.getpid(),m.PS_ARGV,image=dict(status='ok',**identity()['helpers']['ps'],lookup_start=now,lookup_end=now+.001),start=now,end=now+.001)
        entry['raw_args']=' '.join(m.PS_ARGV)
        a.event(out/'monitor-events.jsonl','baseline',pid=pid,rss=10)
        return m.ResidentTree({pid:70,helper:70},{pid:root,helper:entry},{helper:declared})
    def sleep(seconds):
        if seconds==.02 and launches:
            declared=launches[0]
            a.event(out/'monitor-events.jsonl','observer_helper_end',pid=declared['pid'],parent=os.getpid(),launch_id=declared['launch_id'],completion_end=declared['launch_start']-1,reaped=True)
            (out/'finish').touch(); real_sleep(.08)
        else: real_sleep(seconds)
    monkeypatch.setattr(m.time,'sleep',sleep)
    result=m.supervise(COMMAND,out,sampler=sampler,outer_seconds=.5,free_disk_bytes=0)
    assert result['status']=='STOPPED' and result['reason']=='foreign process identity'
    assert result['workers'][str(launches[0]['pid'])]['role']=='unaccounted'


def test_deadline_crossed_in_commit_cannot_persist_completed(tmp_path,monkeypatch):
    monkeypatch.setattr(a,'runtime',identity); clock=[100.]; out=tmp_path/'commit-time'; real_sleep=time.sleep
    monkeypatch.setattr(m.time,'monotonic',lambda:clock[0]); original=m._commit_monitor
    def commit(path,payload,reserve):
        result=original(path,payload,reserve)
        if b'stage_launch_vector_sha256' in payload: clock[0]+=2
        return result
    monkeypatch.setattr(m,'_commit_monitor',commit)
    def sampler(pid):
        a.event(out/'monitor-events.jsonl','baseline',pid=pid,rss=10); (out/'finish').touch(); real_sleep(.08)
        return m.ResidentTree({pid:70},{pid:sample(pid,os.getpid(),COMMAND,start=100.,end=100.)})
    result=m.supervise(COMMAND,out,sampler=sampler,outer_seconds=1,free_disk_bytes=0)
    assert result['status']=='STOPPED' and result['reason']=='outer timeout'
    assert result['outer_seconds']>=2
    assert json.loads((out/'monitor.json').read_text())==result


def test_genuinely_pending_samples_only_revisit_when_their_declaration_arrives(tmp_path,monkeypatch):
    monkeypatch.setattr(a,'runtime',identity); out=tmp_path/'pending'; polls=[]; counted=[]; real_sleep=time.sleep; real_classify=m.classify
    def classify(*args,**kwargs): counted.append(len(args[1])); return real_classify(*args,**kwargs)
    monkeypatch.setattr(m,'classify',classify)
    def sampler(pid):
        now=time.monotonic(); polls.append(now); helper=pid+100000
        root=sample(pid,os.getpid(),COMMAND,start=now,end=now+.001)
        observer=sample(helper,os.getpid(),m.PS_ARGV,image=dict(status='error',errno=errno.ESRCH),start=now,end=now+.001)
        observer['raw_args']=' '.join(m.PS_ARGV)
        if len(polls)==1: a.event(out/'monitor-events.jsonl','baseline',pid=pid,rss=10)
        return m.ResidentTree({pid:70,helper:70},{pid:root,helper:observer})
    def sleep(seconds):
        if seconds==.02 and len(polls)==8:
            pid=next(row['processes'][0]['pid'] for row in rows(out) if row['kind']=='sample')
            declared=witness(pid+100000,os.getpid(),m.PS_ARGV); declared.update(launch_start=polls[0]-.01,completion_end=polls[-1]+.01)
            a.event(out/'monitor-events.jsonl','observer_helper',**declared)
            (out/'finish').touch(); real_sleep(.08)
        elif seconds!=.02: real_sleep(seconds)
    monkeypatch.setattr(m.time,'sleep',sleep)
    result=m.supervise(COMMAND,out,sampler=sampler,outer_seconds=.5,free_disk_bytes=0)
    assert result['status']=='COMPLETED',result
    assert len(polls)==8 and sum(counted)==32
    assert result['incremental_worker_peak_bytes']==130


def test_partial_evidence_write_keeps_prior_rows_readable_and_full_rss(tmp_path,monkeypatch):
    monkeypatch.setattr(a,'runtime',identity); out=tmp_path/'partial'; real_open=Path.open; attempts=[]
    class Partial:
        def __init__(self,stream): self.stream=stream
        def __enter__(self): return self
        def __exit__(self,*args): self.stream.close()
        def flush(self): self.stream.flush()
        def write(self,data):
            if data.startswith(b'{"kind":"sample"'):
                attempts.append(data)
                if len(attempts)==2:
                    self.stream.write(data[:13]); self.stream.flush(); raise OSError('controlled short evidence write')
            return self.stream.write(data)
    def open_path(path,mode='r',*args,**kwargs):
        stream=real_open(path,mode,*args,**kwargs)
        return Partial(stream) if path.name=='monitor-evidence.jsonl' and mode=='ab' else stream
    monkeypatch.setattr(Path,'open',open_path)
    polls=[]
    def sampler(pid):
        polls.append(pid); now=time.monotonic(); entry=sample(pid,os.getpid(),COMMAND,start=now,end=now+.001)
        entry['rss_bytes']=70+len(polls)
        a.event(out/'monitor-events.jsonl','baseline',pid=pid,rss=10)
        return m.ResidentTree({pid:entry['rss_bytes']},{pid:entry})
    result=m.supervise(COMMAND,out,sampler=sampler,outer_seconds=.5,free_disk_bytes=0)
    assert result['reason']=='monitor common failure'
    assert result['absolute_process_tree_peak_bytes']==72 and result['incremental_worker_peak_bytes']>=72
    assert result['evidence']['rejected_observations']==1
    assert sum(row['kind']=='sample' for row in rows(out))==1
    assert json.loads((out/'monitor.json').read_text())==result


def test_minimum_failure_budget_still_retains_readable_numerical_verdict(tmp_path,monkeypatch):
    monkeypatch.setattr(a,'runtime',identity); out=tmp_path/'minimum'
    def sampler(pid):
        now=time.monotonic()
        return m.ResidentTree({pid:70},{pid:sample(pid,os.getpid(),COMMAND,start=now,end=now+.001)})
    result=m.supervise(COMMAND,out,sampler=sampler,outer_seconds=.3,output_bytes=512,free_disk_bytes=0)
    assert result['status']=='STOPPED' and 'output cap' in result['reason']
    assert result['absolute_process_tree_peak_bytes']==70 and result['incremental_worker_peak_bytes']>=70
    assert m.directory_bytes(out)<=512
    assert json.loads((out/'monitor.json').read_text())==result


def test_commit_cost_is_visible_to_external_caller_and_boundary_is_explicit(tmp_path,monkeypatch):
    monkeypatch.setattr(a,'runtime',identity); out=tmp_path/'caller-time'; real_commit=m._commit_monitor
    def commit(*args): time.sleep(.03); return real_commit(*args)
    monkeypatch.setattr(m,'_commit_monitor',commit)
    def sampler(pid):
        now=time.monotonic(); (out/'finish').touch()
        a.event(out/'monitor-events.jsonl','baseline',pid=pid,rss=10)
        return m.ResidentTree({pid:70},{pid:sample(pid,os.getpid(),COMMAND,start=now,end=now+.001)})
    began=time.monotonic()
    result=m.supervise(COMMAND,out,sampler=sampler,outer_seconds=.5,free_disk_bytes=0)
    caller_elapsed=time.monotonic()-began
    assert result['status']=='COMPLETED',result
    assert caller_elapsed-result['outer_seconds']>=.02
    assert 'before bounded final commit' in result['timing_boundary']
    assert json.loads((out/'monitor.json').read_text())==result


def test_final_metadata_serialization_error_uses_same_failure_commit(tmp_path,monkeypatch):
    monkeypatch.setattr(a,'runtime',identity); out=tmp_path/'metadata'
    def broken_hash(vector): raise OSError('controlled metadata serialization failure')
    monkeypatch.setattr(m.commands,'vector_hash',broken_hash)
    def sampler(pid):
        now=time.monotonic(); (out/'finish').touch()
        return m.ResidentTree({pid:70},{pid:sample(pid,os.getpid(),COMMAND,start=now,end=now+.001)})
    result=m.supervise(COMMAND,out,sampler=sampler,outer_seconds=.3,free_disk_bytes=0)
    assert result['reason']=='monitor serialization/write failure'
    assert result['returncode'] is not None and result['absolute_process_tree_peak_bytes']==70
    assert json.loads((out/'monitor.json').read_text())==result
