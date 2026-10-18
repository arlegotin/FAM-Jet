"""Owned-root lifecycle controls: controlled OS boundaries, no native/scientific run."""
import copy
import errno
import json
import os
from pathlib import Path
import sys
import time

import pytest
from validation.kernel_stage_a import authority as a, commands as c, monitor as m
from test_kernel_stage_a_native_process import identity


def exercise(tmp_path, monkeypatch, *, display='(Python)', fault=None):
    runtime=identity(); runtime.update(executable=str(Path(sys.executable).resolve()),
        executable_sha256=a.file_hash(Path(sys.executable).resolve()))
    monkeypatch.setattr(a,'runtime',lambda:runtime)
    out=tmp_path/'monitor'; vector=[sys.executable,'-c','pass']; pid=570001
    calls=[]; saved={}; count=0
    class Owner:
        returncode=None
        def poll(self):
            calls.append('poll')
            if fault!='poll_none': self.returncode=7 if fault=='nonzero' else 0
            return self.returncode
        def wait(self,timeout):
            calls.append('wait')
            if self.returncode is None: self.returncode=-9 if 'kill' in calls else 0
            return self.returncode
    owner=Owner(); owner.pid=pid
    monkeypatch.setattr(m.subprocess,'Popen',lambda *args,**kwargs:owner)
    monkeypatch.setattr(m.time,'sleep',lambda seconds:None)
    def killpg(group,signum):
        assert group==pid and owner.returncode is None
        calls.append('kill')
    monkeypatch.setattr(m.os,'killpg',killpg)
    original_launch=m.PythonLifetimes.launch
    def launch(state,entry,context):
        changes={'launch_parent':{'parent':99},'launch_vector':{'argv':['/wrong']},
            'launch_artifact':{'launcher':{'path':'/wrong','sha256':'x'}},
            'launch_image':{'expected_image':{'path':'/wrong','sha256':'x'}}}
        original_launch(state,dict(entry,**changes.get(fault,{})),context)
        if fault=='duplicate_generation': original_launch(state,entry,context)
    monkeypatch.setattr(m.PythonLifetimes,'launch',launch)
    original_proof=m.PythonLifetimes.root_sample
    def proof(state,row,*,owner_unreaped,sample_context=None):
        if fault=='ownership': owner_unreaped=False
        if fault=='forwarded_proof': sample_context=dict(sample_context,origin='emitter_self')
        if fault=='copied_proof_sample': sample_context=dict(sample_context)
        return original_proof(state,row,owner_unreaped=owner_unreaped,sample_context=sample_context)
    monkeypatch.setattr(m.PythonLifetimes,'root_sample',proof)
    original_end=m.PythonLifetimes.end
    def end(state,event):
        calls.append('end'); saved['state']=state
        if fault=='missing_end': return
        return original_end(state,dict(event,launch_id='wrong') if fault=='wrong_end' else event)
    monkeypatch.setattr(m.PythonLifetimes,'end',end)
    original_qualify=m.PythonLifetimes.qualify_owned_root if hasattr(m.PythonLifetimes,'qualify_owned_root') else None
    if original_qualify is not None:
        def qualify(state,context,observation,poll_start,poll_value):
            saved.update(context=context,observation=observation)
            if fault=='copied_current_sample': context=dict(context)
            if fault=='copied_self': state.self_rows[pid]=dict(state.self_rows[pid])
            if fault=='forwarded_current': context['origin']='emitter_self'
            if fault=='member_time': observation['start']=context['entries'][pid]['sample_start']-1
            return original_qualify(state,context,observation,poll_start,poll_value)
        monkeypatch.setattr(m.PythonLifetimes,'qualify_owned_root',qualify)
    original_classify=m.classify
    def classify(root,entries,*args,**kwargs):
        result=original_classify(root,entries,*args,**kwargs)
        if root in entries and entries[root].get('raw_args')==display:
            saved.setdefault('classifications',[]).append(dict(result=result.copy(),context=kwargs.get('sample_context')))
        return result
    monkeypatch.setattr(m,'classify',classify)
    def emit(event):
        with (out/'monitor-events.jsonl').open('a') as stream: stream.write(json.dumps(event)+'\n')
    def row(rss,terminal=False):
        start=time.monotonic(); end=time.monotonic(); lookup=time.monotonic()
        image=dict(status='error',method='macos.proc_pidpath',reason='native_lookup_failed',errno=errno.ESRCH) if terminal else dict(status='ok',**runtime['process_image'])
        image.update(lookup_start=lookup,lookup_end=time.monotonic())
        return dict(pid=pid,parent=os.getpid(),rss_bytes=rss,raw_comm=display if terminal else '/Python',
            raw_args=display if terminal else c.native_display(vector,runtime),sample_start=start,sample_end=end,image=image)
    def sampler(root,**kwargs):
        nonlocal count
        count+=1; calls.append('sample'); assert owner.returncode is None
        if count==1:
            live=row(226721792); saved['live']=live
            if fault=='proof': live['image']['path']='/wrong'
            return m.ResidentTree({pid:live['rss_bytes']},{pid:live})
        if count==2:
            own=row(226721792)
            if fault!='self':
                emit(dict(event='observer_sample',emitter_pid=pid,self_pid=pid,processes=[own],monotonic=time.monotonic()))
            baseline=dict(event='baseline',pid=pid,rss=226721792,monotonic=time.monotonic(),boundary='post-import/pre-allocation')
            if fault=='stale_baseline': baseline['monotonic']=saved['live']['sample_start']-1
            if fault=='baseline_rss': baseline['rss']=1
            if fault!='baseline': emit(baseline)
            if fault=='duplicate_baseline': emit(baseline)
            live=row(500000000 if fault=='earlier_cap' else 232079360)
            return m.ResidentTree({pid:live['rss_bytes']},{pid:live})
        assert count==3
        terminal=row(0,True)
        changes={'parent':{'parent':99},'rss':{'rss_bytes':1},'float_rss':{'rss_bytes':0.0},
                 'ambiguous':{'ambiguous':True},'time':{'sample_start':saved['live']['sample_start']-1}}
        terminal.update(changes.get(fault,{}))
        if fault=='error': terminal['image']['errno']=errno.EPERM
        if fault=='image': terminal['image'].update(status='ok',path='/wrong',sha256='x')
        if fault=='lookup_time': terminal['image']['lookup_start']=terminal['sample_start']-1
        if fault=='provenance': emit(dict(event='unknown'))
        saved['raw']=copy.deepcopy(terminal)
        return m.ResidentTree({pid:terminal['rss_bytes']},{pid:terminal})
    monkeypatch.setattr(m,'process_tree',sampler)
    def observation(root,rt,**kwargs):
        calls.append('membership'); assert owner.returncode is None
        start=time.monotonic()
        rows=[dict(pid=pid,parent=os.getpid(),pgid=pid,rss_bytes=0)]
        if fault=='member_rss': rows[0]['rss_bytes']=1
        if fault=='member_parent': rows[0]['parent']=99
        if fault=='empty': rows=[]
        if fault=='survivor': rows.append(dict(pid=570002,parent=1,pgid=pid,rss_bytes=1024))
        if fault=='duplicate_member': rows.append(dict(rows[0]))
        return dict(start=start,end=time.monotonic(),rows=rows,helper=None,stdout='',stderr='',complete=fault!='membership',error='incomplete' if fault=='membership' else None)
    monkeypatch.setattr(m,'_cleanup_observation',observation)
    result=m.supervise(vector,out,sampler=sampler,outer_seconds=.5,free_disk_bytes=0)
    records=[json.loads(line) for line in (out/'monitor-evidence.jsonl').read_text().splitlines()]
    (out/'control.json').write_text(json.dumps(dict(fault=fault,calls=calls,result=result),indent=2)+'\n')
    return result,records,calls,saved


