"""Whole-process-group timeout, RSS and output cap. No scientific imports."""
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


def classify(root_pid,processes,baselines,declarations,*,authority_phase=None,current_pids=None,stage_vector=None,reader_context=None):
    phase=authority_phase or dict(active=False,declarations={},completed=set(),commands=[])
    expected={pid for pid,entry in processes.items() if
             Path(entry['executable']).resolve()==Path(sys.executable).resolve() and
             entry['parent']==(os.getpid() if pid==root_pid else root_pid) and
             (commands.matches(entry['argv'],stage_vector) if pid==root_pid else commands.reader_vector(entry['argv'],reader_context) is not None)}
    roles={}
    for pid,entry in processes.items():
        if pid in expected:
            roles[pid]=('authority_worker' if pid==root_pid and phase['active'] else
                        ('worker' if pid in baselines else 'pending_baseline'))
            continue
        git_entry=phase['declarations'].get(pid)
        exact_git=(entry['parent']==root_pid and entry['executable']==authority.GIT and entry['argv'] in phase['commands'])
        if exact_git and phase['active']:
            roles[pid]='authority_helper' if git_entry==entry else 'pending_authority_declaration'; continue
        if exact_git and git_entry==entry and pid in phase.get('completed',set()) and current_pids is not None and pid not in current_pids:
            roles[pid]='authority_helper'; continue
        declared=declarations.get(pid)
        exact_observer=(entry['executable']==PS and entry['argv']==PS_ARGV and
                        (entry['parent']==os.getpid() or entry['parent'] in expected))
        roles[pid]=('observer_helper' if declared==entry else 'pending_observer_declaration') if exact_observer else 'unaccounted'
    return roles


def process_tree(pid,*,observer_log=None,authority_root=None,deadline=None):
    """Native ps RSS is KiB on this host; retain every descendant separately."""
    started=time.monotonic()
    deadline=min(deadline if deadline is not None else started+1,started+1)
    if deadline<=started: raise ObserverFailure('observer timeout')
    probe=subprocess.Popen(PS_ARGV,stdout=subprocess.PIPE,text=True,close_fds=True)
    try:
        own_observer=dict(pid=probe.pid,parent=os.getpid(),executable=PS,argv=PS_ARGV)
        if observer_log is not None:
            with Path(observer_log).open('a') as stream:
                stream.write(json.dumps(dict(event='observer_helper',pid=probe.pid,parent=os.getpid(),
                                             executable=PS,argv=PS_ARGV))+'\n'); stream.flush()
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
        if probe.stdout is not None: probe.stdout.close()
    table={}; identities={}
    for line in raw.splitlines():
        a,b,c,executable,args=line.split(None,4); p=int(a)
        table[p]=(int(b),int(c)*1024)
        commands=[PS_ARGV]+(authority.git_commands(authority_root) if authority_root is not None else [])
        identities[p]=dict(pid=p,parent=int(b),executable=executable,
                           argv=next((cmd for cmd in commands if args==' '.join(cmd)),[args]))
    selected={pid}; previous=set()
    while previous!=selected:
        previous=set(selected)
        selected|={p for p,(parent,rss) in table.items() if parent in selected}
    selected.add(probe.pid)  # charge this sampler's own native observer in full
    return ResidentTree({p:table[p][1] for p in selected if p in table},
                        {p:identities[p] for p in selected if p in table},{probe.pid:own_observer})


def directory_bytes(path):
    # Include logs, incomplete files, failure artifacts, baseline events and temps.
    return sum(p.stat().st_size for p in Path(path).rglob('*') if p.is_file())


