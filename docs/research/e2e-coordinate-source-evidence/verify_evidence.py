"""Read-only final source/policy and retained command-log closure check."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
sys.path.insert(0, str(Path.cwd()))
from famjet_poc.cache import e3_source_sha256
from famjet_poc.contracts import source_sha256
from famjet_poc.inference import source_identity
root = Path('docs/research/e2e-coordinate-source-evidence')
checked = []
for path in sorted(root.glob('*.json')):
    receipt = json.loads(path.read_bytes())
    if 'log' not in receipt:
        continue
    raw = Path(receipt['log']).read_bytes()
    assert len(raw) == receipt['bytes']
    assert hashlib.sha256(raw).hexdigest() == receipt['sha256']
    checked.append(path.name)
policy = json.loads(Path('docs/research/e2e-development-resource-policy.json').read_bytes())
compatibility = json.loads(Path('docs/research/e2e-coordinate-source-compatibility.json').read_bytes())
assert policy['expected_e3_source_sha256'] == compatibility['e3_source_sha256'] == e3_source_sha256()
assert e3_source_sha256() in Path('famjet_poc/transfer.py').read_text()
assert source_sha256() == compatibility['e1_source_sha256'] == 'f78761891876540011e577293e31a89c7661ef66adbb522d2cbcd36c331d8475'
assert source_identity()['sha256'] == compatibility['e2_source_sha256'] == '5cdbae0a61810a0f9d509ed1d462530d708439021f8f9fc81ce04fd12f39bfb4'
assert policy['max_wall_seconds'] == 3600
for name, item in compatibility['modules'].items():
    raw = (Path('famjet_poc') / name).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == item['current_sha256']
    original = subprocess.check_output(['git', 'show', compatibility['base'] + ':famjet_poc/' + name])
    assert hashlib.sha256(original).hexdigest() == item['base_sha256']
    assert (raw == original) == item['unchanged']
assert subprocess.check_output(['git', 'diff', compatibility['base'], '--', 'famjet', 'requirements.lock', 'docs/reporting-requirements.lock', 'famjet_poc/pipeline.py', 'configs']) == b''
print(json.dumps({'verified_receipts': checked, 'e1': source_sha256(), 'e2': source_identity()['sha256'], 'e3': e3_source_sha256(), 'core_config_locks_pipeline_unchanged': True}, indent=2))
