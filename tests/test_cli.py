"""Help exits before touching configs, data, discovery or run directories."""
import os
from pathlib import Path
import subprocess
import sys
import pytest


@pytest.mark.parametrize('module',['doctor','prepare','run'])
def test_cli_help_has_no_run_side_effect(tmp_path,module):
    env={**os.environ,'PYTHONPATH':str(Path(__file__).resolve().parents[1])}
    proc=subprocess.run([sys.executable,'-m',f'famjet.{module}','--help'],cwd=tmp_path,env=env,capture_output=True,text=True)
    assert proc.returncode==0,proc.stderr
    assert 'usage:' in proc.stdout
    assert list(tmp_path.iterdir())==[]
