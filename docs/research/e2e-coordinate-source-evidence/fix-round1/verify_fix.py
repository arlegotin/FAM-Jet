"""Read-only preservation, source-pin, and admission-call inventory for fix round 1."""
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
base = '254424b0f91f7517af503ca04ae9a49f5bc8a00f'
root = Path('docs/research/e2e-coordinate-source-evidence')
old_index = json.loads((root / 'evidence-index.json').read_bytes())
for name, record in old_index['files'].items():
    raw = (root / name).read_bytes()
    assert (len(raw), hashlib.sha256(raw).hexdigest()) == (record['bytes'], record['sha256'])
assert (root / 'evidence-index.json').read_bytes() == subprocess.check_output(['git', 'show', base + ':' + str(root / 'evidence-index.json')])
for receipt_path in sorted((root / 'fix-round1').glob('*.json')):
    receipt = json.loads(receipt_path.read_bytes())
    if 'log' in receipt:
        raw = Path(receipt['log']).read_bytes()
        assert (len(raw), hashlib.sha256(raw).hexdigest()) == (receipt['bytes'], receipt['sha256'])
policy = json.loads(Path('docs/research/e2e-development-resource-policy.json').read_bytes())
compatibility = json.loads(Path('docs/research/e2e-coordinate-source-compatibility.json').read_bytes())
assert policy['expected_e3_source_sha256'] == compatibility['e3_source_sha256'] == e3_source_sha256()
assert e3_source_sha256() in Path('famjet_poc/transfer.py').read_text()
assert source_sha256() == 'f78761891876540011e577293e31a89c7661ef66adbb522d2cbcd36c331d8475'
assert source_identity()['sha256'] == '5cdbae0a61810a0f9d509ed1d462530d708439021f8f9fc81ce04fd12f39bfb4'
unchanged = ['famjet', 'configs', 'requirements.lock', 'docs/reporting-requirements.lock']
unchanged += ['famjet_poc/' + name for name in ('contracts.py', 'data.py', 'models.py', 'inference.py', 'worker.py', 'wire.py', 'cache.py', 'timing.py', 'pipeline.py')]
assert subprocess.check_output(['git', 'diff', base, '--', *unchanged]) == b''
calls = []
for name in ('comparators.py', 'study.py', 'protected.py', 'transfer.py', 'report_inputs.py'):
    path = Path('famjet_poc') / name
    tree = ast.parse(path.read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in ('validate_coordinate_audits', 'validate_scored_receipt'):
            key = 'expected_model' if node.func.id == 'validate_coordinate_audits' else 'coordinate_model'
            assert key in {keyword.arg for keyword in node.keywords}
            calls.append({'path': str(path), 'line': node.lineno, 'call': node.func.id, 'required_keyword': key})
print(json.dumps({'old_evidence_files_unchanged': len(old_index['files']), 'old_evidence_bytes': old_index['total_bytes'], 'source_head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(), 'e1': source_sha256(), 'e2': source_identity()['sha256'], 'e3': e3_source_sha256(), 'all_production_admission_calls': calls, 'core_e1_e2_worker_wire_cache_timing_pipeline_config_locks_unchanged': True}, indent=2))
