"""Native identity controls: synthetic samples only, no scientific allocation."""
import copy
import ctypes
import errno
import os
from pathlib import Path
import sys

import pytest
from validation.kernel_stage_a import authority as a, commands as c, monitor as m


def identity():
    return dict(executable='/launcher/python', executable_sha256='a'*64,
                process_image=dict(path='/long/framework/Python.app/Contents/MacOS/Python',sha256='b'*64,method='macos.proc_pidpath'),
                helpers=dict(ps=dict(path=m.PS,sha256='c'*64),git=dict(path=a.GIT,sha256='d'*64)))


def sample(pid,parent,vector,*,image=None,start=12.,end=13.):
    runtime=identity()
    return dict(pid=pid,parent=parent,rss_bytes=70,sample_start=start,sample_end=end,
                raw_comm='/opt/homebrew/C',raw_args=c.display([runtime['process_image']['path'],*vector[1:]]),
                image=image or dict(status='ok',method='macos.proc_pidpath',**{k:runtime['process_image'][k] for k in ('path','sha256')}))


def witness(pid,parent,vector,helper='ps'):
    return dict(pid=pid,parent=parent,executable=vector[0],argv=vector,
                provenance='source_owned_launch',launch_id='source-1',vector_sha256=c.vector_hash(vector),
                artifact=identity()['helpers'][helper],launch_start=11.,completion_end=14.,reaped=True)


def test_native_display_uses_observed_image_without_changing_launch_vector(tmp_path):
    assert hasattr(c,'native_display')
    vector=c.stage_command(tmp_path,tmp_path/'seal with spaces')
    original=vector.copy(); runtime=identity()
    assert c.native_display(vector,runtime)==c.display([runtime['process_image']['path'],*vector[1:]])
    assert vector==original and vector[0]==sys.executable
    context=dict(root=tmp_path,event_path=tmp_path/'events',deadline=90.)
    reader=c.reader_command(tmp_path,context['event_path'],80.)
    assert c.reader_from_display(c.native_display(reader,runtime),**context,runtime_identity=runtime)==reader
    for tail in ('nan','inf','80','90.1','80.0 extra'):
        bad=c.native_display(reader[:-1]+[tail],runtime)
        assert c.reader_from_display(bad,**context,runtime_identity=runtime) is None


def test_libproc_signature_long_path_and_structured_errors(monkeypatch):
    assert hasattr(a,'process_image')
    long_path='/'+('a'*200)+'/Python'
    class Function:
        def __call__(self,pid,buffer,size):
            assert size==4096
            buffer.value=long_path.encode()
            return len(long_path)
    class Library: proc_pidpath=Function()
    monkeypatch.setattr(a.ctypes,'CDLL',lambda path,**kw: Library())
    monkeypatch.setattr(a,'file_hash',lambda path:'e'*64)
    found=a.process_image(20)
    assert {k:v for k,v in found.items() if not k.startswith('lookup_')}==dict(status='ok',method='macos.proc_pidpath',path=long_path,sha256='e'*64)
    assert found['lookup_start']<=found['lookup_end']
    assert Library.proc_pidpath.argtypes==[ctypes.c_int,ctypes.c_void_p,ctypes.c_uint32]
    assert Library.proc_pidpath.restype is ctypes.c_int
    def gone(*args): ctypes.set_errno(errno.ESRCH); return 0
    Library.proc_pidpath=staticmethod(gone)
    failed=a.process_image(20)
    assert failed['status']=='error' and failed['errno']==errno.ESRCH and failed['reason']=='native_lookup_failed'
    def malformed(pid,buffer,size): buffer.raw=b'x'*size; return size
    Library.proc_pidpath=staticmethod(malformed)
    assert a.process_image(20)['reason']=='invalid_native_path'
    monkeypatch.setattr(a.ctypes,'CDLL',lambda *args,**kw: (_ for _ in ()).throw(OSError('unavailable')))
    assert a.process_image(20)['reason']=='native_binding_failed'


