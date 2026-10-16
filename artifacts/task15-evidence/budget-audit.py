import json,time
from pathlib import Path
import torch
from famjet.config import load_config
from famjet.checkpoint import load_checkpoint
from famjet.eval.isolation import _reconstruct
from famjet.data.synthetic import generate_episode
from famjet.train import move_episode
from famjet.eval.budgets import budget_report

torch.set_num_threads(4)
c=load_config(Path('configs/delta-smoke.yaml'))
ctx=load_checkpoint(Path('artifacts/task15-evidence/cpu-smoke/checkpoint.pt'),{})
m=_reconstruct(ctx['model']); ep=move_episode(generate_episode(c,c.seed,'train-000000000000'),'cpu')
with torch.inference_mode():
    start=time.perf_counter(); s=m.encode(ep.events); encode=time.perf_counter()-start
    start=time.perf_counter(); m.read(s,ep.queries); read=time.perf_counter()-start
report=budget_report(m,s,limit_bytes=1<<20)
report.update(reader=m.reader.cost(),kernel_parameter_bytes=m.kernel.parameter_nbytes(),
    measured_cpu_seconds={'encode':encode,'read_all_8_queries':read,
    'scope':'one warm-process call including validation/hash/clones/host times/native operations; no throughput claim'},
    smoke_resources=json.loads(Path('artifacts/task15-evidence/cpu-smoke/run.json').read_text())['actual_budgets'])
Path('artifacts/task15-evidence/budget.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({k:report[k] for k in ('reader','kernel_parameter_bytes','measured_cpu_seconds','smoke_resources','end_to_end_logical_bytes','eligible')},indent=2))
print(json.dumps({'state_bytes':report['state']['logical_bytes'],'numeric_payload_bytes':report['state']['payload_bytes'],
                  'metadata_bytes':report['state']['metadata_bytes'],'static_parameter_bytes':report['static']['parameter_bytes'],
                  'static_buffer_bytes':report['static']['buffer_bytes']},indent=2))
