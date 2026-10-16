"""Run a tiny non-scientific training pipeline with complete recovery records."""
import argparse
from datetime import datetime, timezone
from pathlib import Path
import uuid


def main(argv: list[str] | None = None) -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',type=Path,required=True)
    parser.add_argument('--run-dir',type=Path)
    parser.add_argument('--resume',type=Path)
    args=parser.parse_args(argv)
    # Help must exit before importing torch or starting any run/discovery.
    from famjet.config import load_config
    from famjet.train import train_model
    destination=args.run_dir or Path('artifacts/runs')/(datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex[:8])
    path=train_model(load_config(args.config),destination,resume=args.resume)
    print(f'completed non-scientific smoke: {path}')
    return 0


if __name__=='__main__':
    raise SystemExit(main())
