"""L1 supervisor handoff controls: synthetic source rows, no native sampling."""
import errno
import json
import os
from pathlib import Path
import sys
import time

import pytest
from validation.kernel_stage_a import authority as a, commands as c, monitor as m
from test_kernel_stage_a_native_process import identity


def run_reader_join(tmp_path,monkeypatch,join,*,failure=None):
    """Exercise actual journal ingestion/settlement/final charging with a fake owner."""
    runtime=identity()
    runtime.update(executable=str(Path(sys.executable).resolve()),
                   executable_sha256=a.file_hash(Path(sys.executable).resolve()))
    monkeypatch.setattr(a,'runtime',lambda:runtime)
    out=tmp_path/'monitor'; events=out/'monitor-events.jsonl'
    stage=c.stage_command(tmp_path,tmp_path/'seal')
    owner_pid=400001; reader_pid=400002; calls=[]; state={}
    def emit(record):
        with events.open('a') as stream: stream.write(json.dumps(record)+'\n')
    def late_events():
        if state.get('late_sent'): return
        state['late_sent']=True
        if failure=='provenance': emit(dict(event='unknown',monotonic=time.monotonic()))
        if join=='baseline': emit(dict(state['baseline'],rss=99 if failure=='baseline' else 100))
        elif join=='launch': emit(state['launch'])
        else: emit(state['self_event'])
        emit(dict(event='python_worker_end',pid=reader_pid,parent=owner_pid,launch_id='reader-generation',
                  reaped=True,returncode=0,completion_end=time.monotonic(),monotonic=time.monotonic()))
    class Owner:
        pid=owner_pid; returncode=None
        def poll(self): return self.returncode
        def wait(self,timeout):
            if failure in ('cap','identity'): late_events()
            if self.returncode is None: self.returncode=0
            return self.returncode
    owner=Owner()
    monkeypatch.setattr(m.subprocess,'Popen',lambda *args,**kwargs:owner)
    def killpg(pid,signum):
        assert pid==owner_pid
        if owner.returncode is None: owner.returncode=-9
    monkeypatch.setattr(m.os,'killpg',killpg)
    monkeypatch.setattr(m.time,'sleep',lambda seconds:None)
    def sampler(pid,**kwargs):
        assert pid==owner_pid
        calls.append(pid)
        if len(calls)==1:
            emit(dict(event='candidate_start',monotonic=time.monotonic()))
            launch_start=time.monotonic(); vector=c.reader_command(tmp_path,events,launch_start+.1)
            launch=dict(event='python_worker_launch',pid=reader_pid,parent=owner_pid,role='reader',argv=vector,
                        executable=vector[0],vector_sha256=c.vector_hash(vector),launch_id='reader-generation',
                        launch_start=launch_start,monotonic=launch_start,provenance='source_owned_python_launch',
                        launcher=dict(path=runtime['executable'],sha256=runtime['executable_sha256']),
                        expected_image=runtime['process_image'],reaped=False)
            sampled=time.monotonic(); lookup=time.monotonic()
            live=dict(pid=reader_pid,parent=owner_pid,rss_bytes=100,sample_start=sampled,sample_end=sampled,
                      raw_args=c.native_display(vector,runtime),raw_comm='/truncated/Python',
                      image=dict(status='ok',**runtime['process_image'],lookup_start=lookup,lookup_end=lookup))
            state.update(launch=launch,self_event=dict(event='observer_sample',emitter_pid=reader_pid,self_pid=reader_pid,
                         processes=[live],monotonic=time.monotonic()),
                         baseline=dict(event='baseline',pid=reader_pid,rss=100,monotonic=time.monotonic(),
                                       boundary='post-import/pre-allocation'))
            if join!='launch': emit(launch)
            if join!='self': emit(state['self_event'])
            if join!='baseline': emit(state['baseline'])
            if failure=='cap':
                gone=dict(live,image=dict(status='error',method='macos.proc_pidpath',reason='native_lookup_failed',
                                         errno=errno.ESRCH,lookup_start=time.monotonic(),lookup_end=time.monotonic()))
                return m.ResidentTree({reader_pid:100},{reader_pid:gone})
            if failure=='identity':
                return m.ResidentTree({reader_pid:100},{reader_pid:dict(live,raw_args=live['raw_args']+' extra')})
            if join=='self':
                return m.ResidentTree({reader_pid:100},{reader_pid:live})
        else:
            assert len(calls)==2,'no later reader sample is needed'
            # Verify the real supervisor already settled the earlier live row.
            before=[json.loads(line) for line in (out/'monitor-evidence.jsonl').read_text().splitlines()]
            settled=[record for record in before if record['kind']=='resolution' and str(reader_pid) in record['roles']]
            assert len(settled)==1 and settled[0]['roles'][str(reader_pid)]=='pending_baseline'
            late_events(); owner.returncode=0
        return m.ResidentTree({},{})
    monkeypatch.setattr(m,'process_tree',sampler)
    result=m.supervise(stage,out,sampler=sampler,authority_root=tmp_path,outer_seconds=.5,
                       free_disk_bytes=0,incremental_bytes=50 if failure=='cap' else 1000)
    records=[json.loads(line) for line in (out/'monitor-evidence.jsonl').read_text().splitlines()]
    source=[json.loads(line) for line in events.read_text().splitlines()]
    samples=[record for record in records if record['kind']=='sample' and str(reader_pid) in record['rss']]
    assert len(samples)==(2 if join=='self' or failure in ('cap','identity') else 1)
    assert len([event for event in source if event['event']=='observer_sample'])==1
    assert all(not record['processes'] for record in records if record['kind']=='sample' and str(reader_pid) not in record['rss'])
    assert result['workers'][str(reader_pid)]['absolute_peak_bytes']==100
    assert result['source_event_accounting']['complete'] is True
    assert json.loads((out/'monitor.json').read_text())==result
    return result,records


