from pathlib import Path
from types import SimpleNamespace
import sys,json,subprocess
import famjet.analysis.development as dev
import famjet.artifacts as art
import famjet.eval.splits as splits
import famjet.train as train
source=train._source();clocks=[];allocations=[];called=[]
class ExpectedFailure(RuntimeError):pass
def fail(*a,**kw):called.append(kw);raise ExpectedFailure('isolated_no_model_failure')
dev.run_development=fail;art.atomic_json=lambda p,v:clocks.append(v);splits._write_immutable=lambda p,v:allocations.append(v);train._source=lambda:source;subprocess.run=lambda *a,**kw:SimpleNamespace(stdout='isolated stub; no host call')
sys.argv=['task18_fixed_basis_learn8192.py','jet'];p=Path('/tmp/task18_fixed_basis_learn8192.py')
try:exec(compile(p.read_text(),str(p),'exec'),{'__file__':str(p),'__name__':'isolated_launcher_test'})
except ExpectedFailure:pass
else:raise AssertionError('failure was swallowed')
assert len(called)==len(clocks)==len(allocations)==1
assert clocks[0]['status']=='failed',clocks[0]
assert clocks[0]['exception_type']=='ExpectedFailure'
assert called[0]['stop_at']==8192
print(json.dumps({'status':'passed_isolated_failure_clock','models_fits_updates':0,'clock':clocks[0]}))
