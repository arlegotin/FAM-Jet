from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,os,signal,subprocess,time
out=Path('artifacts/task18-evidence/epsilon1em6-fullprep-execution-c715479');out.mkdir(exist_ok=False)
cmd=['.venv/bin/python','/tmp/task18-epsilon-fullprep-c715479/task18_epsilon_full_driver.py','--seal','artifacts/task18-evidence/epsilon1em6-fullprep-preparation-c715479/preparation-seal.json','--seal-sha','53fc2cc2e2af15ad915abd4a0f5db90035760e898d5eae81d66a322e6abe93c1']
started=time.perf_counter();utc=datetime.now(timezone.utc)
def write(name,value):
 with (out/name).open('x') as f:json.dump(value,f,sort_keys=True);f.write('\n')
write('allocation.json',{'command':cmd,'timeout_seconds':1800,'scope':'root-authorized seven-phase RAW6144 thenJetBank768fit/features+cold768/96STOP2+24fitted each; no retry or scientific training','utc_start':utc.isoformat(),'helper_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()})
timedout=False;signals=[]
with (out/'stdout.txt').open('x') as log:
 p=subprocess.Popen(cmd,stdout=log,stderr=subprocess.STDOUT,env={**os.environ,'PYTHONPATH':'.:/tmp/task18-epsilon-fullprep-c715479'},start_new_session=True)
 write('process.json',{'pid':p.pid,'process_group':p.pid,'start_new_session':True})
 try:p.wait(timeout=1800)
 except subprocess.TimeoutExpired:
  timedout=True
  try:os.killpg(p.pid,signal.SIGTERM);signals.append('SIGTERM_group')
  except ProcessLookupError:pass
  try:p.wait(timeout=3)
  except subprocess.TimeoutExpired:pass
  # Kill any still-existing children even if the driver exited on SIGTERM.
  try:os.killpg(p.pid,signal.SIGKILL);signals.append('SIGKILL_remaining_group')
  except ProcessLookupError:pass
  p.wait()
end=datetime.now(timezone.utc);record={'status':'timeout' if timedout else 'completed' if p.returncode==0 else 'failed','returncode':p.returncode,'timeout_seconds':1800,'perf_seconds':time.perf_counter()-started,'utc_start':utc.isoformat(),'utc_end':end.isoformat(),'utc_seconds':(end-utc).total_seconds(),'no_retry':True,'signals':signals}
write('summary.json',record);print(json.dumps(record),flush=True)
