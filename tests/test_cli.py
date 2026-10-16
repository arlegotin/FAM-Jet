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


def test_cli_rejects_oversized_reader_before_allocation(tmp_path,monkeypatch):
    from dataclasses import asdict,replace
    import json
    from test_training import tiny,api
    from famjet.run import main
    c=tiny(); c=replace(c,model=replace(c.model,reader=replace(c.model.reader,layers=1_000_000)))
    path=tmp_path/'config.json'; path.write_text(json.dumps(asdict(c)))
    def allocation_forbidden(*args,**kwargs):
        pytest.fail('CLI allocated oversized reader')
    monkeypatch.setattr(api(),'make_model',allocation_forbidden)
    with pytest.raises(ValueError,match='smoke envelope'):
        main(['--config',str(path),'--run-dir',str(tmp_path/'run')])
    record=json.loads((tmp_path/'run'/'run.json').read_text())
    assert record['status']=='failed' and record['attempted_episode_ids']==[]
