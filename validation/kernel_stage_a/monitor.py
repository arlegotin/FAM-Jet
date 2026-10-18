"""Whole-process-group timeout, RSS and output cap. No scientific imports."""
import errno
import json
import os
from pathlib import Path
import selectors
import shutil
import signal
import subprocess
import sys
import time
from . import authority,commands

PS='/bin/ps'
PS_ARGV=[PS,'-axo','pid=,ppid=,rss=,comm=,args=']


class ObserverFailure(RuntimeError):
    def __init__(self,reason,*,pid=None,reaped=True,seconds=0.):
        self.evidence=dict(reason=reason,pid=pid,reaped=reaped,seconds=seconds)
        super().__init__(reason)


class ResidentTree(dict):
    def __init__(self,readings,processes,declarations=None):
        super().__init__(readings); self.processes=processes; self.declarations=declarations or {}


def _synthetic_classify(root_pid,processes,baselines,declarations,*,authority_phase=None,current_pids=None,stage_vector=None,reader_context=None):
    phase=authority_phase or dict(active=False,declarations={},completed=set(),commands=[])
    expected={pid for pid,entry in processes.items() if
             Path(entry['executable']).resolve()==Path(sys.executable).resolve() and
             entry['parent']==(os.getpid() if pid==root_pid else root_pid) and
             (commands.matches(entry['argv'],stage_vector) if pid==root_pid else commands.reader_vector(entry['argv'],reader_context) is not None)}
    def same_declaration(left,right):
        keys=('pid','parent','executable','argv')
        return left is not None and all(left.get(k)==right.get(k) for k in keys)
    roles={}
    for pid,entry in processes.items():
        if pid in expected:
            roles[pid]=('authority_worker' if pid==root_pid and phase['active'] else
                        ('worker' if pid in baselines else 'pending_baseline'))
            continue
        git_entry=phase['declarations'].get(pid)
        exact_git=(entry['parent']==root_pid and entry['executable']==authority.GIT and entry['argv'] in phase['commands'])
        if exact_git and phase['active']:
            roles[pid]='authority_helper' if same_declaration(git_entry,entry) else 'pending_authority_declaration'; continue
        if exact_git and same_declaration(git_entry,entry) and pid in phase.get('completed',set()) and current_pids is not None and pid not in current_pids:
            roles[pid]='authority_helper'; continue
        declared=declarations.get(pid)
        exact_observer=(entry['executable']==PS and entry['argv']==PS_ARGV and
                        (entry['parent']==os.getpid() or entry['parent'] in expected))
        roles[pid]=('observer_helper' if same_declaration(declared,entry) else 'pending_observer_declaration') if exact_observer else 'unaccounted'
    return roles


