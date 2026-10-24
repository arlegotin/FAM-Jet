"""Capture exact focused check invocations without discarding failed logs."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time


def main():
    if len(sys.argv) < 3:
        raise SystemExit('usage: run-check.py NAME ARGV...')
    name, argv = sys.argv[1], sys.argv[2:]
    root = Path(__file__).resolve().parents[3]
    directory = Path(__file__).resolve().parent
    log = directory / f'{name}.log'
    if log.exists():
        raise FileExistsError(log)
    start = time.monotonic()
    result = subprocess.run(argv, cwd=root, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, check=False)
    elapsed = time.monotonic() - start
    log.write_bytes(result.stdout)
    record = {'argv': argv, 'cwd': str(root), 'exit_code': result.returncode,
              'elapsed_seconds': elapsed, 'log': str(log.relative_to(root)),
              'log_sha256': hashlib.sha256(result.stdout).hexdigest(),
              'log_bytes': len(result.stdout)}
    (directory / f'{name}.json').write_text(json.dumps(record, indent=2) + '\n')
    print(json.dumps(record))
    return result.returncode


if __name__ == '__main__':
    raise SystemExit(main())
