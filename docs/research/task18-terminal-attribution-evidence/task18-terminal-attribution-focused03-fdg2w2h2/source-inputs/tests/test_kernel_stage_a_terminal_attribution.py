"""Source-only terminal attribution controls. All OS samples are controlled data."""
import copy
import errno
import json
import inspect
import os

import pytest
from validation.kernel_stage_a import authority as a, commands as c, monitor as m
from test_kernel_stage_a_native_process import identity, witness
from test_kernel_stage_a_python_lifetime import generation
from test_kernel_stage_a_terminal_lifecycle import exercise


def retained(rows, number=1, origin='owned_supervisor'):
    return dict(sample_id=number,entries={r['pid']:r for r in rows},proofs={},origin=origin)


def root_proof(state,row,context):
    options={"sample_context":context} if "sample_context" in inspect.signature(state.root_sample).parameters else {}
    state.root_sample(row,owner_unreaped=True,**options)


def self_proof(state,pid,rows,context):
    options={"sample_context":context} if "sample_context" in inspect.signature(state.self_sample).parameters else {}
    state.self_sample(pid,rows,**options)


def terminal(row):
    return dict(row,raw_comm='<defunct>',raw_args='<defunct>',rss_bytes=0)


def prepared(tmp_path, role='owned_root', *, proof=True, baseline=True, ended=True):
    state,launch,live,gone,end,context=generation(tmp_path,role)
    state.launch(launch,context)
    sample=retained([live],origin='owned_supervisor' if role=='owned_root' else 'emitter_self')
    if proof:
        if role=='owned_root': root_proof(state,live,sample)
        else: self_proof(state,launch['pid'],[live],sample)
    if baseline and role=='reader':
        state.baseline(dict(pid=20,rss=70,monotonic=12.2,boundary='post-import/pre-allocation'))
    if ended: state.end(end)
    return state,launch,live,terminal(gone),end,context


def classify(state, rows, context, *, declarations=None, phase=None, sample_context=None):
    options={"sample_context":sample_context} if "sample_context" in inspect.signature(m.classify).parameters else {}
    return m.classify(10,{r['pid']:r for r in rows},{10:70,20:70},declarations or {},
        stage_vector=state.stage_vector,reader_context=context,runtime_identity=identity(),
        python_lifetimes=state,authority_phase=phase,**options)


@pytest.mark.parametrize('family',['owned_root','reader'])
def test_literal_python_keeps_raw_terminal_and_records_source_proof(tmp_path,family):
    state,launch,live,row,end,context=prepared(tmp_path,family)
    raw=copy.deepcopy(row)
    assert classify(state,[row],context)[row['pid']]=='worker'
    assert {k:v for k,v in row.items() if k!='identity'}==raw
    evidence=row['identity']
    assert evidence['terminal_attribution']=='source_only_terminal_attribution'
    assert evidence['image_evidence']=='unavailable_exited'
    assert evidence['family']==family and evidence['launch_id']=='g1'
    assert evidence['proof']['sample_id']==1
    assert evidence['completion']['completion_end']==14.5
    assert evidence['ownership_observability']==('directly_observed_owner' if family=='owned_root' else 'parent_witnessed')


@pytest.mark.parametrize('missing',['proof','baseline','end'])
def test_reader_needs_genuine_self_baseline_and_completion(tmp_path,missing):
    state,launch,live,row,end,context=prepared(tmp_path,'reader',**{dict(proof='proof',baseline='baseline',end='ended')[missing]:False})
    assert classify(state,[row],context)[20].startswith('pending_')


@pytest.mark.parametrize('change',[
    {'raw_comm':'defunct'}, {'raw_args':'<defunct> '}, {'rss_bytes':1}, {'rss_bytes':0.0}, {'rss_bytes':False},
    {'ambiguous':True}, {'parent':99}, {'sample_start':15.,'sample_end':16.},
    {'sample_start':9.,'sample_end':9.5}, {'sample_start':12.,'sample_end':14.},
])
def test_terminal_row_contradictions_fail_closed(tmp_path,change):
    state,launch,live,row,end,context=prepared(tmp_path)
    row.update(change)
    assert classify(state,[row],context)[10]=='unaccounted'


