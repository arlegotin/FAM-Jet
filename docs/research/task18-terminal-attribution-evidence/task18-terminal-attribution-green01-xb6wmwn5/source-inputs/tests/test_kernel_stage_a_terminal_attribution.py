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
