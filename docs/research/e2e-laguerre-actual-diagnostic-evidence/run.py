"""Single cold diagnostic invocation; retain exact command, clocks, logs and budget."""
import hashlib
import json
import os
from pathlib import Path
import resource
import subprocess
import sys
import time

root = Path(__file__).resolve().parents[3]
out = Path(__file__).resolve().parent
log = out/'diagnostic.log'
assert not log.exists(), 'Never overwrite a diagnostic attempt'
env = dict(os.environ)
variables = {k: '1' for k in ('OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'VECLIB_MAXIMUM_THREADS')}
variables['PYTHONPATH'] = '.'
env.update(variables)
argv = [str(root/'.venv/bin/python'), str(out/'diagnose.py')]
start_epoch, start_mono = time.time(), time.monotonic()
with log.open('xb') as stream:
    process = subprocess.Popen(argv, cwd=root, env=env, stdout=stream, stderr=subprocess.STDOUT)
    try:
        code = process.wait(timeout=295)
    except subprocess.TimeoutExpired:
        process.kill()
        code = process.wait()
end_epoch, end_mono = time.time(), time.monotonic()
peak = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
record = {'argv': argv, 'launcher_argv': sys.argv, 'cwd': str(root), 'environment_overrides': variables,
          'start_epoch_seconds': start_epoch, 'end_epoch_seconds': end_epoch,
          'start_monotonic_seconds': start_mono, 'end_monotonic_seconds': end_mono,
          'elapsed_seconds': end_mono-start_mono, 'exit_code': code,
          'peak_child_rss_bytes': peak if sys.platform == 'darwin' else peak*1024,
          'budget': {'max_wall_seconds': 300, 'max_rss_bytes': 1536*1024**2, 'max_new_output_bytes': 32*1024**2},
          'files': {str(p.relative_to(root)): {'bytes': p.stat().st_size, 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()}
                    for p in sorted(out.iterdir()) if p.is_file()}}
record['new_output_bytes_at_completion'] = sum(r['bytes'] for r in record['files'].values())
(out/'invocation.json').write_text(json.dumps(record, indent=2, sort_keys=True)+'\n')
print(json.dumps(record, indent=2))
assert end_mono-start_mono <= 300
assert record['peak_child_rss_bytes'] <= 1536*1024**2
assert record['new_output_bytes_at_completion'] <= 32*1024**2
raise SystemExit(code)