class PythonLifetimes:
    """Narrow source-owned Python generations; retained state is charged by the journal."""
    def __init__(self,root_pid,stage_vector,runtime_identity):
        self.root_pid=root_pid; self.stage_vector=stage_vector; self.runtime=runtime_identity
        self.generations={}; self.ids=set(); self.ends={}; self.self_rows={}; self.baseline_rows={}
        self.reader_pid=None; self.unbound=set()

    def launch(self,entry,context):
        pid=entry['pid']; vector=entry['argv']; root=entry.get('role')=='owned_root'
        if (pid in self.generations or entry.get('launch_id') in self.ids or not entry.get('launch_id') or
            entry.get('provenance')!='source_owned_python_launch' or
            entry.get('parent')!=(os.getpid() if root else self.root_pid) or
            (pid!=self.root_pid if root else pid==self.root_pid) or
            entry.get('role') not in ('owned_root','reader') or
            (vector!=self.stage_vector if root else commands.reader_vector(vector,context)!=vector) or
            entry.get('executable')!=vector[0] or entry.get('vector_sha256')!=commands.vector_hash(vector) or
            entry.get('launcher')!=dict(path=self.runtime['executable'],sha256=self.runtime['executable_sha256']) or
            entry.get('expected_image')!=self.runtime['process_image'] or entry.get('reaped') is not False):
            raise ValueError('invalid/duplicate Python generation')
        other=self.generations.get(self.reader_pid,{})
        if not root and other.get('completion_end',float('-inf') if self.reader_pid is None else float('inf'))>entry['launch_start']:
            raise ValueError('overlapping reader ownership')
        self.generations[pid]=dict(entry); self.ids.add(entry['launch_id'])
        self.unbound.discard(pid)
        if not root: self.reader_pid=pid
        if pid in self.ends: self._end(self.generations[pid],self.ends[pid])
        if pid in self.self_rows: self._self(pid,self.self_rows[pid])
        self._baseline(pid)

    def end(self,event):
        pid=event['pid']
        if pid in self.ends: raise ValueError('duplicate Python completion')
        self.ends[pid]=dict(event)
        if pid not in self.generations: self.unbound.add(pid)
        if pid in self.generations: self._end(self.generations[pid],event)

    def _end(self,entry,event):
        if (event.get('launch_id')!=entry['launch_id'] or event.get('parent')!=entry['parent'] or
            event.get('reaped') is not True or type(event.get('returncode')) is not int or
            event['completion_end']<entry['launch_start'] or
            event['completion_end']<=entry.get('last_proof_end',float('-inf')) or
            event['completion_end']<self.baseline_rows.get(entry['pid'],{}).get('monotonic',float('-inf')) or
            event['completion_end']<entry.get('latest_sample_start',float('-inf'))):
            raise ValueError('invalid Python completion lifetime')
        entry.update(completion_end=event['completion_end'],reaped=True,returncode=event['returncode'])

    def matches(self,entry,row):
        return (not row.get('ambiguous') and row['pid']==entry['pid'] and row['parent']==entry['parent'] and
                row.get('raw_args')==commands.native_display(entry['argv'],self.runtime) and
                row['sample_end']>=entry['launch_start'] and
                row['sample_start']<=entry.get('completion_end',float('inf')))

    def _proof(self,entry,row,origin):
        image=row.get('image',{}); start=image.get('lookup_start',float('-inf')); end=image.get('lookup_end',float('inf'))
        if (not self.matches(entry,row) or image.get('status')!='ok' or
            any(image.get(k)!=self.runtime['process_image'][k] for k in ('path','sha256')) or
            not entry['launch_start']<=row['sample_start']<=row['sample_end']<=start<=end or
            end>=entry.get('completion_end',float('inf'))):
            raise ValueError('invalid same-generation Python image proof')
        entry.setdefault('proof',dict(launch_id=entry['launch_id'],pid=entry['pid'],origin=origin,
                                     lookup_start=start,lookup_end=end))
        entry['last_proof_end']=max(entry.get('last_proof_end',float('-inf')),end)

    def root_sample(self,row,*,owner_unreaped):
        entry=self.generations.get(row['pid'])
        if entry is not None and entry['role']=='owned_root' and owner_unreaped and 'completion_end' not in entry:
            self._proof(entry,row,'unreaped_owned_root')

    def self_sample(self,emitter_pid,rows):
        own=[row for row in rows if row['pid']==emitter_pid]
        if len(own)!=1 or emitter_pid in self.self_rows: raise ValueError('ambiguous Python self sample')
        self.self_rows[emitter_pid]=dict(own[0])
        if emitter_pid not in self.generations: self.unbound.add(emitter_pid)
        if emitter_pid in self.generations: self._self(emitter_pid,own[0])

    def _self(self,pid,row):
        entry=self.generations[pid]
        # The root proof belongs to its owning supervisor, never a late emitter.
        if entry['role']!='reader': return
        self._proof(entry,row,'trusted_emitter_self_row')
        self._baseline(pid)

    def baseline(self,event):
        pid=event['pid']
        if pid in self.baseline_rows: raise ValueError('duplicate generation baseline')
        self.baseline_rows[pid]=dict(event); self._baseline(pid)
        if pid not in self.generations: self.unbound.add(pid)

    def _baseline(self,pid):
        entry=self.generations.get(pid); baseline=self.baseline_rows.get(pid); row=self.self_rows.get(pid)
        if entry is None or baseline is None or row is None or 'proof' not in entry: return
        if (baseline.get('boundary')!='post-import/pre-allocation' or baseline['rss']!=row['rss_bytes'] or
            not entry['proof']['lookup_end']<=baseline['monotonic']<=entry.get('completion_end',float('inf'))):
            raise ValueError('baseline outside Python generation')
        entry['baseline']=baseline['rss']

    def exited(self,row):
        image=row.get('image',{})
        if (row.get('ambiguous') or row['parent']!=(os.getpid() if row['pid']==self.root_pid else self.root_pid) or
            image.get('status')!='error' or image.get('errno')!=errno.ESRCH or
            image.get('method')!='macos.proc_pidpath' or image.get('reason')!='native_lookup_failed' or
            not row['sample_end']<=image.get('lookup_start',float('-inf'))<=image.get('lookup_end',float('-inf'))):
            return 'unaccounted'
        entry=self.generations.get(row['pid'])
        if entry is None: return 'pending_python_lifetime'
        if not self.matches(entry,row): return 'unaccounted'
        proof=entry.get('proof')
        entry['latest_sample_start']=max(entry.get('latest_sample_start',float('-inf')),row['sample_start'])
        if proof is None or 'completion_end' not in entry: return 'pending_python_lifetime'
        if proof['lookup_end']>image.get('lookup_start',float('-inf')): return 'unaccounted'
        row['identity'].update(image_evidence='unavailable_exited',launch_evidence='source_owned_python_lifetime',
                               launch_id=entry['launch_id'],proof=proof,expected_image=entry['expected_image'])
        return 'attributed'

    def unsettled(self):
        return bool(self.unbound)


