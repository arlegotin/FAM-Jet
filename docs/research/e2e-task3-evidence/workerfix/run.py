"""Record one focused E3 verification command without losing failed output."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time


def main():
    if len(sys.argv) < 3:
        raise SystemExit('usage: run.py NAME COMMAND [ARG ...]')
    name, argv = sys.argv[1], sys.argv[2:]
    root = Path(__file__).resolve().parent
    log = root / (name + '.log')
    record = root / (name + '.json')
    if log.exists() or record.exists():
        raise SystemExit('evidence name already used')
    env = dict(os.environ)
    env.update(OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1',
               VECLIB_MAXIMUM_THREADS='1', NUMEXPR_NUM_THREADS='1')
    started = time.perf_counter()
    try:
        process = subprocess.run(argv, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env)
        output, exit_code = process.stdout, process.returncode
    except OSError as exc:
        output, exit_code = f'{type(exc).__name__}: {exc}\n'.encode(), 127
    elapsed = time.perf_counter() - started
    log.write_bytes(output)
    record.write_text(json.dumps({'argv': argv, 'exit': exit_code,
                                  'elapsed_seconds': elapsed, 'stdout_sha256': hashlib.sha256(output).hexdigest(),
                                  'stdout_bytes': len(output), 'thread_env': {k: env[k] for k in
                                  ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS',
                                   'VECLIB_MAXIMUM_THREADS', 'NUMEXPR_NUM_THREADS')}},
                                 sort_keys=True, indent=2) + '\n')
    sys.stdout.buffer.write(output)
    return exit_code


if __name__ == '__main__':
    raise SystemExit(main())
