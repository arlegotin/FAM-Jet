from pathlib import Path
import subprocess, os, time, json, datetime, hashlib, resource, re, shutil, sys
ROOT=Path(__file__).resolve().parents[3]
MODE=sys.argv[1]
if MODE not in ('probe','calibration'):raise ValueError(MODE)
EXPECTED=sys.argv[2]
SECONDS=float(sys.argv[3]); ATTEMPT=int(sys.argv[4]) if len(sys.argv)>4 else 1
OUT=ROOT/('artifacts/e2e-inference-'+MODE+'-0'+str(ATTEMPT))
PREP=OUT.with_name(OUT.name+'-prep')
CAP=256*2**20
if OUT.exists() or PREP.exists():raise FileExistsError('one-use qualification path exists')
if subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()!=EXPECTED or subprocess.check_output(['git','status','--porcelain'],cwd=ROOT):raise RuntimeError('requires exact clean source')
vm=subprocess.check_output(['vm_stat'],text=True);page=int(re.search(r'page size of (\d+)',vm)[1]);num=lambda n:int(re.search(rf'{n}:\s+(\d+)',vm)[1]);free=(num('Pages free')+num('Pages speculative'))*page
if free<2*2**30 or .75*free<CAP or shutil.disk_usage(ROOT).free<4*2**30:raise RuntimeError('fresh admission refused')
PREP.mkdir(parents=True)
def save(name,value):
 p=PREP/name;t=p.with_suffix(p.suffix+'.tmp');t.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n');t.replace(p)
start=time.monotonic();rec={'utc_start':datetime.datetime.now(datetime.timezone.utc).isoformat(),'source_head':EXPECTED,'wrapper_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'start_monotonic':start,'work_deadline':start+SECONDS-20,'deadline':start+SECONDS,'free_plus_speculative':free,'rss_sum_cap':CAP,'output_cap':128*2**20,'status':'STARTING'}
if MODE=='probe':
 code='from famjet_poc.inference import probe_calibration; import json; r=probe_calibration('+repr(str(OUT))+'); print(json.dumps({"status":r["status"],"resource":r["resource"]})); raise SystemExit(0 if r["status"]=="complete" else 1)'
else:
 code='from famjet_poc.inference import run_calibration, validate_calibration; from pathlib import Path; import json; r=run_calibration('+repr(str(OUT))+',deadline_monotonic='+repr(rec['work_deadline'])+',attempt='+repr(ATTEMPT)+'); v=validate_calibration(r,{"out":'+repr(str(OUT))+',"deadline_monotonic":'+repr(rec['work_deadline'])+'}); Path('+repr(str(PREP/'validation.json'))+').write_text(json.dumps(v,indent=2)); print(json.dumps({"execution":r["status"],"validation":v})); raise SystemExit(0 if r["status"]=="complete" else 1)'
args=[str(ROOT/'.venv/bin/python'),'-c',code];env=dict(os.environ,OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',VECLIB_MAXIMUM_THREADS='1');rec['argv']=args;save('allocation.json',rec);samples=[];guard_failure=None
with (PREP/'stdout.log').open('wb') as stdout,(PREP/'stderr.log').open('wb') as stderr:
 child=subprocess.Popen(args,cwd=ROOT,env=env,stdin=subprocess.DEVNULL,stdout=stdout,stderr=stderr);rec['child_pid']=child.pid;save('allocation.json',rec)
 while child.poll() is None:
  if time.monotonic()>=start+SECONDS-20:guard_failure='work_deadline';child.kill();break
  result=subprocess.run(['ps','-o','pid=,rss=','-p',str(os.getpid())+','+str(child.pid)],capture_output=True,text=True,timeout=5)
  if result.returncode:guard_failure='rss_sample_failed';child.kill();break
  rows=[tuple(map(int,line.split())) for line in result.stdout.splitlines() if line.strip()];rss=sum(row[1]*1024 for row in rows);total=sum(p.stat().st_size for d in (OUT,PREP) if d.exists() for p in d.rglob('*') if p.is_file());samples.append({'monotonic':time.monotonic(),'rss_sum':rss,'pids':[x[0] for x in rows],'output_bytes':total})
  if rss>CAP or total>128*2**20:guard_failure='resource_cap';child.kill();break
  time.sleep(.25)
 actual=child.wait()
rec.update(actual_returncode=actual,guard_failure=guard_failure,elapsed_seconds=time.monotonic()-start,utc_end=datetime.datetime.now(datetime.timezone.utc).isoformat(),samples=samples,child_lifetime_peak_rss=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,source_after=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),status='RETURNED')
save('exit-witness.json',rec)
print(json.dumps({k:rec[k] for k in ['actual_returncode','guard_failure','elapsed_seconds','child_lifetime_peak_rss']}))
raise SystemExit(0 if actual==0 and guard_failure is None and rec['source_after']==EXPECTED and rec['elapsed_seconds']<SECONDS else 1)
