"""Authority boundary attribution; controlled source journals, no native sampling."""
import json
import os
import time

import pytest
from validation.kernel_stage_a import authority as a, monitor as m
from test_kernel_stage_a_native_process import identity, sample
from test_kernel_stage_a_native_process_fix1 import COMMAND, rows


@pytest.mark.parametrize('prior_authority_rss',[0,60])
@pytest.mark.parametrize('copy_failure',[False,True])
def test_post_authority_baseline_batch_cannot_inflate_authority_peak(tmp_path,monkeypatch,prior_authority_rss,copy_failure):
    monkeypatch.setattr(a,'runtime',identity)
    out=tmp_path/('copy_failure' if copy_failure else 'complete'); polls=[]; original=m._bounded_json
    def encode(value,limit,check=lambda:None):
        if (copy_failure and isinstance(value,dict) and value.get('kind')=='event'
                and value['value']['event']=='authority_end'):
            raise m._MonitorStop('output cap')
        return original(value,limit,check)
    monkeypatch.setattr(m,'_bounded_json',encode)
    def sampler(pid):
        polls.append(pid); path=out/'monitor-events.jsonl'
        if len(polls)==1:
            a.event(path,'authority_start',pid=pid)
            if prior_authority_rss:
                now=time.monotonic(); root=sample(pid,os.getpid(),COMMAND,start=now,end=now)
                root['rss_bytes']=prior_authority_rss
                return m.ResidentTree({pid:prior_authority_rss},{pid:root})
        elif len(polls)==2:
            a.event(path,'authority_end',pid=pid,success=True)
            now=time.monotonic(); root=sample(pid,os.getpid(),COMMAND,start=now,end=now)
            root['rss_bytes']=500
            a.event(path,'observer_sample',processes=[root])
            a.event(path,'baseline',pid=pid,rss=500)
            (out/'finish').touch()
        return m.ResidentTree({},{})
    result=m.supervise(COMMAND,out,sampler=sampler,outer_seconds=.5,free_disk_bytes=0,incremental_bytes=100)
    assert result['authority_full_rss_peak_bytes']==prior_authority_rss
    assert result['absolute_process_tree_peak_bytes']==500
    assert result['observed_pid_peak_sum_bytes']==500
    assert result['source_event_accounting']['complete'] is True
    if copy_failure:
        assert result['status']=='STOPPED' and result['reason']=='output cap'
        assert result['source_event_accounting']['identity_complete'] is False
        assert result['incremental_worker_peak_bytes']>=500
        assert next(iter(result['workers'].values()))['baseline_bytes']==0
    else:
        assert result['status']=='COMPLETED' and result['reason'] is None
        assert result['incremental_worker_peak_bytes']==prior_authority_rss
        worker=next(iter(result['workers'].values()))
        assert worker['baseline_bytes']==500 and worker['incremental_peak_bytes']==0
        events=[row['value']['event'] for row in rows(out) if row['kind']=='event']
        assert events==['authority_start','authority_end','baseline']
    source=[json.loads(line) for line in (out/'monitor-events.jsonl').read_text().splitlines()]
    assert [row['event'] for row in source]==['authority_start','authority_end','observer_sample','baseline']
    assert source[2]['processes'][0]['sample_start']>source[1]['monotonic']
    assert json.loads((out/'monitor.json').read_text())==result


@pytest.mark.parametrize('post_end_without_baseline',[False,True])
def test_source_sample_overlapping_authority_end_retains_full_authority_cost(tmp_path,monkeypatch,post_end_without_baseline):
    monkeypatch.setattr(a,'runtime',identity); out=tmp_path/'overlap'; polls=[]; started=[]
    def sampler(pid):
        polls.append(pid); path=out/'monitor-events.jsonl'
        if len(polls)==1:
            a.event(path,'authority_start',pid=pid); started.append(time.monotonic())
        elif len(polls)==2:
            a.event(path,'authority_end',pid=pid,success=True)
            now=time.monotonic(); root=sample(pid,os.getpid(),COMMAND,start=started[0],end=now)
            root['rss_bytes']=80
            a.event(path,'observer_sample',processes=[root])
            if post_end_without_baseline:
                later=sample(pid,os.getpid(),COMMAND,start=now,end=now); later['rss_bytes']=500
                a.event(path,'observer_sample',processes=[later])
            else: a.event(path,'baseline',pid=pid,rss=80)
            (out/'finish').touch()
        return m.ResidentTree({},{})
    result=m.supervise(COMMAND,out,sampler=sampler,outer_seconds=.5,free_disk_bytes=0,incremental_bytes=100)
    assert result['authority_full_rss_peak_bytes']==80
    if post_end_without_baseline:
        assert result['status']=='STOPPED' and result['incremental_worker_peak_bytes']>=500
        assert result['absolute_process_tree_peak_bytes']==500
    else:
        assert result['status']=='COMPLETED' and result['incremental_worker_peak_bytes']==80
    assert next(iter(result['workers'].values()))['authority_phase_peak_bytes']==80
    assert json.loads((out/'monitor.json').read_text())==result
