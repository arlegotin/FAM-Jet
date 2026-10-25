"""ONE committed stdlib native control; no science, retries or owning orphan reap."""
import time
ALLOCATION_START=time.monotonic()
ABSOLUTE_DEADLINE=ALLOCATION_START+10
import errno
import hashlib
import json
import os
from pathlib import Path
import select
import socket
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
from validation.kernel_stage_a import authority, commands, monitor

ROOT_BODY=r'''
import json, os, select, socket, sys, time
case,peer_path,deadline=sys.argv[1],sys.argv[2],float(sys.argv[3])
pid=os.getpid(); proof=None
while time.monotonic()<deadline:
    records=[]
    with open('monitor-evidence.jsonl') as stream:
        for line in stream:
            if line.endswith('\n'): records.append(json.loads(line))
    samples={row['sample_id']:row for row in records if row['kind']=='sample'}
    for row in records:
        if row['kind']!='resolution': continue
        native=row.get('identities',{}).get(str(pid),{})
        if native.get('image_evidence')!='kernel_image': continue
        sample=samples[row['sample_id']]
        own=[entry for entry in sample['processes'] if entry['pid']==pid]
        if len(own)==1 and own[0]['image']['status']=='ok': proof=own[0]; break
    if proof is not None: break
    time.sleep(min(.002,max(0,deadline-time.monotonic())))
if proof is None: raise SystemExit('no actual supervisor proof within original bound')
with open('monitor-events.jsonl','a') as stream:
    stream.write(json.dumps(dict(event='baseline',pid=pid,rss=proof['rss_bytes'],
        monotonic=time.monotonic(),boundary='post-import/pre-allocation'))+'\n'); stream.flush()
child=None
if case=='survivor':
    read,write=os.pipe(); child=os.fork()
    if child==0:
        os.close(read)
        peer=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM)
        peer.settimeout(max(0,deadline-time.monotonic()))
        peer.connect(peer_path)
        peer.sendall((json.dumps(dict(pid=os.getpid(),parent=os.getppid(),pgid=os.getpgrp()))+'\n').encode())
        peer.settimeout(None)
        os.write(write,b'R'); os.close(write)
        # Sole peer owner after parent exit. EOF from controller is fallback
        # lifecycle cleanup only, never a successful native SIGKILL control.
        peer.recv(1)
        os._exit(0)
    os.close(write)
    ready=select.select([read],[],[],max(0,deadline-time.monotonic()))[0]
    if not ready or os.read(read,1)!=b'R': raise SystemExit('survivor readiness failed')
    os.close(read)
print(json.dumps(dict(root_pid=pid,child_pid=child,root_pgid=os.getpgrp(),proof_sample_end=proof['sample_end'])),flush=True)
'''


def main():
    destination=Path(sys.argv[1]).resolve()
    destination.mkdir(exist_ok=False)
    result=dict(allocation_start=ALLOCATION_START,absolute_deadline=ABSOLUTE_DEADLINE,
                scope='ONE stdlib native two-case terminal lifecycle integration; zero science',cases=[],
                source_git=os.environ['TASK18_SOURCE_GIT'],control_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
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
            vector=[sys.executable,'-I','-S','-c',ROOT_BODY,case,str(peer_path),repr(case_deadline)]
            record.update(vector=vector,vector_sha256=commands.vector_hash(vector))
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
            proofs=[entry for row in records if row['kind']=='sample' for entry in row['processes']
                    if entry['pid']==root_pid and entry.get('image',{}).get('status')=='ok']
            assert proofs and max(row['image']['lookup_end'] for row in proofs)<ends[0]['completion_end']
            if case=='empty':
                assert not members and not signals and verdict['status']=='COMPLETED',verdict
            else:
                assert signals and all(row['success'] and row['owner_unreaped'] for row in signals)
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
                assert any(row['pid']==child['pid'] for row in members),'genuine survivor was not queried'
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
