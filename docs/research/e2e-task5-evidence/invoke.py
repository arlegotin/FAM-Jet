"""Retain exact E5 focused command output, including failed attempts."""

import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time


label, *argv = sys.argv[1:]
if not label or not argv or '/' in label:
    raise SystemExit('usage: invoke.py LABEL COMMAND [ARG ...]')
root = Path(__file__).resolve().parent
path = root / (label + '.log')
if path.exists():
    raise SystemExit(f'capture exists: {path}')
started = time.perf_counter()
with path.open('wb') as stream:
    result = subprocess.run(argv, stdout=stream, stderr=subprocess.STDOUT, check=False)
elapsed = time.perf_counter() - started
raw = path.read_bytes()
receipt = {'argv': argv, 'stdout_stderr_log': str(path.relative_to(root)),
           'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest(),
           'exit_code': result.returncode, 'elapsed_seconds': elapsed}
(root / (label + '.json')).write_text(json.dumps(receipt, sort_keys=True, indent=2) + '\n')
print(json.dumps(receipt, sort_keys=True))
raise SystemExit(result.returncode)