@pytest.mark.parametrize('change',[{'errno':errno.EPERM},{'reason':'native_binding_failed'},
    {'method':'invented'},{'status':'ok','path':'/wrong','sha256':'x'},
    {'lookup_start':13.5},{'lookup_end':14.9}])
def test_terminal_requires_real_ordered_proc_pidpath_esrch(tmp_path,change):
    state,launch,live,row,end,context=prepared(tmp_path)
    row['image'].update(change)
    assert classify(state,[row],context)[10]=='unaccounted'


def helper(parent=10, *, start=13., end=14., launch_start=12.3, completion=14.5):
    row=dict(pid=30,parent=parent,rss_bytes=0,raw_comm='<defunct>',raw_args='<defunct>',
             sample_start=start,sample_end=end,image=dict(status='error',method='macos.proc_pidpath',
             reason='native_lookup_failed',errno=errno.ESRCH,lookup_start=end,lookup_end=end+.1))
    declared=witness(30,parent,m.PS_ARGV)
    declared.update(launch_id='helper',launch_start=launch_start,completion_end=completion)
    return row,declared


@pytest.mark.parametrize('parent_state',['live','absent','terminal'])
def test_ps_helper_historical_parent_routes(tmp_path,parent_state):
    state,launch,live,row,end,context=prepared(tmp_path,ended=parent_state=='terminal')
    child,declared=helper()
    rows=[child]
    if parent_state=='terminal': rows.append(row)
    if parent_state=='live':
        current=copy.deepcopy(live); current.update(sample_start=13.,sample_end=14.)
        current['image'].update(lookup_start=14.,lookup_end=14.1); rows.append(current)
    assert classify(state,rows,context,declarations={30:declared})[30]=='observer_helper'
    assert child['identity']['parent_qualification']['route']=='historical_'+parent_state
    assert child['identity']['parent_qualification']['launch_id']=='g1'


@pytest.mark.parametrize('family',['ps','git'])
def test_declared_terminal_helpers_require_own_launch_reap_not_historical_image(tmp_path,family):
    state,launch,live,row,end,context=prepared(tmp_path)
    child,declared=helper(parent=os.getpid() if family=='ps' else 10)
    phase=None
    if family=='git':
        vector=[a.GIT,'-C',str(tmp_path),'rev-parse','HEAD']
        declared=witness(30,10,vector,'git'); declared['launch_id']='git';
        phase=dict(active=True,started=True,start=10.,end=15.,commands=[vector],declarations={30:declared},completed={30})
    assert classify(state,[child],context,declarations={30:declared} if family=='ps' else {},phase=phase)[30]==('observer_helper' if family=='ps' else 'authority_helper')
    assert child['identity']['family']==family
    assert 'proof' not in child['identity']


@pytest.mark.parametrize('family',['owned_root','reader'])
def test_first_same_sample_live_parent_join_needs_no_extra_observation(tmp_path,family):
    state,launch,live,gone,end,context=generation(tmp_path,family)
    state.launch(launch,context)
    child,declared=helper(parent=launch['pid'],start=11.,end=12.,launch_start=11.2,completion=11.9)
    batch=retained([child,live],origin='owned_supervisor' if family=='owned_root' else 'emitter_self')
    if family=='owned_root': root_proof(state,live,batch)
    else: self_proof(state,20,[child,live],batch)
    before=classify(state,[child,live],context,declarations={30:declared},sample_context=batch)
    if family=='reader':
        assert before[30].startswith('pending_')
        state.baseline(dict(pid=20,rss=70,monotonic=12.2,boundary='post-import/pre-allocation'))
    assert classify(state,[child,live],context,declarations={30:declared},sample_context=batch)[30]=='observer_helper'
    relation=child['identity']['parent_qualification']
    assert relation['route']=='same_sample_live' and relation['proof']['sample_id']==1
    assert relation['proof']['lookup_end']>declared['completion_end']


