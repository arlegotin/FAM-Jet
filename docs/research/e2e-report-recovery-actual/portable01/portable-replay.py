"""Root's reversible unavailable-originals replay witness; no science execution."""
from pathlib import Path
import datetime, hashlib, json, os, signal, subprocess, sys

ROOT = Path(subprocess.check_output(['git', 'rev-parse', '--show-toplevel'], text=True).strip())
BASE = ROOT / 'artifacts/e2e-run06-original-archive'
OUT = ROOT / 'artifacts/e2e-run06-portable-replay-01'
OUT.mkdir(exist_ok=False)
INDEX = json.loads((ROOT / 'docs/research/e2e-run06-execution-record/index.json').read_bytes())
ORIGINALS = [ROOT / INDEX['run_root'], ROOT / INDEX['prep_root'], ROOT / 'docs/research/e2e-run06-execution-source']
MOVED = []
proof = {'schema_version': 1, 'kind': 'run06_portable_unavailable_originals_replay',
         'utc_start': datetime.datetime.now(datetime.timezone.utc).isoformat(),
         'wrapper_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
         'original_locations': [str(p) for p in ORIGINALS],
         'copied_run': str(BASE / 'run'), 'copied_source': str(BASE / 'execution-source'),
         'clean_python': '/private/tmp/famjet-clean-20261024-01/bin/python', 'status': 'starting'}

def save():
    (OUT / 'portable-replay-proof.json').write_text(json.dumps(proof, indent=2) + '\n')

def file_record(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return {'bytes': path.stat().st_size, 'sha256': digest.hexdigest()}

def stopped(signum, frame):
    raise InterruptedError('owned replay interrupted: ' + str(signum))

signal.signal(signal.SIGTERM, stopped)
signal.signal(signal.SIGINT, stopped)
save()
try:
    for original in ORIGINALS:
        temporary = original.with_name(original.name + '.unavailable-for-portable-replay')
        if not original.is_dir() or temporary.exists():
            raise RuntimeError('expected original and fresh temporary name required')
        original.rename(temporary)
        MOVED.append((original, temporary))
    proof['unavailable_before_render'] = all(not original.exists() for original in ORIGINALS)
    if not proof['unavailable_before_render']:
        raise RuntimeError('original paths still available')
    save()
    command = [proof['clean_python'], str(ROOT / 'scripts/report_run06_recovery.py'),
               '--run', str(BASE / 'run'), '--out', str(OUT / 'report/final.md'),
               '--archived-source', str(BASE / 'execution-source'),
               '--compatibility-id', 'run06-report-order-v1']
    proof['argv'] = command
    result = subprocess.run(command, cwd=ROOT, check=False)
    proof['returncode'] = result.returncode
    proof['unavailable_after_render'] = all(not original.exists() for original in ORIGINALS)
    if result.returncode or not proof['unavailable_after_render']:
        raise RuntimeError('copied report failed or originals became available')
finally:
    for original, temporary in reversed(MOVED):
        if temporary.exists() and not original.exists():
            temporary.rename(original)
    proof['originals_restored'] = all(original.is_dir() for original in ORIGINALS)
    proof['utc_restored'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    save()

for root, records in [(ORIGINALS[0], INDEX['files']), (ORIGINALS[1], INDEX['prep_files'])]:
    found = {p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file()}
    if found != set(records):
        raise RuntimeError('original inventory changed')
    for name, expected in records.items():
        if file_record(root / name) != expected:
            raise RuntimeError('original bytes changed: ' + name)
for name, digest in INDEX['frozen_executable']['files'].items():
    if file_record(ORIGINALS[2] / name)['sha256'] != digest:
        raise RuntimeError('original execution source changed')

FIRST = ROOT / 'artifacts/e2e-run06-recovery-01/report'
SECOND = OUT / 'report'
files = lambda root: {p.relative_to(root).as_posix(): file_record(p)
                      for p in root.rglob('*') if p.is_file() and p.name != 'recovery-receipt.json'}
first, second = files(FIRST), files(SECOND)
if first != second:
    proof['status'] = 'failed_deterministic_output_comparison'
    proof['different_files'] = sorted(name for name in set(first) | set(second) if first.get(name) != second.get(name))
    save()
    raise RuntimeError('deterministic report outputs differ')
proof.update(status='passed', original_run_files_unchanged=len(INDEX['files']),
             original_prep_files_unchanged=len(INDEX['prep_files']),
             original_execution_files_unchanged=len(INDEX['frozen_executable']['files']),
             deterministic_output_files=first, deterministic_output_count=len(first),
             utc_end=datetime.datetime.now(datetime.timezone.utc).isoformat())
save()
print(json.dumps({key: proof[key] for key in ['status', 'returncode', 'originals_restored', 'deterministic_output_count']}))
