"""STATIC input only. One future allocated process; no numerical request/work."""
import json
import os
from pathlib import Path
import select
import socket
import sys
import time

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from validation.kernel_stage_a import authority, commands, monitor


def main():
    case,peer_path,deadline=sys.argv[1],sys.argv[2],float(sys.argv[3])
    events=Path('monitor-events.jsonl').resolve(); pid=os.getpid()
    if case=='families':
        authority.event(events,'authority_start',pid=pid)
        success=False
        try:
            revision=authority.git(ROOT,'rev-parse','HEAD',deadline=deadline,event_path=events)
            status=authority.git(ROOT,'status','--porcelain',deadline=deadline,event_path=events)
            if revision!=os.environ['TASK18_SOURCE_GIT'] or status: raise RuntimeError('native source is not the allocated clean revision')
            success=True
        finally: authority.event(events,'authority_end',pid=pid,success=success)
    elif case!='unknown': raise ValueError('closed native case')
    import torch
    import famjet
    torch.set_num_threads(1); torch.set_num_interop_threads(1)
    if case=='families':
        from validation.kernel_stage_a.production import owned_reader_dispatch
    baseline=monitor.record_baseline(events,deadline=deadline)
    result=dict(case=case,pid=pid,pgid=os.getpgrp(),baseline=baseline,read_operations=0,factor_operations=0)
    if case=='families':
        authority.event(events,'candidate_start')
        try:
            vector=commands.reader_command(ROOT,events,deadline)
            temporary=Path('reader-temporary').resolve(); temporary.mkdir()
            env={key:value for key,value in os.environ.items() if key not in ('PYTHONPATH','PYTHONHOME')}
            with Path('reader-result.jsonl').open('wb') as stdout,Path('reader-stderr.log').open('wb') as stderr:
                completed=owned_reader_dispatch(vector,input=b'{}',stdout=stdout,stderr=stderr,cwd=temporary,
                    env=env,deadline=deadline,event_path=events)
            # Existing reader_worker rejects this closed-schema mismatch before
            # Trace, isolation._worker, factor construction or a read can run.
            if completed.returncode==0: raise RuntimeError('invalid request unexpectedly succeeded')
            if Path('reader-result.jsonl').read_bytes(): raise RuntimeError('invalid request emitted results/counters')
            if 'closed read-only worker request required' not in Path('reader-stderr.log').read_text():
                raise RuntimeError('reader failed before expected schema rejection')
            result.update(reader_returncode=completed.returncode,reader_vector=vector,
                          reader_operation='expected failed operation: invalid closed request')
        finally: authority.event(events,'candidate_end')
    else:
        read,write=os.pipe(); child=os.fork()
        if child==0:
            os.close(read)
            peer=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM)
            peer.settimeout(max(0,deadline-time.monotonic())); peer.connect(peer_path)
            peer.sendall((json.dumps(dict(pid=os.getpid(),parent=os.getppid(),pgid=os.getpgrp()))+'\n').encode())
            peer.settimeout(None)
            os.write(write,b'R'); os.close(write)
            # Sole child owns this socket. A controller close is unsuccessful
            # fallback cleanup only; successful control requires earlier EOF.
            try: peer.recv(1)
            finally: peer.close(); os._exit(0)
        os.close(write)
        try:
            ready=select.select([read],[],[],max(0,deadline-time.monotonic()))[0]
            if not ready or os.read(read,1)!=b'R': raise RuntimeError('unknown child readiness failed')
        finally: os.close(read)
        result['unknown_child']=child
    print(json.dumps(result),flush=True)
    return 0


if __name__=='__main__': raise SystemExit(main())
