"""External phase sequencing; no candidate or scientific-policy implementation."""
import json
from pathlib import Path

def run_sequence(phases, runner):
    completed=[]
    for phase in phases:
        code=runner(phase['command'])
        if code != 0:
            raise RuntimeError(f"phase {phase['command']} exited {code}")
        path=Path(phase['summary'])
        if not path.is_file():
            raise FileNotFoundError(f"phase summary missing: {path}")
        record=json.loads(path.read_text())
        if record.get('status') != phase['expected_status']:
            raise RuntimeError(f"phase summary failed: {path}: {record.get('status')}")
        completed.append(phase['command'])
    return completed