@pytest.mark.parametrize('wrong',['copy','different_sample','different_emitter','forwarded_root','late_python_terminal'])
def test_same_sample_exception_cannot_be_borrowed(tmp_path,wrong):
    state,launch,live,gone,end,context=generation(tmp_path,'owned_root')
    state.launch(launch,context)
    child,declared=helper(start=11.,end=12.,launch_start=11.2,completion=11.9)
    batch=retained([child,live])
    root_proof(state,live,batch if wrong!='forwarded_root' else retained([live],origin='emitter_self'))
    if wrong=='copy': live=copy.deepcopy(live)
    if wrong in ('different_sample','different_emitter'): batch=retained([child,live],2,origin='emitter_self' if wrong=='different_emitter' else 'owned_supervisor')
    if wrong=='late_python_terminal':
        state.end(end); row=terminal(gone); row.update(sample_start=12.,sample_end=14.)
        assert classify(state,[row],context)[10]=='unaccounted'; return
    assert classify(state,[child,live],context,declarations={30:declared},sample_context=batch)[30]!='observer_helper'


@pytest.mark.parametrize('change',[{'reaped':False},{'parent':99},{'argv':['/bin/ps']},{'vector_sha256':'bad'},
    {'artifact':{'path':'/wrong','sha256':'c'*64}},{'launch_id':None},{'provenance':'copied'},
    {'launch_start':9.},{'completion_end':12.},{'ambiguous':True}])
def test_terminal_helper_rejects_contradictory_source_witness(tmp_path,change):
    state,launch,live,row,end,context=prepared(tmp_path)
    child,declared=helper(); declared.update(change)
    assert classify(state,[child],context,declarations={30:declared})[30]=='unaccounted'


def terminal_exercise(tmp_path,monkeypatch,*,literal=True,group='root',failure=None,proof=True,cap=False,forwarded=False):
    original=m.supervise
    def supervise(command,out,**kwargs):
        sampler=kwargs['sampler']; observe=m._cleanup_observation; count=0
        def sample(pid,**options):
            nonlocal count
            data=sampler(pid,**options); count+=1
            if forwarded and count==1:
                own=data.processes[pid]
                a.event(out/'monitor-events.jsonl','observer_sample',emitter_pid=pid,self_pid=pid,processes=[copy.deepcopy(own)])
                return m.ResidentTree({}, {})
            if count==2:
                row=data.processes[pid]; row['rss_bytes']=0; data[pid]=0
                if literal: row.update(raw_args='<defunct>',raw_comm='<defunct>')
            return data
        def membership(*args,**options):
            result=observe(*args,**options)
            for row in result['rows']:
                if row['pid']==470001: row['rss_bytes']=0
            if group=='survivor': result['rows'].append(dict(pid=470001,parent=os.getpid(),pgid=470001,rss_bytes=0))
            return result
        monkeypatch.setattr(m,'process_tree',sample); monkeypatch.setattr(m,'_cleanup_observation',membership)
        kwargs['sampler']=sample
        return original(command,out,**kwargs)
    monkeypatch.setattr(m,'supervise',supervise)
    return exercise(tmp_path,monkeypatch,group=group,failure=failure,proof=proof,cap=cap)


@pytest.mark.parametrize('literal',[True,False])
def test_root_only_cleanup_is_truthful_nonempty_and_resolves_after_actual_end(tmp_path,monkeypatch,literal):
    result,records,order=terminal_exercise(tmp_path,monkeypatch,literal=literal)
    assert result['status']=='COMPLETED',result
    decisions=[r for r in records if r['kind']=='cleanup_terminal_qualification']
    assert len(decisions)==1 and decisions[0]['qualified_terminal_root_only'] is True
    assert decisions[0]['membership_empty'] is False
    assert decisions[0]['route']==('literal_terminal' if literal else 'exact_display_esrch')
    assert order.index('membership')<order.index('poll')<order.index('end') and 'kill' not in order
    end_index=next(i for i,r in enumerate(records) if r['kind']=='python_root_end')
    resolution_index=next(i for i,r in enumerate(records) if r['kind']=='resolution' and r['sample_id']==2)
    assert end_index<resolution_index
    raw=[r for r in records if r['kind']=='sample' and r['sample_id']==2][0]['processes'][0]
    assert raw['rss_bytes']==0 and 'identity' not in raw
    assert raw['raw_args']=='<defunct>' if literal else raw['raw_args']!='<defunct>'


