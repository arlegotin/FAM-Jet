"""Review regression controls only; no scientific allocation or native profile."""
from copy import deepcopy
from decimal import Decimal
import json
import os
from pathlib import Path
import sys
import time

import pytest
from validation.kernel_stage_a import reference as r


def test_f1_decisive_tiny_positive_floor_defers_only_unused_sign():
    passes=[]
    for precision in (80,160):
        with r.context(precision):
            window=r.decode([Decimal('1e-100')],[[Decimal('2e-100')]], [Decimal(1)],[3.])
            assert window['code']==5
            assert window['mass']==Decimal('1e-100')
            assert window['prediction']==[Decimal(3)]
            assert window['margins']['floor'] < Decimal('-9e-9')
            passes.append(dict(code=5,prediction=[Decimal(3)],windows=[window],residuals=[]))
    r.validate_pair(*passes)


def test_f1_negative_code_and_genuine_thresholds_remain_required():
    with r.context(80):
        negative=r.decode([Decimal('1e-100')],[[Decimal('2e-100')]], [Decimal(-1)],[3.])
        assert negative['code']==4
        result=dict(code=4,prediction=[Decimal(3)],windows=[negative])
        with pytest.raises(r.ReferenceFailure,match='threshold'): r.validate_pair(result,result)
        changed=deepcopy(result); changed['code']=5; changed['windows'][0]['code']=5
        with pytest.raises(r.ReferenceFailure,match='precision'): r.validate_pair(result,changed)
        for code,margin_name in ((5,'floor'),(6,'cancellation')):
            near=dict(code=code,prediction=[Decimal(3)],windows=[dict(code=code,margins={margin_name:Decimal('-1e-70')})])
            with pytest.raises(r.ReferenceFailure,match='threshold'): r.validate_pair(near,near)


def eligible_record(task='mean'):
    window=dict(code=0,prediction=[2.],mass=1.,bound=0.,raw=[2.],
                reached=dict(coefficients=True,mass=True,bound=True,raw=True,prediction=True))
    count=2 if task=='contrast' else 1
    return dict(code=0,prediction=[0.] if task=='contrast' else [2.],path='decoded',task=task,
                windows=[deepcopy(window) for _ in range(count)],coefficients=[[1.] for _ in range(count)],
                window_vectors=[[.5] for _ in range(count)])


@pytest.mark.parametrize('field', ['coefficients','windows','window_vectors','prediction','mass','raw'])
def test_f4_missing_eligible_evidence_fails_closed(field):
    good=eligible_record(); broken=deepcopy(good)
    if field in ('mass','raw'): broken['windows'][0][field]=None
    elif field=='prediction': broken[field]=None
    else: broken[field]=[]
    assert r.compare(broken,good)['status']=='FAILED'


def test_f4_outer_lengths_truncated_vectors_and_explicit_unreached_paths():
    good=eligible_record('contrast')
    for field in ('coefficients','windows','window_vectors'):
        broken=deepcopy(good); broken[field]=broken[field][:1]
        assert r.compare(broken,good)['status']=='FAILED'
    broken=deepcopy(good); broken['coefficients'][0]=[]
    assert r.compare(broken,good)['status']=='FAILED'
    empty=dict(code=5,prediction=[3.],path='empty',task='contrast',windows=[],coefficients=[],window_vectors=[])
    assert r.compare(empty,deepcopy(empty))['status']=='PASS'
    failed=deepcopy(good); failed.update(code=5,prediction=[3.])
    failed['windows']=[dict(code=5,prediction=None,mass=0.,bound=None,raw=None,
                           reached=dict(coefficients=True,mass=True,bound=False,raw=False,prediction=False))]
    failed['coefficients']=[[1.]]; failed['window_vectors']=[[.5]]
    assert r.compare(failed,deepcopy(failed))['status']=='PASS'
    broken=deepcopy(empty); broken['prediction']=None
    assert r.compare(broken,empty)['status']=='FAILED'


