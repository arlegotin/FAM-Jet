from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,os,signal,subprocess,time
out=Path('artifacts/task18-evidence/epsilon1em6-remaining-9aca1b');out.mkdir(exist_ok=False)
cmd=['.venv/bin/python','/tmp/task18-epsilon-numerical-9aca1b/task18_epsilon_numeric_driver.py','remaining','--seal','artifacts/task18-evidence/epsilon1em6-numerical-preparation-9aca1b/preparation-seal.json','--seal-sha','bb6b226e8ca5ebd23006573ca6b7f51cf272701a7d0ea0212e1da91c92cebf49']
started=time.perf_counter();utc=datetime.now(timezone.utc)
def write(name,value):
 with (out/name).open('x') as f:json.dump(value,f,sort_keys=True);f.write('\n')
write('allocation.json',{'command':cmd,'timeout_seconds':90,'scope':'root-authorized remaining23 Jet01-11 thenBank00-11 only, no retry','utc_start':utc.isoformat(),'helper_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()})
timedout=False
with (out/'stdout.txt').open('x') as log:
 p=subprocess.Popen(cmd,stdout=log,stderr=subprocess.STDOUT,env={**os.environ,'PYTHONPATH':'.:/tmp/task18-epsilon-numerical-9aca1b'},start_new_session=True)
 write('process.json',{'pid':p.pid,'process_group':p.pid,'start_new_session':True})
 try:p.wait(timeout=90)
 except subprocess.TimeoutExpired:
  timedout=True;os.killpg(p.pid,signal.SIGTERM)
  try:p.wait(timeout=3)
  except subprocess.TimeoutExpired:os.killpg(p.pid,signal.SIGKILL);p.wait()
end=datetime.now(timezone.utc);record={'status':'timeout' if timedout else 'completed' if p.returncode==0 else 'failed','returncode':p.returncode,'timeout_seconds':90,'perf_seconds':time.perf_counter()-started,'utc_start':utc.isoformat(),'utc_end':end.isoformat(),'utc_seconds':(end-utc).total_seconds(),'no_retry':True}
write('summary.json',record);print(json.dumps(record),flush=True)