@pytest.mark.parametrize('join',['baseline','launch','self'])
def test_valid_reader_join_publishes_after_previous_sample_settles(tmp_path,monkeypatch,join):
    result,records=run_reader_join(tmp_path,monkeypatch,join)
    assert result['status']=='COMPLETED' and result['reason'] is None,result
    worker=result['workers']['400002']
    assert worker['role']=='worker' and worker['baseline_bytes']==100 and worker['incremental_peak_bytes']==0
    assert result['unresolved_worker_count']==0 and result['missing_worker_baselines']==[]
    # Publication must not invent/reopen a previously settled raw observation.
    resolutions=[row for row in records if row['kind']=='resolution' and '400002' in row['roles']]
    assert len(resolutions)==(2 if join=='self' else 1)


@pytest.mark.parametrize('join,failure',[('baseline','baseline'),('baseline','provenance'),
                                      ('launch','provenance'),('self','provenance')])
def test_late_reader_join_never_bypasses_validation_or_failed_provenance(tmp_path,monkeypatch,join,failure):
    result,_=run_reader_join(tmp_path,monkeypatch,join,failure=failure)
    assert result['status']=='STOPPED' and result['reason']=='monitor common failure'
    worker=result['workers']['400002']
    assert worker['baseline_bytes']==0 and worker['incremental_peak_bytes']==100
    assert result['incremental_worker_peak_bytes']>=100
    assert result['source_event_accounting']['identity_complete'] is False


def test_late_valid_reader_join_cannot_clear_previously_failed_identity(tmp_path,monkeypatch):
    result,_=run_reader_join(tmp_path,monkeypatch,'baseline',failure='identity')
    assert result['status']=='STOPPED' and result['reason']=='foreign process identity'
    assert result['source_event_accounting']['identity_complete'] is True
    worker=result['workers']['400002']
    assert worker['role']=='unaccounted' and worker['baseline_bytes']==0 and worker['incremental_peak_bytes']==100
    assert result['incremental_worker_peak_bytes']>=100


def test_late_reader_join_retains_previously_established_full_rss_cap(tmp_path,monkeypatch):
    result,records=run_reader_join(tmp_path,monkeypatch,'baseline',failure='cap')
    assert result['status']=='STOPPED' and result['reason']=='incremental worker memory cap'
    assert result['incremental_worker_peak_bytes']>=100
    # A cap stop may stop reconciliation with other samples still pending.
    # Late valid evidence must be retained without promising resolved status.
    joined=[row['value'] for row in records if row['kind']=='event']
    assert next(row for row in joined if row['event']=='baseline')['rss']==100
    assert next(row for row in joined if row['event']=='python_worker_end')['reaped'] is True
