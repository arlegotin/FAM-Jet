"""Controlled source lifecycle observations; no native subprocess or numerical work."""
import copy
import errno
import os
import pytest
from validation.kernel_stage_a import authority as a, commands as c, monitor as m
from test_kernel_stage_a_native_process import identity, witness
from test_kernel_stage_a_terminal_attribution import prepared, classify
from test_kernel_stage_a_python_lifetime import generation


def helper_case(tmp_path, family='ps', display='(ps)', rss=3850240):
    state, launch, live, gone, end, context = prepared(tmp_path)
    vector=m.PS_ARGV if family=='ps' else a.git_commands(tmp_path)[int(family[-1])]
    declaration=witness(30,10,vector,'ps' if family=='ps' else 'git')
    declaration.update(launch_id='helper',launch_start=12.3,completion_end=13.6,returncode=0)
    row=dict(pid=30,parent=10,rss_bytes=rss,raw_comm=display,raw_args=display,
             sample_start=13.,sample_end=14.,image=dict(status='error',errno=errno.ESRCH,
             method='macos.proc_pidpath',reason='native_lookup_failed',lookup_start=14.1,lookup_end=14.2))
    phase=None if family=='ps' else dict(active=False,started=True,start=10.,end=14.5,
         commands=a.git_commands(tmp_path),declarations={30:declaration},completed={30})
    def resolve():
        return classify(state,[row],context,declarations={30:declaration} if family=='ps' else {},phase=phase)[30]
    return state,declaration,row,resolve


@pytest.mark.parametrize('family',['ps','git0','git1'])
@pytest.mark.parametrize('display,rss',[('(ps)',3850240),('arbitrary retained display',1802240),('<defunct>',17)])
def test_overlapping_completed_helpers_need_no_live_image(tmp_path,family,display,rss):
    state,decl,row,resolve=helper_case(tmp_path,family,display,rss)
    assert resolve()==('observer_helper' if family=='ps' else 'authority_helper')
    assert row['identity']['launch_evidence']=='source_owned_lifecycle'
    assert row['identity']['image_evidence']=='image_unavailable'
    assert row['identity']['completion']['returncode']==0
    assert row['rss_bytes']==rss and row['raw_args']==display


def test_forwarded_earlier_sample_keeps_positive_peak_and_source_join(tmp_path):
    state,decl,row,resolve=helper_case(tmp_path)
    assert resolve()=='observer_helper'
    row.update(raw_args=c.display(m.PS_ARGV),raw_comm='/bin/ps',rss_bytes=1802240,sample_start=12.2,sample_end=13.8)
    assert resolve()=='observer_helper'


@pytest.mark.parametrize('change',[{'parent':99},{'ambiguous':True},{'rss_bytes':True},
    {'sample_start':14.6,'sample_end':15.},{'sample_start':14.5,'sample_end':13.}])
def test_row_contradictions_remain_sticky(tmp_path,change):
    state,decl,row,resolve=helper_case(tmp_path); original=copy.deepcopy(row); row.update(change)
    assert resolve()=='unaccounted'
    row.clear(); row.update(original)
    assert resolve()=='unaccounted'


@pytest.mark.parametrize('change',[{'status':'ok','path':'/wrong','sha256':'c'*64},
    {'method':'fabricated'},{'reason':'native_binding_failed'},{'lookup_start':12.},
    {'lookup_end':14.0},{'errno':errno.EPERM}])
def test_malformed_or_contradictory_lookup_cannot_be_repaired(tmp_path,change):
    state,decl,row,resolve=helper_case(tmp_path); row['image'].update(change)
    assert resolve()=='unaccounted'


@pytest.mark.parametrize('change',[{'returncode':None},{'reaped':False},{'artifact':{}},
    {'launch_start':15.},{'parent':99},{'argv':['/bin/ps']},{'provenance':'copied'},
    {'launch_id':None},{'completion_end':12.}])
def test_bad_source_lifetime_never_certifies(tmp_path,change):
    state,decl,row,resolve=helper_case(tmp_path); decl.update(change)
    assert resolve()=='unaccounted'


