"""Read-only source and sealed run identity check for the R7 source gate."""

import hashlib
import json
from pathlib import Path
import sys

root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(root))

from famjet.provenance import canonical_hash
from famjet_poc.protected import executable_identity
from famjet_poc.report_inputs import _admit_report_migration


manifest = json.loads((root / 'docs/research/e2e-run06-report-migration.json').read_bytes())
archive = root / 'docs/research/e2e-run06-execution-source'
old = manifest['old_files']
new = executable_identity()
assert len(old) == len(new['files']) == 74
assert canonical_hash(old) == manifest['old_sha256']
assert new == {'files': manifest['new_files'], 'sha256': manifest['new_sha256']}
assert {key for key in old if old[key] != new['files'][key]} == {'famjet_poc/report_inputs.py'}
assert set(old) | {'identity.json'} == {
    str(path.relative_to(archive)) for path in archive.rglob('*') if path.is_file()}
for name, sha in old.items():
    assert hashlib.sha256((archive / name).read_bytes()).hexdigest() == sha
for run in (root / 'artifacts/e2e-core-run-06',
            root / 'artifacts/e2e-run06-original-archive/run'):
    accepted = _admit_report_migration(run, 'run06-report-order-v1', archive)
    assert accepted['execution_sha256'] == manifest['old_sha256']
    assert accepted['reporter_sha256'] == manifest['new_sha256']
print(json.dumps({'status': 'passed', 'old_sha256': manifest['old_sha256'],
                  'new_sha256': manifest['new_sha256'],
                  'changed_files': ['famjet_poc/report_inputs.py'],
                  'source_file_count': len(old), 'preflight_roots': 2}, sort_keys=True))
