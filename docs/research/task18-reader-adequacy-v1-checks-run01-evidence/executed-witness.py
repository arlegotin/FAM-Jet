"""One fresh, bounded fixture invocation; controller custody, not model code."""
from pathlib import Path
import datetime, hashlib, json, os, subprocess, sys, time

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / 'artifacts/task18-reader-adequacy-v1-checks-01'
PREP = ROOT / 'artifacts/task18-reader-adequacy-v1-checks-01-prep'
EXPECTED_HEAD = 'e63a8c1824e94dad347de92039544d5dd0a5e4c0'
SECONDS = 1200
FINALIZATION_RESERVE_SECONDS = 20
ENV_THREADS = ('OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'VECLIB_MAXIMUM_THREADS')


def write(name, data):
    path = PREP / name
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(data, indent=2, allow_nan=False) + '\n')
    tmp.replace(path)


def main():
    start = time.monotonic()
    if OUT.exists() or PREP.exists():
        raise FileExistsError('one-use artifact paths already exist; no replay')
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    if head != EXPECTED_HEAD or subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT):
        raise ValueError('requires exact clean reviewed source')
    PREP.mkdir(parents=True)
    argv = [str(ROOT / '.venv/bin/python'), '-m', 'validation.reader_adequacy_v1.check_run',
            '--mode', 'numerical_then_tiny_fit', '--out', str(OUT)]
    env = dict(os.environ, **{k: '1' for k in ENV_THREADS})
    record = dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(), source_head=head,
                  wrapper_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  argv=argv, thread_environment={k: env[k] for k in ENV_THREADS},
                  start_monotonic=start, deadline_monotonic=start+SECONDS,
                  work_deadline_monotonic=start+SECONDS-FINALIZATION_RESERVE_SECONDS,
                  finalization_reserve_seconds=FINALIZATION_RESERVE_SECONDS,
                  output=str(OUT.relative_to(ROOT)), status='STARTING', external_time_cap_seconds=SECONDS,
                  scope='Numerical and known-sufficient tiny fit only; no development/protection')
    write('allocation.json', record)
    exit_code = None
    timed_out = False
    with (PREP/'stdout.log').open('wb') as stdout, (PREP/'stderr.log').open('wb') as stderr:
        child = subprocess.Popen(argv, cwd=ROOT, env=env, stdin=subprocess.DEVNULL, stdout=stdout, stderr=stderr)
        record['pid'] = child.pid
        write('allocation.json', record)
        try:
            exit_code = child.wait(timeout=max(0., start+SECONDS-FINALIZATION_RESERVE_SECONDS-time.monotonic()))
        except subprocess.TimeoutExpired:
            timed_out = True
            child.kill()
            exit_code = child.wait()
    elapsed = time.monotonic()-start
    # This is a post-return observation. It does not promote the child's own status.
    record.update(status=('FAILED_TIMEOUT' if timed_out else ('RETURNED_ZERO' if exit_code == 0 else 'FAILED_RETURN')), actual_returncode=exit_code, timed_out=timed_out,
                  end_monotonic=time.monotonic(), elapsed_seconds=elapsed,
                  git_head_after=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip())
    record['output_bytes_before_exit_witness'] = sum(x.stat().st_size for d in (OUT, PREP) if d.exists()
                                              for x in d.rglob('*') if x.is_file())
    record['child_json_after_return'] = [dict(path=str(x.relative_to(ROOT)), bytes=x.stat().st_size,
                                               sha256=hashlib.sha256(x.read_bytes()).hexdigest())
                                         for x in sorted(OUT.glob('*.json'))] if OUT.exists() else []
    record['interrupted_work_note'] = ('Only last durably recorded work is known; any in-flight updates are not invented.'
                                       if timed_out else None)
    write('exit-witness.json', record)
    print(json.dumps({k:record[k] for k in ('actual_returncode','timed_out','elapsed_seconds','output_bytes_before_exit_witness')}))
    return 124 if timed_out else (0 if exit_code == 0 and elapsed <= SECONDS and record['git_head_after'] == head else 1)


if __name__ == '__main__':
    raise SystemExit(main())