def classify(root_pid,processes,baselines,declarations,*,authority_phase=None,current_pids=None,
             stage_vector=None,reader_context=None,runtime_identity=None,python_lifetimes=None):
    """Native samples need image proof; the explicit synthetic test seam is separate."""
    native={pid:entry for pid,entry in processes.items() if 'raw_args' in entry}
    synthetic={pid:entry for pid,entry in processes.items() if 'raw_args' not in entry}
    roles=_synthetic_classify(root_pid,synthetic,baselines,declarations,authority_phase=authority_phase,
                             current_pids=current_pids,stage_vector=stage_vector,reader_context=reader_context)
    if not native: return roles
    runtime_identity=runtime_identity if runtime_identity is not None else authority.runtime()
    phase=authority_phase or dict(active=False,declarations={},completed=set(),commands=[])
    python_image=runtime_identity['process_image']
    def image_matches(entry,artifact):
        image=entry.get('image',{})
        return image.get('status')=='ok' and all(image.get(k)==artifact[k] for k in ('path','sha256'))
    expected=set()
    for pid,entry in native.items():
        display_ok=(stage_vector is not None and entry['raw_args']==commands.native_display(stage_vector,runtime_identity)) if pid==root_pid else (
            reader_context is not None and commands.reader_from_display(entry['raw_args'],**reader_context,runtime_identity=runtime_identity) is not None)
        if (not entry.get('ambiguous') and entry['parent']==(os.getpid() if pid==root_pid else root_pid)
                and display_ok and image_matches(entry,python_image) and
                (python_lifetimes is None or pid not in python_lifetimes.generations or
                 python_lifetimes.matches(python_lifetimes.generations[pid],entry))):
            expected.add(pid)
    for pid,entry in native.items():
        entry['identity']=dict(image_evidence='unresolved',launch_evidence=None)
        if pid in expected:
            if python_lifetimes is not None and pid in python_lifetimes.generations:
                generation=python_lifetimes.generations[pid]
                generation['latest_sample_start']=max(generation.get('latest_sample_start',float('-inf')),entry['sample_start'])
            entry['identity'].update(image_evidence='kernel_image',expected_image=python_image)
            roles[pid]=('authority_worker' if pid==root_pid and phase['active'] else
                        ('worker' if pid in baselines else 'pending_baseline'))
            continue
        if python_lifetimes is not None:
            python_vector=(stage_vector if pid==root_pid and entry['raw_args']==commands.native_display(stage_vector,runtime_identity) else
                           commands.reader_from_display(entry['raw_args'],**reader_context,runtime_identity=runtime_identity) if reader_context is not None and pid!=root_pid else None)
            if python_vector is not None:
                outcome=python_lifetimes.exited(entry)
                roles[pid]=('authority_worker' if pid==root_pid and phase['active'] else
                            'worker' if pid in baselines else 'pending_baseline') if outcome=='attributed' else outcome
                continue
        vector=None; declared=None; helper=None
        if entry['parent']==root_pid:
            vector=next((cmd for cmd in phase['commands'] if entry['raw_args']==commands.display(cmd)),None)
            if vector is not None: declared=phase['declarations'].get(pid); helper='git'
        if vector is None and entry['raw_args']==commands.display(PS_ARGV) and (entry['parent']==os.getpid() or entry['parent'] in expected):
            vector=PS_ARGV; declared=declarations.get(pid); helper='ps'
        roles[pid]='unaccounted'
        if vector is None or entry.get('ambiguous'): continue
        artifact=runtime_identity['helpers'][helper]; image=entry.get('image',{})
        kernel=image_matches(entry,artifact)
        exited=image.get('status')=='error' and image.get('errno')==errno.ESRCH
        # A contradictory image or any other native failure cannot be repaired.
        if not kernel and not exited: continue
        if helper=='git' and (not phase.get('started',phase['active']) or
                entry['sample_end']<phase.get('start',float('-inf')) or entry['sample_start']>phase.get('end',float('inf'))): continue
        if declared is None:
            roles[pid]='pending_authority_declaration' if helper=='git' else 'pending_observer_declaration'
            continue
        if (declared.get('ambiguous') or declared.get('provenance')!='source_owned_launch' or
            declared.get('pid')!=pid or declared.get('parent')!=entry['parent'] or
            declared.get('executable')!=vector[0] or declared.get('argv')!=vector or
            declared.get('vector_sha256')!=commands.vector_hash(vector) or declared.get('artifact')!=artifact or
            not declared.get('launch_id') or declared.get('launch_start',float('inf'))>entry['sample_end'] or
            declared.get('completion_end',float('inf'))<entry['sample_start']): continue
        if helper=='git' and (declared['launch_start']<phase.get('start',float('-inf')) or
                              declared.get('completion_end',float('-inf'))>phase.get('end',float('inf'))): continue
        if kernel and image.get('lookup_start',float('-inf'))>=declared.get('completion_end',float('inf')): continue
        if exited and 'completion_end' in declared and not declared.get('reaped'): continue
        if exited and 'completion_end' not in declared:
            roles[pid]='pending_authority_declaration' if helper=='git' else 'pending_observer_declaration'
            continue
        entry['identity'].update(image_evidence='kernel_image' if kernel else 'unavailable_exited',
                                 launch_evidence='source_owned_launch',launch_id=declared['launch_id'],expected_image=artifact)
        roles[pid]='authority_helper' if helper=='git' else 'observer_helper'
    return roles


def process_tree(pid,*,observer_log=None,authority_root=None,deadline=None,runtime_identity=None):
    """Parse numeric RSS first; lookup only the selected native sample identities."""
    started=time.monotonic()
    deadline=min(deadline if deadline is not None else started+1,started+1)
    if deadline<=started: raise ObserverFailure('observer timeout')
    runtime_identity=runtime_identity if runtime_identity is not None else authority.runtime()
    own_observer=authority.helper_launch(PS_ARGV,runtime_identity['helpers']['ps'])
    probe=subprocess.Popen(PS_ARGV,stdout=subprocess.PIPE,text=True,close_fds=True)
    own_observer['pid']=probe.pid
    try:
        authority.event(observer_log,'observer_helper',**own_observer)
        try: raw=probe.communicate(timeout=max(0,deadline-time.monotonic()))[0]
        except subprocess.TimeoutExpired as exc:
            probe.kill(); probe.communicate(timeout=1)
            raise ObserverFailure('observer timeout',pid=probe.pid,reaped=probe.poll() is not None,
                                  seconds=time.monotonic()-started) from exc
        if probe.returncode: raise ObserverFailure('observer failed',pid=probe.pid,reaped=True,seconds=time.monotonic()-started)
    except BaseException:
        if probe.poll() is None:
            probe.kill(); probe.communicate(timeout=1)
        raise
    finally:
        own_observer.update(completion_end=time.monotonic(),reaped=probe.poll() is not None)
        authority.event(observer_log,'observer_helper_end',pid=probe.pid,parent=os.getpid(),
                        launch_id=own_observer['launch_id'],completion_end=own_observer['completion_end'],reaped=own_observer['reaped'])
        if probe.stdout is not None: probe.stdout.close()
    sampled_end=time.monotonic(); table={}; raw_identity={}; ambiguous=set(); parents={}
    for line in raw.splitlines():
        fields=line.split(None,3)
        if len(fields)<3: raise ObserverFailure('malformed numeric ps row')
        try: p,parent,rss=map(int,fields[:3])
        except ValueError as exc: raise ObserverFailure('malformed numeric ps row') from exc
        if p<=0 or parent<0 or rss<0: raise ObserverFailure('invalid numeric ps row')
        if p in table: ambiguous.add(p)
        parents.setdefault(p,set()).add(parent)
        table[p]=(parent,max(rss*1024,table.get(p,(0,0))[1]))
        raw_identity[p]=fields[3].split(None,1) if len(fields)==4 else []
    selected={pid}; previous=set()
    while previous!=selected:
        previous=set(selected)
        selected|={p for p,possible in parents.items() if possible & selected}
    selected.add(probe.pid)
    readings={p:table[p][1] for p in selected if p in table}
    identities={}
    for p in readings:
        display=raw_identity[p]
        identities[p]=dict(pid=p,parent=table[p][0],rss_bytes=readings[p],sample_start=started,sample_end=sampled_end,
                           raw_comm=display[0] if display else None,raw_args=display[1] if len(display)>1 else None,
                           image=authority.process_image(p),ambiguous=p in ambiguous)
    return ResidentTree(readings,identities,{probe.pid:own_observer})


