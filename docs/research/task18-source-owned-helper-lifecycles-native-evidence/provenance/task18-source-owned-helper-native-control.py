"""STATIC input only; requires separate source review and ONE native allocation."""
import time
ALLOCATION_START=time.monotonic()
UTC_START=time.time()
ABSOLUTE_DEADLINE=ALLOCATION_START+10
import ast
import hashlib
import json
import os
from pathlib import Path
import socket
import signal
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from validation.kernel_stage_a import authority, commands, monitor


def hashed(path):
    raw=path.read_bytes()
    return dict(path=str(path),sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw))


def records(path):
    raw=path.read_bytes()
    if raw and not raw.endswith(b'\n'): raise ValueError('truncated native journal')
    return [json.loads(line) for line in raw.splitlines()]


def validate_owned_kill(raw,root):
    ends=[(i,e['value']) for i,e in enumerate(raw) if e['kind']=='python_root_end']
    assert len(ends)==1 and ends[0][1]['pid']==root
    assert ends[0][1]['reaped'] is True and type(ends[0][1]['returncode']) is int
    signals=[(i,e) for i,e in enumerate(raw) if e['kind']=='cleanup_signal']
    assert signals and all(i<ends[0][0] and e.get('pid')==root and
        e.get('signal')==signal.SIGKILL and e.get('success') is True and
        not e.get('absent',False) and e.get('owner_unreaped') is True for i,e in signals)


def reserve_parent_artifacts(destination,output_bytes,*,report_bytes=1048576,timing_bytes=2048):
    # Both placeholders are charged before any monitor allocation. In-place
    # overwrites avoid a temporary duplicate of the final serialized artifact.
    if min(report_bytes,timing_bytes)<512 or monitor.directory_bytes(destination)+report_bytes+timing_bytes>output_bytes:
        raise ValueError('aggregate output cap including parent reservations')
    initial=b'{"compatibility":"NEEDS_CONTEXT","reason":"parent commitment incomplete"}\n'
    for name,size in (('native-result.json',report_bytes),('native-commit-timing.json',timing_bytes)):
        with (destination/name).open('xb') as stream:
            if stream.write(initial+b' '*(size-len(initial)))!=size: raise OSError('short parent reservation')


def commit_result(result,destination,allocation_start,deadline,output_bytes):
    report=destination/'native-result.json'; receipt=destination/'native-commit-timing.json'
    report_bytes=report.stat().st_size; receipt_bytes=receipt.stat().st_size
    result.update(end=time.monotonic(),utc_end_epoch=time.time(),timing_boundary='before report commit')
    result['elapsed']=result['end']-allocation_start
    result['compatibility']='PASS' if len(result['cases'])==2 and all(r['compatibility']=='PASS' for r in result['cases']) else 'NEEDS_CONTEXT'
    def check():
        if monitor.directory_bytes(destination)>output_bytes: raise ValueError('original aggregate output cap')
        if time.monotonic()>=deadline: raise TimeoutError('original parent allocation exhausted')
    def failed(error):
        end=time.monotonic()
        return dict(compatibility='NEEDS_CONTEXT',error=str(error)[:300],end=end,
            elapsed=end-allocation_start,timing_boundary='before report commit',
            details='original per-case logs retained; parent summary could not be committed within limits')
    try:
        payload=monitor._bounded_json(result,report_bytes,check)
    except Exception as exc:
        result=failed(exc); payload=monitor._bounded_json(result,report_bytes)
    monitor._commit_monitor(report,payload,report_bytes)
    report_end=time.monotonic()
    try: check()
    except Exception as exc:
        result=failed(exc)
        monitor._commit_monitor(report,monitor._bounded_json(result,report_bytes),report_bytes)
        report_end=time.monotonic()
    timing=dict(compatibility=result['compatibility'],report_commit_end=report_end,
        report_elapsed=report_end-allocation_start,utc_report_commit_end_epoch=time.time(),
        timing_boundary='after report commit; before timing receipt commit')
    monitor._commit_monitor(receipt,monitor._bounded_json(timing,receipt_bytes),receipt_bytes)
    try: check()
    except Exception as exc:
        # Bounded failure commitment uses only already allocated bytes; it grants
        # no extended deadline or successful timing claim after an overrun.
        result=failed(exc)
        monitor._commit_monitor(report,monitor._bounded_json(result,report_bytes),report_bytes)
        timing.update(compatibility='NEEDS_CONTEXT',report_commit_end=time.monotonic(),utc_report_commit_end_epoch=time.time())
        timing['report_elapsed']=timing['report_commit_end']-allocation_start
        monitor._commit_monitor(receipt,monitor._bounded_json(timing,receipt_bytes),receipt_bytes)
    caller_end=time.monotonic()
    print(json.dumps(dict(compatibility=result['compatibility'],elapsed=caller_end-allocation_start,
        caller_end=caller_end,timing_boundary='after all artifact writes; before stdout',destination=str(destination))))
    return 0 if result['compatibility']=='PASS' else 1