def test_reader_lifecycle_alone_never_grants_baseline(tmp_path):
    state,launch,live,row,end,context=generation(tmp_path)
    state.launch(launch,context); state.end(end)
    row.update(raw_args='arbitrary reader teardown',raw_comm='(Python)')
    roles=m.classify(10,{20:row},{},{},reader_context=context,stage_vector=state.stage_vector,
                     runtime_identity=identity(),python_lifetimes=state)
    assert roles[20]=='reader_lifecycle'
    assert row['identity']['image_evidence']=='image_unavailable'
    assert 'baseline' not in state.generations[20]


def test_missing_helper_end_stays_pending_then_resolves(tmp_path):
    state,decl,row,resolve=helper_case(tmp_path)
    end=decl.pop('completion_end'); decl['reaped']=False; decl.pop('returncode')
    assert resolve().startswith('pending_')
    decl.update(completion_end=end,reaped=True,returncode=0)
    assert resolve()=='observer_helper'


@pytest.mark.parametrize('collision',['pid','id','family','end'])
def test_registry_cross_family_collisions_are_sticky(collision):
    registry=m.SourceLifecycles(); first=witness(30,10,m.PS_ARGV); first['returncode']=0
    registry.declare(first,'ps',dict(kind='parent_reported',path='events',offset=17))
    other=witness(31,10,m.PS_ARGV); other.update(launch_id='other',returncode=0)
    if collision in ('pid','family'): other['pid']=30
    if collision=='id': other['launch_id']=first['launch_id']
    with pytest.raises(ValueError):
        if collision=='end': registry.complete(first)
        else: registry.declare(other,'git' if collision=='family' else 'ps')
    assert (31 if collision=='id' else 30) in registry.failed
    if collision=='id': assert 30 in registry.failed


@pytest.mark.parametrize('family',['ps','cleanup_ps','git'])
def test_source_end_can_arrive_before_launch_without_fabricated_peak(tmp_path,family):
    registry=m.SourceLifecycles(); vector=m._CLEANUP_ARGV if family=='cleanup_ps' else a.git_commands(tmp_path)[0] if family=='git' else m.PS_ARGV
    entry=witness(30,10,vector,'git' if family=='git' else 'ps'); entry['returncode']=7
    end={k:entry[k] for k in ('pid','parent','launch_id','reaped','completion_end','returncode')}
    registry.complete(end)
    launch={k:v for k,v in entry.items() if k not in ('completion_end','returncode')}; launch['reaped']=False
    assert registry.unsettled()
    registry.declare(launch,family,dict(kind='parent_reported',path='events',offset=3))
    assert not registry.unsettled()
    assert registry.generations[30]['peak_bytes'] is None
    assert registry.ends[30]['returncode']==7


def test_observer_end_uses_actual_retained_popen_status(monkeypatch,tmp_path):
    import json
    class Probe:
        pid=700001; stdout=None; returncode=None
        def communicate(self,timeout): self.returncode=0; return ('700001 1 2 /bin/ps ignored\n','')
        def poll(self): return self.returncode
    monkeypatch.setattr(m.subprocess,'Popen',lambda *args,**kw:Probe())
    monkeypatch.setattr(a,'helper_artifact',lambda path:identity()['helpers']['ps'])
    monkeypatch.setattr(a,'process_image',lambda pid:dict(status='error',errno=errno.ESRCH))
    path=tmp_path/'events.jsonl'
    sampled=m.process_tree(10,observer_log=path,runtime_identity=identity())
    events=[json.loads(line) for line in path.read_text().splitlines()]
    assert events[-1]['returncode']==sampled.declarations[700001]['returncode']==0
    assert events[-1]['reaped'] and events[-1]['launch_id']==events[0]['launch_id']