def directory_bytes(path):
    # Include logs, incomplete files, failure artifacts, baseline events and temps.
    return sum(p.stat().st_size for p in Path(path).rglob('*') if p.is_file())


def record_baseline(path,*,deadline=None):
    pid=os.getpid(); readings=process_tree(pid,observer_log=path,deadline=deadline); rss=readings[pid]
    if getattr(readings,'processes',None):
        authority.event(path,'observer_sample',emitter_pid=pid,self_pid=pid,processes=list(readings.processes.values()))
    record=dict(event='baseline',pid=pid,rss=rss,monotonic=time.monotonic(),utc_epoch=time.time(),
                boundary='post-import/pre-allocation')
    with Path(path).open('a') as f:
        f.write(json.dumps(record)+'\n'); f.flush()
    return record


class _MonitorStop(RuntimeError): pass


def _bounded_json(value,limit,check=lambda:None):
    """Stop encoding at the available byte budget; never build a report backlog."""
    chunks=[]; size=0
    for chunk in json.JSONEncoder(separators=(',',':'),allow_nan=False).iterencode(value):
        check(); encoded=chunk.encode(); size+=len(encoded)
        if size+1>limit: raise _MonitorStop('output cap')
        chunks.append(encoded)
    check()
    return b''.join(chunks)+b'\n'


def _commit_monitor(path,payload,reserve):
    """Overwrite only preallocated verdict space; never grow/rewrite a large report."""
    if len(payload)>reserve: raise _MonitorStop('output cap')
    with Path(path).open('r+b') as stream:
        if stream.write(payload+b' '*(reserve-len(payload)))!=reserve: raise OSError('short monitor write')
        stream.flush()


