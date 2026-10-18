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


def classify(root_pid,processes,baselines,declarations,*,authority_phase=None,current_pids=None,
             stage_vector=None,reader_context=None,runtime_identity=None):
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
                and display_ok and image_matches(entry,python_image)):
            expected.add(pid)
    for pid,entry in native.items():
        entry['identity']=dict(image_evidence='unresolved',launch_evidence=None)
        if pid in expected:
            entry['identity'].update(image_evidence='kernel_image',expected_image=python_image)
            roles[pid]=('authority_worker' if pid==root_pid and phase['active'] else
                        ('worker' if pid in baselines else 'pending_baseline'))
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
        authority.event(path,'observer_sample',processes=list(readings.processes.values()))
    record=dict(event='baseline',pid=pid,rss=rss,monotonic=time.monotonic(),utc_epoch=time.time(),
                boundary='post-import/pre-allocation')
    with Path(path).open('a') as f:
        f.write(json.dumps(record)+'\n'); f.flush()
    return record


def supervise(command,output,*,outer_seconds=600,output_bytes=67108864,free_disk_bytes=4294967296,
              incremental_bytes=201326592,sampler=process_tree,preparation_output=None,authority_root=None,deadline=None):
    """Own one sequential stage group and reconcile every retained observation."""
    output=Path(output)
    if output.exists(): raise ValueError('output must be fresh')
    if shutil.disk_usage(output.parent).free<free_disk_bytes: raise ValueError('disk entry condition')
    output.mkdir(); start=time.monotonic(); utc=time.time(); reason=None; peak=0
    deadline=min(deadline if deadline is not None else start+outer_seconds,start+outer_seconds,start+600)
    monitor_failure=None
    baselines={}; per_worker={}; candidate_start=None; event_offset=0; declarations={}; identities={}
    native_runtime=None
    root_samples=[]; native_samples=[]; launch_witnesses=[]; candidate_ranges=[]; incremental_peak=0; overhead_peak=0; authority_peak=0; final_roles={}
    phase=dict(active=False,declarations={},completed=set(),ends={},
               commands=authority.git_commands(authority_root) if authority_root is not None else [],started=False)
    def charged_bytes():
        return directory_bytes(output)+(directory_bytes(preparation_output) if preparation_output is not None else 0)
    def retain_native(batch):
        nonlocal peak
        native_samples.append(batch)
        peak=max(peak,sum(entry['rss_bytes'] for entry in batch.values()))
        for pid,entry in batch.items():
            item=per_worker.setdefault(str(pid),dict(absolute_peak_bytes=0,incremental_peak_bytes=0,baseline_bytes=None))
            item['absolute_peak_bytes']=max(item['absolute_peak_bytes'],entry['rss_bytes'])
            item['parent']=entry['parent']
            if pid==process.pid: root_samples.append((entry['sample_start'],entry['sample_end'],entry['rss_bytes']))
    def declaration(target,entry):
        old=target.get(entry['pid'])
        if old is not None and old.get('launch_id')!=entry.get('launch_id'):
            old['ambiguous']=True; entry['ambiguous']=True
        if entry.get('provenance')=='source_owned_launch': launch_witnesses.append(entry.copy())
        target[entry['pid']]=dict(entry,ambiguous=entry.get('ambiguous',False)) if entry.get('launch_id') else entry
    def completion(target,event):
        entry=target.get(event['pid'])
        if entry is None or entry.get('launch_id')!=event.get('launch_id') or entry['parent']!=event['parent']:
            raise ValueError('ambiguous helper completion')
        if event.get('launch_id'):
            entry.update(completion_end=event['completion_end'],reaped=event['reaped'])
            launch_witnesses.append(dict(entry))
    def read_events():
        nonlocal event_offset,candidate_start
        path=output/'monitor-events.jsonl'
        if not path.exists(): return
        with path.open() as stream:
            stream.seek(event_offset)
            while True:
                position=stream.tell(); line=stream.readline()
                if not line or not line.endswith('\n'):
                    event_offset=position; break
                event=json.loads(line); kind=event['event']
                if kind=='baseline': baselines[event['pid']]=event['rss']
                elif kind=='observer_helper': declaration(declarations,{k:v for k,v in event.items() if k not in ('event','monotonic')})
                elif kind=='observer_helper_end': completion(declarations,event)
                elif kind=='observer_sample':
                    retain_native({entry['pid']:entry for entry in event['processes']})
                elif kind=='candidate_start':
                    candidate_start=event['monotonic']; candidate_ranges.append([candidate_start,None])
                elif kind=='candidate_end':
                    if candidate_ranges and candidate_ranges[-1][1] is None: candidate_ranges[-1][1]=event['monotonic']
                    candidate_start=None
                elif kind=='authority_start':
                    if event['pid']!=process.pid or phase['started'] or baselines or candidate_start is not None:
                        raise ValueError('invalid authority phase start')
                    phase.update(active=True,started=True,start=event['monotonic'])
                elif kind=='authority_helper':
                    entry={k:v for k,v in event.items() if k not in ('event','monotonic')}
                    if not phase['active'] or entry['parent']!=process.pid or entry['executable']!=authority.GIT or entry['argv'] not in phase['commands'] or entry['pid'] in phase['declarations']:
                        raise ValueError('undeclared authority identity/operation')
                    declaration(phase['declarations'],entry)
                elif kind=='authority_helper_end':
                    if not phase['active'] or event['pid'] not in phase['declarations'] or event['parent']!=process.pid:
                        raise ValueError('invalid authority helper lifetime')
                    completion(phase['declarations'],event)
                    phase['completed'].add(event['pid']); phase['ends'][event['pid']]=event['monotonic']
                elif kind=='authority_end':
                    if not phase['active'] or event['pid']!=process.pid: raise ValueError('invalid authority phase end')
                    if event['success'] and (set(phase['declarations'])!=phase['completed'] or
                       sorted(entry['argv'] for entry in phase['declarations'].values())!=sorted(phase['commands'])):
                        raise ValueError('incomplete exact authority operations')
                    phase.update(active=False,end=event['monotonic'],success=event['success'])
                else: raise ValueError('unknown monitoring event')
    def reader_context(before=None,after=None):
        if authority_root is None: return None
        bound=deadline
        if before is not None:
            bounds=[min(deadline,a+90) for a,b in candidate_ranges if after>=a and before<=(b if b is not None else float('inf'))]
            if not bounds: return None
            bound=max(bounds)
        return dict(root=authority_root,event_path=output/'monitor-events.jsonl',deadline=bound)
    def reconcile(*,final=False):
        nonlocal incremental_peak,overhead_peak,authority_peak,final_roles
        # Historical identities remain attributable after their exact lifetime.
        historical=dict(phase,active=False)
        final_roles=classify(process.pid,identities,baselines,declarations,authority_phase=historical,current_pids=set(),stage_vector=command,reader_context=reader_context())
        native_roles={}
        for batch in native_samples:
            first=next(iter(batch.values()))
            before,after=first['sample_start'],first['sample_end']
            sample_phase=dict(phase,active=phase['started'] and after>=phase.get('start',float('inf')) and before<=phase.get('end',float('inf')))
            resolved=classify(process.pid,batch,baselines,declarations,authority_phase=sample_phase,
                              stage_vector=command,reader_context=reader_context(before,after),runtime_identity=native_runtime)
            for pid,role in resolved.items():
                if role=='authority_worker' and pid in baselines: role='worker'
                previous=native_roles.get(pid)
                if previous=='unaccounted' or role=='unaccounted': native_roles[pid]='unaccounted'
                elif previous is not None and previous.startswith('pending_'): continue
                else: native_roles[pid]=role
        final_roles.update(native_roles)
        worker_peak=0; outer_observer=0; inner_observer=0; git_peak=0; unresolved_peak=0; unresolved_root=0
        for pid_text,item in per_worker.items():
            pid=int(pid_text); role=final_roles.get(pid,'pending_baseline'); item['role']=role
            # A sampled exact live admission is retained as a resource charge,
            # even if termination prevents its helper-end event. This does not
            # extend that helper's identity exception beyond its lifetime.
            charge_role='authority_helper' if item.get('sampled_authority_helper') else role
            absolute=item['absolute_peak_bytes']
            if charge_role=='worker':
                item['baseline_bytes']=baselines[pid]
                item['incremental_peak_bytes']=max(0,absolute-baselines[pid])
                worker_peak=max(worker_peak,item['incremental_peak_bytes'])
            elif charge_role in ('observer_helper','authority_helper'):
                item['baseline_bytes']=0; item['incremental_peak_bytes']=absolute
                if charge_role=='authority_helper': git_peak=max(git_peak,absolute)
                elif item.get('parent',identities.get(pid,{}).get('parent'))==os.getpid(): outer_observer=max(outer_observer,absolute)
                else: inner_observer=max(inner_observer,absolute)
            elif pid in native_roles and (role!='pending_baseline' or final):
                item['baseline_bytes']=0; item['incremental_peak_bytes']=absolute
                if pid==process.pid: unresolved_root=absolute
                else: unresolved_peak+=absolute
            else: item['baseline_bytes']=None
        if phase['started']:
            end=phase.get('end',float('inf'))
            authority_worker=max((rss for before,after,rss in root_samples if after>=phase['start'] and before<=end),default=0)
            authority_peak=max(authority_peak,authority_worker+git_peak)
            item=per_worker.get(str(process.pid))
            if item is not None: item['authority_phase_peak_bytes']=authority_worker
        overhead_peak=max(overhead_peak,outer_observer+inner_observer)
        # These conservative peaks may come from different instants; no sampled
        # worker/helper evidence is discarded when its declaration arrives late.
        incremental_peak=max(incremental_peak,max(worker_peak,authority_peak,unresolved_root)+overhead_peak+unresolved_peak)
    with (output/'stdout.log').open('wb') as stdout,(output/'stderr.log').open('wb') as stderr:
        process=subprocess.Popen(command,cwd=output,stdout=stdout,stderr=stderr,start_new_session=True,close_fds=True)
        try:
            while process.poll() is None:
                if time.monotonic()>=deadline: reason='outer timeout'; break
                if charged_bytes()>output_bytes-4096: reason='output cap'; break
                if shutil.disk_usage(output).free<free_disk_bytes: reason='disk free prerequisite'; break
                read_events(); reconcile()
                if candidate_start is not None and time.monotonic()-candidate_start>=90:
                    reason='candidate timeout'; break
                before=time.monotonic()
                applicable=min(deadline,candidate_start+90 if candidate_start is not None else deadline)
                if sampler is process_tree:
                    if native_runtime is None: native_runtime=authority.runtime()
                    readings=sampler(process.pid,authority_root=authority_root,deadline=applicable,runtime_identity=native_runtime)
                else: readings=sampler(process.pid)
                after=time.monotonic()
                observed=getattr(readings,'processes',{})
                native={pid:entry for pid,entry in observed.items() if 'raw_args' in entry}
                if native: retain_native(native)
                identities.update({pid:entry for pid,entry in observed.items() if 'raw_args' not in entry})
                peak=max(peak,sum(readings.values()))
                if process.pid in readings: root_samples.append((before,after,readings[process.pid]))
                for pid,rss in readings.items():
                    item=per_worker.setdefault(str(pid),dict(absolute_peak_bytes=0,incremental_peak_bytes=0,baseline_bytes=None))
                    item['absolute_peak_bytes']=max(item['absolute_peak_bytes'],rss)
                    if pid in observed: item['parent']=observed[pid]['parent']
                # All numeric RSS is retained before events or identity resolution.
                if native and native_runtime is None: native_runtime=authority.runtime()
                for entry in getattr(readings,'declarations',{}).values(): declaration(declarations,entry)
                read_events()
                # A completed helper observed during this sampling interval is
                # historical, not an authority exception extending past phase end.
                live={pid for pid in readings if phase['ends'].get(pid,float('-inf'))<before}
                sampled_phase=dict(phase,active=phase['started'] and after>=phase.get('start',float('inf')) and before<=phase.get('end',float('inf')))
                roles=classify(process.pid,identities|native,baselines,declarations,authority_phase=sampled_phase,current_pids=live,
                               stage_vector=command,reader_context=reader_context(before,after),runtime_identity=native_runtime)
                for pid in readings:
                    if roles.get(pid)=='authority_helper': per_worker[str(pid)]['sampled_authority_helper']=True
                reconcile()
                if any(roles.get(pid)=='unaccounted' for pid in readings): reason='foreign process identity'; break
                if incremental_peak>incremental_bytes: reason='incremental worker memory cap'; break
                time.sleep(.02)
        except ObserverFailure as exc:
            reason=str(exc); monitor_failure=exc.evidence
        except Exception as exc:
            reason='monitor common failure'; monitor_failure=dict(type=type(exc).__name__,message=str(exc))
        finally:
            try: os.killpg(process.pid,signal.SIGKILL)
            except ProcessLookupError: pass
            process.wait(timeout=1)
    try: read_events(); reconcile(final=True)
    except Exception as exc:
        if reason is None: reason='monitor common failure'
        monitor_failure=dict(type=type(exc).__name__,message=str(exc))
    if monitor_failure is not None and native_samples:
        # Failed event/identity reconciliation never erases a numeric charge.
        native_pids={pid for batch in native_samples for pid in batch}
        for pid in native_pids:
            item=per_worker[str(pid)]; item['baseline_bytes']=0
            item['incremental_peak_bytes']=item['absolute_peak_bytes']
        incremental_peak=max(incremental_peak,sum(per_worker[str(pid)]['absolute_peak_bytes'] for pid in native_pids))
    if incremental_peak>incremental_bytes and reason is None: reason='incremental worker memory cap'
    unresolved=[pid for pid in per_worker if final_roles.get(int(pid)) not in ('worker','observer_helper','authority_helper')]
    if unresolved and reason is None: reason='missing post-import worker baseline or unresolved declaration'
    if phase['started'] and (phase['active'] or not phase.get('success')) and reason is None: reason='authority verification incomplete/failed'
    result=dict(status='STOPPED' if reason or process.returncode else 'COMPLETED',reason=reason,
                monitor_failure=monitor_failure,runtime_identity=native_runtime,
                process_samples=[entry for batch in native_samples for entry in batch.values()],
                source_launch_witnesses=launch_witnesses,
                stage_launch_vector_sha256=commands.vector_hash(command),
                argv_observation='exact source-generated expected native display; not arbitrary argv-byte certification',
                returncode=process.returncode,outer_seconds=time.monotonic()-start,utc_start_epoch=utc,
                utc_end_epoch=time.time(),absolute_process_tree_peak_bytes=peak,incremental_worker_peak_bytes=incremental_peak,
                workers=per_worker,observer_helper_peak_bytes=overhead_peak,
                observer_helper_charge='full RSS, baseline zero; conservative observed helper peaks added to worker peak',
                authority_phase=dict(phase,completed=sorted(phase['completed'])),authority_full_rss_peak_bytes=authority_peak,
                output_bytes_before_monitor_report=charged_bytes(),timer_resolution=time.get_clock_info('monotonic').resolution,
                rss_poll_seconds=.02,rss_scope='sampled resident memory; not allocator peak',missing_worker_baselines=unresolved)
    raw=json.dumps(result,indent=2)+'\n'
    if charged_bytes()+len(raw.encode())>output_bytes and reason is None:
        result.update(status='STOPPED',reason='output cap including final monitor report')
        raw=json.dumps(result,indent=2)+'\n'
    # One final serialization after any verdict change, one durable write.
    (output/'monitor.json').write_text(raw)
    return result
