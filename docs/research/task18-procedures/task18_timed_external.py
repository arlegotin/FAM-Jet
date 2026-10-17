from pathlib import Path
from datetime import datetime, timezone
import argparse, subprocess, time, json, hashlib
p=argparse.ArgumentParser();p.add_argument('name');p.add_argument('command',nargs=argparse.REMAINDER);a=p.parse_args()
out=Path('artifacts/task18-evidence')/f'{a.name}-time-boundary.json'
assert not out.exists(), out
start=datetime.now(timezone.utc);tick=time.perf_counter()
record={'command':a.command,'start_utc':start.isoformat(),'timer':'time.perf_counter; not CPU time and may exclude system sleep on this host','power_override':False,'helper_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
out.write_text(json.dumps(record,sort_keys=True)+'\n')
try:
 r=subprocess.run(a.command);record['returncode']=r.returncode
finally:
 end=datetime.now(timezone.utc);record.update(end_utc=end.isoformat(),utc_interval_seconds=(end-start).total_seconds(),perf_counter_seconds=time.perf_counter()-tick);out.write_text(json.dumps(record,sort_keys=True)+'\n')
raise SystemExit(r.returncode)