def test_f6_candidate_gram_arithmetic_continues_fixed_candidates_but_reference_stops_all():
    from validation.kernel_stage_a import driver,production,descriptors
    calls=[]
    comparison=dict(status='FAILED',failed_fields=['prediction[0]'],production_gram=[[1.]],reference_gram=[[2.]])
    class Controlled:
        def setup(self,candidate,ledger):
            calls.append(candidate)
            if len(calls)==1: production.gram_gate(candidate,comparison,ledger)
        def slot(self,candidate,slot,ledger):
            ledger.call('read',lambda:None)
            return dict(reader_arithmetic='PASS',source_state_fidelity='PASS',end_to_end_gate='PASS',stop='continue')
    result=driver.execute(Controlled(),checkpoint=lambda:None)
    assert result['status']=='FAILED'
    assert calls==list(descriptors.candidates())
    assert result['counts']['read']==620
    assert result['events'][0]['comparison']==comparison
    assert result['inventory'][128]['status']=='EXECUTED'
    class BrokenReference(Controlled):
        def setup(self,candidate,ledger): raise r.ReferenceFailure('controlled reference engine')
    result=driver.execute(BrokenReference(),checkpoint=lambda:None)
    assert result['status']=='STOPPED' and result['counts'].get('read',0)==0


def test_f2_real_worker_authority_phase_finishes_before_backend_and_refusal_blocks_it(tmp_path,monkeypatch):
    from validation.kernel_stage_a import authority, __main__ as launch
    out=tmp_path/'out'; out.mkdir()
    (out/'stdout.log').touch(); (out/'stderr.log').touch()
    pending=dict(output_directory=str(out),resource_measurement_boundary_seal=dict(deadline_monotonic=time.monotonic()+2))
    seal=dict(pending=pending); order=[]
    def checked(seal,root,**kwargs):
        events=[json.loads(line) for line in (out/'monitor-events.jsonl').read_text().splitlines()]
        assert events[-1]['event']=='authority_start'
        assert kwargs['deadline']==pending['resource_measurement_boundary_seal']['deadline_monotonic']
        assert kwargs['event_path']==out/'monitor-events.jsonl'
        order.extend(['live_HEAD','clean_status','package_runtime_helpers'])
        return pending
    monkeypatch.setattr(authority,'verify',checked)
    def backend(*args):
        events=[json.loads(line) for line in (out/'monitor-events.jsonl').read_text().splitlines()]
        assert events[-1]['event']=='authority_end' and events[-1]['success'] is True
        order.append('backend'); return 7
    assert launch.verified_worker(seal,tmp_path,backend_entry=backend)==7
    assert order==['live_HEAD','clean_status','package_runtime_helpers','backend']
    monkeypatch.setattr(authority,'verify',lambda *args,**kwargs:(_ for _ in ()).throw(authority.AuthorityError('changed HEAD')))
    with pytest.raises(authority.AuthorityError): launch.verified_worker(seal,tmp_path,backend_entry=lambda *args:pytest.fail('backend after refusal'))


def test_f2_exact_git_authority_identity_is_distinct_and_foreign_stops_immediately(tmp_path):
    from validation.kernel_stage_a import authority,monitor as m
    root_pid=100; git_pid=101
    entry=dict(pid=git_pid,parent=root_pid,executable=authority.GIT,
               argv=authority.git_commands(tmp_path)[0])
    stage=[sys.executable,'-c','pass']
    processes={root_pid:dict(pid=root_pid,parent=os.getpid(),executable=sys.executable,argv=stage),git_pid:entry}
    phase=dict(active=True,declarations={git_pid:entry},commands=authority.git_commands(tmp_path))
    assert m.classify(root_pid,processes,{}, {},authority_phase=phase,stage_vector=stage)[git_pid]=='authority_helper'
    assert m.classify(root_pid,processes,{}, {},authority_phase=phase,stage_vector=stage)[root_pid]=='authority_worker'
    assert m.classify(root_pid,processes,{}, {},authority_phase=dict(phase,active=False),stage_vector=stage)[git_pid]=='unaccounted'
    for changed in (dict(parent=99),dict(executable='/tmp/git'),dict(argv=[authority.GIT,'status'])):
        altered=dict(processes); altered[git_pid]=dict(entry,**changed)
        assert m.classify(root_pid,altered,{}, {},authority_phase=phase,stage_vector=stage)[git_pid]=='unaccounted'
    script='import time; time.sleep(10)'
    def foreign(pid):
        bad=dict(pid=pid+999,parent=pid,executable='/tmp/foreign',argv=[])
        return m.ResidentTree({pid:10,pid+999:10},{pid:dict(pid=pid,parent=os.getpid(),executable=sys.executable,argv=[sys.executable,'-c',script]),pid+999:bad})
    result=m.supervise([sys.executable,'-c',script],tmp_path/'foreign',outer_seconds=1,
                        free_disk_bytes=0,sampler=foreign)
    assert result['reason']=='foreign process identity'
    assert result['outer_seconds']<.5


