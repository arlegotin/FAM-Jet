import subprocess,time,json,hashlib,sys
from pathlib import Path
name=sys.argv[1];argv=sys.argv[2:];started=time.monotonic()
r=subprocess.run(argv,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
p=Path('docs/research/e2e-report-timing-fix-evidence')/(name+'.log');p.write_bytes(r.stdout)
receipt={'argv':argv,'exit_code':r.returncode,'elapsed_seconds':time.monotonic()-started,'log':str(p),'bytes':len(r.stdout),'sha256':hashlib.sha256(r.stdout).hexdigest()}
p.with_suffix('.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps(receipt));print(r.stdout.decode())