@pytest.mark.parametrize('fault',[None,'unknown','missing_end','source_gap','cap','cleanup_failure'])
def test_supervisor_source_reordering_full_rss_and_failures(tmp_path,monkeypatch,fault):
    import json, time
    from test_kernel_stage_a_owned_root_terminal import exercise
    original=m.supervise
    def supervise(command,out,**options):
        original_sample=options['sampler']; original_cleanup=m._cleanup_observation; count=0; saved={}
        def emit(event):
            with (out/'monitor-events.jsonl').open('a') as stream: stream.write(json.dumps(event)+'\n')
        def sampler(pid,**kwargs):
            nonlocal count
            data=original_sample(pid,**kwargs); count+=1
            if count==2:
                start=time.monotonic(); launch=time.monotonic(); completion=time.monotonic(); end=time.monotonic()
                declaration=witness(700002,pid,m.PS_ARGV); declaration.update(launch_id='reordered',launch_start=launch,reaped=False)
                declaration.pop('completion_end'); declaration.pop('returncode',None)
                row=dict(pid=700002,parent=pid,rss_bytes=3850240,raw_args='(ps)',raw_comm='(ps)',sample_start=start,sample_end=end,
                         image=dict(status='error',errno=errno.ESRCH,reason='native_lookup_failed',method='macos.proc_pidpath',
                                    lookup_start=time.monotonic(),lookup_end=time.monotonic()))
                saved.update(declaration=declaration,completion=completion,row=row)
                data[700002]=row['rss_bytes']; data.processes[700002]=row
            if count==3 and fault!='unknown':
                emit(dict(saved['declaration'],event='observer_helper',monotonic=time.monotonic()))
                if fault!='missing_end':
                    emit(dict(event='observer_helper_end',pid=700002,parent=pid,launch_id='reordered',completion_end=saved['completion'],
                              reaped=True,returncode=0,monotonic=time.monotonic()))
                earlier=copy.deepcopy(saved['row']); earlier.update(rss_bytes=1802240,raw_args=c.display(m.PS_ARGV))
                emit(dict(event='observer_sample',processes=[earlier],monotonic=time.monotonic()))
                if fault=='source_gap':
                    with (out/'monitor-events.jsonl').open('a') as stream: stream.write('{')
            return data
        def cleanup(*args,**kwargs):
            value=original_cleanup(*args,**kwargs)
            if fault=='cleanup_failure': value.update(complete=False,error='controlled query failure')
            return value
        monkeypatch.setattr(m,'process_tree',sampler); monkeypatch.setattr(m,'_cleanup_observation',cleanup)
        options['sampler']=sampler
        return original(command,out,**options)
    monkeypatch.setattr(m,'supervise',supervise)
    result,records,*_=exercise(tmp_path,monkeypatch,incremental_bytes=7000000 if fault=='cap' else 201326592)
    assert result['status']==('COMPLETED' if fault is None else 'FAILED' if fault=='source_gap' else 'STOPPED')
    helper=result['workers']['700002']
    assert helper['baseline_bytes']==0 and helper['absolute_peak_bytes']==3850240
    assert helper['incremental_peak_bytes']==3850240
    if fault is None:
        assert helper['role']=='observer_helper'
        resolutions=[r for r in records if r['kind']=='resolution' and r['roles'].get('700002')=='observer_helper']
        assert resolutions and resolutions[-1]['identities']['700002']['source']['offset']>=0


@pytest.mark.parametrize('change',[{'lookup_start':float('nan')},{'lookup_end':float('inf')}])
def test_nonfinite_lookup_is_not_ordered_native_evidence(tmp_path,change):
    state,decl,row,resolve=helper_case(tmp_path); row['image'].update(change)
    assert resolve()=='unaccounted'


def test_delayed_live_helper_declaration_is_pending_without_certification(tmp_path):
    state,decl,row,resolve=helper_case(tmp_path)
    row.update(raw_args=c.display(m.PS_ARGV),sample_start=12.4,sample_end=12.5)
    row['image']=dict(status='ok',method='macos.proc_pidpath',**identity()['helpers']['ps'],lookup_start=12.5,lookup_end=12.6)
    # A live source owner and valid image can await its declaration in the existing drain.
    state.ends.pop(10)
    assert classify(state,[row],None)[30].startswith('pending_')
    assert row['identity']['image_evidence']=='unresolved'
    assert resolve()=='observer_helper'


def test_unmeasured_cleanup_image_does_not_manufacture_zero_rss():
    registry=m.SourceLifecycles(); entry=witness(30,os.getpid(),m._CLEANUP_ARGV); entry['returncode']=0
    registry.declare(entry,'cleanup_ps',dict(kind='owned_supervisor'))
    image=dict(status='error',errno=errno.ESRCH,method='macos.proc_pidpath',reason='native_lookup_failed',lookup_start=12.,lookup_end=12.1)
    assert registry.image_evidence(30,image,11.,14.,numeric=True)=='image_unavailable'
    assert registry.generations[30]['peak_bytes'] is None


def test_cleanup_family_cannot_reuse_observed_source_pid(tmp_path):
    state,decl,row,resolve=helper_case(tmp_path)
    assert resolve()=='observer_helper'
    other=witness(30,os.getpid(),m._CLEANUP_ARGV); other.update(launch_id='cleanup',returncode=0)
    with pytest.raises(ValueError,match='duplicate/reused'): state.registry.declare(other,'cleanup_ps')
    assert resolve()=='unaccounted'