@pytest.mark.parametrize('failure',['poll_none','provenance','mismatched_end'])
def test_missing_cleanup_prerequisite_never_qualifies(tmp_path,monkeypatch,failure):
    result,records,order=terminal_exercise(tmp_path,monkeypatch,failure=failure)
    assert result['status']!='COMPLETED'
    assert not any(r.get('qualified_terminal_root_only') for r in records)


def test_terminal_root_does_not_exempt_survivors_or_prior_cap(tmp_path,monkeypatch):
    result,records,order=terminal_exercise(tmp_path,monkeypatch,group='survivor',cap=True)
    assert result['status']=='STOPPED' and result['reason']=='incremental worker memory cap'
    assert order.index('kill')<order.index('wait')
    assert not any(r.get('qualified_terminal_root_only') for r in records)


def test_forwarded_emitter_root_cannot_create_owner_proof(tmp_path,monkeypatch):
    result,records,order=terminal_exercise(tmp_path,monkeypatch,forwarded=True)
    assert result['status']!='COMPLETED'
    assert not any(r.get('qualified_terminal_root_only') for r in records)
    assert not any(e.get('proof',{}).get('origin')=='unreaped_owned_root'
        for r in records for e in (r.get('identities') or {}).values() if e)


@pytest.mark.parametrize('contradiction',['duplicate','wrong_end','wrong_baseline','bad_image','reused_id'])
def test_failed_generation_cannot_be_repaired_by_late_valid_events(tmp_path,contradiction):
    state,launch,live,row,end,context=prepared(tmp_path,'reader',ended=False)
    if contradiction=='bad_image':
        bad=dict(live,image=dict(status='ok',path='/wrong',sha256='x'))
        assert classify(state,[bad],context)[20]=='unaccounted'
    else:
        with pytest.raises(ValueError):
            if contradiction=='duplicate': state.launch(launch,context)
            elif contradiction=='reused_id': state.launch(dict(launch,pid=21),context)
            elif contradiction=='wrong_end': state.end(dict(end,launch_id='wrong'))
            else: state.baseline(dict(pid=20,rss=71,monotonic=12.3,boundary='post-import/pre-allocation'))
    try: state.end(end)
    except ValueError: pass
    assert classify(state,[row],context)[20]=='unaccounted'


@pytest.mark.parametrize('change',[{'lookup_start':11.},{'lookup_end':11.5},{'lookup_start':15.,'lookup_end':16.}])
def test_historical_helper_parent_rejects_current_invalid_proof_timing(tmp_path,change):
    state,launch,live,row,end,context=prepared(tmp_path,ended=True)
    parent=copy.deepcopy(live); parent.update(sample_start=13.,sample_end=14.)
    parent['image'].update(lookup_start=14.,lookup_end=14.1); parent['image'].update(change)
    child,declared=helper()
    assert classify(state,[child,parent],context,declarations={30:declared})[30]=='unaccounted'


