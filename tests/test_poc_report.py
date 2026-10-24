"""Report replay must be artifact-only, deterministic, and explicit about scope."""

import hashlib
import json

import pytest

from test_poc_report_inputs import _tiny_run
from famjet_poc.pipeline import StageLedger


def test_test_only_report_is_deterministic_and_never_claims_science(tmp_path):
    from famjet_poc.report import render_report
    run = _tiny_run(tmp_path / 'run')
    first = render_report(run, tmp_path / 'one' / 'final.md')
    second = render_report(run, tmp_path / 'two' / 'final.md')
    assert first['sha256'] == second['sha256']
    assert first['bytes'] == second['bytes']
    text = (tmp_path / 'one' / 'final.md').read_text()
    assert 'non_scientific_smoke' in text
    assert 'does not support a scientific conclusion' in text
    assert 'scientific_artifacts_validated' not in text
    machine = json.loads((tmp_path / 'one' / 'final.json').read_text())
    assert machine['status'] == 'non_scientific_smoke'
    assert machine['metrics']['native_rmse_micrograms'] is None
    assert machine['metrics']['native_rmse_status'] == 'not_applicable_test_fixture'
    assert hashlib.sha256((tmp_path / 'one' / 'final.md').read_bytes()).hexdigest() == first['sha256']


def test_report_rejects_tampered_release_without_publishing_output(tmp_path):
    from famjet_poc.report import render_report
    run = _tiny_run(tmp_path / 'run')
    (run / 'release' / 'bank.json').write_text('[]')
    target = tmp_path / 'final.md'
    with pytest.raises(ValueError, match='hash'):
        render_report(run, target)
    assert not target.exists()


def test_explicit_plot_interpreter_must_exist(tmp_path, monkeypatch):
    from famjet_poc.report import _plot_python
    monkeypatch.setenv('FAMJET_REPORT_PYTHON', str(tmp_path / 'absent-python'))
    with pytest.raises(RuntimeError, match='FAMJET_REPORT_PYTHON|Matplotlib'):
        _plot_python()


def test_render_before_and_after_report_stage_completion_is_byte_identical(tmp_path):
    from famjet_poc.report import render_report
    run = _tiny_run(tmp_path / 'run')
    first = None
    def action(directory):
        nonlocal first
        first = render_report(run, directory / 'final.md')
        return first
    StageLedger(run).stage('report', {'test_only': True}, action)
    second = render_report(run, tmp_path / 'replay' / 'final.md')
    assert first['sha256'] == second['sha256']