@pytest.mark.parametrize('sampled',[False,True])
@pytest.mark.parametrize('order',['parent_first','parent_end_late','parent_declaration_late'])
def test_child_completion_cannot_outlive_owner_even_with_reordered_evidence(tmp_path,sampled,order):
    parent=witness(10,os.getpid(),m.PS_ARGV); parent.update(launch_id='parent',launch_start=10.,completion_end=14.5,returncode=0)
    child=witness(30,10,m.PS_ARGV); child.update(launch_id='child',launch_start=12.3,completion_end=16.,returncode=0)
    registry=m.SourceLifecycles()
    if order=='parent_first': registry.declare(parent,'owned_root')
    elif order=='parent_end_late':
        launch={k:v for k,v in parent.items() if k not in ('completion_end','returncode')}; launch['reaped']=False
        registry.declare(launch,'owned_root')
    with pytest.raises(ValueError,match='parent'):
        registry.declare(child,'ps')
        if sampled:
            _,_,row,_=helper_case(tmp_path)
            assert registry.attribute(row)=='attributed'
        if order=='parent_end_late': registry.complete(parent)
        elif order=='parent_declaration_late': registry.declare(parent,'owned_root')
    assert 30 in registry.failed
    _,_,row,_=helper_case(tmp_path)
    assert registry.attribute(row)=='unaccounted'


def test_sampled_helper_rejects_completion_after_retained_parent(tmp_path):
    state,decl,row,resolve=helper_case(tmp_path); decl['completion_end']=16.
    assert resolve()=='unaccounted'
    assert 30 in state.failed


@pytest.mark.parametrize('fault',[None,'early_launch','late_completion','unqualified_parent'])
def test_unsampled_git_still_requires_exact_phase_and_qualified_parent(tmp_path,monkeypatch,fault):
    import json,time
    import sys
    from pathlib import Path
    runtime=identity(); runtime.update(executable=str(Path(sys.executable).resolve()),
        executable_sha256=a.file_hash(Path(sys.executable).resolve()))
    monkeypatch.setattr(a,'runtime',lambda:runtime)
    pid=570001; vector=[sys.executable,'-c','pass']; out=tmp_path/'monitor'; state={}
    class Owner:
        returncode=None
        def poll(self): self.returncode=0; return 0
        def wait(self,timeout): self.returncode=0; return 0
    owner=Owner(); owner.pid=pid
    monkeypatch.setattr(m.subprocess,'Popen',lambda *args,**kw:owner)
    monkeypatch.setattr(m.os,'killpg',lambda *args:None)
    original=m.PythonLifetimes.launch
    def launch(self,entry,context): original(self,entry,context); state['owner']=self
    monkeypatch.setattr(m.PythonLifetimes,'launch',launch)
    def sampler(root,**kw):
        import math
        instants=[state['owner'].generations[pid]['launch_start']]
        for _ in range(4): instants.append(math.nextafter(instants[-1],float('inf')))
        t0,t1,t2,t3,t4=instants
        assert t0<t1<t2<t3<t4<time.monotonic()
        if fault!='unqualified_parent':
            row=dict(pid=pid,parent=os.getpid(),rss_bytes=1,raw_args=c.native_display(vector,runtime),
                sample_start=t0,sample_end=t1,image=dict(status='ok',**runtime['process_image'],lookup_start=t1,lookup_end=t2))
            context=dict(sample_id=1,entries={pid:row},proofs={},origin='owned_supervisor')
            state['owner'].root_sample(row,owner_unreaped=True,sample_context=context)
        events=[dict(event='authority_start',pid=pid,monotonic=t1)]
        for number,argv in enumerate(a.git_commands(tmp_path)):
            entry=witness(700010+number,pid,argv,'git')
            entry.update(launch_id='git'+str(number),launch_start=t0 if fault=='early_launch' else t2,reaped=False)
            entry.pop('completion_end'); entry.pop('returncode',None)
            events.extend([dict(entry,event='authority_helper',monotonic=t2),dict(event='authority_helper_end',pid=entry['pid'],
                parent=pid,launch_id=entry['launch_id'],completion_end=t3,monotonic=t3,reaped=True,returncode=0)])
        events.append(dict(event='authority_end',pid=pid,success=True,monotonic=t2 if fault=='late_completion' else t4))
        with (out/'monitor-events.jsonl').open('a') as stream:
            for event in events: stream.write(json.dumps(event)+'\n')
        return m.ResidentTree({}, {})
    monkeypatch.setattr(m,'process_tree',sampler)
    monkeypatch.setattr(m,'_cleanup_observation',lambda *args,**kw:dict(start=time.monotonic(),end=time.monotonic(),rows=[],helper=None,complete=True,error=None))
    result=m.supervise(vector,out,sampler=sampler,authority_root=tmp_path,outer_seconds=.5,free_disk_bytes=0)
    records=[json.loads(line) for line in (out/'monitor-evidence.jsonl').read_text().splitlines()]
    assert (result['status']=='COMPLETED') is (fault is None),result
    if fault is None:
        joins=[r for r in records if r['kind']=='source_lifecycle' and r['family']=='git']
        assert len(joins)==2 and all(r['measured_peak_bytes'] is None and r['parent_generation'] for r in joins)


