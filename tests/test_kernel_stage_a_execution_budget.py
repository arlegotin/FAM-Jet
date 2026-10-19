"""Source-only execution-budget controls; no native or scientific launch."""
import ast
import hashlib
import json
from pathlib import Path
import sys
import time

import pytest

from validation.kernel_stage_a import __main__ as cli
from validation.kernel_stage_a import authority as a, monitor as m


ADOPTED = 402653184
RECORDED = 286146560
REVIEWED = Path('docs/research/task18-stage-a-execution-budget-source-evidence/preedit-task-18-stage-a-setup-parent-reviewed-template.py')
CURRENT = Path('docs/research/task18-stage-a-setup-parent-384mib.py')


@pytest.mark.parametrize(('charge', 'limit', 'reason'), [
    (RECORDED, 201326592, 'incremental worker memory cap'),
    (RECORDED, ADOPTED, None),
    (ADOPTED, ADOPTED, None),
    (ADOPTED + 1, ADOPTED, 'incremental worker memory cap'),
])
def test_controlled_monitor_charge_respects_both_limits_and_new_boundary(
        tmp_path, monkeypatch, charge, limit, reason):
    output = tmp_path / 'monitor'
    samples = []
    killed = []

    class Owner:
        pid = 570001
        returncode = None

        def poll(self):
            if len(samples) >= 3 and self.returncode is None:
                self.returncode = 0
            return self.returncode

        def wait(self, timeout):
            if self.returncode is None:
                self.returncode = -9 if killed else 0
            return self.returncode

    monkeypatch.setattr(m.subprocess, 'Popen', lambda *args, **kwargs: Owner())
    monkeypatch.setattr(m.os, 'killpg', lambda group, signal: killed.append((group, signal)))
    monkeypatch.setattr(m.time, 'sleep', lambda seconds: None)

    def sampler(pid):
        samples.append(pid)
        if len(samples) == 1:
            with (output / 'monitor-events.jsonl').open('a') as stream:
                stream.write(json.dumps({'event': 'baseline', 'pid': pid, 'rss': 0}) + '\n')
        return m.ResidentTree({pid: charge if len(samples) == 2 else 0}, {})

    result = m.supervise(['/controlled/python'], output, sampler=sampler,
                         outer_seconds=0.5, free_disk_bytes=0, incremental_bytes=limit)
    assert result['reason'] == reason, result
    assert result['status'] == ('COMPLETED' if reason is None else 'STOPPED'), result
    assert result['incremental_worker_peak_bytes'] == charge
    assert result['evidence']['accepted_samples'] >= 2


def _seal(tmp_path, limit):
    setup = tmp_path / 'setup.json'
    setup.write_text(json.dumps({'output_directory': str(tmp_path / 'setup-output')}))
    started = time.monotonic() - 1
    return {'version': 1, 'scope': 'Task18 kernel Stage A only',
            'observed': {'source': 'controlled'},
            'pending': {'implementation_review': 'controlled',
                        'represented_rate_records': 'controlled',
                        'static_exports': 'controlled',
                        'fresh_launch_snapshot': 'controlled',
                        'output_directory': str(tmp_path / 'output'),
                        'resource_measurement_boundary_seal': {
                            'allocation_start_monotonic': started,
                            'deadline_monotonic': started + a.LIMITS['outer_seconds'],
                            'setup_ledger': {'path': str(setup)}}},
            'limits': dict(a.LIMITS, incremental_worker_bytes=limit),
            'root_stage_A_release': {'approved': True}}


def test_exact_new_seal_passes_entry_and_old_seal_fails_before_supervise(tmp_path, monkeypatch, capsys):
    calls = []

    def fake_supervise(command, output, **options):
        calls.append(options)
        return {'status': 'COMPLETED'}

    monkeypatch.setattr(m, 'supervise', fake_supervise)
    monkeypatch.setattr(cli.commands, 'stage_command', lambda root, seal: ['/controlled/stage'])
    for limit, expected_exit in [(201326592, 2), (ADOPTED, 0)]:
        seal_path = tmp_path / f'seal-{limit}.json'
        seal_path.write_text(json.dumps(_seal(tmp_path, limit)))
        monkeypatch.setattr(sys, 'argv', ['stage-a', '--seal', str(seal_path)])
        assert cli.main() == expected_exit
    assert len(calls) == 1
    assert calls[0]['incremental_bytes'] == ADOPTED
    assert 'seal scope/limits mismatch' in capsys.readouterr().err


def test_new_static_setup_template_changes_only_supervise_limit_and_preserves_worker():
    reviewed_bytes = REVIEWED.read_bytes()
    assert hashlib.sha256(reviewed_bytes).hexdigest() == (
        '0ad8232b3bef8758b8f671bc4cdea980f5738e04899b0cbb10c0cc8027bd9291')
    old = ast.parse(reviewed_bytes)
    new = ast.parse(CURRENT.read_text())
    calls = [node for node in ast.walk(old) if isinstance(node, ast.Call)
             and isinstance(node.func, ast.Name) and node.func.id == 'supervise']
    assert len(calls) == 1
    limit = next(keyword for keyword in calls[0].keywords if keyword.arg == 'incremental_bytes')
    assert isinstance(limit.value, ast.Constant) and limit.value.value == 201326592
    limit.value.value = ADOPTED
    assert ast.dump(old, include_attributes=False) == ast.dump(new, include_attributes=False)
    workers = [node.value.value for node in new.body if isinstance(node, ast.Assign)
               and any(isinstance(target, ast.Name) and target.id == 'worker' for target in node.targets)
               and isinstance(node.value, ast.Constant)]
    assert len(workers) == 1
    assert hashlib.sha256(workers[0].encode('utf-8')).hexdigest() == (
        'f768a8f98577653e81779f080bac27edddd854b173a3c221e3499b5d21ccc1b0')