@pytest.mark.parametrize('late',['worker','observer'])
def test_f3_final_reconciliation_charges_all_retained_late_peaks(tmp_path,monkeypatch,late):
    from validation.kernel_stage_a import monitor as m
    out=tmp_path/late; sampled=[]; original_sleep=time.sleep
    helper_start=time.monotonic()
    code='from pathlib import Path; import time\nwhile not Path("finish").exists(): time.sleep(.005)'
    def sample(pid):
        sampled.append(pid)
        identities={pid:dict(pid=pid,parent=os.getpid(),executable=sys.executable,argv=[sys.executable,'-c',code])}
        if late=='worker': return m.ResidentTree({pid:100},identities)
        events=out/'monitor-events.jsonl'
        if not events.stat().st_size:
            with events.open('a') as stream: stream.write(json.dumps(dict(event='baseline',pid=pid,rss=10))+'\n')
        helper=dict(pid=pid+100000,parent=pid,executable=m.PS,argv=m.PS_ARGV)
        identities[helper['pid']]=helper
        return m.ResidentTree({pid:20,helper['pid']:100},identities)
    finished=[False]
    def finish_after_last_sample(seconds):
        if seconds==.02 and sampled and not finished[0]:
            pid=sampled[-1]
            entry=(dict(event='baseline',pid=pid,rss=10) if late=='worker' else
                   dict(event='observer_helper',pid=pid+100000,parent=pid,executable=m.PS,
                        argv=m.PS_ARGV,launch_id='late-final-observer-1',
                        launch_start=helper_start,reaped=False))
            with (out/'monitor-events.jsonl').open('a') as stream:
                stream.write(json.dumps(entry)+'\n')
                if late=='observer':
                    stream.write(json.dumps(dict(event='observer_helper_end',pid=pid+100000,
                        parent=pid,launch_id='late-final-observer-1',completion_end=time.monotonic(),
                        reaped=True,returncode=0))+'\n')
            (out/'finish').touch(); finished[0]=True; original_sleep(.08)
        else: original_sleep(seconds)
    monkeypatch.setattr(m.time,'sleep',finish_after_last_sample)
    result=m.supervise([sys.executable,'-c',code],out,outer_seconds=1,free_disk_bytes=0,
                       incremental_bytes=50,sampler=sample)
    assert result['reason']=='incremental worker memory cap'
    assert result['incremental_worker_peak_bytes']==(90 if late=='worker' else 110)
    assert json.loads((out/'monitor.json').read_text())==result


def test_f3_final_report_overflow_has_one_durable_returned_verdict(tmp_path):
    from validation.kernel_stage_a import monitor as m
    out=tmp_path/'overflow'; command=[sys.executable,'-c','import time; time.sleep(.04)']
    def sample(pid):
        (out/'monitor-events.jsonl').write_text(json.dumps(dict(event='baseline',pid=pid,rss=1))+'\n')
        identities={pid:dict(pid=pid,parent=os.getpid(),executable=sys.executable,argv=command)}
        declarations={pid+i:dict(pid=pid+i,parent=os.getpid(),executable=m.PS,argv=m.PS_ARGV) for i in range(100000,100064)}
        return m.ResidentTree({pid:1,**{p:1 for p in declarations}},dict(identities,**{} )|declarations,declarations)
    result=m.supervise(command,out,outer_seconds=1,
                       output_bytes=8192,free_disk_bytes=0,sampler=sample)
    assert result['status']=='STOPPED' and result['reason']=='output cap'
    assert m.directory_bytes(out)<=8192
    assert json.loads((out/'monitor.json').read_text())==result


def test_f5_hung_observer_is_bounded_reaped_and_stops_owned_worker(tmp_path,monkeypatch):
    from validation.kernel_stage_a import monitor as m
    real_popen=m.subprocess.Popen; processes=[]
    def capture(*args,**kwargs):
        process=real_popen(*args,**kwargs); processes.append(process); return process
    monkeypatch.setattr(m.subprocess,'Popen',capture)
    monkeypatch.setattr(m,'PS_ARGV',[sys.executable,'-c','import time; time.sleep(10)'])
    # This controlled sleeper substitutes both the observer vector and its artifact.
    runtime=m.authority.runtime(); runtime['helpers']['ps']=m.authority.helper_artifact(sys.executable)
    monkeypatch.setattr(m.authority,'runtime',lambda:runtime)
    started=time.monotonic()
    result=m.supervise([sys.executable,'-c','import time; time.sleep(10)'],tmp_path/'hung',
                       outer_seconds=.15,free_disk_bytes=0)
    assert result['status']=='STOPPED' and result['reason']=='observer timeout'
    assert time.monotonic()-started<.7
    assert len(processes)==2 and all(p.poll() is not None for p in processes)
    assert processes[0].returncode!=0 and processes[1].returncode!=0
    assert json.loads((tmp_path/'hung/monitor.json').read_text())==result