def test_poll_sleep_preserves_original_cleanup_reserve(tmp_path,monkeypatch):
    now=[100.]; sleeps=[]; waits=[]
    class Owner:
        pid=570001; returncode=None
        def poll(self): return self.returncode
        def wait(self,timeout):
            waits.append(timeout)
            if timeout<=0: raise m.subprocess.TimeoutExpired('controlled owner',timeout)
            self.returncode=-9; return -9
    owner=Owner()
    monkeypatch.setattr(m.subprocess,'Popen',lambda *args,**kw:owner)
    monkeypatch.setattr(m.os,'killpg',lambda *args:None)
    monkeypatch.setattr(m.time,'monotonic',lambda:now[0])
    def sleep(seconds): sleeps.append(seconds); now[0]+=seconds
    monkeypatch.setattr(m.time,'sleep',sleep)
    def sampler(pid): now[0]=100.071; return {}
    result=m.supervise(['/fixture/python'],tmp_path/'monitor',sampler=sampler,outer_seconds=.08,free_disk_bytes=0)
    assert sleeps and max(sleeps)<=.001000001
    assert waits and waits[0]>0 and result['returncode']==-9
    assert result['outer_seconds']<=.08


def static_control_helpers():
    """Compile only isolated pure guards/commit functions, never native imports/main.

    The legacy AST slices preserve the pre-fix behavior for the RED control;
    after extraction the same tests use the actual named helpers.
    """
    import ast,json,signal,time
    from pathlib import Path
    path=Path(__file__).parents[1]/'docs/research/task18-source-owned-helper-native-control.py'
    tree=ast.parse(path.read_text()); functions={n.name:n for n in tree.body if isinstance(n,ast.FunctionDef)}
    namespace=dict(json=json,time=time,signal=signal,monitor=m,Path=Path,print=lambda *args:None)
    selected=[functions[n] for n in ('validate_owned_kill','reserve_parent_artifacts','commit_result') if n in functions]
    if 'validate_owned_kill' not in functions:
        main=functions['main']; branch=next(n for n in ast.walk(main) if isinstance(n,ast.If) and ast.unparse(n.test)=="case == 'families'")
        body=branch.orelse[1:4]  # owned signal checks and actual end ordering, no socket code
        header=ast.parse('def validate_owned_kill(raw, root):\n pass').body[0]
        header.body=ast.parse("signals=[e for e in raw if e['kind']=='cleanup_signal']").body+body
        selected.append(header)
    if 'commit_result' not in functions:
        body=functions['main'].body
        index=next(i for i,n in enumerate(body) if isinstance(n,ast.Expr) and ast.unparse(n).startswith('result.update(end='))
        header=ast.parse('def commit_result(result, destination, allocation_start, deadline, output_bytes):\n pass').body[0]
        header.body=ast.parse('ALLOCATION_START=allocation_start\nABSOLUTE_DEADLINE=deadline').body+body[index:]
        selected.append(header)
    exec(compile(ast.fix_missing_locations(ast.Module(body=selected,type_ignores=[])),str(path)+'[pure helpers only]','exec'),namespace)
    return namespace


