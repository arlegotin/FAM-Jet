"""Read-only preservation and policy check for the K16 probe admission fix."""
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
base = 'eb6d33eac3f3995208c7453fa4eb0e51fbcb7df7'
root = Path('docs/research/e2e-coordinate-source-evidence')
old_count = 0
for directory in (root, root / 'fix-round1'):
    index_path = directory / 'evidence-index.json'
    assert index_path.read_bytes() == subprocess.check_output(['git', 'show', base + ':' + str(index_path)])
    index = json.loads(index_path.read_bytes())
    for name, record in index['files'].items():
        raw = (directory / name).read_bytes()
        assert (len(raw), hashlib.sha256(raw).hexdigest()) == (record['bytes'], record['sha256'])
        old_count += 1
for path in (root / 'fix-round2').glob('*.json'):
    record = json.loads(path.read_bytes())
    if 'log' in record:
        raw = Path(record['log']).read_bytes()
        assert (len(raw), hashlib.sha256(raw).hexdigest()) == (record['bytes'], record['sha256'])
policy = json.loads(Path('docs/research/e2e-development-resource-policy.json').read_bytes())
previous = json.loads(subprocess.check_output(['git', 'show', base + ':docs/research/e2e-development-resource-policy.json']))
assert policy == {**previous, 'fresh_probe_required': True}
assert source_sha256() == 'f78761891876540011e577293e31a89c7661ef66adbb522d2cbcd36c331d8475'
assert source_identity()['sha256'] == '5cdbae0a61810a0f9d509ed1d462530d708439021f8f9fc81ce04fd12f39bfb4'
assert e3_source_sha256() == policy['expected_e3_source_sha256'] == 'e25b63ee60f51ed511fc7af5d3f713c9a404301f51178283c0a2066d940e68ba'
current = ast.parse(Path('famjet_poc/pipeline.py').read_text())
old = ast.parse(subprocess.check_output(['git', 'show', base + ':famjet_poc/pipeline.py'], text=True))
current.body = [node for node in current.body if not isinstance(node, ast.FunctionDef) or node.name != 'k16_probe_allocation']
old.body = [node for node in old.body if not isinstance(node, ast.FunctionDef) or node.name != 'k16_probe_allocation']
assert ast.dump(current) == ast.dump(old)
paths = ['famjet', 'configs', 'requirements.lock', 'docs/reporting-requirements.lock']
paths += [str(path) for path in Path('famjet_poc').glob('*.py') if path.name != 'pipeline.py']
assert subprocess.check_output(['git', 'diff', base, '--', *paths]) == b''
print(json.dumps({'source_head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(), 'old_indexed_evidence_files_unchanged': old_count, 'e1': source_sha256(), 'e2': source_identity()['sha256'], 'e3': e3_source_sha256(), 'resource_policy_only_adds_true_flag': True, 'pipeline_outside_k16_probe_allocation_unchanged': True, 'all_other_production_modules_core_config_locks_unchanged': True}, indent=2))
