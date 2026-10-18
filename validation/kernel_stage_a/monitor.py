"""Whole-process-group timeout, RSS and output cap. No scientific imports."""
import json
import os
from pathlib import Path
import selectors
import shutil
import signal
import subprocess
import time

PS='/bin/ps'
PS_ARGV=[PS,'-axo','pid=,ppid=,rss=,comm=,args=']


class ResidentTree(dict):
    def __init__(self,readings,processes,declarations=None):
        super().__init__(readings); self.processes=processes; self.declarations=declarations or {}


def classify(root_pid,processes,baselines,declarations):
    roles={}
    for pid,entry in processes.items():
        if pid in baselines: roles[pid]='worker'; continue
        declared=declarations.get(pid)
        roles[pid]='observer_helper' if (declared is not None and entry==declared and
            entry['executable']==PS and entry['argv']==PS_ARGV and
            (entry['parent']==os.getpid() or (entry['parent'] in baselines and
            (entry['parent']==root_pid or processes.get(entry['parent'],{}).get('parent')==root_pid)))) else 'unaccounted'
    return roles


def process_tree(pid,*,observer_log=None):
    """Native ps RSS is KiB on this host; retain every descendant separately."""
    with subprocess.Popen(PS_ARGV,stdout=subprocess.PIPE,text=True,close_fds=True) as probe:
        own_observer=dict(pid=probe.pid,parent=os.getpid(),executable=PS,argv=PS_ARGV)
        if observer_log is not None:
            with Path(observer_log).open('a') as stream:
                stream.write(json.dumps(dict(event='observer_helper',pid=probe.pid,parent=os.getpid(),
                                             executable=PS,argv=PS_ARGV))+'\n'); stream.flush()
        raw=probe.communicate()[0]
        if probe.returncode: raise subprocess.CalledProcessError(probe.returncode,PS_ARGV)
    table={}; identities={}
    for line in raw.splitlines():
        a,b,c,executable,args=line.split(None,4); p=int(a)
        table[p]=(int(b),int(c)*1024)
        identities[p]=dict(pid=p,parent=int(b),executable=executable,
                           argv=PS_ARGV if args==' '.join(PS_ARGV) else [args])
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


def record_baseline(path):
    pid=os.getpid(); rss=process_tree(pid,observer_log=path)[pid]
    record=dict(event='baseline',pid=pid,rss=rss,monotonic=time.monotonic(),utc_epoch=time.time(),
                boundary='post-import/pre-allocation')
    with Path(path).open('a') as f:
        f.write(json.dumps(record)+'\n'); f.flush()
    return record