@pytest.mark.parametrize('change',[{}, {'absent':True},{'signal':15},{'pid':99},{'success':False},{'owner_unreaped':False},{'after_end':True}])
def test_static_unknown_control_requires_nonabsent_owned_sigkill(change):
    import signal
    helpers=static_control_helpers()
    event=dict(kind='cleanup_signal',pid=10,signal=signal.SIGKILL,success=True,owner_unreaped=True)
    event.update({k:v for k,v in change.items() if k!='after_end'})
    raw=[event,dict(kind='python_root_end',value=dict(pid=10,reaped=True,returncode=-9))]
    if change.get('after_end'): raw.reverse()
    if change:
        with pytest.raises(AssertionError): helpers['validate_owned_kill'](raw,10)
    else: helpers['validate_owned_kill'](raw,10)


def test_static_parent_final_artifact_cannot_overrun_aggregate(tmp_path):
    import json,time
    helpers=static_control_helpers(); cap=8192
    (tmp_path/'retained.log').write_bytes(b'L'*4096)
    if 'reserve_parent_artifacts' in helpers: helpers['reserve_parent_artifacts'](tmp_path,cap,report_bytes=3072,timing_bytes=1024)
    result=dict(cases=[dict(compatibility='PASS')]*2,payload='x'*10000)
    start=time.monotonic()
    status=helpers['commit_result'](result,tmp_path,start,start+1,cap)
    saved=json.loads((tmp_path/'native-result.json').read_text())
    assert status==1 and saved['compatibility']=='NEEDS_CONTEXT'
    assert m.directory_bytes(tmp_path)<=cap
    assert (tmp_path/'retained.log').read_bytes()==b'L'*4096


def test_static_parent_retains_honest_post_report_boundary(tmp_path,monkeypatch):
    import json
    helpers=static_control_helpers(); clock=[1.]
    monkeypatch.setattr(helpers['time'],'monotonic',lambda:clock[0])
    if 'reserve_parent_artifacts' in helpers: helpers['reserve_parent_artifacts'](tmp_path,8192,report_bytes=6144,timing_bytes=2048)
    original=m._commit_monitor
    def commit(*args): original(*args); clock[0]+=.01
    monkeypatch.setattr(m,'_commit_monitor',commit)
    status=helpers['commit_result'](dict(cases=[dict(compatibility='PASS')]*2),tmp_path,0.,2.,8192)
    saved=json.loads((tmp_path/'native-result.json').read_text())
    receipt=tmp_path/'native-commit-timing.json'
    assert receipt.exists()
    timing=json.loads(receipt.read_text())
    assert status==0 and timing['report_commit_end']>saved['end']
    assert saved['timing_boundary']=='before report commit'
    assert timing['timing_boundary']=='after report commit; before timing receipt commit'
    assert m.directory_bytes(tmp_path)==8192


@pytest.mark.parametrize('extra',['reservation','during_report','deadline'])
def test_static_parent_cap_and_clock_failures_keep_failure_status(tmp_path,monkeypatch,extra):
    import json
    helpers=static_control_helpers(); clock=[1.]; cap=8192
    monkeypatch.setattr(helpers['time'],'monotonic',lambda:clock[0])
    if extra=='reservation':
        (tmp_path/'existing.log').write_bytes(b'x')
        with pytest.raises(ValueError,match='cap'):
            helpers['reserve_parent_artifacts'](tmp_path,cap,report_bytes=6144,timing_bytes=2048)
        assert list(tmp_path.iterdir())==[tmp_path/'existing.log']
        return
    helpers['reserve_parent_artifacts'](tmp_path,cap,report_bytes=6144,timing_bytes=2048)
    sizes=[]; original=m._commit_monitor
    def commit(path,payload,reserve):
        original(path,payload,reserve); sizes.append(m.directory_bytes(tmp_path))
        if len(sizes)==1:
            if extra=='during_report': (tmp_path/'unexpected.log').write_bytes(b'x')
            else: clock[0]=2.1
    monkeypatch.setattr(m,'_commit_monitor',commit)
    assert helpers['commit_result'](dict(cases=[dict(compatibility='PASS')]*2),tmp_path,0.,2.,cap)==1
    assert all(size<=cap+(extra=='during_report') for size in sizes)
    for name in ('native-result.json','native-commit-timing.json'):
        assert json.loads((tmp_path/name).read_text())['compatibility']=='NEEDS_CONTEXT'
    if extra=='during_report': assert (tmp_path/'unexpected.log').read_bytes()==b'x'