def main():
    destination=Path(sys.argv[1]).resolve()
    if destination.is_relative_to(ROOT): raise ValueError('native output must be outside allocated clean source')
    destination.mkdir(exist_ok=False)
    reserve_parent_artifacts(destination,67108864)
    for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','VECLIB_MAXIMUM_THREADS','NUMEXPR_NUM_THREADS'):
        os.environ[key]='1'
    worker=ROOT/'docs/research/task18-source-owned-helper-native-worker.py'
    inputs=[Path(__file__).resolve(),worker,ROOT/'validation/kernel_stage_a/monitor.py',
            ROOT/'validation/kernel_stage_a/source_lifecycles.py',ROOT/'validation/kernel_stage_a/authority.py',
            ROOT/'validation/kernel_stage_a/production.py',ROOT/'validation/kernel_stage_a/commands.py',
            ROOT/'validation/kernel_stage_a/reader_worker.py']
    for path in inputs: ast.parse(path.read_bytes())
    result=dict(scope='source lifecycle compatibility only; zero model/factor/read work',
        allocation_start=ALLOCATION_START,utc_start_epoch=UTC_START,absolute_deadline=ABSOLUTE_DEADLINE,
        source_git=os.environ['TASK18_SOURCE_GIT'],inputs=[hashed(path) for path in inputs],cases=[])
    for case in ('families','unknown'):
        start=time.monotonic(); deadline=min(start+4.5,ABSOLUTE_DEADLINE-.25)
        row=dict(case=case,start=start,deadline=deadline,utc_start_epoch=time.time(),fallback_cleanup=False)
        result['cases'].append(row); listener=None; peer=None
        peer_path=destination/(case+'.socket')
        try:
            if deadline<=start: raise TimeoutError('native allocation exhausted')
            if case=='unknown':
                listener=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM)
                listener.bind(str(peer_path)); listener.listen(1)
            vector=[sys.executable,'-I','-B',str(worker),case,str(peer_path),repr(deadline)]
            row.update(vector=vector,vector_sha256=commands.vector_hash(vector))
            output=destination/(case+'-output')
            verdict=monitor.supervise(vector,output,deadline=deadline,outer_seconds=deadline-start,authority_root=ROOT,
                output_bytes=67108864-monitor.directory_bytes(destination))
            row['verdict']=verdict
            raw=records(output/'monitor-evidence.jsonl'); events=records(output/'monitor-events.jsonl')
            launches=[r['value'] for r in raw if r['kind']=='python_root_launch']
            ends=[r['value'] for r in raw if r['kind']=='python_root_end']
            memberships=[r for r in raw if r['kind']=='cleanup_membership']
            signals=[r for r in raw if r['kind']=='cleanup_signal']
            if len(launches)!=len(ends) or len(ends)!=1 or len(memberships)!=1:
                raise AssertionError('missing actual root lifecycle or cleanup')
            root=launches[0]['pid']; row['root_pid']=root
            assert ends[0]['launch_id']==launches[0]['launch_id'] and ends[0]['reaped'] is True
            assert type(ends[0]['returncode']) is int
            membership=memberships[0]['value']
            assert memberships[0]['owner_unreaped'] and membership['complete']
            assert membership['helper']['launch']['argv']==monitor._CLEANUP_ARGV
            assert membership['helper']['completion']['returncode']==0
            assert membership['helper']['image_evidence'] in ('kernel_image','image_unavailable')
            baselines=[e for e in events if e['event']=='baseline' and e['pid']==root]
            selves=[e for e in events if e['event']=='observer_sample' and e.get('self_pid')==e.get('emitter_pid')==root]
            assert len(baselines)==len(selves)==1
            own=[r for r in selves[0]['processes'] if r['pid']==root]
            assert len(own)==1 and own[0]['image']['status']=='ok' and own[0]['rss_bytes']==baselines[0]['rss']
            assert own[0]['image']['lookup_end']<=baselines[0]['monotonic']
            row['baseline']=baselines[0]
            if case=='families':
                assert verdict['status']=='COMPLETED' and ends[0]['returncode']==0 and not signals
                stdout=records(output/'stdout.log'); assert len(stdout)==1
                assert stdout[0]['read_operations']==stdout[0]['factor_operations']==0
                reader_launch=[e for e in events if e['event']=='python_worker_launch']
                reader_end=[e for e in events if e['event']=='python_worker_end']
                assert len(reader_launch)==len(reader_end)==1
                assert reader_launch[0]['argv']==stdout[0]['reader_vector']
                assert reader_end[0]['launch_id']==reader_launch[0]['launch_id'] and reader_end[0]['reaped']
                assert reader_end[0]['returncode']==stdout[0]['reader_returncode']!=0
                assert (output/'reader-result.jsonl').read_bytes()==b''
                assert 'closed read-only worker request required' in (output/'reader-stderr.log').read_text()
                git_launch=[e for e in events if e['event']=='authority_helper']
                git_end=[e for e in events if e['event']=='authority_helper_end']
                assert sorted(e['argv'] for e in git_launch)==sorted(authority.git_commands(ROOT))
                assert len(git_end)==2 and all(e['returncode']==0 and e['reaped'] for e in git_end)
                joins=[r for r in raw if r['kind']=='source_lifecycle']
                assert {'git','ps','cleanup_ps','reader'}<={r['family'] for r in joins}
                assert all(r['source']['path'] in ('monitor-events.jsonl','monitor-evidence.jsonl') and
                    type(r['source']['offset']) is int and r['completion']['reaped'] for r in joins)
                assert {e['launch_id'] for e in git_launch+reader_launch}<={r['launch_id'] for r in joins}
                row.update(operation='expected reader rejection, zero actual reads',source_generations=joins)
                # No requirement that a fast helper be sampled; null remains unmeasured.
                row['observed_helper_pids']=[pid for pid,item in verdict['workers'].items() if item['role'] in ('observer_helper','authority_helper')]
            else:
                assert verdict['status']!='COMPLETED' and ends[0]['returncode'] in (0,-9)
                validate_owned_kill(raw,root)
                listener.settimeout(max(0,deadline-time.monotonic())); peer,_=listener.accept()
                peer.settimeout(max(0,deadline-time.monotonic())); payload=bytearray(); eof=False
                read_start=time.monotonic()
                while len(payload)<=4096:
                    part=peer.recv(min(4097-len(payload),4096))
                    if not part: eof=True; break
                    payload.extend(part)
                row['peer']=dict(start=read_start,end=time.monotonic(),raw=bytes(payload).decode('latin1'),eof=eof)
                assert eof and len(payload)<=4096
                child=json.loads(payload); assert child['pgid']==root and child['pid']!=root
                assert any(r['pid']==child['pid'] and r['pgid']==root for r in membership['rows'])
                row['unknown_child']=child
                row['termination_evidence']='actual group membership, owned signal before end, sole-child socket EOF before fallback'
            assert verdict['source_event_accounting']['complete'] and verdict['source_event_accounting']['identity_complete']
            if monitor.directory_bytes(destination)>67108864: raise RuntimeError('original aggregate output cap')
            if time.monotonic()>=deadline: raise TimeoutError('original case allocation exhausted')
            row['compatibility']='PASS'
        except Exception as exc:
            row.update(compatibility='NEEDS_CONTEXT',error=dict(type=type(exc).__name__,message=str(exc)[:800]))
            if listener is not None:
                row['fallback_cleanup']=True
                if peer is None:
                    try:
                        listener.settimeout(max(0,min(.1,ABSOLUTE_DEADLINE-time.monotonic())))
                        peer,_=listener.accept()
                    except OSError as cleanup: row['fallback_error']=str(cleanup)
        finally:
            if peer is not None: peer.close()
            if listener is not None: listener.close()
            if peer_path.exists(): peer_path.unlink()
            row.update(end=time.monotonic(),utc_end_epoch=time.time()); row['elapsed']=row['end']-start
        if row['compatibility']!='PASS': break
    return commit_result(result,destination,ALLOCATION_START,ABSOLUTE_DEADLINE,67108864)


if __name__=='__main__': raise SystemExit(main())