def run_pending_join(tmp_path,monkeypatch,join,*,failure=None):
    """Real supervisor event ingestion, mocked owning process/native observations."""
    from pathlib import Path
    import sys
    import time
    runtime=identity(); runtime.update(executable=str(Path(sys.executable).resolve()),
        executable_sha256=a.file_hash(Path(sys.executable).resolve()))
    monkeypatch.setattr(a,'runtime',lambda:runtime)
    out=tmp_path/'join'; events=out/'monitor-events.jsonl'; root=610001; reader=610002; child=610003
    vector=c.stage_command(tmp_path,tmp_path/'seal'); calls=[]; saved={}
    def emit(event):
        with events.open('a') as stream: stream.write(json.dumps(event)+'\n')
    class Owner:
        pid=root; returncode=None
        def poll(self): self.returncode=0; return 0
        def wait(self,timeout):
            if self.returncode is None: self.returncode=0
            return self.returncode
    owner=Owner()
    monkeypatch.setattr(m.subprocess,'Popen',lambda *args,**kw:owner)
    monkeypatch.setattr(m.time,'sleep',lambda value:None)
    monkeypatch.setattr(m.os,'killpg',lambda *args:None)
    def membership(*args,**kw):
        now=time.monotonic()
        return dict(start=now,end=now,rows=[],helper=None,complete=True,error=None,stdout='',stderr='')
    monkeypatch.setattr(m,'_cleanup_observation',membership)
    def observe(pid,**kw):
        calls.append(pid)
        start=time.monotonic(); end=time.monotonic(); lookup=time.monotonic()
        image=(dict(status='ok',**runtime['process_image']) if len(calls)==1 else
               dict(status='error',errno=errno.ESRCH,method='macos.proc_pidpath',reason='native_lookup_failed'))
        row=dict(pid=root,parent=os.getpid(),rss_bytes=0,raw_comm='/Python',raw_args=c.native_display(vector,runtime),
                 sample_start=start,sample_end=end,image=dict(image,lookup_start=lookup,lookup_end=time.monotonic()))
        if len(calls)==1:
            emit(dict(event='baseline',pid=root,rss=0,monotonic=time.monotonic()))
            emit(dict(event='candidate_start',monotonic=time.monotonic()))
            launch_start=time.monotonic(); argv=c.reader_command(tmp_path,events,launch_start+.2)
            launch=dict(event='python_worker_launch',pid=reader,parent=root,role='reader',argv=argv,
                executable=argv[0],vector_sha256=c.vector_hash(argv),launch_id='reader',launch_start=launch_start,
                provenance='source_owned_python_launch',launcher=dict(path=runtime['executable'],sha256=runtime['executable_sha256']),
                expected_image=runtime['process_image'],reaped=False,monotonic=launch_start)
            sample_start=time.monotonic(); helper_start=time.monotonic(); completed=time.monotonic()
            sample_end=time.monotonic(); lookup=time.monotonic(); lookup_end=time.monotonic()
            live=dict(pid=reader,parent=root,rss_bytes=100,raw_comm='/Python',raw_args=c.native_display(argv,runtime),
                sample_start=sample_start,sample_end=sample_end,
                image=dict(status='ok',**runtime['process_image'],lookup_start=lookup,lookup_end=lookup_end))
            helper_row=dict(pid=child,parent=reader,rss_bytes=0,raw_comm='<defunct>',raw_args='<defunct>',
                sample_start=sample_start,sample_end=sample_end,
                image=dict(status='error',errno=errno.ESRCH,method='macos.proc_pidpath',reason='native_lookup_failed',lookup_start=lookup,lookup_end=lookup_end))
            declared=witness(child,reader,m.PS_ARGV); declared.update(launch_id='ps-child',launch_start=helper_start,reaped=False)
            declared.pop('completion_end')
            emit(dict(declared,event='observer_helper',monotonic=helper_start))
            emit(dict(event='observer_helper_end',pid=child,parent=reader,launch_id='ps-child',reaped=True,completion_end=completed,monotonic=completed))
            sample_event=dict(event='observer_sample',emitter_pid=reader,self_pid=reader,processes=[helper_row,live],monotonic=time.monotonic())
            baseline=dict(event='baseline',pid=reader,rss=100,boundary='post-import/pre-allocation',monotonic=time.monotonic())
            saved.update(launch=launch,baseline=baseline,self=sample_event)
            if join!='launch': emit(launch)
            if join!='self': emit(sample_event)
            else:
                # Same rows forwarded by a different emitter cannot supply SELF.
                copy_event=dict(event='observer_sample',processes=[helper_row,live],monotonic=time.monotonic())
                emit(copy_event)
            if join!='baseline': emit(baseline)
        else:
            assert len(calls)==2,'late dependency must settle the existing helper without more observations'
            prior=[json.loads(line) for line in (out/'monitor-evidence.jsonl').read_text().splitlines()]
            pending=[r for r in prior if r['kind']=='resolution' and str(child) in r['roles']]
            assert len(pending)==1 and pending[0]['roles'][str(child)].startswith('pending_')
            if failure=='provenance': emit(dict(event='unknown',monotonic=time.monotonic()))
            elif failure=='parent':
                emit(dict(saved['launch'],argv=['/wrong'],launch_id='replacement'))
            elif failure=='duplicate_helper':
                emit(dict(event='observer_helper',**{k:v for k,v in declared.items()}))
            emit(saved[join])
            emit(dict(event='python_worker_end',pid=reader,parent=root,launch_id='reader',reaped=True,returncode=0,
                      completion_end=time.monotonic(),monotonic=time.monotonic()))
        return m.ResidentTree({root:0},{root:row})
    monkeypatch.setattr(m,'process_tree',observe)
    result=m.supervise(vector,out,sampler=observe,authority_root=tmp_path,outer_seconds=.5,free_disk_bytes=0,incremental_bytes=1000)
    records=[json.loads(line) for line in (out/'monitor-evidence.jsonl').read_text().splitlines()]
    return result,records


