from pathlib import Path
import subprocess,time,json,hashlib,os,zipfile,email,sys
out=Path("artifacts/e2e-report-env-01");envdir=Path("/private/tmp/famjet-report-20261024-01");wheels=Path("/private/tmp/famjet-report-wheels-20261024-01")
if envdir.exists() or wheels.exists():raise FileExistsError("one-use env exists")
wheels.mkdir();records=[]
def run(name,args):
 start=time.monotonic()
 with (out/(name+".log")).open("wb") as f:r=subprocess.run(args,stdout=f,stderr=subprocess.STDOUT,timeout=600)
 log=out/(name+".log");records.append({"argv":args,"exit_code":r.returncode,"elapsed_seconds":time.monotonic()-start,"log_sha256":hashlib.sha256(log.read_bytes()).hexdigest(),"log_bytes":log.stat().st_size});(out/"invocations.json").write_text(json.dumps(records,indent=2)+"\n")
 if r.returncode:raise SystemExit(r.returncode)
run("venv",[".venv/bin/python","-m","venv",str(envdir)])
run("download",[str(envdir/"bin/python"),"-m","pip","download","--only-binary=:all:","--dest",str(wheels),"matplotlib"])
assets=[];lines=["# Separate optional report environment; main requirements.lock unchanged.","--only-binary :all:"]
for wheel in sorted(wheels.glob("*.whl")):
 with zipfile.ZipFile(wheel) as z:
  names=[n for n in z.namelist() if n.endswith(".dist-info/METADATA")];m=email.message_from_bytes(z.read(names[0]))
 name,version=m["Name"],m["Version"];digest=hashlib.sha256(wheel.read_bytes()).hexdigest();lines.append(name+"=="+version+" --hash=sha256:"+digest);assets.append({"name":name,"version":version,"file":wheel.name,"bytes":wheel.stat().st_size,"sha256":digest,"license_expression":m.get("License-Expression"),"license_classifiers":[x for x in m.get_all("Classifier",[]) if x.startswith("License")]})
lock=out/"requirements.lock";lock.write_text("\n".join(lines)+"\n");(out/"assets.json").write_text(json.dumps(assets,indent=2)+"\n")
run("install",[str(envdir/"bin/python"),"-m","pip","install","--no-index","--find-links",str(wheels),"--require-hashes","-r",str(lock)])
(out/"environment.json").write_text(json.dumps({"venv":str(envdir),"lock_sha256":hashlib.sha256(lock.read_bytes()).hexdigest(),"status":"report_dependencies_installed_plot_pending"},indent=2)+"\n")
print(json.dumps({"status":"report_dependencies_installed_plot_pending","packages":len(assets),"seconds":sum(x["elapsed_seconds"] for x in records)}))
