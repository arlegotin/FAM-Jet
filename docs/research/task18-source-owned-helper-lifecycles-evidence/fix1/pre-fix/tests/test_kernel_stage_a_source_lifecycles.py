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