def test_f5_baseline_observation_receives_original_remaining_deadline(tmp_path,monkeypatch):
    from validation.kernel_stage_a import monitor as m
    deadline=time.monotonic()+.1; observed=[]
    def sample(pid,**kwargs): observed.append(kwargs); return {pid:10}
    monkeypatch.setattr(m,'process_tree',sample)
    m.record_baseline(tmp_path/'events',deadline=deadline)
    assert observed[0]['deadline']==deadline


def test_f2_real_full_authority_launch_is_accounted_and_gates_a_nonnumerical_backend(tmp_path,monkeypatch):
    from validation.kernel_stage_a import authority as a,monitor as m
    fake=tmp_path/'readonly-git'
    fake.write_text('#!'+sys.executable+'\nimport sys,time\ntime.sleep(.04)\nprint("controlled-head" if sys.argv[-2:]==["rev-parse","HEAD"] else "",end="")\n')
    fake.chmod(0o755); monkeypatch.setattr(a,'GIT',str(fake.resolve()))
    root=Path.cwd(); observed=a.observe(root); start=time.monotonic()
    record=tmp_path/'record.json'; record.write_text('{}')
    ref=dict(path=str(record),sha256=a.file_hash(record)); setupdir=tmp_path/'setup-output'; setupdir.mkdir()
    setup=tmp_path/'setup.json'; out=tmp_path/'launch'
    statics={f'{family}:{rho.hex()}':ref for family,rho in __import__('validation.kernel_stage_a.descriptors',fromlist=['candidates']).candidates()}
    rates={family:ref for family in ('jet','bank')}
    setup.write_text(json.dumps(dict(actual_factor_constructions=6,actual_reads=0,allocation_start_monotonic=start,
          package_hash=a.PACKAGE,source_full_git=observed['source_full_git'],static_exports=statics,represented_rate_records=rates,
          output_directory=str(setupdir),output_peak_bytes=0,incremental_worker_peak_bytes=0)))
    pending=dict(implementation_review=dict(ref,approved=True),represented_rate_records=rates,static_exports=statics,
        resource_measurement_boundary_seal=dict(baseline='post-import/pre-allocation per worker',absolute_rss=True,process_tree_rss=True,
            sequential_workers=True,outputs_include_temporaries=True,allocation_start_monotonic=start,deadline_monotonic=start+a.LIMITS['outer_seconds'],
            allocation_start_utc_epoch=time.time(),setup_ledger=dict(path=str(setup),sha256=a.file_hash(setup))),
        fresh_launch_snapshot=dict(utc_epoch=time.time(),free_disk_bytes=2**40,power_observation='synthetic control',host_identity=observed['host_identity']),
        output_directory=str(out))
    seal=dict(version=1,scope='Task18 kernel Stage A only',observed=observed,pending=pending,limits=a.LIMITS)
    seal['root_stage_A_release']=dict(approved=True,scope='Stage A scientific execution',payload_sha256=a.digest(seal),
                                      ruling_path=str(record),ruling_sha256=a.file_hash(record))
    seal_path=tmp_path/'synthetic-seal.json'; seal_path.write_text(json.dumps(seal))
    code='''
import json,os,sys,time
from pathlib import Path
sys.path.insert(0,sys.argv[3])
from validation.kernel_stage_a import authority as a
from validation.kernel_stage_a.__main__ import verified_worker
a.GIT=sys.argv[1]
seal=json.loads(Path(sys.argv[2]).read_text())
def proof(seal,root,pending):
 out=Path(pending['output_directory'])
 a.event(out/'monitor-events.jsonl','baseline',pid=os.getpid(),rss=10)
 (out/'backend-proof.json').write_text(json.dumps({'verified_package':seal['observed']['package_hash']}))
 time.sleep(.05)
 return 0
raise SystemExit(verified_worker(seal,Path(sys.argv[3]),backend_entry=proof))
'''
    command=[sys.executable,'-c',code,str(fake),str(seal_path),str(root)]
    def sample(pid):
        entries={pid:dict(pid=pid,parent=os.getpid(),executable=sys.executable,argv=command)}
        readings={pid:100}; path=out/'monitor-events.jsonl'
        if path.exists():
            events=[json.loads(line) for line in path.read_text().splitlines()]
            completed={event['pid'] for event in events if event['event']=='authority_helper_end'}
            for event in events:
                if event['event']=='authority_helper' and event['pid'] not in completed:
                    entries[event['pid']]={k:event[k] for k in ('pid','parent','executable','argv')}; readings[event['pid']]=20
        return m.ResidentTree(readings,entries)
    for key in ('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS','VECLIB_MAXIMUM_THREADS','NUMEXPR_NUM_THREADS'): monkeypatch.setenv(key,'1')
    result=m.supervise(command,out,outer_seconds=2,
                       free_disk_bytes=0,sampler=sample,authority_root=root)
    assert result['status']=='COMPLETED',result
    assert result['authority_phase']['success'] is True
    assert len(result['authority_phase']['completed'])==2
    assert result['authority_full_rss_peak_bytes']>=100
    assert json.loads((out/'backend-proof.json').read_text())=={'verified_package':a.PACKAGE}