def supervise(command,output,*,outer_seconds=600,output_bytes=67108864,free_disk_bytes=4294967296,
              incremental_bytes=201326592,sampler=process_tree,preparation_output=None,authority_root=None,deadline=None):
    """One owned group, charged append-only evidence and a bounded final commitment."""
    output=Path(output)
    if output.exists(): raise ValueError('output must be fresh')
    if shutil.disk_usage(output.parent).free<free_disk_bytes: raise ValueError('disk entry condition')
    if output_bytes<512: raise ValueError('at least 512 bytes for a bounded failure verdict')
    start=time.monotonic(); utc=time.time(); output.mkdir()
    deadline=min(deadline if deadline is not None else start+outer_seconds,start+outer_seconds,start+600)
    # This time/space belongs to the original allocation, not an extension.
    work_deadline=deadline-min(.1,max(0,(deadline-start)*.1))
    reserve=min(8192,max(512,output_bytes//2)); verdict=output/'monitor.json'; evidence_path=output/'monitor-evidence.jsonl'
    process=None; reason=None; monitor_failure=None; native_runtime=None; conservative=False; python_lifetimes=None; root_witness=None
    peak=0; incremental_peak=0; overhead_peak=0; authority_peak=0; rss_peak_sum=0
    worker_peak=0; outer_observer=0; inner_observer=0; git_peak=0; authority_worker=0; unresolved_sum=0; unresolved_root=0
    baselines={}; per_worker={}; declarations={}; last_roles={}; failed=set(); native_pids=set(); unresolved_pids=set()
    pending={}; dependencies={}; dirty=set(); pending_roles={}; helper_bounds={}; sequence=0; classified=0
    candidate_start=None; candidate_ranges=[]; event_offset=0; numeric_event_offset=0
    source_accounting=dict(complete=True,status='COMPLETE',identity_complete=True,through_bytes=0,samples=0)
    evidence=dict(path=evidence_path.name,accepted_records=0,accepted_samples=0,bytes=0,
                  rejected_observations=0,rejected_rss_bytes=0,rejected_raw_complete=True)
    phase=dict(active=False,declarations={},completed=set(),ends={},
               commands=authority.git_commands(authority_root) if authority_root is not None else [],started=False)
    def charged_bytes():
        return directory_bytes(output)+(directory_bytes(preparation_output) if preparation_output is not None else 0)
    def check(*,final=False):
        if time.monotonic()>=(deadline if final else work_deadline): raise _MonitorStop('outer timeout')
        if not final and candidate_start is not None and time.monotonic()>=candidate_start+90: raise _MonitorStop('candidate timeout')
    def append(record,*,final=False):
        check(final=final)
        raw=_bounded_json(record,max(0,output_bytes-charged_bytes()),lambda:check(final=final))
        original_size=evidence_path.stat().st_size
        try:
            with evidence_path.open('ab') as stream:
                if stream.write(raw)!=len(raw): raise OSError('short monitor evidence write')
                stream.flush()
        except BaseException:
            # Keep every previously accepted JSONL row readable after a short write.
            with evidence_path.open('r+b') as stream: stream.truncate(original_size)
            raise
        evidence['accepted_records']+=1; evidence['bytes']+=len(raw)
    def charge(pid,*,final=False):
        nonlocal worker_peak,outer_observer,inner_observer,git_peak,authority_worker,unresolved_sum,unresolved_root,incremental_peak,authority_peak,overhead_peak
        item=per_worker[str(pid)]; absolute=item['absolute_peak_bytes']
        role='unaccounted' if pid in failed else ('pending_observer_declaration' if pending_roles.get(pid) else last_roles.get(pid,'pending_baseline'))
        if role in ('pending_baseline','authority_worker') and pid in baselines and pid not in failed: role='worker'
        item['role']=role
        if role in ('worker','observer_helper','authority_helper'): unresolved_pids.discard(pid)
        else: unresolved_pids.add(pid)
        unresolved_sum-=item.pop('_unresolved_charge',0)
        if process is not None and pid==process.pid: unresolved_root=0
        resource_role='authority_helper' if item.get('sampled_authority_helper') else role
        if conservative or item.get('_forced_full'):
            item.update(baseline_bytes=0,incremental_peak_bytes=absolute)
            if process is not None and pid==process.pid: unresolved_root=absolute
            else: item['_unresolved_charge']=absolute; unresolved_sum+=absolute
        elif resource_role=='worker':
            item.update(baseline_bytes=baselines[pid],incremental_peak_bytes=max(0,absolute-baselines[pid]))
            worker_peak=max(worker_peak,item['incremental_peak_bytes'])
        elif resource_role in ('authority_worker','authority_helper','observer_helper'):
            # Root authority RSS comes only from intervals attributed below, never
            # from its whole-lifetime maximum (which includes later imports).
            attributed=item.get('authority_phase_peak_bytes',0) if resource_role=='authority_worker' else absolute
            item.update(baseline_bytes=0,incremental_peak_bytes=attributed)
            if resource_role=='authority_worker': authority_worker=max(authority_worker,attributed)
            elif resource_role=='authority_helper': git_peak=max(git_peak,absolute)
            elif item.get('parent')==os.getpid(): outer_observer=max(outer_observer,absolute)
            else: inner_observer=max(inner_observer,absolute)
        elif pid in native_pids and (role!='pending_baseline' or final):
            item.update(baseline_bytes=0,incremental_peak_bytes=absolute)
            if process is not None and pid==process.pid: unresolved_root=absolute
            else: item['_unresolved_charge']=absolute; unresolved_sum+=absolute
        else: item.update(baseline_bytes=None,incremental_peak_bytes=0)
        authority_peak=max(authority_peak,authority_worker+git_peak)
        overhead_peak=max(overhead_peak,outer_observer+inner_observer)
        incremental_peak=max(incremental_peak,max(worker_peak,authority_peak,unresolved_root)+overhead_peak+unresolved_sum)
    def numeric(readings,entries):
        nonlocal peak,rss_peak_sum
        peak=max(peak,sum(readings.values()))
        for pid,rss in readings.items():
            item=per_worker.setdefault(str(pid),dict(absolute_peak_bytes=0,baseline_bytes=None,incremental_peak_bytes=0))
            if 'role' not in item:
                item['role']='pending_baseline'; unresolved_pids.add(pid)
            previous=item['absolute_peak_bytes']; item['absolute_peak_bytes']=max(previous,rss); rss_peak_sum+=item['absolute_peak_bytes']-previous
            if pid in entries:
                item['parent']=entries[pid].get('parent')
                if 'raw_args' in entries[pid]: native_pids.add(pid)
            # Raw recovery can run ahead of semantic boundaries. Attribution and
            # ordinary charging wait for reconciliation; failure retains full RSS.
    def refused(readings,exc):
        nonlocal incremental_peak
        evidence['rejected_observations']+=1; evidence['rejected_rss_bytes']+=sum(readings.values()); evidence['rejected_raw_complete']=False
        evidence['last_refusal']=dict(kind='refused_observation',reason=str(exc)[:80],raw_identity_complete=False,
                                     sampled_process_count=len(readings),rss_bytes=sum(readings.values()))
        for pid in readings:
            per_worker[str(pid)]['_forced_full']=True; charge(pid,final=True)
        incremental_peak=max(incremental_peak,rss_peak_sum)
    def wake(pid): dirty.update(dependencies.get(pid,()))
    def declaration(target,entry,*,final=False):
        old=target.get(entry['pid'])
        if old is not None and old.get('launch_id')!=entry.get('launch_id'):
            entry=dict(entry,ambiguous=True); old['ambiguous']=True; failed.add(entry['pid'])
            if str(entry['pid']) in per_worker: charge(entry['pid'])
        append(dict(kind='witness',value=entry),final=final)
        target[entry['pid']]=entry; wake(entry['pid'])
        if entry.get('ambiguous'): raise _MonitorStop('foreign process identity')
    def completion(target,event,*,final=False):
        entry=target.get(event['pid'])
        if entry is None or entry.get('launch_id')!=event.get('launch_id') or entry['parent']!=event['parent']: raise ValueError('ambiguous helper completion')
        append(dict(kind='completion',value=event),final=final)
        if event.get('launch_id'):
            # Negative lifetime consistency only; never supplies image proof to a new sample.
            bounds=helper_bounds.get(event['launch_id'],(float('-inf'),float('-inf')))
            end=event['completion_end']
            if (end<entry['launch_start'] or end<bounds[0] or end<=bounds[1] or
                    ('completion_end' in entry and end!=entry['completion_end'])):
                failed.add(event['pid'])
                if str(event['pid']) in per_worker: charge(event['pid'])
                raise _MonitorStop('foreign process identity')
            entry.update(completion_end=end,reaped=event['reaped'])
        wake(event['pid'])
    def reader_context(before,after):
        if authority_root is None: return None
        bounds=[min(deadline,a+90) for a,b in candidate_ranges if after>=a and before<=(b if b is not None else float('inf'))]
        return dict(root=authority_root,event_path=output/'monitor-events.jsonl',deadline=max(bounds)) if bounds else None
    def collect(readings,entries,before,after,*,final=False,accounted=False):
        nonlocal sequence
        if not accounted: numeric(readings,entries)  # BEFORE any encoding, identity or event failure.
        sequence+=1
        try: append(dict(kind='sample',sample_id=sequence,rss=readings,processes=list(entries.values()),before=before,after=after),final=final)
        except BaseException as exc:
            refused(readings,exc); raise
        evidence['accepted_samples']+=1
        pending[sequence]=dict(entries=entries,before=before,after=after,root_rss=readings.get(process.pid,0),roles={},context=None,owner_unreaped=process.returncode is None)
        dirty.add(sequence)
        check(final=final)
    def numeric_events(*,final=False):
        """One bounded pass over new source bytes, independent of copied proof/admission."""
        nonlocal numeric_event_offset
        path=output/'monitor-events.jsonl'
        try:
            end=path.stat().st_size
            if end<numeric_event_offset: raise ValueError('source event journal truncated')
            if end==numeric_event_offset:
                source_accounting.update(complete=True,status='COMPLETE'); return
            with path.open('rb') as stream:
                stream.seek(numeric_event_offset)
                while numeric_event_offset<end:
                    check(final=final)
                    line=stream.readline(min(output_bytes+1,end-numeric_event_offset))
                    if len(line)>output_bytes: raise _MonitorStop('output cap')
                    if not line or not line.endswith(b'\n'):
                        source_accounting.update(complete=False,status='PENDING')
                        if final: raise ValueError('incomplete source event row')
                        return
                    event=json.loads(line)
                    if event['event']=='observer_sample':
                        entries={entry['pid']:entry for entry in event['processes']}
                        readings={pid:entry['rss_bytes'] for pid,entry in entries.items()}
                        if any(type(pid) is not int or pid<=0 or type(rss) is not int or rss<0 for pid,rss in readings.items()):
                            raise ValueError('invalid source sample numerical RSS')
                        numeric(readings,entries)
                        source_accounting['samples']+=1
                    # Move only after this row's numerical information is retained.
                    numeric_event_offset=stream.tell(); source_accounting['through_bytes']=numeric_event_offset
                    check(final=final)
            source_accounting.update(complete=True,status='COMPLETE')
        except BaseException:
            source_accounting.update(complete=False,status='FAILED',identity_complete=False)
            raise
    def semantic_events(*,final=False):
        nonlocal event_offset,candidate_start,authority_worker
        path=output/'monitor-events.jsonl'
        with path.open() as stream:
            stream.seek(event_offset)
            while True:
                check(final=final); position=stream.tell(); line=stream.readline(output_bytes+1)
                if len(line)>output_bytes: raise _MonitorStop('output cap')
                if not line or not line.endswith('\n'): event_offset=position; break
                event_offset=stream.tell()
                if event_offset>numeric_event_offset: numeric_events(final=final)
                event=json.loads(line); kind=event['event']
                if kind=='observer_sample':
                    entries={entry['pid']:entry for entry in event['processes']}
                    first=next(iter(entries.values()))
                    if python_lifetimes is not None and 'emitter_pid' in event:
                        if event.get('self_pid')!=event['emitter_pid']: raise ValueError('invalid self row tag')
                        python_lifetimes.self_sample(event['emitter_pid'],list(entries.values())); wake(event['emitter_pid'])
                    collect({pid:entry['rss_bytes'] for pid,entry in entries.items()},entries,first['sample_start'],first['sample_end'],final=final,accounted=True)
                elif kind=='observer_helper': declaration(declarations,{k:v for k,v in event.items() if k not in ('event','monotonic')},final=final)
                elif kind=='observer_helper_end': completion(declarations,event,final=final)
                else:
                    append(dict(kind='event',value=event),final=final)
                    if kind=='baseline':
                        if python_lifetimes is not None and event['pid']!=process.pid:
                            python_lifetimes.baseline(event)
                        else: baselines[event['pid']]=event['rss']
                        wake(event['pid'])
                        if str(event['pid']) in per_worker: charge(event['pid'])
                    elif kind=='python_worker_launch':
                        if python_lifetimes is None: raise ValueError('Python runtime witness missing')
                        entry={k:v for k,v in event.items() if k not in ('event','monotonic')}
                        context=reader_context(entry['launch_start'],entry['launch_start'])
                        if entry.get('role')!='reader': raise ValueError('invalid emitted Python role')
                        python_lifetimes.launch(entry,context); wake(entry['pid'])
                    elif kind=='python_worker_end':
                        if python_lifetimes is None: raise ValueError('Python runtime witness missing')
                        python_lifetimes.end(event); wake(event['pid'])
                    elif kind=='candidate_start': candidate_start=event['monotonic']; candidate_ranges.append([candidate_start,None])
                    elif kind=='candidate_end':
                        if candidate_ranges and candidate_ranges[-1][1] is None: candidate_ranges[-1][1]=event['monotonic']
                        candidate_start=None
                    elif kind=='authority_start':
                        if event['pid']!=process.pid or phase['started'] or baselines or candidate_start is not None: raise ValueError('invalid authority phase start')
                        phase.update(active=True,started=True,start=event['monotonic']); wake(process.pid)
                    elif kind=='authority_helper':
                        entry={k:v for k,v in event.items() if k not in ('event','monotonic')}
                        if not phase['active'] or entry['parent']!=process.pid or entry['executable']!=authority.GIT or entry['argv'] not in phase['commands'] or entry['pid'] in phase['declarations']: raise ValueError('undeclared authority identity/operation')
                        declaration(phase['declarations'],entry,final=final)
                    elif kind=='authority_helper_end':
                        if not phase['active'] or event['pid'] not in phase['declarations'] or event['parent']!=process.pid: raise ValueError('invalid authority helper lifetime')
                        completion(phase['declarations'],event,final=final)
                        phase['completed'].add(event['pid']); phase['ends'][event['pid']]=event['monotonic']
                    elif kind=='authority_end':
                        if not phase['active'] or event['pid']!=process.pid: raise ValueError('invalid authority phase end')
                        if event['success'] and (set(phase['declarations'])!=phase['completed'] or sorted(entry['argv'] for entry in phase['declarations'].values())!=sorted(phase['commands'])): raise ValueError('incomplete exact authority operations')
                        phase.update(active=False,end=event['monotonic'],success=event['success'])
                        for entry in phase['declarations'].values():
                            if entry.get('completion_end',event['monotonic'])>event['monotonic']:
                                failed.add(entry['pid'])
                                if str(entry['pid']) in per_worker: charge(entry['pid'])
                                raise _MonitorStop('foreign process identity')
                        wake(process.pid)
                    else: raise ValueError('unknown monitoring event')
    def read_events(*,final=False):
        numeric_events(final=final)
        try: semantic_events(final=final)
        except BaseException:
            source_accounting['identity_complete']=False
            raise
    def stopped_status(): return 'STOPPED' if source_accounting['complete'] else 'FAILED'
    def reconcile(*,final=False):
        nonlocal classified,authority_worker
        while dirty:
            check(final=final); identifier=dirty.pop(); batch=pending.get(identifier)
            if batch is None: continue
            entries=batch['entries']; before,after=batch['before'],batch['after']
            for pid,role in batch['roles'].items():
                pending_roles.get(pid,set()).discard(identifier)
            sample_phase=dict(phase,active=phase['started'] and after>=phase.get('start',float('inf')) and before<=phase.get('end',float('inf')))
            live={pid for pid in entries if phase['ends'].get(pid,float('-inf'))<before}
            context=reader_context(before,after)
            if source_accounting['identity_complete']:
                if python_lifetimes is not None:
                    root_row=entries.get(process.pid)
                    if root_row is not None and root_row.get('image',{}).get('status')=='ok':
                        python_lifetimes.root_sample(root_row,owner_unreaped=batch['owner_unreaped'])
                    for pid in entries:
                        generation=python_lifetimes.generations.get(pid,{})
                        if 'baseline' in generation: baselines[pid]=generation['baseline']
                resolved=classify(process.pid,entries,baselines,declarations,authority_phase=sample_phase,current_pids=live,
                                  stage_vector=command,reader_context=context,runtime_identity=native_runtime,python_lifetimes=python_lifetimes)
            else:
                # A skipped boundary can leave phase active after its actual end.
                # Failed provenance cannot authorize new attribution or proof.
                resolved={pid:'unaccounted' for pid in entries}
            classified+=len(entries)
            # Identity history is immutable evidence, never a per-PID proof cache.
            for pid,role in resolved.items():
                if role=='authority_worker':
                    item=per_worker[str(pid)]
                    item['authority_phase_peak_bytes']=max(item.get('authority_phase_peak_bytes',0),batch['root_rss'])
                    authority_worker=max(authority_worker,item['authority_phase_peak_bytes'])
                if role=='unaccounted': failed.add(pid)
                if role=='authority_helper': per_worker.get(str(pid),{})['sampled_authority_helper']=True
                if role in ('authority_helper','observer_helper') and 'raw_args' in entries[pid]:
                    declared=phase['declarations'].get(pid) if role=='authority_helper' else declarations.get(pid)
                    launch_id=declared['launch_id']; prior=helper_bounds.get(launch_id,(float('-inf'),float('-inf')))
                    image=entries[pid].get('image',{})
                    helper_bounds[launch_id]=(max(prior[0],entries[pid]['sample_start']),
                        max(prior[1],image.get('lookup_start',float('-inf'))) if image.get('status')=='ok' else prior[1])
                last_roles[pid]=role
                if role.startswith('pending_') and not (role=='pending_baseline' and pid in native_pids): pending_roles.setdefault(pid,set()).add(identifier)
                if str(pid) in per_worker: charge(pid,final=final)
            batch['roles']=resolved
            check(final=final)
            append(dict(kind='resolution',sample_id=identifier,roles=resolved,
                        identities={pid:entry.get('identity') for pid,entry in entries.items() if 'raw_args' in entry}),final=final)
            waiting={pid for pid,role in resolved.items() if role.startswith('pending_') and not (role=='pending_baseline' and pid in native_pids)}
            if waiting:
                for pid in waiting: dependencies.setdefault(pid,set()).add(identifier)
            else:
                pending.pop(identifier,None)
                for pid in entries:
                    dependencies.get(pid,set()).discard(identifier)
            if any(role=='unaccounted' for role in resolved.values()): raise _MonitorStop('foreign process identity')
            if incremental_peak>incremental_bytes: raise _MonitorStop('incremental worker memory cap')
    def failure(exc):
        nonlocal reason,monitor_failure,conservative,incremental_peak
        if not source_accounting['identity_complete']:
            # Raw source recovery survives a refused boundary/witness copy, but
            # cannot supply phase attribution or proof. Charge the full known cost.
            conservative=True; incremental_peak=max(incremental_peak,rss_peak_sum)
        if isinstance(exc,_MonitorStop):
            if reason is None or str(exc)=='outer timeout': reason=str(exc)
        elif isinstance(exc,ObserverFailure): reason=str(exc); monitor_failure=exc.evidence
        else:
            reason='monitor common failure'; monitor_failure=dict(type=type(exc).__name__,message=str(exc)[:300]); conservative=True
            incremental_peak=max(incremental_peak,rss_peak_sum)
    def emergency(why):
        # Independent of the normal JSON encoder and Path write boundary.
        body=('{"status":"'+stopped_status()+'","reason":"'+why+'","returncode":'+str(process.returncode if process is not None and process.returncode is not None else 'null')+
              ',"absolute_process_tree_peak_bytes":'+str(peak)+',"incremental_worker_peak_bytes":'+str(max(incremental_peak,rss_peak_sum))+
              ',"outer_seconds":'+repr(time.monotonic()-start)+',"timing_boundary":"before emergency commit; caller includes write"'+
              ',"raw_identity_complete":'+str(evidence['rejected_raw_complete'] and source_accounting['identity_complete']).lower()+
              ',"refused_observations":'+str(evidence['rejected_observations'])+',"refused_rss_bytes":'+str(evidence['rejected_rss_bytes'])+
              ',"source_accounting_complete":'+str(source_accounting['complete']).lower()+'}\n').encode()
        return body
    initial=emergency('monitor incomplete')
    with verdict.open('xb') as stream: stream.write(initial+b' '*(reserve-len(initial)))
    evidence_path.touch(); (output/'monitor-events.jsonl').touch()
    try:
        check()
        if charged_bytes()>output_bytes: raise _MonitorStop('output cap')
        with (output/'stdout.log').open('wb') as stdout,(output/'stderr.log').open('wb') as stderr:
            if sampler is process_tree:
                native_runtime=authority.runtime(); append(dict(kind='runtime',value=native_runtime))
                root_witness=authority.python_launch(command,native_runtime,'owned_root')
            process=subprocess.Popen(command,cwd=output,stdout=stdout,stderr=stderr,start_new_session=True,close_fds=True)
            try:
                if root_witness is not None:
                    root_witness['pid']=process.pid
                    python_lifetimes=PythonLifetimes(process.pid,command,native_runtime)
                    python_lifetimes.launch(root_witness,None); append(dict(kind='python_root_launch',value=root_witness))
                while process.poll() is None:
                    check()
                    if charged_bytes()>output_bytes: raise _MonitorStop('output cap')
                    if shutil.disk_usage(output).free<free_disk_bytes: raise _MonitorStop('disk free prerequisite')
                    read_events(); reconcile()
                    before=time.monotonic(); applicable=min(work_deadline,candidate_start+90 if candidate_start is not None else work_deadline)
                    if sampler is process_tree:
                        if native_runtime is None:
                            native_runtime=authority.runtime(); append(dict(kind='runtime',value=native_runtime))
                        readings=sampler(process.pid,authority_root=authority_root,deadline=applicable,runtime_identity=native_runtime)
                    else: readings=sampler(process.pid)
                    after=time.monotonic(); entries=getattr(readings,'processes',{})
                    collect(dict(readings),entries,before,after)
                    if any('raw_args' in entry for entry in entries.values()) and native_runtime is None:
                        native_runtime=authority.runtime(); append(dict(kind='runtime',value=native_runtime))
                    for entry in getattr(readings,'declarations',{}).values(): declaration(declarations,entry)
                    read_events(); reconcile(); check()
                    time.sleep(.02)
            except (Exception,) as exc: failure(exc)
            finally:
                try: os.killpg(process.pid,signal.SIGKILL)
                except ProcessLookupError: pass
                process.wait(timeout=1)
                if python_lifetimes is not None:
                    end=dict(pid=process.pid,parent=os.getpid(),launch_id=root_witness['launch_id'],reaped=True,
                             returncode=process.returncode,completion_end=time.monotonic())
                    python_lifetimes.end(end); append(dict(kind='python_root_end',value=end),final=True); wake(process.pid)
    except Exception as exc: failure(exc)
    finalization_start=time.monotonic()
    try:
        numeric_events(final=True)
        check(final=True)
        if process is not None: read_events(final=True); reconcile(final=True)
        if python_lifetimes is not None and python_lifetimes.unsettled(): raise ValueError('unmatched Python generation evidence')
        for pid_text in per_worker:
            check(final=True); charge(int(pid_text),final=True)
        if incremental_peak>incremental_bytes and reason is None: reason='incremental worker memory cap'
    except Exception as exc:
        failure(exc)
        if not isinstance(exc,_MonitorStop) or str(exc)=='outer timeout':
            conservative=True; incremental_peak=max(incremental_peak,rss_peak_sum)
    unresolved_count=len(unresolved_pids); unresolved=[]
    # Final summaries are bounded while traversing; raw histories stay in the log.
    workers={}; workers_complete=True
    for pid in unresolved_pids:
        unresolved.append(str(pid))
        if len(unresolved)==16: break
    for pid_text,item in per_worker.items():
        if len(workers)==16: workers_complete=False; break
        clean={k:v for k,v in item.items() if not k.startswith('_')}
        if conservative or item.get('_forced_full'): clean.update(baseline_bytes=0,incremental_peak_bytes=item['absolute_peak_bytes'])
        workers[pid_text]=clean
    if unresolved_count and reason is None: reason='missing post-import worker baseline or unresolved declaration'
    if phase['started'] and (phase['active'] or not phase.get('success')) and reason is None: reason='authority verification incomplete/failed'
    if charged_bytes()>output_bytes and reason is None: reason='output cap'
    try:
        phase_complete=len(phase['declarations'])<=16 and len(phase['completed'])<=16
        phase_summary=dict(phase,completed=sorted(phase['completed']) if phase_complete else [],
                           declarations=phase['declarations'] if phase_complete else {},
                           ends=phase['ends'] if phase_complete else {},
                           details_complete_inline=phase_complete,helper_count=len(phase['declarations']),completed_count=len(phase['completed']))
        result=dict(status=stopped_status() if reason or process is None or process.returncode or not source_accounting['complete'] else 'COMPLETED',reason=reason,monitor_failure=monitor_failure,
                    stage_launch_vector_sha256=commands.vector_hash(command),returncode=process.returncode if process is not None else None,
                    outer_seconds=time.monotonic()-start,utc_start_epoch=utc,utc_end_epoch=time.time(),
                    timing_boundary='before bounded final commit; caller must measure full elapsed including commit',
                    finalization_start_seconds=finalization_start-start,
                    absolute_process_tree_peak_bytes=peak,incremental_worker_peak_bytes=incremental_peak,
                    observed_pid_peak_sum_bytes=rss_peak_sum,workers=workers,workers_complete_inline=workers_complete,worker_count=len(per_worker),
                    observer_helper_peak_bytes=overhead_peak,authority_full_rss_peak_bytes=authority_peak,
                    authority_phase=phase_summary,
                    missing_worker_baselines=unresolved,unresolved_worker_count=unresolved_count,evidence=evidence,source_event_accounting=source_accounting,
                    classified_process_observations=classified,verdict_reserved_bytes=reserve,
                    rss_scope='sampled resident memory; not allocator peak')
        try: _bounded_json(result,reserve)
        except _MonitorStop:
            result.update(workers={},workers_complete_inline=False,
                          authority_phase={k:phase[k] for k in ('active','started')})
            if result['reason'] is None: result.update(status=stopped_status(),reason='output cap including final monitor report')
        # Includes the completed bounded summary traversal/first encoding.
        result['outer_seconds']=time.monotonic()-start
        result['output_bytes_before_monitor_report']=charged_bytes()
        if time.monotonic()>=deadline: result.update(status=stopped_status(),reason='outer timeout')
        raw=_bounded_json(result,reserve)
        if time.monotonic()>=deadline:
            result.update(status=stopped_status(),reason='outer timeout',outer_seconds=time.monotonic()-start)
            # One bounded last encoding, never a size/timestamp fixed point.
            raw=_bounded_json(result,reserve)
        _commit_monitor(verdict,raw,reserve)
        if time.monotonic()>=deadline and result['status']=='COMPLETED': raise _MonitorStop('outer timeout')
        return result
    except Exception as exc:
        raw=emergency(str(exc) if isinstance(exc,_MonitorStop) else 'monitor serialization/write failure')
        fd=os.open(verdict,os.O_WRONLY)
        try:
            payload=raw+b' '*(reserve-len(raw)); written=0
            while written<len(payload):
                count=os.write(fd,payload[written:])
                if count<=0: raise OSError('short emergency monitor write')
                written+=count
        finally: os.close(fd)
        return json.loads(raw)
