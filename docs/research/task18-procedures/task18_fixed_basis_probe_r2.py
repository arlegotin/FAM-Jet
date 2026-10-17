"""Twelve fresh records/family only; not a scientific feature cache or calibration."""
from pathlib import Path
from dataclasses import asdict
from datetime import datetime,timezone
import argparse,hashlib,io,json,platform,resource,shutil,time
import torch
from task18_fixed_basis_numeric import config,static_inventory,EXPECTED,PACKAGE
from famjet.train import make_model,_source,check_smoke_memory
from famjet.analysis.development import draw_config
from famjet.data.synthetic import generate_episode
from famjet.data.feature_cache import feature_record
from famjet.artifacts import atomic_json,append_jsonl
from famjet.eval.splits import _write_immutable

p=argparse.ArgumentParser();p.add_argument('family',choices=['jet','bank','multiscale']);p.add_argument('out');p.add_argument('--gate-root',required=True);args=p.parse_args()
source=_source();assert source['commit']==EXPECTED and source['package_hash']==PACKAGE and not source['diff'] and not source['untracked_package_files']
gate=Path(args.gate_root)
for family in ('jet','bank','multiscale'):
 for ordinal in range(12):
  record=json.loads((gate/f'{family}-{ordinal:02d}'/'summary.json').read_text());assert record['status']=='passed' and record['source']==source
supp=Path('artifacts/task18/fixed-basis-task-supplement')
for family in ('jet','bank','multiscale'):
 for ordinal in range(1,12):
  record=json.loads((supp/f'{family}-{ordinal:02d}'/'summary.json').read_text());assert record['status']=='passed' and record['source']==source
c=config(args.family);torch.set_num_threads(4);out=Path(args.out);out.mkdir(parents=True,exist_ok=False);start=time.perf_counter();utc=datetime.now(timezone.utc);factor=1 if platform.system()=='Darwin' else 1024;base=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*factor
procedure={'source':source,'helper_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'common_helper_sha256':hashlib.sha256(Path('/tmp/task18_fixed_basis_numeric.py').read_bytes()).hexdigest(),'config':asdict(c),'scope':'12 unique training records (one per length/regime), fresh raw generation then production feature_record; UNFITTED raw features for cost only, no declared scientific cache/fit/training/quality','gate_root':str(gate),'supplement_summary_sha256':hashlib.sha256((supp/'summary.json').read_bytes()).hexdigest(),'numeric_summary_hashes':{f'{family}-{i:02d}':hashlib.sha256((gate/f'{family}-{i:02d}'/'summary.json').read_bytes()).hexdigest() for family in ('jet','bank','multiscale') for i in range(12)},'net_limit':201326592,'power_override':False,'utc_start':utc.isoformat()};_write_immutable(out/'procedure.json',procedure)
rows=[];construction_start=time.perf_counter();torch.manual_seed(c.seed);model=make_model(c).eval();construction_seconds=time.perf_counter()-construction_start;before=static_inventory(model,c);atomic_json(out/'static-inventory.json',before)
try:
 for ordinal in range(12):
  tick=time.perf_counter();dc,hid=draw_config(c,ordinal);ep=generate_episode(dc,c.development.data_seed,hid);generation=time.perf_counter()-tick
  preparation=model.kernel.call_preparation_cost(ep.events,ep.queries,mode='terminal',reader_kind='generic_contracted') if args.family=='multiscale' else {'scope':'no host matrix exponentials'}
  tick=time.perf_counter();wire=feature_record(model,ep,'terminal');encoding=time.perf_counter()-tick
  tick=time.perf_counter();buf=io.BytesIO();torch.save(wire,buf);payload=buf.getvalue();file=out/f'{ordinal:02d}.pt';file.write_bytes(payload);serialization_write=time.perf_counter()-tick
  tick=time.perf_counter();loaded=file.read_bytes();sha=hashlib.sha256(loaded).hexdigest();read_hash=time.perf_counter()-tick;assert sha==hashlib.sha256(payload).hexdigest()
  tick=time.perf_counter();restored=torch.load(io.BytesIO(loaded),weights_only=True);decode=time.perf_counter()-tick
  assert torch.equal(restored['values'],wire['values']) and restored['values'].dtype==torch.float64
  assert restored['queries']['history_ids']==wire['queries']['history_ids'] and torch.equal(restored['queries']['query_ids'],ep.queries.query_ids) and torch.equal(restored['labels'],ep.labels)
  row={'ordinal':ordinal,'history_id':hid,'length':int(ep.events.lengths[0]),'regime':ep.metadata['regime'],'raw_hashes':ep.metadata['hashes'],'bytes':len(payload),'sha256':sha,'generation_seconds':generation,'encode_query_seconds':encoding,'serialize_write_seconds':serialization_write,'disk_read_sha_seconds':read_hash,'decode_seconds':decode,'preparation':preparation,'net_peak_bytes':max(0,resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*factor-base)};rows.append(row);append_jsonl(out/'records.jsonl',row);check_smoke_memory(c,row['net_peak_bytes']);del ep,wire,buf,payload,loaded,restored
 after=static_inventory(model,c);atomic_json(out/'static-after.json',after);assert before==after,'unexpected persistent object/cache growth'
 end=datetime.now(timezone.utc);fields=('generation_seconds','encode_query_seconds','serialize_write_seconds','disk_read_sha_seconds','decode_seconds');totals={k:sum(r[k] for r in rows) for k in fields};nbytes=sum(r['bytes'] for r in rows)
 summary={'status':'completed_cost_probe_only','source':source,'family':args.family,'records':12,'construction_seconds':construction_seconds,'actual_probe_bytes':nbytes,'static_before_after_exact':True,'disk_read_scope':'actual file read+SHA immediately after write; warm OS cache, not cold storage throughput','totals':totals,'projected6144_feature_data_bytes':nbytes*512,'projected6144_stage_seconds':{k:v*512 for k,v in totals.items()},'projection_scope':'balanced one-per-cell linear projection only,12 measured records; no cache fit, full scan/manifest, cold768fit/96dev or scientific learning included','disk_free_after_bytes':shutil.disk_usage(out).free,'retained_task18_cache_bytes':sum(p.stat().st_size for root in Path('artifacts/task18').glob('cache*') if root.is_dir() for p in root.rglob('*') if p.is_file()),'net_peak_bytes':max(r['net_peak_bytes'] for r in rows),'perf_seconds':time.perf_counter()-start,'utc_start':utc.isoformat(),'utc_end':end.isoformat(),'utc_seconds':(end-utc).total_seconds(),'static_inventory_sha256':hashlib.sha256((out/'static-inventory.json').read_bytes()).hexdigest(),'next':'report measured projection before full6144/new coldcal allocation'};atomic_json(out/'summary.json',summary);print(json.dumps(summary),flush=True)
except BaseException as exc:
 atomic_json(out/'failure.json',{'source':source,'type':type(exc).__name__,'error':str(exc),'completed_records':len(rows),'perf_seconds':time.perf_counter()-start});raise
