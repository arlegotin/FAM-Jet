"""Prospective launch only; incomplete seals exit before backend imports."""
import argparse
import json
from pathlib import Path
import sys
import time
from . import authority


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seal',type=Path,required=True)
    parser.add_argument('--worker',action='store_true',help=argparse.SUPPRESS)
    args=parser.parse_args(); root=Path(__file__).resolve().parents[2]
    seal=json.loads(args.seal.read_bytes())
    try: pending=authority.verify(seal,root,output_initialized=args.worker)
    except authority.AuthorityError as exc:
        print('REFUSED: '+str(exc),file=sys.stderr); return 2
    if args.worker:
        from .production import Backend,finite
        from .driver import execute
        from .monitor import record_baseline
        out=Path(pending['output_directory']); record_baseline(out/'monitor-events.jsonl')
        deadline=pending['resource_measurement_boundary_seal']['deadline_monotonic']
        def checkpoint():
            if time.monotonic()>=deadline: raise TimeoutError('original outer deadline')
        result=execute(Backend(seal,root),checkpoint=checkpoint)
        (out/'stage-a.json').write_bytes(authority.canonical(finite(result)))
        return 0 if result['status']=='PASS' else 1
    from .monitor import supervise
    bootstrap='import sys; sys.path.insert(0,'+repr(str(root))+'); from validation.kernel_stage_a.__main__ import main; raise SystemExit(main())'
    boundary=pending['resource_measurement_boundary_seal']
    setup=json.loads((root/boundary['setup_ledger']['path']).read_bytes())
    result=supervise([sys.executable,'-I','-c',bootstrap,'--worker','--seal',str(args.seal.resolve())],
             Path(pending['output_directory']),outer_seconds=boundary['deadline_monotonic']-time.monotonic(),
             preparation_output=Path(setup['output_directory']))
    print(json.dumps(result,sort_keys=True)); return 0 if result['status']=='COMPLETED' else 1


if __name__=='__main__': raise SystemExit(main())