@pytest.mark.parametrize('join',['launch','baseline'])
def test_pending_helper_wakes_on_parent_generation_or_first_baseline(tmp_path,monkeypatch,join):
    result,records=run_pending_join(tmp_path,monkeypatch,join)
    assert result['status']=='COMPLETED',result
    resolutions=[r for r in records if r['kind']=='resolution' and '610003' in r['roles']]
    assert len(resolutions)==2 and resolutions[-1]['roles']['610003']=='observer_helper'
    relation=resolutions[-1]['identities']['610003']['parent_qualification']
    assert relation['route']=='same_sample_live' and relation['proof']['sample_id']==resolutions[-1]['sample_id']
    assert len([r for r in records if r['kind']=='sample' and '610003' in r['rss']])==1


@pytest.mark.parametrize('failure',['provenance','parent'])
def test_pending_helper_cannot_recover_from_parent_or_provenance_failure(tmp_path,monkeypatch,failure):
    result,records=run_pending_join(tmp_path,monkeypatch,'baseline',failure=failure)
    assert result['status']!='COMPLETED'
    assert not any(r['roles'].get('610003')=='observer_helper' for r in records if r['kind']=='resolution')


def test_later_self_copy_does_not_repair_original_helper_sample(tmp_path,monkeypatch):
    result,records=run_pending_join(tmp_path,monkeypatch,'self')
    assert result['status']!='COMPLETED'
    resolutions=[r for r in records if r['kind']=='resolution' and r['sample_id']==2]
    assert all(r['roles']['610003']!='observer_helper' for r in resolutions)


def test_only_forwarded_live_root_cannot_qualify_terminal_cleanup(tmp_path,monkeypatch):
    from pathlib import Path
    import sys
    import time
    runtime=identity(); runtime.update(executable=str(Path(sys.executable).resolve()),
        executable_sha256=a.file_hash(Path(sys.executable).resolve()))
    monkeypatch.setattr(a,'runtime',lambda:runtime)
    pid=620001; out=tmp_path/'forwarded'; vector=[sys.executable,'-c','pass']; signals=[]
    class Owner:
        returncode=None
        def poll(self): self.returncode=0; return 0
        def wait(self,timeout): self.returncode=0; return 0
    owner=Owner(); owner.pid=pid
    monkeypatch.setattr(m.subprocess,'Popen',lambda *args,**kw:owner)
    monkeypatch.setattr(m.os,'killpg',lambda *args:signals.append(args))
    def observe(root,**kw):
        start=time.monotonic(); end=time.monotonic(); lookup=time.monotonic()
        live=dict(pid=pid,parent=os.getpid(),rss_bytes=100,raw_comm='/Python',raw_args=c.native_display(vector,runtime),
            sample_start=start,sample_end=end,image=dict(status='ok',**runtime['process_image'],lookup_start=lookup,lookup_end=time.monotonic()))
        a.event(out/'monitor-events.jsonl','observer_sample',emitter_pid=pid,self_pid=pid,processes=[live])
        a.event(out/'monitor-events.jsonl','baseline',pid=pid,rss=100)
        start=time.monotonic(); end=time.monotonic(); lookup=time.monotonic()
        gone=dict(pid=pid,parent=os.getpid(),rss_bytes=0,raw_comm='<defunct>',raw_args='<defunct>',sample_start=start,sample_end=end,
            image=dict(status='error',method='macos.proc_pidpath',reason='native_lookup_failed',errno=errno.ESRCH,lookup_start=lookup,lookup_end=time.monotonic()))
        return m.ResidentTree({pid:0},{pid:gone})
    def membership(*args,**kw):
        now=time.monotonic()
        return dict(start=now,end=now,rows=[dict(pid=pid,parent=os.getpid(),pgid=pid,rss_bytes=0)],helper=None,
                    complete=True,error=None,stdout='',stderr='')
    monkeypatch.setattr(m,'process_tree',observe); monkeypatch.setattr(m,'_cleanup_observation',membership)
    result=m.supervise(vector,out,sampler=observe,outer_seconds=.5,free_disk_bytes=0)
    records=[json.loads(line) for line in (out/'monitor-evidence.jsonl').read_text().splitlines()]
    assert result['status']!='COMPLETED' and signals
    assert not any(r.get('qualified_terminal_root_only') for r in records)
    assert not any(e.get('proof',{}).get('origin')=='unreaped_owned_root'
        for r in records for e in (r.get('identities') or {}).values() if e)


