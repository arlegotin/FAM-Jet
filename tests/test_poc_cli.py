"""The public entry point must be runnable without starting a scientific run."""

import subprocess
import sys

import pytest


def test_help_and_subcommand_help_are_lightweight():
    for args in (('--help',), ('run', '--help'), ('report', '--help')):
        script = (
            "import sys\n"
            "from famjet_poc.__main__ import main\n"
            "try:\n"
            "    main(sys.argv[1:])\n"
            "except SystemExit as exc:\n"
            "    assert exc.code == 0\n"
            "assert 'torch' not in sys.modules\n"
        )
        result = subprocess.run([sys.executable, '-c', script, *args],
                                capture_output=True, text=True, timeout=10)
        assert result.returncode == 0, result.stderr
        assert 'usage:' in result.stdout


def test_run_dispatches_actual_pipeline_and_propagates_failure(tmp_path, monkeypatch):
    from famjet_poc.__main__ import main
    from famjet_poc import pipeline

    calls = []
    def run(out, resume=False):
        calls.append((out, resume))
        raise RuntimeError('blocked science')

    monkeypatch.setattr(pipeline, 'run', run)
    with pytest.raises(RuntimeError, match='blocked science'):
        main(['run', '--out', str(tmp_path / 'run'), '--resume'])
    assert calls == [(tmp_path / 'run', True)]


def test_report_dispatches_render_and_requires_content_ref(tmp_path, monkeypatch):
    from famjet_poc.__main__ import main
    from famjet_poc import report

    calls = []
    monkeypatch.setattr(report, 'render_report', lambda run, out: calls.append((run, out)) or None)
    with pytest.raises(RuntimeError, match='content reference'):
        main(['report', '--run', str(tmp_path / 'run'), '--out', str(tmp_path / 'final.md')])
    assert calls == [(tmp_path / 'run', tmp_path / 'final.md')]
