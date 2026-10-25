"""Read-only scope, identity and raw-evidence verification for the timing report fix."""
import ast
import hashlib
import json
from pathlib import Path
import subprocess
import sys
sys.path.insert(0, str(Path.cwd()))
from famjet_poc.cache import e3_source_sha256
from famjet_poc.contracts import source_sha256
from famjet_poc.inference import source_identity
base = '95c9557edda09eea02f3ff3296edd6f87155ef1c'
root = Path('docs/research/e2e-report-timing-fix-evidence')
for path in root.glob('*.json'):
    receipt = json.loads(path.read_bytes())
    if 'log' in receipt:
        raw = Path(receipt['log']).read_bytes()
        assert (len(raw), hashlib.sha256(raw).hexdigest()) == (receipt['bytes'], receipt['sha256'])
for filename, allowed in (('report.py', {'_science_chart_data', '_science_markdown'}),
                          ('report_inputs.py', {'_verify_timing'})):
    path = Path('famjet_poc') / filename
    old = ast.parse(subprocess.check_output(['git', 'show', base + ':' + str(path)], text=True))
    current = ast.parse(path.read_text())
    old.body = [n for n in old.body if not isinstance(n, ast.FunctionDef) or n.name not in allowed]
    current.body = [n for n in current.body if not isinstance(n, ast.FunctionDef) or n.name not in allowed]
    assert ast.dump(old) == ast.dump(current)
paths = ['famjet', 'configs', 'requirements.lock', 'docs/reporting-requirements.lock',
         'docs/research/e2e-development-resource-policy.json', 'docs/research/e2e-coordinate-source-compatibility.json',
         'docs/research/e2e-coordinate-source-evidence']
paths += [str(p) for p in Path('famjet_poc').glob('*.py') if p.name not in {'report.py', 'report_inputs.py'}]
assert subprocess.check_output(['git', 'diff', base, '--', *paths]) == b''
assert source_sha256() == 'f78761891876540011e577293e31a89c7661ef66adbb522d2cbcd36c331d8475'
assert source_identity()['sha256'] == '5cdbae0a61810a0f9d509ed1d462530d708439021f8f9fc81ce04fd12f39bfb4'
assert e3_source_sha256() == 'e25b63ee60f51ed511fc7af5d3f713c9a404301f51178283c0a2066d940e68ba'
print(json.dumps({'source_head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
                  'e1': source_sha256(), 'e2': source_identity()['sha256'], 'e3': e3_source_sha256(),
                  'only_named_report_functions_changed': True,
                  'all_other_production_including_plots_pipeline_numeric_config_locks_policy_unchanged': True,
                  'old_coordinate_source_evidence_unchanged': True}, indent=2))