@pytest.mark.parametrize('reverse',[False,True])
def test_terminal_parent_completion_is_required_independently_of_row_order(tmp_path,reverse):
    state,launch,live,row,end,context=prepared(tmp_path,ended=False)
    child,declared=helper(); rows=[row,child] if reverse else [child,row]
    before=classify(state,rows,context,declarations={30:declared})
    assert before[10].startswith('pending_') and before[30].startswith('pending_')
    state.end(end)
    after=classify(state,rows,context,declarations={30:declared})
    assert after=={r['pid']:'worker' if r['pid']==10 else 'observer_helper' for r in rows}


@pytest.mark.parametrize('change',[{'reaped':False},{'returncode':False},{'launch_id':'wrong'},
    {'parent':99},{'completion_end':12.1},{'completion_end':9.}])
def test_terminal_python_rejects_false_or_incompatible_completion(tmp_path,change):
    state,launch,live,row,end,context=prepared(tmp_path,ended=False)
    with pytest.raises(ValueError): state.end(dict(end,**change))
    assert classify(state,[row],context)[10]=='unaccounted'


@pytest.mark.parametrize('change',[{'role':'other'},{'argv':['/wrong']},{'vector_sha256':'wrong'},
    {'launcher':{'path':'/wrong','sha256':'a'*64}},{'expected_image':{'path':'/wrong','sha256':'b'*64}},
    {'provenance':'copy'},{'parent':99}])
def test_terminal_python_source_launch_cannot_be_repaired(tmp_path,change):
    state,launch,live,row,end,context=generation(tmp_path)
    with pytest.raises(ValueError): state.launch(dict(launch,**change),context)
    with pytest.raises(ValueError): state.launch(launch,context)


@pytest.mark.parametrize('mutation',['outside_phase','wrong_vector','incomplete_end','missing_launch'])
def test_terminal_git_never_escapes_declared_authority_phase(tmp_path,mutation):
    state,launch,live,row,end,context=prepared(tmp_path)
    child,declared=helper(); vector=[a.GIT,'-C',str(tmp_path),'rev-parse','HEAD']
    declared=witness(30,10,vector,'git')
    phase=dict(active=True,started=True,start=10.,end=15.,commands=[vector],declarations={30:declared},completed={30})
    expected='unaccounted'
    if mutation=='outside_phase': phase['end']=12.
    elif mutation=='wrong_vector': declared['argv']=[a.GIT,'status']
    elif mutation=='incomplete_end': declared.pop('completion_end'); expected='pending_terminal_launch'
    else: phase['declarations']={}; expected='pending_terminal_launch'
    assert classify(state,[child],context,phase=phase)[30]==expected