def test_runtime_binds_launcher_and_own_image_separately_without_transients(monkeypatch):
    assert hasattr(a,'process_image')
    monkeypatch.setattr(a,'process_image',lambda pid:dict(status='ok',method='macos.proc_pidpath',path='/actual/image',sha256='f'*64))
    observed=a.runtime()
    assert observed['executable']==str(Path(sys.executable).resolve())
    assert observed['process_image']==dict(path='/actual/image',sha256='f'*64,method='macos.proc_pidpath')
    assert observed['helpers']['ps']['path']==m.PS
    assert not {'pid','monotonic','timestamp'} & observed.keys()
    monkeypatch.setattr(a,'process_image',lambda pid:dict(status='error',errno=errno.EPERM))
    with pytest.raises(a.AuthorityError,match='image'): a.runtime()


def test_native_python_requires_image_parent_and_exact_raw_display(tmp_path):
    runtime=identity(); stage=c.stage_command(tmp_path,tmp_path/'seal')
    entry=sample(10,os.getpid(),stage)
    def role(value):
        return m.classify(10,{10:value},{10:1},{},stage_vector=stage,runtime_identity=runtime)[10]
    assert role(entry)=='worker'
    assert entry['identity']['image_evidence']=='kernel_image'
    for change in (dict(parent=99999),dict(raw_args=entry['raw_args']+' extra'),
                   dict(image=dict(status='error',errno=errno.ESRCH)),
                   dict(image=dict(status='ok',path='/wrong',sha256='b'*64)),
                   dict(image=dict(status='ok',path=runtime['process_image']['path'],sha256='0'*64))):
        assert role(dict(entry,**change))=='unaccounted'


def test_exited_observer_witness_keeps_kernel_absence_and_rejects_conflicts():
    runtime=identity(); declared=witness(30,os.getpid(),m.PS_ARGV)
    entry=sample(30,os.getpid(),m.PS_ARGV,image=dict(status='error',errno=errno.ESRCH))
    entry['raw_args']=c.display(m.PS_ARGV)
    def role(value,decl=declared):
        return m.classify(10,{30:value},{},{30:decl},runtime_identity=runtime)[30]
    assert role(entry)=='observer_helper'
    assert entry['identity']['image_evidence']=='unavailable_exited'
    assert entry['identity']['launch_evidence']=='source_owned_launch'
    for change in (dict(image=dict(status='error',errno=errno.EPERM)),
                   dict(image=dict(status='ok',path='/wrong',sha256='c'*64)),dict(sample_start=15.,sample_end=16.)):
        assert role(dict(entry,**change))=='unaccounted'
    for change in (dict(artifact=dict(path=m.PS,sha256='0'*64)),dict(parent=9999),dict(reaped=False),dict(ambiguous=True)):
        assert role(copy.deepcopy(entry),dict(declared,**change))=='unaccounted'


def test_git_witness_requires_sampled_authority_phase_and_exact_generation(tmp_path):
    runtime=identity(); vector=a.git_commands(tmp_path)[0]
    declared=witness(30,10,vector,'git')
    entry=sample(30,10,vector,image=dict(status='error',errno=errno.ESRCH)); entry['raw_args']=c.display(vector)
    phase=dict(active=True,started=True,start=10.,end=14.,declarations={30:declared},completed={30},commands=a.git_commands(tmp_path))
    assert m.classify(10,{30:entry},{},{},authority_phase=phase,runtime_identity=runtime)[30]=='authority_helper'
    phase['end']=11.
    assert m.classify(10,{30:entry},{},{},authority_phase=phase,runtime_identity=runtime)[30]=='unaccounted'
    phase.update(end=14.,active=False)
    later=dict(entry,sample_start=15.,sample_end=16.,image=dict(status='ok',**runtime['helpers']['git']))
    assert m.classify(10,{30:later},{},{},authority_phase=phase,runtime_identity=runtime)[30]=='unaccounted'


