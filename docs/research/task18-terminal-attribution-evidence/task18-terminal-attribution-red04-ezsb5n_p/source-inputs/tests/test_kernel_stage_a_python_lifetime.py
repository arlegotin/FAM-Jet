"""Generation joins and owned dispatch; no numerical requests or models."""
import copy
import errno
import json
import os
from pathlib import Path
import subprocess
import sys
import time

import pytest
from validation.kernel_stage_a import authority as a, commands as c, monitor as m
from test_kernel_stage_a_native_process import identity, sample


def generation(tmp_path, role='reader'):
    runtime=identity(); parent=10 if role=='reader' else os.getpid()
    context=dict(root=tmp_path,event_path=tmp_path/'events',deadline=90.)
    vector=c.reader_command(tmp_path,context['event_path'],80.) if role=='reader' else c.stage_command(tmp_path,tmp_path/'seal')
    launch=dict(pid=20 if role=='reader' else 10,parent=parent,role=role,argv=vector,
                executable=vector[0],vector_sha256=c.vector_hash(vector),launch_id='g1',launch_start=10.,
                provenance='source_owned_python_launch',launcher=dict(path=runtime['executable'],sha256=runtime['executable_sha256']),
                expected_image=runtime['process_image'],reaped=False)
    live=sample(launch['pid'],parent,vector,start=11.,end=12.)
    live['image'].update(lookup_start=12.,lookup_end=12.1)
    gone=sample(launch['pid'],parent,vector,start=13.,end=14.,image=dict(status='error',errno=errno.ESRCH,method='macos.proc_pidpath',reason='native_lookup_failed',lookup_start=15.,lookup_end=15.1))
    end=dict(pid=launch['pid'],parent=parent,launch_id='g1',reaped=True,returncode=2,completion_end=14.5)
    state=m.PythonLifetimes(10, c.stage_command(tmp_path,tmp_path/'seal'),runtime)
    return state,launch,live,gone,end,context


def role(state,row,context):
    return m.classify(10,{row['pid']:row},{row['pid']:5},{},reader_context=context,
                      stage_vector=state.stage_vector,runtime_identity=identity(),python_lifetimes=state)[row['pid']]


def test_same_generation_self_proof_end_admits_esrch_with_raw_rss(tmp_path):
    state,launch,live,gone,end,context=generation(tmp_path)
    state.launch(launch,context); state.self_sample(20,[live]); state.end(end)
    assert role(state,gone,context)=='worker'
    assert gone['rss_bytes']==70 and gone['image']['errno']==errno.ESRCH
    assert gone['identity']['launch_evidence']=='source_owned_python_lifetime'
    assert gone['identity']['proof']['launch_id']=='g1'
    assert state.generations[20]['returncode']==2


@pytest.mark.parametrize('ordering',[('sample','end','launch'),('end','launch','sample'),('launch','sample','end')])
def test_delayed_generation_events_join_without_pid_only_proof(tmp_path,ordering):
    state,launch,live,gone,end,context=generation(tmp_path)
    for action in ordering:
        {'launch':lambda:state.launch(launch,context),'sample':lambda:state.self_sample(20,[live]),'end':lambda:state.end(end)}[action]()
    assert role(state,gone,context)=='worker'


@pytest.mark.parametrize('missing',['proof','end'])
def test_missing_generation_evidence_remains_pending(tmp_path,missing):
    state,launch,live,gone,end,context=generation(tmp_path); state.launch(launch,context)
    if missing!='proof': state.self_sample(20,[live])
    if missing!='end': state.end(end)
    assert role(state,gone,context)=='pending_python_lifetime'


@pytest.mark.parametrize('change',[dict(parent=99),dict(raw_args='python unknown'),dict(sample_start=16.,sample_end=17.),
    dict(image=dict(status='error',errno=errno.EPERM)),dict(image=dict(status='ok',path='/wrong',sha256='b'*64))])
def test_conflicting_or_outside_generation_fails(tmp_path,change):
    state,launch,live,gone,end,context=generation(tmp_path); state.launch(launch,context); state.self_sample(20,[live]); state.end(end)
    assert role(state,dict(gone,**change),context)=='unaccounted'