def record_baseline(path,*,deadline=None):
    pid=os.getpid(); rss=process_tree(pid,observer_log=path,deadline=deadline)[pid]
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
    root_samples=[]; candidate_ranges=[]; incremental_peak=0; overhead_peak=0; authority_peak=0; final_roles={}
    phase=dict(active=False,declarations={},completed=set(),ends={},
               commands=authority.git_commands(authority_root) if authority_root is not None else [],started=False)
    def charged_bytes():
        return directory_bytes(output)+(directory_bytes(preparation_output) if preparation_output is not None else 0)
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
                elif kind=='observer_helper': declarations[event['pid']]={k:event[k] for k in ('pid','parent','executable','argv')}
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
                    entry={k:event[k] for k in ('pid','parent','executable','argv')}
                    if not phase['active'] or entry['parent']!=process.pid or entry['executable']!=authority.GIT or entry['argv'] not in phase['commands'] or entry['pid'] in phase['declarations']:
                        raise ValueError('undeclared authority identity/operation')
                    phase['declarations'][event['pid']]=entry
                elif kind=='authority_helper_end':
                    if not phase['active'] or event['pid'] not in phase['declarations'] or event['parent']!=process.pid:
                        raise ValueError('invalid authority helper lifetime')
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
    def reconcile():
        nonlocal incremental_peak,overhead_peak,authority_peak,final_roles
        # Historical identities remain attributable after their exact lifetime.
        historical=dict(phase,active=False)
        final_roles=classify(process.pid,identities,baselines,declarations,authority_phase=historical,current_pids=set(),stage_vector=command,reader_context=reader_context())
        worker_peak=0; outer_observer=0; inner_observer=0; git_peak=0
        for pid_text,item in per_worker.items():
            pid=int(pid_text); role=final_roles.get(pid,'pending_baseline'); item['role']=role
            absolute=item['absolute_peak_bytes']
            if role=='worker':
                item['baseline_bytes']=baselines[pid]
                item['incremental_peak_bytes']=max(0,absolute-baselines[pid])
                worker_peak=max(worker_peak,item['incremental_peak_bytes'])
            elif role in ('observer_helper','authority_helper'):
                item['baseline_bytes']=0; item['incremental_peak_bytes']=absolute
                if role=='authority_helper': git_peak=max(git_peak,absolute)
                elif identities[pid]['parent']==os.getpid(): outer_observer=max(outer_observer,absolute)
                else: inner_observer=max(inner_observer,absolute)
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
        incremental_peak=max(incremental_peak,max(worker_peak,authority_peak)+overhead_peak)
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
                readings=sampler(process.pid,authority_root=authority_root,deadline=applicable) if sampler is process_tree else sampler(process.pid)
                after=time.monotonic(); read_events()
                identities.update(getattr(readings,'processes',{})); declarations.update(getattr(readings,'declarations',{}))
                peak=max(peak,sum(readings.values()))
                if process.pid in readings: root_samples.append((before,after,readings[process.pid]))
                for pid,rss in readings.items():
                    item=per_worker.setdefault(str(pid),dict(absolute_peak_bytes=0,incremental_peak_bytes=0,baseline_bytes=None))
                    item['absolute_peak_bytes']=max(item['absolute_peak_bytes'],rss)
                # A completed helper observed during this sampling interval is
                # historical, not an authority exception extending past phase end.
                live={pid for pid in readings if phase['ends'].get(pid,float('-inf'))<before}
                sampled_phase=dict(phase,active=phase['started'] and after>=phase.get('start',float('inf')) and before<=phase.get('end',float('inf')))
                roles=classify(process.pid,identities,baselines,declarations,authority_phase=sampled_phase,current_pids=live,
                               stage_vector=command,reader_context=reader_context(before,after))
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
    try: read_events(); reconcile()
    except Exception as exc:
        if reason is None: reason='monitor common failure'
        monitor_failure=dict(type=type(exc).__name__,message=str(exc))
    if incremental_peak>incremental_bytes and reason is None: reason='incremental worker memory cap'
    unresolved=[pid for pid in per_worker if final_roles.get(int(pid)) not in ('worker','observer_helper','authority_helper')]
    if unresolved and reason is None: reason='missing post-import worker baseline or unresolved declaration'
    if phase['started'] and (phase['active'] or not phase.get('success')) and reason is None: reason='authority verification incomplete/failed'
    result=dict(status='STOPPED' if reason or process.returncode else 'COMPLETED',reason=reason,
                monitor_failure=monitor_failure,
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
