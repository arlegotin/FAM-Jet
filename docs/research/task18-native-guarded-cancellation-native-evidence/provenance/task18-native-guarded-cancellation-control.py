"""Static diagnostic input: imported-runtime guarded cancellation; allocate separately."""
import time
ALLOCATION_START=time.monotonic()
ABSOLUTE_DEADLINE=ALLOCATION_START+10
import ast
import hashlib
import json
import os
from pathlib import Path
import socket
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from validation.kernel_stage_a import authority, commands, monitor


def require(condition,message):
    if not condition: raise AssertionError(message)


def main():
    parent_path=Path(__file__).resolve()
    worker_path=(ROOT/'docs/research/task18-owned-root-lifecycle-native-worker.py').resolve()
    parent_bytes=parent_path.read_bytes(); worker_bytes=worker_path.read_bytes()
    ast.parse(parent_bytes); ast.parse(worker_bytes)
    inputs=dict(parent_path=str(parent_path),parent_sha256=hashlib.sha256(parent_bytes).hexdigest(),
                parent_bytes=len(parent_bytes),worker_path=str(worker_path),
                worker_sha256=hashlib.sha256(worker_bytes).hexdigest(),worker_bytes=len(worker_bytes),
                parent_ast_parse=True,worker_ast_parse=True,
                monitor_path=str(Path(monitor.__file__).resolve()),
                monitor_sha256=hashlib.sha256(Path(monitor.__file__).read_bytes()).hexdigest())
    destination=Path(sys.argv[1]).resolve()
    destination.mkdir(exist_ok=False)
    case_start=time.monotonic(); case_deadline=min(case_start+4.5,ABSOLUTE_DEADLINE-.25)
    record=dict(case='survivor',start=case_start,deadline=case_deadline,syscalls=[],fallback_cleanup=False)
    result=dict(allocation_start=ALLOCATION_START,absolute_deadline=ABSOLUTE_DEADLINE,
                scope='ONE imported-runtime native guarded-cancellation diagnostic; zero factors/reads',
                source_git=os.environ['TASK18_SOURCE_GIT'],control_sha256=inputs['parent_sha256'],
                inputs=inputs,cases=[record])
    listener=None; peer=None; peer_path=destination/'survivor.socket'
    try:
        require(case_deadline>case_start,'original control allocation exhausted')
        require(inputs['worker_sha256']=='da9819fb58547721371a65930c76101fe5344ad8d2a291ea88b782b007d5b8e5',
                'frozen worker hash changed')
        listener=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM)
        listener.bind(str(peer_path)); listener.listen(1)
        vector=[sys.executable,'-I','-B',str(worker_path),'survivor',str(peer_path),repr(case_deadline)]
        vector_sha256=commands.vector_hash(vector)
        record.update(vector=vector,vector_sha256=vector_sha256,inputs=dict(inputs))
        output=destination/'survivor-output'
        verdict=monitor.supervise(vector,output,outer_seconds=case_deadline-case_start,
                                 deadline=case_deadline)
        record.update(execution_status=verdict['status'],verdict=verdict)
        artifacts={}
        for name in ('monitor.json','monitor-evidence.jsonl','monitor-events.jsonl','stdout.log','stderr.log'):
            body=(output/name).read_bytes()
            artifacts[name]=dict(bytes=len(body),sha256=hashlib.sha256(body).hexdigest())
        record['artifacts']=artifacts
        records=[json.loads(line) for line in (output/'monitor-evidence.jsonl').read_text().splitlines()]
        source_events=[json.loads(line) for line in (output/'monitor-events.jsonl').read_text().splitlines()]
        runtimes=[row['value'] for row in records if row['kind']=='runtime']
        launches=[row['value'] for row in records if row['kind']=='python_root_launch']
        ends=[row['value'] for row in records if row['kind']=='python_root_end']
        memberships=[row for row in records if row['kind']=='cleanup_membership']
        signals=[row for row in records if row['kind']=='cleanup_signal']
        waits=[row for row in records if row['kind']=='cleanup_owner_wait']
        require(len(runtimes)==len(launches)==len(ends)==len(memberships)==len(signals)==len(waits)==1,
                'missing or duplicate runtime/root/query/signal/wait witness')
        runtime=runtimes[0]; launch=launches[0]; end=ends[0]; observed=memberships[0]
        signal=signals[0]; wait=waits[0]; root_pid=launch['pid']
        record.update(runtime=runtime,launch=launch,owning_end=end,signal=signal,
                      owner_wait=wait,membership=observed)
        require(launch['provenance']=='source_owned_python_launch' and launch['role']=='owned_root' and
                launch['parent']==os.getpid() and launch['argv']==vector and
                launch['vector_sha256']==vector_sha256 and launch['executable']==vector[0] and
                launch['launcher']==dict(path=runtime['executable'],sha256=runtime['executable_sha256']) and
                launch['expected_image']==runtime['process_image'] and launch['reaped'] is False and
                isinstance(launch['launch_id'],str) and bool(launch['launch_id']),
                'root launch generation/source/runtime mismatch')
        require(verdict['stage_launch_vector_sha256']==vector_sha256 and
                verdict['source_event_accounting']['complete'] is True and
                verdict['source_event_accounting']['identity_complete'] is True and
                verdict['source_event_accounting']['status']=='COMPLETE' and
                verdict['evidence']['rejected_raw_complete'] is True and
                verdict['evidence']['rejected_observations']==0,
                'incomplete source/vector accounting')
        require(verdict['status']=='STOPPED' and verdict['reason']=='foreign process identity' and
                verdict['monitor_failure'] is None and not verdict['cleanup_diagnostics'] and
                verdict['returncode']==end['returncode'] and
                type(verdict['incremental_worker_peak_bytes']) is int and
                0<=verdict['incremental_worker_peak_bytes']<=201326592 and
                type(verdict['output_bytes_before_monitor_report']) is int and
                0<=verdict['output_bytes_before_monitor_report']<=67108864 and
                verdict['outer_seconds']<=4.5,
                'monitor STOPPED/cost/bound accounting mismatch')
        require(end['pid']==root_pid and end['parent']==launch['parent'] and
                end['launch_id']==launch['launch_id'] and end['reaped'] is True and
                type(end['returncode']) is int and end['returncode'] in (0,-9) and
                launch['launch_start']<=end['completion_end'],
                'wrong owning completion or returncode')
        require(observed['owner_pid']==root_pid and observed['owner_unreaped'] is True and
                observed['value']['complete'] is True and
                observed['value']['start']<=observed['value']['end']<=wait['start'],
                'membership was not complete under unreaped owner')
        require(signal['pid']==root_pid and signal['signal']==9 and signal['success'] is True and
                signal['owner_unreaped'] is True and signal.get('absent') is not True and
                wait['reaped'] is True and wait['returncode']==end['returncode'] and
                wait['end']<=end['completion_end'] and
                records.index(observed)<records.index(signal)<records.index(waits[0])<
                next(i for i,row in enumerate(records) if row['kind']=='python_root_end'),
                'missing successful owned SIGKILL before owning end')
        members=[row for row in observed['value']['rows'] if row['pgid']==root_pid]
        require(len(members) in (1,2) and all(type(row['rss_bytes']) is int and row['rss_bytes']>=0
                                               for row in members),
                'invalid numeric membership or RSS')
        roots=[row for row in members if row['pid']==root_pid]
        require(len(roots)<=1 and all(row['parent']==launch['parent'] for row in roots),
                'invalid root row in membership')
        record.update(root_pid=root_pid,member_rows=members,
                      membership_root_rss_bytes=roots[0]['rss_bytes'] if roots else None)
        membership_index=records.index(observed)
        samples=[row for row in records[:membership_index]
                 if row['kind']=='sample' and row.get('origin')=='owned_supervisor']
        proof_rows=[(sample,row) for sample in samples for row in sample['processes']
                    if row['pid']==root_pid and row['parent']==launch['parent'] and
                    not row.get('ambiguous') and
                    row.get('raw_args')==commands.native_display(vector,runtime) and
                    row.get('image',{}).get('status')=='ok' and
                    all(row['image'].get(k)==runtime['process_image'][k] for k in ('path','sha256')) and
                    launch['launch_start']<=row['sample_start']<=row['sample_end']<=
                    row['image']['lookup_start']<=row['image']['lookup_end']<end['completion_end']]
        require(bool(proof_rows),'missing genuine earlier owned live root proof')
        record['owned_live_proof']=dict(sample_id=proof_rows[0][0]['sample_id'],row=proof_rows[0][1])
        latest=samples[-1]
        latest_root=[row for row in latest['processes'] if row['pid']==root_pid]
        if latest_root:
            require(len(latest_root)==1 and type(latest_root[0]['rss_bytes']) is int and
                    latest_root[0]['rss_bytes']>=0,'invalid latest root RSS')
            record['latest_owned_root']=dict(sample_id=latest['sample_id'],row=latest_root[0])
        baselines=[row for row in source_events if row['event']=='baseline' and row['pid']==root_pid]
        selves=[row for row in source_events if row['event']=='observer_sample' and
                row.get('emitter_pid')==row.get('self_pid')==root_pid]
        require(len(baselines)==len(selves)==1,'real record_baseline SELF path required')
        own=[row for row in selves[0]['processes'] if row['pid']==root_pid]
        require(len(own)==1 and own[0]['parent']==launch['parent'] and
                type(own[0]['rss_bytes']) is int and own[0]['rss_bytes']>=0 and
                own[0]['rss_bytes']==baselines[0]['rss'] and
                baselines[0]['boundary']=='post-import/pre-allocation' and
                own[0]['image']['status']=='ok' and
                all(own[0]['image'].get(k)==runtime['process_image'][k] for k in ('path','sha256')) and
                launch['launch_start']<=own[0]['sample_start']<=own[0]['sample_end']<=
                own[0]['image']['lookup_start']<=own[0]['image']['lookup_end']<=
                baselines[0]['monotonic']<end['completion_end'],
                'imported-runtime SELF/baseline generation mismatch')
        record.update(baseline=baselines[0],self_event=selves[0])
        listener.settimeout(max(0,case_deadline-time.monotonic()))
        peer,_=listener.accept()
        read_start=time.monotonic(); peer.settimeout(max(0,case_deadline-read_start))
        raw=bytearray(); eof=False
        try:
            while len(raw)<=4096:
                part=peer.recv(min(4097-len(raw),4096))
                if not part: eof=True; break
                raw.extend(part)
        finally:
            read_end=time.monotonic()
            record['peer_read']=dict(start=read_start,end=read_end,raw=bytes(raw).decode('latin1'),eof=eof)
        require(eof and len(raw)<=4096 and raw.endswith(b'\n') and raw.count(b'\n')==1 and
                read_end<case_deadline,'no bounded pre-fallback child line and EOF')
        child=json.loads(raw); record['descendant']=child
        require(type(child['pid']) is int and child['pid']!=root_pid and
                child['parent']==root_pid and child['pgid']==root_pid,
                'frozen sole-fork socket identity mismatch')
        children=[row for row in members if row['pid']==child['pid']]
        require(len(children)==1 and len(members)==len(roots)+1 and
                children[0]['pgid']==child['pgid'],
                'socket child missing from sole numeric group member')
        record['child_query_parent']=children[0]['parent']
        record['child_socket_parent']=child['parent']
        for operation,call in [('image',lambda:authority.process_image(child['pid'])),
                               ('getpgid',lambda:os.getpgid(child['pid'])),
                               ('nonowner_waitpid',lambda:os.waitpid(child['pid'],os.WNOHANG))]:
            before=time.monotonic()
            try: outcome=dict(ok=True,value=call())
            except OSError as exc: outcome=dict(ok=False,type=type(exc).__name__,errno=exc.errno,message=str(exc))
            record['syscalls'].append(dict(operation=operation,start=before,end=time.monotonic(),**outcome))
        record['descendant_evidence']='actual same-group query + successful owned SIGKILL + sole child socket line/EOF before fallback; no owning orphan reap claimed'
        require(time.monotonic()<case_deadline,'original case bound exhausted')
        record['compatibility']='PASS'
    except Exception as exc:
        record.update(compatibility='NEEDS_CONTEXT',error=dict(type=type(exc).__name__,message=str(exc)[:600]))
        record['fallback_cleanup']=True
        # Closing an accepted peer lets the trusted survivor exit. This is unsuccessful.
        if peer is None and listener is not None:
            try:
                listener.settimeout(max(0,min(.1,ABSOLUTE_DEADLINE-time.monotonic())))
                peer,_=listener.accept()
            except OSError as cleanup_exc: record['fallback_error']=str(cleanup_exc)
    finally:
        if peer is not None: peer.close()
        if listener is not None: listener.close()
        if peer_path.exists(): peer_path.unlink()
        record['end']=time.monotonic(); record['elapsed']=record['end']-case_start
    result['end']=time.monotonic(); result['elapsed']=result['end']-ALLOCATION_START
    result['compatibility']='PASS' if record['compatibility']=='PASS' and not record['fallback_cleanup'] and result['end']<ABSOLUTE_DEADLINE else 'NEEDS_CONTEXT'
    (destination/'native-result.json').write_text(json.dumps(result,indent=2)+'\n')
    result['artifact_commit_end']=time.monotonic()
    if result['artifact_commit_end']>=ABSOLUTE_DEADLINE:
        result['compatibility']='NEEDS_CONTEXT'; result['overrun']=True
        (destination/'native-result.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(compatibility=result['compatibility'],elapsed=result['elapsed'],destination=str(destination))))
    return 0 if result['compatibility']=='PASS' else 1


if __name__=='__main__': raise SystemExit(main())
