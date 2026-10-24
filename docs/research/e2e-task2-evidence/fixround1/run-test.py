"""Capture every E2 source test invocation before the first RED run."""
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

name = sys.argv[1]
argv = sys.argv[2:]
out = Path(__file__).parent
start = time.monotonic()
p = subprocess.run(argv, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
elapsed = time.monotonic() - start
log = p.stdout
(out / f'{name}.log').write_bytes(log)
record = {'argv': argv, 'elapsed_seconds': elapsed, 'exit_code': p.returncode,
          'log_bytes': len(log), 'log_sha256': hashlib.sha256(log).hexdigest()}
(out / f'{name}.json').write_text(json.dumps(record, indent=2, sort_keys=True) + '\n')
sys.stdout.buffer.write(log)
sys.exit(p.returncode)
