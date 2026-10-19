"""Prospective launch only; incomplete seals exit before backend imports."""
import argparse
import json
from pathlib import Path
import sys
import time
from . import authority,commands


def scientific_worker(seal,root,pending):
    from .production import Backend,finite
    from .driver import execute
    from .monitor import record_baseline
    out=Path(pending['output_directory'])
    deadline=pending['resource_measurement_boundary_seal']['deadline_monotonic']
    record_baseline(out/'monitor-events.jsonl',deadline=deadline)
    def checkpoint():
        if time.monotonic()>=deadline: raise TimeoutError('original outer deadline')
    result=execute(Backend(seal,root),checkpoint=checkpoint)
    (out/'stage-a.json').write_bytes(authority.canonical(finite(result)))
    return 0 if result['status']=='PASS' else 1


def verified_worker(seal,root,*,backend_entry=None):
    """The single monitored live authority phase precedes all backend imports."""
    path=Path(seal['pending']['output_directory'])/'monitor-events.jsonl'
    deadline=seal['pending']['resource_measurement_boundary_seal']['deadline_monotonic']
    import os
    authority.event(path,'authority_start',pid=os.getpid())
    success=False
    try:
        pending=authority.verify(seal,root,output_initialized=True,deadline=deadline,event_path=path)
        success=True
    finally: authority.event(path,'authority_end',pid=os.getpid(),success=success)
    return (scientific_worker if backend_entry is None else backend_entry)(seal,root,pending)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seal',type=Path,required=True)
    parser.add_argument('--worker',action='store_true',help=argparse.SUPPRESS)
    args=parser.parse_args(); root=Path(__file__).resolve().parents[2]
    seal=json.loads(args.seal.read_bytes())
    try:
        authority.entry(seal)
        if args.worker: return verified_worker(seal,root)
        pending=seal['pending']
    except authority.AuthorityError as exc:
        print('REFUSED: '+str(exc),file=sys.stderr); return 2
    from .monitor import supervise
    boundary=pending['resource_measurement_boundary_seal']
    setup=json.loads((root/boundary['setup_ledger']['path']).read_bytes())
    result=supervise(commands.stage_command(root,args.seal),
             Path(pending['output_directory']),outer_seconds=boundary['deadline_monotonic']-time.monotonic(),
             preparation_output=Path(setup['output_directory']),authority_root=root,deadline=boundary['deadline_monotonic'],
             incremental_bytes=authority.LIMITS['incremental_worker_bytes'],
             output_bytes=authority.LIMITS['output_bytes'],
             outer_ceiling_seconds=authority.LIMITS['outer_seconds'],
             candidate_seconds=authority.LIMITS['candidate_seconds'])
    print(json.dumps(result,sort_keys=True)); return 0 if result['status']=='COMPLETED' else 1


if __name__=='__main__': raise SystemExit(main())
