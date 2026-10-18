"""FROZEN imported-runtime owned-root control; requires a separate native allocation."""
import time
ALLOCATION_START=time.monotonic()
ABSOLUTE_DEADLINE=ALLOCATION_START+10
import ast
import errno
import hashlib
import json
import os
from pathlib import Path
import select
import socket
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from validation.kernel_stage_a import authority, commands, monitor



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
    result=dict(allocation_start=ALLOCATION_START,absolute_deadline=ABSOLUTE_DEADLINE,
                scope='ONE imported-runtime native two-case owned-root lifecycle integration; zero factors/reads',cases=[],
                source_git=os.environ['TASK18_SOURCE_GIT'],control_sha256=inputs['parent_sha256'],inputs=inputs)
    for case in ('empty','survivor'):
        case_start=time.monotonic(); case_deadline=min(case_start+4.5,ABSOLUTE_DEADLINE-.25)
        record=dict(case=case,start=case_start,deadline=case_deadline,syscalls=[],fallback_cleanup=False)
        result['cases'].append(record)
        listener=None; peer=None
        try:
            if case_deadline<=case_start: raise TimeoutError('original control allocation exhausted')
            peer_path=destination/(case+'.socket')
            if case=='survivor':
                listener=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM)
                listener.bind(str(peer_path)); listener.listen(1)
            vector=[sys.executable,'-I','-B',str(worker_path),case,str(peer_path),repr(case_deadline)]
            record.update(vector=vector,vector_sha256=commands.vector_hash(vector),inputs=dict(inputs))
            verdict=monitor.supervise(vector,destination/(case+'-output'),outer_seconds=case_deadline-case_start,
                                     deadline=case_deadline)
            record['execution_status']=verdict['status']; record['verdict']=verdict
            records=[json.loads(line) for line in (destination/(case+'-output')/'monitor-evidence.jsonl').read_text().splitlines()]
            launches=[row['value'] for row in records if row['kind']=='python_root_launch']
            ends=[row['value'] for row in records if row['kind']=='python_root_end']
            memberships=[row for row in records if row['kind']=='cleanup_membership']
            signals=[row for row in records if row['kind']=='cleanup_signal']
            if len(launches)!=1 or len(ends)!=1 or len(memberships)!=1:
                raise AssertionError('missing/duplicate actual root/query witnesses')
            root_pid=launches[0]['pid']; observed=memberships[0]
            members=[row for row in observed['value']['rows'] if row['pgid']==root_pid]
            record.update(root_pid=root_pid,member_rows=members)
            assert observed['owner_unreaped'] and observed['value']['complete']
            assert ends[0]['launch_id']==launches[0]['launch_id'] and ends[0]['reaped'] and type(ends[0]['returncode']) is int
            assert ends[0]['returncode']==0,'after-exit control requires actual natural root returncode0'
            proofs=[entry for row in records if row['kind']=='sample' for entry in row['processes']
                    if entry['pid']==root_pid and entry.get('image',{}).get('status')=='ok']
            assert proofs and max(row['image']['lookup_end'] for row in proofs)<ends[0]['completion_end']
            root_members=[row for row in members if row['pid']==root_pid]
            terminal_route=None
            if root_members:
                assert len(root_members)==1 and type(root_members[0]['rss_bytes']) is int and root_members[0]['rss_bytes']==0
                membership_index=records.index(observed)
                samples=[row for row in records[:membership_index] if row['kind']=='sample' and row.get('origin')=='owned_supervisor']
                assert samples,'missing actual owning-supervisor sample'
                current=samples[-1]
                roots=[row for row in current['processes'] if row['pid']==root_pid]
                assert len(roots)==1 and roots[0]['rss_bytes']==0
                raw_root=roots[0]; native=raw_root['image']
                assert native['status']=='error' and native['method']=='macos.proc_pidpath'
                assert native['reason']=='native_lookup_failed' and native['errno']==errno.ESRCH
                assert raw_root['sample_start']<=raw_root['sample_end']<=native['lookup_start']<=native['lookup_end']
                if case=='empty':
                    resolved=[row for row in records if row['kind']=='resolution' and row['sample_id']==current['sample_id']]
                    assert resolved,'missing actual terminal attribution resolution'
                    attribution=resolved[-1]['identities'][str(root_pid)]
                    assert resolved[-1]['roles'][str(root_pid)]=='worker'
                    assert attribution['image_evidence']=='unavailable_exited'
                    assert attribution['terminal_attribution']=='source_owned_root_lifecycle'
                    assert attribution['launch_id']==launches[0]['launch_id']
                    proof=attribution['proof']
                    assert proof['origin']=='unreaped_owned_root' and proof['lookup_end']<raw_root['sample_start']
                    proof_samples=[row for row in records if row['kind']=='sample' and row['sample_id']==proof['sample_id']]
                    assert len(proof_samples)==1 and proof_samples[0]['origin']=='owned_supervisor'
                    assert attribution['completion']==ends[0]
                    assert attribution['baseline']['boundary']=='post-import/pre-allocation'
                    assert records.index(current)<membership_index<next(i for i,row in enumerate(records) if row['kind']=='python_root_end')<records.index(resolved[-1])
                    terminal_route='source_owned_root_lifecycle'
                else:
                    assert not any(row['kind']=='cleanup_terminal_qualification' for row in records)
            source_events=[json.loads(line) for line in (destination/(case+'-output')/'monitor-events.jsonl').read_text().splitlines()]
            baselines=[row for row in source_events if row['event']=='baseline' and row['pid']==root_pid]
            selves=[row for row in source_events if row['event']=='observer_sample' and row.get('emitter_pid')==row.get('self_pid')==root_pid]
            assert len(baselines)==len(selves)==1,'real record_baseline SELF path required'
            own=[row for row in selves[0]['processes'] if row['pid']==root_pid]
            assert len(own)==1 and own[0]['rss_bytes']==baselines[0]['rss']
            assert own[0]['image']['status']=='ok' and own[0]['image']['lookup_end']<=baselines[0]['monotonic']<ends[0]['completion_end']
            record['baseline']=baselines[0]
            record['terminal_root_route']=terminal_route
            if case=='empty':
                assert not signals and verdict['status']=='COMPLETED',verdict
                if not members:
                    assert any(row['kind']=='cleanup_group_observation' and row['complete'] and row['membership_empty'] for row in records)
                    record['membership_distinction']='literally_empty'
                else:
                    assert len(members)==1 and terminal_route is not None
                    qualifications=[row for row in records if row['kind']=='cleanup_terminal_qualification']
                    assert len(qualifications)==1 and qualifications[0]['qualified_terminal_root_only'] is True
                    assert qualifications[0]['membership_empty'] is False and qualifications[0]['route']==terminal_route
                    record['membership_distinction']='qualified_terminal_root_only'
            else:
                assert verdict['status']!='COMPLETED','survivor must retain unsuccessful accounting'
                assert signals and all(row['success'] and row['owner_unreaped'] for row in signals)
                assert all(records.index(row)<next(i for i,r in enumerate(records) if r['kind']=='python_root_end') for row in signals)
                listener.settimeout(max(0,case_deadline-time.monotonic()))
                peer,_=listener.accept(); peer.settimeout(max(0,case_deadline-time.monotonic()))
                raw=bytearray(); eof=False; read_start=time.monotonic()
                while len(raw)<=4096:
                    part=peer.recv(min(4097-len(raw),4096))
                    if not part: eof=True; break
                    raw.extend(part)
                record['peer_read']=dict(start=read_start,end=time.monotonic(),raw=bytes(raw).decode('latin1'),eof=eof)
                assert eof and len(raw)<=4096,'no bounded descendant termination EOF'
                child=json.loads(raw); record['descendant']=child
                assert child['pgid']==root_pid and child['pid']!=root_pid
                queried=[row for row in members if row['pid']==child['pid']]
                assert len(queried)==1,'genuine survivor was not queried uniquely'
                assert queried[0]['parent']!=root_pid and queried[0]['pgid']==root_pid,'survivor was not queried after root exit/reparenting'
                for operation,call in [('image',lambda:authority.process_image(child['pid'])),
                                       ('getpgid',lambda:os.getpgid(child['pid'])),
                                       ('nonowner_waitpid',lambda:os.waitpid(child['pid'],os.WNOHANG))]:
                    before=time.monotonic()
                    try: outcome=dict(ok=True,value=call())
                    except OSError as exc: outcome=dict(ok=False,type=type(exc).__name__,errno=exc.errno,message=str(exc))
                    record['syscalls'].append(dict(operation=operation,start=before,end=time.monotonic(),**outcome))
                record['descendant_evidence']='actual same-group query + required group signal + sole descendant socket EOF; no owning orphan reap claimed'
            if time.monotonic()>=case_deadline: raise TimeoutError('original case bound exhausted')
            record['compatibility']='PASS'
        except Exception as exc:
            record.update(compatibility='NEEDS_CONTEXT',error=dict(type=type(exc).__name__,message=str(exc)[:600]))
            if case=='survivor':
                record['fallback_cleanup']=True
                # Closing an accepted peer permits the trusted survivor to exit;
                # this fallback is explicitly unsuccessful and never a retry.
                if peer is None and listener is not None:
                    try:
                        listener.settimeout(max(0,min(.1,ABSOLUTE_DEADLINE-time.monotonic())))
                        peer,_=listener.accept()
                    except OSError as cleanup_exc: record['fallback_error']=str(cleanup_exc)
        finally:
            if peer is not None: peer.close()
            if listener is not None: listener.close()
            peer_path=destination/(case+'.socket')
            if peer_path.exists(): peer_path.unlink()
            record['end']=time.monotonic(); record['elapsed']=record['end']-case_start
        if record['compatibility']!='PASS': break
    result['end']=time.monotonic(); result['elapsed']=result['end']-ALLOCATION_START
    result['compatibility']='PASS' if len(result['cases'])==2 and all(row['compatibility']=='PASS' for row in result['cases']) and result['end']<ABSOLUTE_DEADLINE else 'NEEDS_CONTEXT'
    payload=json.dumps(result,indent=2)+'\n'
    (destination/'native-result.json').write_text(payload)
    result['artifact_commit_end']=time.monotonic()
    if result['artifact_commit_end']>=ABSOLUTE_DEADLINE:
        result['compatibility']='NEEDS_CONTEXT'; result['overrun']=True
        (destination/'native-result.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(compatibility=result['compatibility'],elapsed=result['elapsed'],destination=str(destination))))
    return 0 if result['compatibility']=='PASS' else 1


if __name__=='__main__': raise SystemExit(main())
