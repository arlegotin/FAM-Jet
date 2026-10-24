from pathlib import Path
import subprocess,time,json,hashlib,os,sys
out=Path("artifacts/e2e-clean-install-01")
envdir=Path("/private/tmp/famjet-clean-20261024-01")
if envdir.exists():raise FileExistsError(envdir)
records=[]
for name,args in [("venv",[".venv/bin/python","-m","venv",str(envdir)]),("install",[str(envdir/"bin/python"),"-m","pip","install","--require-hashes","-r","requirements.lock"])]:
 start=time.monotonic()
 with (out/(name+".log")).open("wb") as f:
  r=subprocess.run(args,stdout=f,stderr=subprocess.STDOUT,timeout=900,env=dict(os.environ,OMP_NUM_THREADS="1",MKL_NUM_THREADS="1",OPENBLAS_NUM_THREADS="1",VECLIB_MAXIMUM_THREADS="1"))
 log=out/(name+".log");records.append({"argv":args,"exit_code":r.returncode,"elapsed_seconds":time.monotonic()-start,"log_sha256":hashlib.sha256(log.read_bytes()).hexdigest(),"log_bytes":log.stat().st_size})
 (out/"invocations.json").write_text(json.dumps(records,indent=2)+"\n")
 if r.returncode:raise SystemExit(r.returncode)
(out/"environment.json").write_text(json.dumps({"venv":str(envdir),"lock_sha256":hashlib.sha256(Path("requirements.lock").read_bytes()).hexdigest(),"status":"dependencies_installed_cli_pending"},indent=2)+"\n")
print(json.dumps({"status":"dependencies_installed_cli_pending","seconds":sum(x["elapsed_seconds"] for x in records)}))
