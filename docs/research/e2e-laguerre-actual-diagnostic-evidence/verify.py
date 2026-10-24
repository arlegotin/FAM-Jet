"""Fresh stdlib-only evidence verification; does not rerun scientific work."""
import hashlib
import json
from pathlib import Path
import sys
import time

epoch, start = time.time(), time.monotonic()
out = Path(__file__).resolve().parent
assert not (out/'verification.json').exists()
checks = []


def check_file(path, record):
    raw = Path(path).read_bytes()
    assert len(raw) == record['bytes']
    assert hashlib.sha256(raw).hexdigest() == record['sha256']
    checks.append(str(path))


inv = json.loads((out/'invocation.json').read_bytes())
assert inv['exit_code'] == 0 and inv['elapsed_seconds'] < 300
assert inv['peak_child_rss_bytes'] < 1536*1024**2
for path, record in inv['files'].items():
    check_file(path, record)
r = json.loads((out/'result.json').read_bytes())
for path, record in r['immutable_inputs'].items():
    check_file(path, record)
assert [h['status'] for h in r['histories']] == ['passed', 'passed', 'passed', 'failed', 'passed']
assert r['histories'][3]['prediction']['max_tolerance_ratio'] > 1
assert all(h['state'][s]['strict_allclose'] for h in r['histories'] for s in ('z', 'h'))
assert all(h[k] for h in r['histories'] for k in ('support_equal', 'failure_equal', 'finite_mask_equal'))
summary = json.loads((out/'summary-invocation.json').read_bytes())
check_file(out/'summary.log', {'bytes': summary['log_bytes'], 'sha256': summary['log_sha256']})
assert summary['source_sha256'] == hashlib.sha256((out/'summarize.py').read_bytes()).hexdigest()
report = out.parent/'e2e-laguerre-actual-diagnostic-report.md'
mirror = Path('.superpowers/sdd/2026-10-16-famjet/e2e-laguerre-actual-diagnostic-report.md')
assert report.read_bytes() == mirror.read_bytes()
files = [p for p in out.iterdir() if p.is_file()] + [report, mirror]
output_bytes = sum(p.stat().st_size for p in files)
assert output_bytes + 10000 < 32*1024**2
message = f'PASS: {len(checks)} byte/hash pairs; strict failure retained; original inputs unchanged; report mirror identical; output {output_bytes} bytes before verification records.\n'
(out/'verification.log').write_text(message)
record = {'argv': [sys.executable, *sys.argv], 'cwd': str(Path.cwd()),
          'start_epoch_seconds': epoch, 'end_epoch_seconds': time.time(),
          'elapsed_seconds': time.monotonic()-start, 'exit_code': 0,
          'checked_paths': checks, 'new_output_bytes_before_verification_records': output_bytes,
          'log_bytes': len(message.encode()), 'log_sha256': hashlib.sha256(message.encode()).hexdigest(),
          'files': {str(p): {'bytes': p.stat().st_size, 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()} for p in files}}
(out/'verification.json').write_text(json.dumps(record, indent=2, sort_keys=True)+'\n')
print(message, end='')
