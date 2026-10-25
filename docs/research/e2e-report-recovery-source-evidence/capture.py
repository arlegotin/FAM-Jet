"""Capture exact R7 source verification commands and raw output bytes."""

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import time

root = Path(__file__).resolve().parents[3]
evidence = Path(__file__).resolve().parent
commands = {
    'green-targeted': ['.venv/bin/python', '-m', 'pytest', '-q',
        'tests/test_poc_report_inputs.py', 'tests/test_poc_report_recovery.py',
        'tests/test_poc_report.py', 'tests/test_poc_report_scientific.py',
        'tests/test_poc_cli.py', 'tests/test_measured_execution.py'],
    'compile': ['.venv/bin/python', '-m', 'compileall', '-q',
        'famjet_poc/report_inputs.py', 'scripts/report_run06_recovery.py',
        'tests/test_poc_report_inputs.py', 'tests/test_poc_report_recovery.py'],
    'launcher-help': ['.venv/bin/python', 'scripts/report_run06_recovery.py', '--help'],
    'source-preservation': ['.venv/bin/python',
        'docs/research/e2e-report-recovery-source-evidence/verify_source.py'],
    'diff-check': ['git', 'diff', '--check'],
}
results = {}
for label, argv in commands.items():
    started = datetime.now(timezone.utc).isoformat()
    clock = time.perf_counter()
    result = subprocess.run(argv, cwd=root, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, timeout=180, check=False)
    raw = result.stdout
    (evidence / f'{label}.log').write_bytes(raw)
    results[label] = {'argv': argv, 'start_utc': started,
                      'end_utc': datetime.now(timezone.utc).isoformat(),
                      'elapsed_seconds': time.perf_counter() - clock,
                      'exit_code': result.returncode,
                      'log_bytes': len(raw),
                      'log_sha256': hashlib.sha256(raw).hexdigest()}
    if result.returncode:
        break
(evidence / 'checks.json').write_text(json.dumps(results, indent=2, sort_keys=True) + '\n')
if any(item['exit_code'] for item in results.values()) or len(results) != len(commands):
    raise SystemExit(1)
print(json.dumps(results, indent=2, sort_keys=True))