def supervise(command,output,*,outer_seconds=600,output_bytes=67108864,free_disk_bytes=4294967296,
              incremental_bytes=201326592,sampler=process_tree,preparation_output=None):
    """Sequential root worker; terminate AND reap its group on every stop."""
    output=Path(output)
    if output.exists(): raise ValueError('output must be fresh')
    if shutil.disk_usage(output.parent).free<free_disk_bytes: raise ValueError('disk entry condition')
    output.mkdir(); start=time.monotonic(); utc=time.time(); reason=None; peak=0; incremental_peak=0
    def charged_bytes():
        return directory_bytes(output)+(directory_bytes(preparation_output) if preparation_output is not None else 0)
    baselines={}; per_worker={}; candidate_start=None; event_offset=0; declarations={}; identities={}
    overhead_peak=0
    def read_events():
        nonlocal event_offset,candidate_start
        events=output/'monitor-events.jsonl'
        if not events.exists(): return
        with events.open() as stream:
            stream.seek(event_offset)
            for line in stream:
                event=json.loads(line)
                if event['event']=='baseline': baselines[event['pid']]=event['rss']
                elif event['event']=='observer_helper': declarations[event['pid']]={k:event[k] for k in ('pid','parent','executable','argv')}
                elif event['event']=='candidate_start': candidate_start=event['monotonic']
                elif event['event']=='candidate_end': candidate_start=None
            event_offset=stream.tell()
    with (output/'stdout.log').open('wb') as stdout,(output/'stderr.log').open('wb') as stderr:
        process=subprocess.Popen(command,cwd=output,stdout=stdout,stderr=stderr,start_new_session=True,close_fds=True)
        try:
            while process.poll() is None:
                elapsed=time.monotonic()-start
                if elapsed>=outer_seconds: reason='outer timeout'; break
                if charged_bytes()>output_bytes-4096: reason='output cap'; break
                if shutil.disk_usage(output).free<free_disk_bytes: reason='disk free prerequisite'; break
                read_events()
                if candidate_start is not None and time.monotonic()-candidate_start>=90:
                    reason='candidate timeout'; break
                readings=sampler(process.pid)
                identities.update(getattr(readings,'processes',{}))
                declarations.update(getattr(readings,'declarations',{}))
                roles=classify(process.pid,identities,baselines,declarations)
                peak=max(peak,sum(readings.values()))
                helper_rss=sum(rss for pid,rss in readings.items() if roles.get(pid)=='observer_helper')
                active_worker_increment=0
                for pid,rss in readings.items():
                    item=per_worker.setdefault(str(pid),dict(absolute_peak_bytes=0,incremental_peak_bytes=0,baseline_bytes=None))
                    item['absolute_peak_bytes']=max(item['absolute_peak_bytes'],rss)
                    if pid in baselines:
                        item['baseline_bytes']=baselines[pid]
                        item['incremental_peak_bytes']=max(item['incremental_peak_bytes'],rss-baselines[pid])
                        active_worker_increment=max(active_worker_increment,max(0,rss-baselines[pid]))
                    elif roles.get(pid)=='observer_helper':
                        item.update(baseline_bytes=0,role='observer_helper')
                        item['incremental_peak_bytes']=max(item['incremental_peak_bytes'],rss)
                # Late declarations must charge already-observed short probes.
                outer_helper_peak=max((item['absolute_peak_bytes'] for pid,item in per_worker.items()
                      if roles.get(int(pid))=='observer_helper' and identities[int(pid)]['parent']==os.getpid()),default=0)
                inner_helper_peak=max((item['absolute_peak_bytes'] for pid,item in per_worker.items()
                      if roles.get(int(pid))=='observer_helper' and identities[int(pid)]['parent']!=os.getpid()),default=0)
                overhead_peak=max(overhead_peak,helper_rss,outer_helper_peak+inner_helper_peak)
                worker_peak=max((item['incremental_peak_bytes'] for pid,item in per_worker.items()
                                 if roles.get(int(pid))!='observer_helper'),default=0)
                incremental_peak=max(incremental_peak,worker_peak+overhead_peak)
                if incremental_peak>incremental_bytes: reason='incremental worker memory cap'; break
                time.sleep(.02)
        except BaseException:
            os.killpg(process.pid,signal.SIGKILL); process.wait(); raise
        finally:
            # Also kill any orphaned descendants after an otherwise normal exit.
            try: os.killpg(process.pid,signal.SIGKILL)
            except ProcessLookupError: pass
            process.wait()
    read_events()
    final_roles=classify(process.pid,identities,baselines,declarations)
    for pid,item in per_worker.items():
        if int(pid) in baselines: item['baseline_bytes']=baselines[int(pid)]
        elif final_roles.get(int(pid))=='observer_helper': item.update(baseline_bytes=0,role='observer_helper')
    result=dict(status='STOPPED' if reason or process.returncode else 'COMPLETED',reason=reason,
                returncode=process.returncode,outer_seconds=time.monotonic()-start,utc_start_epoch=utc,
                utc_end_epoch=time.time(),absolute_process_tree_peak_bytes=peak,
                incremental_worker_peak_bytes=incremental_peak,workers=per_worker,
                observer_helper_peak_bytes=overhead_peak,observer_helper_charge='full RSS, baseline zero; conservative observed helper peak added to worker peak',
                output_bytes_before_monitor_report=charged_bytes(),timer_resolution=time.get_clock_info('monotonic').resolution,
                rss_poll_seconds=.02,rss_scope='sampled resident memory; not allocator peak',
                missing_worker_baselines=[pid for pid,v in per_worker.items() if v['baseline_bytes'] is None and
                     classify(process.pid,identities,baselines,declarations).get(int(pid))!='observer_helper'])
    if result['missing_worker_baselines'] and not reason:
        result.update(status='STOPPED',reason='missing post-import worker baseline')
    (output/'monitor.json').write_text(json.dumps(result,indent=2)+'\n')
    if charged_bytes()>output_bytes and not reason:
        result.update(status='STOPPED',reason='output cap including final monitor report')
    return result