@pytest.mark.parametrize('change',[dict(launch_id='g2'),dict(pid=21),{}])
def test_duplicate_pid_or_launch_id_rejected(tmp_path,change):
    state,launch,live,gone,end,context=generation(tmp_path); state.launch(launch,context)
    with pytest.raises(ValueError): state.launch(dict(launch,**change),context)


def test_root_proof_cannot_be_established_after_owner_reaps(tmp_path):
    state,launch,live,gone,end,context=generation(tmp_path,'owned_root'); state.launch(launch,None); state.end(end)
    state.root_sample(live,owner_unreaped=False)
    assert role(state,gone,context)=='pending_python_lifetime'


def test_outer_reader_image_cannot_supply_self_generation_proof(tmp_path):
    state,launch,live,gone,end,context=generation(tmp_path); state.launch(launch,context)
    assert role(state,live,context)=='worker'
    state.end(end)
    assert role(state,gone,context)=='pending_python_lifetime'


def test_python_launcher_is_rechecked_and_distinct_from_image(tmp_path):
    runtime=a.runtime(); vector=[sys.executable,'-c','pass']
    witness=a.python_launch(vector,runtime,'reader')
    assert witness['launcher']['path']==runtime['executable']
    assert witness['expected_image']==runtime['process_image'] and witness['launch_start']<=time.monotonic()
    with pytest.raises(a.AuthorityError): a.python_launch(vector,dict(runtime,executable_sha256='0'*64),'reader')


@pytest.mark.parametrize('failure',['nonzero','timeout','witness'])
def test_owned_dispatch_once_reaps_and_emits_truthful_end(tmp_path,monkeypatch,failure):
    from validation.kernel_stage_a.production import owned_reader_dispatch
    events=tmp_path/'events'; runtime=a.runtime(); launched=[]; original=subprocess.Popen
    def capture(*args,**kwargs):
        child=original(*args,**kwargs); launched.append(child); return child
    monkeypatch.setattr(subprocess,'Popen',capture)
    if failure=='witness':
        original_event=a.event
        def emit(path,kind,**fields):
            if kind=='python_worker_launch': raise OSError('launch witness refused')
            original_event(path,kind,**fields)
        monkeypatch.setattr(a,'event',emit)
    vector=[sys.executable,'-c','import sys; sys.stdin.buffer.read(); raise SystemExit(3)'] if failure=='nonzero' else [sys.executable,'-c','import time; time.sleep(10)']
    with (tmp_path/'stdout').open('wb') as stdout,(tmp_path/'stderr').open('wb') as stderr:
        kwargs=dict(input=b'',stdout=stdout,stderr=stderr,cwd=tmp_path,env={},deadline=time.monotonic()+.1,event_path=events,runtime_identity=runtime)
        if failure=='nonzero': assert owned_reader_dispatch(vector,**kwargs).returncode==3
        else:
            with pytest.raises(subprocess.TimeoutExpired if failure=='timeout' else OSError): owned_reader_dispatch(vector,**kwargs)
    assert len(launched)==1 and launched[0].returncode is not None
    rows=[json.loads(x) for x in events.read_text().splitlines()]
    assert rows[-1]['event']=='python_worker_end' and rows[-1]['reaped'] is True
    assert rows[-1]['returncode']==launched[0].returncode


def test_baseline_is_joined_to_own_self_row_not_other_emitter(tmp_path):
    state,launch,live,gone,end,context=generation(tmp_path)
    state.baseline(dict(pid=20,rss=70,monotonic=12.2,boundary='post-import/pre-allocation'))
    state.self_sample(20,[live]); state.launch(launch,context)
    assert state.generations[20]['baseline']==70
    wrong=copy.deepcopy(live); wrong['pid']=21
    with pytest.raises(ValueError): state.self_sample(22,[wrong])


@pytest.mark.parametrize('change',[dict(rss=69),dict(monotonic=9.),dict(boundary='before-import')])
def test_baseline_wrong_generation_boundary_fails(tmp_path,change):
    state,launch,live,gone,end,context=generation(tmp_path); state.launch(launch,context); state.self_sample(20,[live])
    with pytest.raises(ValueError):
        state.baseline(dict(dict(pid=20,rss=70,monotonic=12.2,boundary='post-import/pre-allocation'),**change))