@pytest.mark.parametrize('duplicate',[False,True])
def test_numeric_rss_retained_before_malformed_identity_lookup(monkeypatch,duplicate):
    assert hasattr(a,'process_image')
    class Probe:
        pid=30; returncode=0; stdout=None
        def communicate(self,**kw): return ('10 1 12 /truncated exact stage\n20 10 7\n'+('20 999 9 different args\n' if duplicate else '')+'999 1 3 irrelevant irrelevant\n30 1 4 /bin/ps '+c.display(m.PS_ARGV)+'\n',None)
        def poll(self): return 0
    monkeypatch.setattr(m.subprocess,'Popen',lambda *args,**kw:Probe())
    monkeypatch.setattr(a,'runtime',identity)
    monkeypatch.setattr(a,'helper_artifact',lambda path:identity()['helpers']['ps'])
    looked=[]
    def lookup(pid): looked.append(pid); return dict(status='error',errno=errno.ESRCH)
    monkeypatch.setattr(a,'process_image',lookup)
    tree=m.process_tree(10)
    assert dict(tree)=={10:12*1024,20:(9 if duplicate else 7)*1024,30:4*1024}
    assert tree.processes[20]['ambiguous'] is duplicate
    assert set(looked)=={10,20,30} and 999 not in looked
    assert tree.processes[20]['raw_args']==('args' if duplicate else None)
    assert 'argv' not in tree.processes[10] and tree.processes[10]['raw_comm']=='/truncated'
    assert tree.declarations[30]['reaped'] is True


def test_native_unresolved_python_failure_preserves_full_rss(tmp_path,monkeypatch):
    runtime=identity(); stage=[sys.executable,'-c','import time; time.sleep(10)']
    monkeypatch.setattr(a,'runtime',lambda:runtime)
    def sampler(pid):
        entry=sample(pid,os.getpid(),stage,image=dict(status='error',errno=errno.ESRCH))
        return m.ResidentTree({pid:70},{pid:entry})
    result=m.supervise(stage,tmp_path/'unresolved',sampler=sampler,outer_seconds=.3,free_disk_bytes=0)
    assert result['reason']=='foreign process identity'
    item=next(iter(result['workers'].values()))
    assert item['absolute_peak_bytes']==70 and item['baseline_bytes']==0 and item['incremental_peak_bytes']==70
    assert result['incremental_worker_peak_bytes']>=70 and result['process_samples'][0]['image']['errno']==errno.ESRCH


@pytest.mark.parametrize('reuse',[False,True])
def test_late_native_witness_reconciles_history_without_authorizing_reuse(tmp_path,monkeypatch,reuse):
    import json
    import time
    out=tmp_path/'late'; stage=[sys.executable,'-c','from pathlib import Path; import time\nwhile not Path("finish").exists(): time.sleep(.005)']
    monkeypatch.setattr(a,'runtime',identity)
    captured=[]; real_sleep=time.sleep
    def sampler(pid):
        now=time.monotonic()
        helper=pid+100000
        root=sample(pid,os.getpid(),stage,start=now,end=now+.001)
        observer=sample(helper,os.getpid(),m.PS_ARGV,image=dict(status='error',errno=errno.ESRCH),start=now,end=now+.001)
        observer['raw_args']=c.display(m.PS_ARGV)
        declared=witness(helper,os.getpid(),m.PS_ARGV)
        declared.update(launch_start=now-.01,completion_end=now+.002)
        captured.append(declared)
        a.event(out/'monitor-events.jsonl','baseline',pid=pid,rss=10)
        return m.ResidentTree({pid:20,helper:100},{pid:root,helper:observer})
    def finish(seconds):
        if seconds==.02 and captured:
            declared=captured[0]
            a.event(out/'monitor-events.jsonl','observer_helper',**declared)
            if reuse: a.event(out/'monitor-events.jsonl','observer_helper',**dict(declared,launch_id='later-generation'))
            (out/'finish').touch(); real_sleep(.08)
        else: real_sleep(seconds)
    monkeypatch.setattr(m.time,'sleep',finish)
    result=m.supervise(stage,out,outer_seconds=.5,free_disk_bytes=0,sampler=sampler)
    helper=str(captured[0]['pid'])
    assert result['workers'][helper]['absolute_peak_bytes']==100
    assert result['workers'][helper]['baseline_bytes']==0
    assert result['incremental_worker_peak_bytes']>=110
    if reuse:
        assert result['status']=='STOPPED' and helper in result['missing_worker_baselines']
        assert result['workers'][helper]['role']=='unaccounted'
        assert len({row['launch_id'] for row in result['source_launch_witnesses']})==2
    else:
        assert result['status']=='COMPLETED',result
        observed=next(row for row in result['process_samples'] if row['pid']==int(helper))
        assert observed['identity']['image_evidence']=='unavailable_exited'


