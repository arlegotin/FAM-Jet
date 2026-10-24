"""Root audit helper: capture one argv without shell expansion or log overwrite."""
import datetime, hashlib, json, os, pathlib, subprocess, sys, time
out = pathlib.Path(sys.argv[1]); timeout = float(sys.argv[2]); argv = sys.argv[3:]
if not argv or timeout <= 0: raise ValueError('output stem, positive timeout, argv required')
out.parent.mkdir(parents=True, exist_ok=True)
meta = out.with_suffix('.json'); log = out.with_suffix('.log')
if meta.exists() or log.exists(): raise FileExistsError('one-use audit paths required')
env = dict(os.environ, OMP_NUM_THREADS='1', MKL_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', VECLIB_MAXIMUM_THREADS='1')
start = time.monotonic(); utc = datetime.datetime.now(datetime.timezone.utc).isoformat(); status = 'completed'
with log.open('xb') as stream:
    try: result = subprocess.run(argv, env=env, stdout=stream, stderr=subprocess.STDOUT, timeout=timeout); code = result.returncode
    except subprocess.TimeoutExpired: code = 124; status = 'timeout'
    except BaseException as exc: code = 125; status = type(exc).__name__ + ': ' + str(exc)
raw = log.read_bytes(); record = {'argv':argv, 'cwd':os.getcwd(), 'utc_start':utc, 'elapsed_seconds':time.monotonic()-start, 'timeout_seconds':timeout, 'actual_returncode':code, 'status':status, 'log':str(log), 'log_sha256':hashlib.sha256(raw).hexdigest(), 'log_bytes':len(raw), 'thread_env':{k:env[k] for k in ('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS','VECLIB_MAXIMUM_THREADS')}, 'report_python':env.get('FAMJET_REPORT_PYTHON')}
meta.write_text(json.dumps(record,indent=2)+'\n'); print(json.dumps(record)); raise SystemExit(code)