def test_overlapping_readers_and_unmatched_completion_rejected(tmp_path):
    state,launch,live,gone,end,context=generation(tmp_path); state.launch(launch,context)
    with pytest.raises(ValueError): state.launch(dict(launch,pid=21,launch_id='g2'),context)
    other,launch,live,gone,end,context=generation(tmp_path)
    other.end(end)
    assert other.unsettled()
    with pytest.raises(ValueError): other.launch(dict(launch,launch_id='wrong'),context)


def test_root_self_emitter_does_not_supply_unreaped_owner_proof(tmp_path):
    state,launch,live,gone,end,context=generation(tmp_path,'owned_root'); state.launch(launch,None)
    state.end(end); state.self_sample(10,[live])
    assert role(state,gone,context)=='pending_python_lifetime'


def test_monitor_root_generation_reconciles_natural_reap_without_erasing_failure(tmp_path,monkeypatch):
    runtime=a.runtime(); out=tmp_path/'monitor'; children=[]; original=subprocess.Popen
    command=[sys.executable,'-c','from pathlib import Path; import time\nwhile not Path("finish").exists(): time.sleep(.001)\nraise SystemExit(3)']
    def capture(*args,**kwargs):
        child=original(*args,**kwargs); children.append(child); return child
    monkeypatch.setattr(subprocess,'Popen',capture)
    count=0
    def sampler(pid,**kwargs):
        nonlocal count
        count+=1; start=time.monotonic(); end=time.monotonic()
        image=dict(status='ok',**runtime['process_image'],lookup_start=end,lookup_end=time.monotonic())
        if count==2:
            (out/'finish').touch(); children[0].wait(timeout=1)
            image=dict(status='error',errno=errno.ESRCH,method='macos.proc_pidpath',reason='native_lookup_failed',lookup_start=time.monotonic(),lookup_end=time.monotonic())
        entry=dict(pid=pid,parent=os.getpid(),rss_bytes=70,sample_start=start,sample_end=end,
                   raw_args=c.native_display(command,runtime),image=image)
        if count==1: a.event(out/'monitor-events.jsonl','baseline',pid=pid,rss=10)
        return m.ResidentTree({pid:70},{pid:entry})
    monkeypatch.setattr(m,'process_tree',sampler)
    result=m.supervise(command,out,sampler=sampler,outer_seconds=.5,free_disk_bytes=0)
    # This seam deliberately reaps behind the supervisor's back. It may still
    # join truthful exit evidence, but cannot certify group cleanup after losing
    # its ownership boundary.
    assert result['status']=='STOPPED' and result['returncode']==3,result
    assert result['reason']=='root ownership released before group observation',result
    records=[json.loads(line) for line in (out/'monitor-evidence.jsonl').read_text().splitlines()]
    resolutions=[x for x in records if x['kind']=='resolution']
    final=resolutions[-1]['identities'][str(children[0].pid)]
    assert final['launch_evidence']=='source_owned_python_lifetime'
    assert final['image_evidence']=='unavailable_exited'
    assert result['workers'][str(children[0].pid)]['absolute_peak_bytes']==70
    assert result['incremental_worker_peak_bytes']==60


def test_completion_cannot_precede_later_owned_image_proof(tmp_path):
    state,launch,live,gone,end,context=generation(tmp_path,'owned_root'); state.launch(launch,None)
    state.root_sample(live,owner_unreaped=True)
    later=copy.deepcopy(live); later['sample_start']=14.; later['sample_end']=15.; later['image'].update(lookup_start=15.,lookup_end=15.1)
    state.root_sample(later,owner_unreaped=True)
    with pytest.raises(ValueError): state.end(end)


@pytest.mark.parametrize('change',[dict(parent=99),dict(image=dict(status='error',errno=errno.EPERM)),
    dict(image=dict(status='error',errno=errno.ESRCH,reason='native_binding_failed'))])
def test_missing_launch_does_not_defer_conflicting_native_sample(tmp_path,change):
    state,launch,live,gone,end,context=generation(tmp_path)
    assert role(state,dict(gone,**change),context)=='unaccounted'


def test_completion_rechecks_already_bound_baseline_lifetime(tmp_path):
    state,launch,live,gone,end,context=generation(tmp_path); state.launch(launch,context); state.self_sample(20,[live])
    state.baseline(dict(pid=20,rss=70,monotonic=16.,boundary='post-import/pre-allocation'))
    with pytest.raises(ValueError): state.end(end)
