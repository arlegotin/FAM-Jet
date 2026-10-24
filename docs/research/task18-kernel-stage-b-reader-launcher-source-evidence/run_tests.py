"""Preserve exact source-test invocations and raw outputs for this correction."""

import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time


directory = Path(__file__).resolve().parent
label, *tests = sys.argv[1:]
argv = [str(Path(sys.executable).absolute()), "-m", "pytest", "-q", *tests]
start = time.monotonic()
result = subprocess.run(argv, cwd=directory.parents[2], stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE, check=False)
elapsed = time.monotonic() - start
refs = {}
for name, raw in (("stdout", result.stdout), ("stderr", result.stderr)):
    path = directory / f"{label}.{name}"
    path.write_bytes(raw)
    refs[name] = {"path": path.relative_to(directory.parents[2]).as_posix(),
                  "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
record = {"argv": argv, "elapsed_seconds": elapsed, "exit_code": result.returncode,
          "raw": refs}
(directory / f"{label}.json").write_text(json.dumps(record, indent=2) + "\n")
sys.stdout.buffer.write(result.stdout)
sys.stderr.buffer.write(result.stderr)
raise SystemExit(result.returncode)