def test_f5_exact_authority_git_wait_is_bounded_and_reaped(tmp_path,monkeypatch):
    from validation.kernel_stage_a import authority as a
    fake=tmp_path/'hung-readonly-git'
    fake.write_text('#!'+sys.executable+'\nimport time\ntime.sleep(10)\n'); fake.chmod(0o755)
    monkeypatch.setattr(a,'GIT',str(fake.resolve()))
    real_popen=a.subprocess.Popen; processes=[]
    def capture(*args,**kwargs):
        process=real_popen(*args,**kwargs); processes.append(process); return process
    monkeypatch.setattr(a.subprocess,'Popen',capture)
    started=time.monotonic(); events=tmp_path/'events.jsonl'
    with pytest.raises(a.subprocess.TimeoutExpired):
        a.git(tmp_path,'rev-parse','HEAD',deadline=started+.1,event_path=events)
    assert time.monotonic()-started<.7
    assert len(processes)==1 and processes[0].poll() is not None and processes[0].returncode!=0
    records=[json.loads(line) for line in events.read_text().splitlines()]
    assert records[0]['argv']==a.git_commands(tmp_path)[0]
    assert records[-1]['event']=='authority_helper_end' and records[-1]['returncode']!=0
    with pytest.raises(a.AuthorityError,match='undeclared'): a.git(tmp_path,'log')


def test_f2_same_interpreter_wrong_argv_is_foreign_and_exact_commands_can_await_baseline(tmp_path):
    from validation.kernel_stage_a import monitor as m
    root_pid=100
    wrong={root_pid:dict(pid=root_pid,parent=os.getpid(),executable=sys.executable,argv=[sys.executable,'-c','foreign'])}
    assert m.classify(root_pid,wrong,{root_pid:10},{})[root_pid]=='unaccounted'
    from validation.kernel_stage_a import commands as c
    stage=c.stage_command(tmp_path,tmp_path/'seal.json')
    reader=c.reader_command(tmp_path,tmp_path/'events.jsonl',100.)
    context=dict(root=tmp_path,event_path=tmp_path/'events.jsonl',deadline=100.)
    expected={root_pid:dict(wrong[root_pid],argv=stage),101:dict(pid=101,parent=root_pid,executable=sys.executable,argv=reader)}
    roles=m.classify(root_pid,expected,{}, {},stage_vector=stage,reader_context=context)
    assert roles=={100:'pending_baseline',101:'pending_baseline'}
    for bad in (reader+['extra'],reader[:-1]+['101.0'],reader[:-1]+['nan'],reader[:-2]+['wrong-events','100.0']):
        altered=dict(expected); altered[101]=dict(expected[101],argv=bad)
        assert m.classify(root_pid,altered,{100:10,101:10},{},stage_vector=stage,reader_context=context)[101]=='unaccounted'
    assert c.reader_from_display(c.display(reader),**context)==reader
    assert c.reader_from_display(c.display(reader)+' extra',**context) is None
    command=[sys.executable,'-c','import time; time.sleep(10)']
    def foreign(pid):
        return m.ResidentTree({pid:10},{pid:dict(pid=pid,parent=os.getpid(),executable=sys.executable,argv=wrong[root_pid]['argv'])})
    result=m.supervise(command,tmp_path/'wrong-python',outer_seconds=1,free_disk_bytes=0,sampler=foreign)
    assert result['reason']=='foreign process identity' and result['outer_seconds']<.5
