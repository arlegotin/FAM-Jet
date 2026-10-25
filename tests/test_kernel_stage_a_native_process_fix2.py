"""Bounded source-event numerical recovery; synthetic workers and journals only."""
import errno
import json
import os
from pathlib import Path
import time

import pytest
from validation.kernel_stage_a import authority as a, monitor as m
from test_kernel_stage_a_native_process import identity, sample, witness
from test_kernel_stage_a_native_process_fix1 import COMMAND, rows


@pytest.mark.parametrize('failure',['declaration_cap','completion_cap','serialization'])
def test_late_inner_rss_survives_failed_copy_of_prior_source_provenance(tmp_path,monkeypatch,failure):
    monkeypatch.setattr(a,'runtime',identity); out=tmp_path/failure; budget=16384; original=m._bounded_json; inner=[]; prior=[]
    def encode(value,limit,check=lambda:None):
        kind=value.get('kind') if isinstance(value,dict) else None
        selected=(kind=='runtime' if failure=='declaration_cap' else kind=='witness')
        if selected and not prior:
            if failure=='serialization': prior.append(True); raise OSError('controlled witness encoding failure')
            raw=original(value,limit,check)
            padding=budget-m.directory_bytes(out)-len(raw)-16
            assert padding>0
            (out/'charged-padding.bin').write_bytes(b'p'*padding)
            prior.append(True)
            return raw
        return original(value,limit,check)
    monkeypatch.setattr(m,'_bounded_json',encode)
    def sampler(pid):
        now=time.monotonic(); helper=pid+100000; inner.append(helper)
        root=sample(pid,os.getpid(),COMMAND,start=now,end=now+.001); root['rss_bytes']=80
        observer=sample(helper,pid,m.PS_ARGV,image=dict(status='error',errno=errno.ESRCH),start=now,end=now+.001)
        observer.update(raw_args=' '.join(m.PS_ARGV),rss_bytes=900)
        declared=witness(helper,pid,m.PS_ARGV); declared.update(launch_start=now-.01,reaped=False); declared.pop('completion_end')
        path=out/'monitor-events.jsonl'
        a.event(path,'observer_helper',**declared)
        a.event(path,'observer_helper_end',pid=helper,parent=pid,launch_id=declared['launch_id'],completion_end=now+.005,reaped=True)
        a.event(path,'observer_sample',processes=[root,observer])
        a.event(path,'baseline',pid=pid,rss=80)
        outer=sample(pid,os.getpid(),COMMAND,start=now,end=now+.001)
        return m.ResidentTree({pid:70},{pid:outer})  # outer observation misses inner helper
    result=m.supervise(COMMAND,out,sampler=sampler,outer_seconds=.5,output_bytes=budget,free_disk_bytes=0)
    assert result['status']=='STOPPED' and result['returncode'] is not None
    assert result['absolute_process_tree_peak_bytes']==980
    assert result['observed_pid_peak_sum_bytes']==980
    assert result['incremental_worker_peak_bytes']>=980
    helper=result['workers'][str(inner[0])]
    assert helper['baseline_bytes']==0 and helper['incremental_peak_bytes']==900
    assert helper['role'] not in ('worker','observer_helper','authority_helper')
    assert result['source_event_accounting']['complete'] is True
    assert result['source_event_accounting']['identity_complete'] is False
    assert result['source_event_accounting']['samples']==1
    assert m.directory_bytes(out)<=budget
    assert json.loads((out/'monitor.json').read_text())==result
    assert rows(out)[0]['kind']=='sample'
    assert [row['event'] for row in map(json.loads,(out/'monitor-events.jsonl').read_text().splitlines())]==['observer_helper','observer_helper_end','observer_sample','baseline']


def test_unscanned_complete_source_rows_at_deadline_are_explicit_failed_accounting(tmp_path,monkeypatch):
    monkeypatch.setattr(a,'runtime',identity); out=tmp_path/'deadline'; clock=[100.]; original=m._bounded_json
    monkeypatch.setattr(m.time,'monotonic',lambda:clock[0])
    def encode(value,limit,check=lambda:None):
        raw=original(value,limit,check)
        if isinstance(value,dict) and value.get('kind')=='runtime': clock[0]+=2
        return raw
    monkeypatch.setattr(m,'_bounded_json',encode)
    def sampler(pid):
        root=sample(pid,os.getpid(),COMMAND,start=100.,end=100.); root['rss_bytes']=900
        a.event(out/'monitor-events.jsonl','observer_sample',processes=[root])
        outer=sample(pid,os.getpid(),COMMAND,start=100.,end=100.)
        return m.ResidentTree({pid:70},{pid:outer})
    result=m.supervise(COMMAND,out,sampler=sampler,outer_seconds=1,free_disk_bytes=0)
    assert result['status']=='FAILED'
    assert result['source_event_accounting']['complete'] is False
    assert result['source_event_accounting']['status']=='FAILED'
    assert result['absolute_process_tree_peak_bytes']==70  # known lower observation, not an invented900 bound
    assert json.loads((out/'monitor.json').read_text())==result


@pytest.mark.parametrize('failure',['storage','partial','truncated'])
def test_unrecoverable_source_journal_is_failed_with_incomplete_accounting(tmp_path,monkeypatch,failure):
    monkeypatch.setattr(a,'runtime',identity); out=tmp_path/failure; original=Path.open; polls=[]
    if failure=='storage':
        def open_path(path,mode='r',*args,**kwargs):
            if path.name=='monitor-events.jsonl' and mode=='rb' and path.stat().st_size: raise OSError('controlled source journal read failure')
            return original(path,mode,*args,**kwargs)
        monkeypatch.setattr(Path,'open',open_path)
    def sampler(pid):
        polls.append(pid); now=time.monotonic(); path=out/'monitor-events.jsonl'
        if failure=='partial': path.write_bytes(b'{"event":"observer_sample","processes":[')
        elif failure=='truncated' and len(polls)>1: path.write_bytes(b'{}\n')
        elif failure=='truncated': a.event(path,'baseline',pid=pid,rss=10)
        else:
            root=sample(pid,os.getpid(),COMMAND,start=now,end=now+.001); root['rss_bytes']=900
            a.event(path,'observer_sample',processes=[root])
        return m.ResidentTree({pid:70},{pid:sample(pid,os.getpid(),COMMAND,start=now,end=now+.001)})
    # This case probes journal failure after a sample, not the launch deadline.
    result=m.supervise(COMMAND,out,sampler=sampler,outer_seconds=.5,free_disk_bytes=0)
    assert polls, 'the malformed source journal must be sampled'
    if failure=='partial':
        assert (out/'monitor-events.jsonl').read_bytes().startswith(b'{"event":"observer_sample","processes":[')
    assert result['status']=='FAILED' and result['returncode'] is not None
    assert result['source_event_accounting']['complete'] is False
    assert result['source_event_accounting']['status']=='FAILED'
    assert result['absolute_process_tree_peak_bytes']==70
    assert json.loads((out/'monitor.json').read_text())==result
