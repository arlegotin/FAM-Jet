from pathlib import Path
from dataclasses import replace,asdict
from datetime import datetime,timezone
import json,hashlib,time,subprocess,yaml
from famjet.config import load_config
from famjet.train import _source
from famjet.artifacts import atomic_json
from famjet.eval.splits import _write_immutable
root=Path('artifacts/task18/width128-initial-gate');root.mkdir(exist_ok=True);start=time.perf_counter();utc=datetime.now(timezone.utc)
configs={}
for family in ('jet','bank'):
 c=load_config(Path(f'configs/development/{family}_learned_cpu64_raw_32768.yaml'));c=replace(c,model=replace(c.model,reader=replace(c.model.reader,width=128)));p=root/f'{family}-numeric.yaml';p.write_text(yaml.safe_dump(asdict(c),sort_keys=False));configs[family]=str(p)
procedure={'source':_source(),'helper_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'config_sha256':{f:hashlib.sha256(Path(p).read_bytes()).hexdigest() for f,p in configs.items()},'scope':'initial actual rates12 training cells per family; unchanged original1e-12; uniformly applied reviewedDecimal60/80 reference; small fresh-reader check separately firstordinal0 before rawprep','numeric_helper_sha256':hashlib.sha256(Path('/tmp/task18_learned_numeric64.py').read_bytes()).hexdigest(),'decimal_helper_sha256':hashlib.sha256(Path('/tmp/task18_decimal_checkpoint.py').read_bytes()).hexdigest(),'limits':'net201326592B per child; no full768fit before actualcoldprofile; no rawprep until accepted numerical+source gates','start_utc':utc.isoformat(),'power_override':False}
procedure['recovery']='progress list-to-object only; preserve completed Jet capture and original driver failure';_write_immutable(root/'recovery-procedure.json',procedure);records=[]
for f in ('jet','bank'):
 out=Path(f'artifacts/task18/width128-initial-{f}');log=Path(f'artifacts/task18-evidence/width128-initial-{f}.txt');tick=time.perf_counter()
 if (out/'summary.json').exists():
  prior=json.loads((out/'summary.json').read_text());assert prior['source']==_source() and prior['cases']==12;records.append({'stage':'retained_completed_capture','family':f,'original_seconds':prior['total_seconds']});continue
 with log.open('w') as target:r=subprocess.run(['.venv/bin/python','/tmp/task18_learned_numeric64.py',f,str(out),'--config',configs[f]],stdout=target,stderr=subprocess.STDOUT)
 records.append({'stage':'initial_binary64_reference','family':f,'returncode':r.returncode,'seconds':time.perf_counter()-tick});atomic_json(root/'progress.json',{'records':records})
 if r.returncode:raise SystemExit(r.returncode)
for f in ('jet','bank'):
 for i in range(12):
  tick=time.perf_counter();log=Path(f'artifacts/task18-evidence/width128-initial-decimal-{f}-{i:02d}.txt')
  with log.open('w') as target:r=subprocess.run(['.venv/bin/python','/tmp/task18_decimal_checkpoint.py',f,str(i),'--input-root',f'artifacts/task18/width128-initial-{f}','--output-root',str(root/'decimal')],stdout=target,stderr=subprocess.STDOUT)
  records.append({'stage':'decimal60_80','family':f,'ordinal':i,'returncode':r.returncode,'seconds':time.perf_counter()-tick});atomic_json(root/'progress.json',{'records':records})
  if r.returncode:raise SystemExit(r.returncode)
cases=[json.loads((root/'decimal'/f'{f}-{i:02d}'/'summary.json').read_text()) for f in ('jet','bank') for i in range(12)];end=datetime.now(timezone.utc)
summary={'status':'passed_uniform_corrected_memory_reference' if all(c['status']=='passed' for c in cases) else 'failed','source':_source(),'cases':24,'tolerances':{'rtol':1e-12,'atol':1e-12},'families':{f:{'max_pointwise_ratio':max(m['max_pointwise_ratio'] for c in cases if c['family']==f for m in c['metrics']),'binary64_record':json.loads(Path(f'artifacts/task18/width128-initial-{f}/summary.json').read_text())} for f in ('jet','bank')},'records':records,'perf_counter_seconds':time.perf_counter()-start,'start_utc':utc.isoformat(),'end_utc':end.isoformat(),'utc_interval_seconds':(end-utc).total_seconds(),'scope':'captured states/contractions/key/value/gate/logits; no separate rawdLdr/sharedqueryinputs certification; fresh-reader gate separate','max_case_rss_additional_bytes':max(c['rss_additional_bytes'] for c in cases)};atomic_json(root/'summary.json',summary);print(json.dumps(summary),flush=True)