def test_static_unknown_signal_must_precede_matching_actual_owner_end():
    import signal
    helpers=static_control_helpers()
    raw=[dict(kind='cleanup_signal',pid=10,signal=signal.SIGKILL,success=True,owner_unreaped=True),
        dict(kind='python_root_end',value=dict(pid=99,reaped=True,returncode=-9))]
    with pytest.raises(AssertionError): helpers['validate_owned_kill'](raw,10)


@pytest.mark.parametrize('waitable_delay',[.0035,None],ids=['reaped','unknown'])
def test_owning_wait_leaves_time_for_actual_evidence_and_failed_source_commit(tmp_path,monkeypatch,waitable_delay):
    """Run stdlib POSIX wait with controlled waitpid, clock and journal cost."""
    import json,threading
    now=[100.]; waitable=[float('inf')]; sleeps=[]; timeouts=[]; trace=[]
    real_popen=m.subprocess.Popen
    owner=real_popen.__new__(real_popen)
    owner.pid=570001; owner.args=['controlled owner']; owner.returncode=None; owner._child_created=False
    owner._waitpid_lock=threading.Lock()
    owner.poll=lambda:owner.returncode
    owner._try_wait=lambda options:(owner.pid,9) if now[0]>=waitable[0] else (0,0)
    actual_wait=owner.wait
    def wait(timeout):
        timeouts.append(timeout); trace.append(dict(operation='wait_start',time=now[0],timeout=timeout))
        value=actual_wait(timeout=timeout)
        trace.append(dict(operation='wait_end',time=now[0],returncode=value))
        return value
    owner.wait=wait
    monkeypatch.setattr(m.subprocess,'Popen',lambda *args,**kw:owner)
    monkeypatch.setattr(m.subprocess,'_time',lambda:now[0])
    monkeypatch.setattr(m.time,'monotonic',lambda:now[0])
    def sleep(seconds): sleeps.append(seconds); now[0]+=seconds
    monkeypatch.setattr(m.time,'sleep',sleep)
    def kill(pid,signum):
        assert pid==owner.pid and signum==9 and owner.returncode is None
        waitable[0]=now[0]+waitable_delay if waitable_delay is not None else float('inf')
        trace.append(dict(operation='signal',time=now[0]))
    monkeypatch.setattr(m.os,'killpg',kill)
    original_json=m._bounded_json
    def encode(value,*args,**kwargs):
        if value.get('kind')=='cleanup_owner_wait': now[0]+=.0011
        if 'outer_seconds' in value: now[0]+=.0002
        return original_json(value,*args,**kwargs)
    monkeypatch.setattr(m,'_bounded_json',encode)
    out=tmp_path/'monitor'
    def sampler(pid):
        now[0]=100.0718
        (out/'monitor-events.jsonl').write_bytes(b'{"event":')
        return {}
    result=m.supervise(['/fixture/python'],out,sampler=sampler,outer_seconds=.08,free_disk_bytes=0)
    raw=[json.loads(line) for line in (out/'monitor-evidence.jsonl').read_text().splitlines()]
    (out/'controlled-timing.json').write_text(json.dumps(dict(trace=trace,sleeps=sleeps,timeouts=timeouts,end=now[0]),indent=2)+'\n')
    assert result['status']=='FAILED' and result['source_event_accounting']['complete'] is False
    expected=-9 if waitable_delay is not None else None
    assert result['returncode']==expected
    waited=[r for r in raw if r['kind']=='cleanup_owner_wait']
    ended=[r for r in raw if r['kind']=='cleanup_owner_end']
    assert len(waited)==len(ended)==1
    assert waited[0]['returncode']==ended[0]['returncode']==expected
    assert waited[0]['reaped'] is ended[0]['reaped'] is (expected is not None)
    assert ended[0]['pid']==owner.pid and ended[0]['origin']=='synthetic_sampler'
    assert not any(r['kind']=='python_root_end' for r in raw)
    assert raw.index(next(r for r in raw if r['kind']=='cleanup_signal'))<raw.index(waited[0])<raw.index(ended[0])
    assert waited[0]['end']<=ended[0]['monotonic']<100.08
    assert now[0]<100.08 and result['outer_seconds']<.08
    if waitable_delay is None:
        assert waited[0]['error']['type']=='TimeoutExpired'
        assert [d['operation'] for d in result['cleanup_diagnostics']]==['wait']
    else: assert not result['cleanup_diagnostics']
