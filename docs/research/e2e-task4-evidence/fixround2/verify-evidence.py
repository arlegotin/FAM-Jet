"""Verify raw command outputs match their retained invocation records."""
import hashlib
import json
from pathlib import Path


root = Path(__file__).resolve().parents[4]
directory = Path(__file__).resolve().parent
count = 0
for record_path in sorted(directory.glob('*.json')):
    record = json.loads(record_path.read_text())
    raw = (root / record['log']).read_bytes()
    assert record['log_bytes'] == len(raw), record_path
    assert record['log_sha256'] == hashlib.sha256(raw).hexdigest(), record_path
    assert type(record['argv']) is list and record['cwd'] == str(root), record_path
    assert type(record['exit_code']) is int and record['elapsed_seconds'] >= 0, record_path
    count += 1
print(f'verified {count} round-2 invocation/raw-log pairs')