@pytest.mark.parametrize('display',['(Python)','harmless teardown display'])
def test_root_ownership_replaces_display_spelling_after_actual_completion(tmp_path,monkeypatch,display):
    result,records,calls,saved=exercise(tmp_path,monkeypatch,display=display)
    assert result['status']=='COMPLETED',result
    assert result['incremental_worker_peak_bytes']==5357568
    assert result['workers']['570001']['baseline_bytes']==226721792
    qualified=[r for r in records if r['kind']=='cleanup_terminal_qualification']
    assert len(qualified)==1 and qualified[0]['route']=='source_owned_root_lifecycle'
    assert qualified[0]['membership_empty'] is False
    terminal=next(r for r in records if r['kind']=='sample' and any(p.get('raw_args')==display for p in r['processes']))
    assert terminal['processes'][0]==saved['raw']
    resolved=[r for r in records if r['kind']=='resolution' and r['sample_id']==terminal['sample_id']][-1]
    evidence=resolved['identities']['570001']
    assert resolved['roles']['570001']=='worker'
    assert evidence['image_evidence']=='unavailable_exited'
    assert evidence['terminal_attribution']=='source_owned_root_lifecycle'
    assert calls.index('membership')<calls.index('poll')<calls.index('end') and 'kill' not in calls


@pytest.mark.parametrize('fault',['proof','self','baseline','stale_baseline','baseline_rss','duplicate_baseline',
    'parent','rss','float_rss','ambiguous','time','error','image','lookup_time','provenance',
    'member_rss','member_parent','empty','survivor','duplicate_member','membership',
    'poll_none','nonzero','missing_end','wrong_end','earlier_cap',
    'launch_parent','launch_vector','launch_artifact','launch_image','duplicate_generation',
    'ownership','forwarded_proof','copied_proof_sample','copied_current_sample','copied_self','forwarded_current','member_time'])
