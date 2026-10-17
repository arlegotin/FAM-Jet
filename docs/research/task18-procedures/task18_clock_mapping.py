from pathlib import Path
from datetime import datetime
import json,hashlib
from famjet.artifacts import atomic_json
from famjet.train import _source
r={'source':_source(),'scope':'separate accounting notice; original timing/run records unchanged','meaning':'perf_counter intervals are neither CPU time nor guaranteed civil wall when this host sleeps','records':{},'power_evidence':{'path':'artifacts/task18-evidence/learned-cpu64-8192-sleep-wake.txt','sha256':hashlib.sha256(Path('artifacts/task18-evidence/learned-cpu64-8192-sleep-wake.txt').read_bytes()).hexdigest(),'timezone':'literal log +0200; training timestamps UTC','finding':'Repeated maintenance sleeps and dark wakes overlap Jet training, including literal Dark Wake Thermal Emergency entries. This supports substantial sleep contribution but does not attribute every missing second or establish that training caused thermal events.','power_override_applied':False}}
for family in ('jet','bank'):
 p=Path(f'artifacts/task18/learning-{family}-cpu64-8192/training/run.json');x=json.loads(p.read_text());utc=(datetime.fromisoformat(x['end_utc'])-datetime.fromisoformat(x['start_utc'])).total_seconds();r['records'][family]={'run_path':str(p),'run_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'start_utc':x['start_utc'],'end_utc':x['end_utc'],'utc_interval_seconds':utc,'original_total_seconds_perf_counter':x['total_seconds'],'utc_minus_perf_seconds':utc-x['total_seconds'],'boundary':'training run; development wrapper has a wider boundary, not substituted here'}
atomic_json(Path('artifacts/task18/learned-cpu64-8192-clock-accounting.json'),r)