def test_event_failure_after_native_sampling_still_charges_all_rss(tmp_path,monkeypatch):
    runtime=identity(); monkeypatch.setattr(a,'runtime',lambda:runtime)
    out=tmp_path/'bad-event'; command=[sys.executable,'-c','import time; time.sleep(10)']
    def sampler(pid):
        (out/'monitor-events.jsonl').write_text('{"event":"unknown"}\n')
        return m.ResidentTree({pid:70},{pid:sample(pid,os.getpid(),command)})
    result=m.supervise(command,out,outer_seconds=.3,free_disk_bytes=0,sampler=sampler)
    assert result['reason']=='monitor common failure'
    assert result['absolute_process_tree_peak_bytes']==70
    assert result['incremental_worker_peak_bytes']>=70
    assert next(iter(result['workers'].values()))['baseline_bytes']==0


def test_native_call_exception_is_structured(monkeypatch):
    class Call:
        def __call__(self,*args): raise OSError('call denied')
    class Library: proc_pidpath=Call()
    monkeypatch.setattr(a.ctypes,'CDLL',lambda *args,**kwargs:Library())
    assert a.process_image(20)['reason']=='native_call_failed'


def test_inner_baseline_sample_retains_observer_missed_by_outer_sampler(tmp_path,monkeypatch):
    import time
    monkeypatch.setattr(a,'runtime',identity)
    out=tmp_path/'inner'; command=[sys.executable,'-c','import time; time.sleep(10)']; helper=[]
    def sampler(pid):
        now=time.monotonic(); observer=pid+100000; helper.append(observer)
        root=sample(pid,os.getpid(),command,start=now,end=now+.001)
        entry=sample(observer,os.getpid(),m.PS_ARGV,image=dict(status='error',errno=errno.ESRCH),start=now,end=now+.001)
        entry['raw_args']=c.display(m.PS_ARGV)
        declared=witness(observer,os.getpid(),m.PS_ARGV); declared.update(launch_start=now-.01,completion_end=now+.002)
        a.event(out/'monitor-events.jsonl','observer_helper',**declared)
        a.event(out/'monitor-events.jsonl','observer_sample',processes=[root,entry])
        a.event(out/'monitor-events.jsonl','baseline',pid=pid,rss=10)
        return m.ResidentTree({pid:20},{pid:root})
    result=m.supervise(command,out,sampler=sampler,outer_seconds=.3,free_disk_bytes=0,incremental_bytes=50)
    assert result['reason']=='incremental worker memory cap'
    assert result['workers'][str(helper[0])]['incremental_peak_bytes']==70
    assert result['observer_helper_peak_bytes']==70


def test_successful_helper_lookup_after_reap_is_ambiguous_generation():
    runtime=identity(); declared=witness(30,os.getpid(),m.PS_ARGV)
    entry=sample(30,os.getpid(),m.PS_ARGV,image=dict(status='ok',**runtime['helpers']['ps'],lookup_start=15.,lookup_end=16.))
    entry['raw_args']=c.display(m.PS_ARGV)
    assert m.classify(10,{30:entry},{},{30:declared},runtime_identity=runtime)[30]=='unaccounted'