def test_incomplete_owned_root_contract_never_qualifies(tmp_path,monkeypatch,fault):
    result,records,calls,saved=exercise(tmp_path,monkeypatch,fault=fault)
    assert result['status']!='COMPLETED',result
    assert not any(r['kind']=='cleanup_terminal_qualification' and r['route']=='source_owned_root_lifecycle' for r in records)
    if '570001' in result['workers'] and not (fault.startswith('launch_') or fault=='duplicate_generation'):
        assert result['workers']['570001']['incremental_peak_bytes']>=226721792
    if fault in ('survivor','membership','poll_none'):
        assert calls.index('membership')<calls.index('kill')<calls.index('wait')
    if fault=='earlier_cap': assert result['reason']=='incremental worker memory cap'


@pytest.mark.parametrize('borrow',['row_copy','sample_copy','coincident_sample','emitter_sample','no_sample',
    'baseline_copy','proof_copy','generation_copy','failed_generation','reader','helper','fake_identity'])
def test_receipt_cannot_be_borrowed_or_fabricated(tmp_path,monkeypatch,borrow):
    result,records,calls,saved=exercise(tmp_path,monkeypatch)
    assert result['status']=='COMPLETED'
    state=saved['state']; context=saved['context']; row=context['entries'][570001]
    if borrow=='row_copy': row=copy.deepcopy(row)
    if borrow=='sample_copy': context=copy.deepcopy(context)
    if borrow=='coincident_sample': context=dict(context)
    if borrow=='emitter_sample': context=dict(context,origin='emitter_self')
    if borrow=='no_sample': context=None
    if borrow=='baseline_copy': state.owned_baseline=dict(state.owned_baseline)
    if borrow=='proof_copy': state.owned_proof=tuple(list(state.owned_proof))
    if borrow=='generation_copy': state.generations[570001]=dict(state.generations[570001])
    if borrow=='failed_generation': state.failed.add(570001)
    if borrow in ('reader','helper'): row=dict(row,pid=570002,parent=570001)
    if borrow=='fake_identity':
        state.owned_receipt=None
        row['identity']=dict(terminal_attribution='source_owned_root_lifecycle',sample_id=context['sample_id'])
    roles=m.classify(570001,{row['pid']:row},{570001:226721792},{},stage_vector=state.stage_vector,
        runtime_identity=state.runtime,python_lifetimes=state,sample_context=context)
    assert roles[row['pid']]=='unaccounted'


def test_pending_completion_has_no_identity_credit_and_is_fully_charged(tmp_path,monkeypatch):
    result,records,calls,saved=exercise(tmp_path,monkeypatch,fault='poll_none')
    pending=[r for r in records if r['kind']=='resolution' and r['roles'].get('570001')=='pending_owned_root_completion']
    assert pending
    assert all(r['identities']['570001']['launch_evidence'] is None for r in pending)
    assert result['workers']['570001']['baseline_bytes']==0
    assert result['incremental_worker_peak_bytes']>=232079360
