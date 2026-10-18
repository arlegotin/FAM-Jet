"""Owned unique pytest attempt, immutable inputs and immediate full output archive."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time
ROOT=Path(__file__).resolve().parents[3]
OUT=Path(__file__).resolve().parent
name=sys.argv[1]; destination=OUT/name; base=Path('/tmp/task18-python-lifetime-fix1-'+name)
if destination.exists() or base.exists(): raise RuntimeError('attempt paths must be new')
destination.mkdir(); inputs=destination/'source-inputs'; inputs.mkdir()
paths=[*sorted((ROOT/'validation/kernel_stage_a').glob('*.py')),
       ROOT/'tests/test_kernel_stage_a_python_lifetime_fix1.py',ROOT/'tests/test_kernel_stage_a_native_process.py']
for path in paths:
    target=inputs/path.relative_to(ROOT); target.parent.mkdir(parents=True,exist_ok=True); shutil.copyfile(path,target)
command=[str(ROOT/'.venv/bin/python'),'-m','pytest','-q',*sys.argv[2:],'--basetemp='+str(base)]
started=time.monotonic()
with (destination/'output.log').open('wb') as stream:
    result=subprocess.run(command,cwd=ROOT,stdout=stream,stderr=subprocess.STDOUT)
if base.exists(): shutil.copytree(base,destination/'specimens',symlinks=True)
record=dict(command=command,exit=result.returncode,seconds=time.monotonic()-started,
            original_basetemp=str(base),actual_basetemp=str(base.resolve()),durable_specimens=str(destination/'specimens'),
            source_inputs=str(inputs),source_head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip())
(destination/'attempt.json').write_text(json.dumps(record,indent=2)+'\n')
print((destination/'output.log').read_text()); print(json.dumps(record,indent=2))
raise SystemExit(result.returncode)