def test_python_success_and_later_missing_image_are_distinct_retained_samples(tmp_path,monkeypatch):
    import time
    monkeypatch.setattr(a,'runtime',identity); out=tmp_path/'history'
    command=[sys.executable,'-c','import time; time.sleep(10)']; polls=[]
    def sampler(pid):
        now=time.monotonic(); polls.append(pid)
        image=None if len(polls)==1 else dict(status='error',errno=errno.ESRCH)
        entry=sample(pid,os.getpid(),command,image=image,start=now,end=now+.001)
        a.event(out/'monitor-events.jsonl','baseline',pid=pid,rss=10)
        return m.ResidentTree({pid:70},{pid:entry})
    result=m.supervise(command,out,sampler=sampler,outer_seconds=.3,free_disk_bytes=0)
    assert result['reason']=='foreign process identity'
    assert [row['identity']['image_evidence'] for row in result['process_samples']]==['kernel_image','unresolved']
    assert result['incremental_worker_peak_bytes']>=70


def test_native_live_authority_charge_counts_worker_once_before_helper_end(tmp_path,monkeypatch):
    import time
    monkeypatch.setattr(a,'runtime',identity); out=tmp_path/'live-native'
    command=[sys.executable,'-c','import time; time.sleep(10)']
    def sampler(pid):
        a.event(out/'monitor-events.jsonl','authority_start',pid=pid)
        now=time.monotonic(); helper=pid+100000; vector=a.git_commands(tmp_path)[0]
        declared=witness(helper,pid,vector,'git'); declared.update(launch_start=now,reaped=False); declared.pop('completion_end')
        a.event(out/'monitor-events.jsonl','authority_helper',**declared)
        root=sample(pid,os.getpid(),command,start=now,end=now+.001); root['rss_bytes']=60
        entry=sample(helper,pid,vector,image=dict(status='ok',**identity()['helpers']['git']),start=now,end=now+.001)
        entry['raw_args']=c.display(vector)
        return m.ResidentTree({pid:60,helper:70},{pid:root,helper:entry})
    result=m.supervise(command,out,sampler=sampler,outer_seconds=.3,free_disk_bytes=0,incremental_bytes=100,authority_root=tmp_path)
    assert result['reason']=='incremental worker memory cap'
    assert result['authority_full_rss_peak_bytes']==130
    assert result['incremental_worker_peak_bytes']==130


def test_native_final_missing_baseline_is_charged_in_full(tmp_path,monkeypatch):
    import time
    monkeypatch.setattr(a,'runtime',identity)
    command=[sys.executable,'-c','import time; time.sleep(10)']
    def sampler(pid):
        now=time.monotonic()
        return m.ResidentTree({pid:70},{pid:sample(pid,os.getpid(),command,start=now,end=now+.001)})
    result=m.supervise(command,tmp_path/'missing-baseline',sampler=sampler,outer_seconds=.04,free_disk_bytes=0)
    assert result['status']=='STOPPED'
    assert result['incremental_worker_peak_bytes']>=70
    assert next(iter(result['workers'].values()))['baseline_bytes']==0


def test_git_launch_witness_write_failure_still_reaps_owned_child(tmp_path,monkeypatch):
    fake=tmp_path/'readonly-git'; fake.write_text('#!'+sys.executable+'\nimport time\ntime.sleep(10)\n'); fake.chmod(0o755)
    monkeypatch.setattr(a,'GIT',str(fake.resolve())); real_popen=a.subprocess.Popen; processes=[]
    def capture(*args,**kwargs):
        process=real_popen(*args,**kwargs); processes.append(process); return process
    monkeypatch.setattr(a.subprocess,'Popen',capture)
    monkeypatch.setattr(a,'event',lambda *args,**kwargs:(_ for _ in ()).throw(OSError('witness write failed')))
    try:
        with pytest.raises(OSError,match='witness'): a.git(tmp_path,'rev-parse','HEAD')
        assert processes[0].poll() is not None
    finally:
        for process in processes:
            if process.poll() is None: process.kill(); process.wait(timeout=1)
