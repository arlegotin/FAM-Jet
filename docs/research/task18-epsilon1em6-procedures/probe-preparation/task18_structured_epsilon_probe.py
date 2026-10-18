"""Bounded12-record structured transport probe, no fit or scientific cache."""
from pathlib import Path
from dataclasses import asdict
from datetime import datetime,timezone
import argparse,hashlib,io,json,platform,resource,shutil,time,sys
import torch
from task18_structured_epsilon_numeric import config,static_inventory,EXPECTED,PACKAGE,sha
from task18_static_compare import compare_static
from task18_epsilon_probe_driver import preflight,verified,canonical
from famjet.train import make_model,_source,check_smoke_memory
from famjet.analysis.development import draw_config,parameter_accounting
from famjet.data.synthetic import generate_episode
from famjet.data.feature_cache import feature_record
from famjet.artifacts import atomic_json,append_jsonl
from famjet.eval.splits import _write_immutable
def assert_exact_transport(left,right):
 if isinstance(left,torch.Tensor):assert isinstance(right,torch.Tensor) and left.dtype==right.dtype and left.shape==right.shape and torch.equal(left,right)
 elif isinstance(left,dict):
  assert isinstance(right,dict) and left.keys()==right.keys()
  for key in left:assert_exact_transport(left[key],right[key])
 elif isinstance(left,(list,tuple)):
  assert type(left)==type(right) and len(left)==len(right)
  for x,y in zip(left,right):assert_exact_transport(x,y)
 else:assert type(left)==type(right) and left==right
p=argparse.ArgumentParser();p.add_argument('family',choices=['jet','bank']);p.add_argument('--seal',required=True);p.add_argument('--seal-sha',required=True);p.add_argument('--run-id',required=True);a=p.parse_args();assert sha(a.seal)==a.seal_sha;seal=json.loads(Path(a.seal).read_text());preflight(seal)
if a.family=='bank':verified(seal,a.seal_sha,'jet')
source=_source();assert source['commit']==EXPECTED and source['package_hash']==PACKAGE and not source['diff'] and not source['untracked_package_files']
gate=Path('artifacts/task18/epsilon1em6-initial-9aca1b');rootgate=gate/'root-verified-aggregate.json';assert sha(rootgate)==seal['root_gate_sha256']
audit=Path('artifacts/task18/fixed-basis-feature-size-audit');oldrows=json.loads((audit/'sizes.json').read_text())['rows'];assert len(oldrows)==6144;oldmax=max(r['bytes'] for r in oldrows);assert oldmax==24700
width=105 if a.family=='jet' else 113;new_payload=8*width*8;conservative_per_record=oldmax+new_payload
c=config(a.family);assert canonical(asdict(c))==seal['configs'][a.family]['config_hash'];torch.set_num_threads(4);out=Path(seal['output_root'])/a.family;out.mkdir(parents=True,exist_ok=False);start=time.perf_counter();utc=datetime.now(timezone.utc);factor=1 if platform.system()=='Darwin' else 1024;base=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*factor
free=shutil.disk_usage(out).free;assert free>=4*1024**3
procedure={'source':source,'helper_sha256':sha(__file__),'numeric_helper_sha256':sha(Path(__file__).with_name('task18_structured_epsilon_numeric.py')),'static_helper_sha256':sha(Path(__file__).with_name('task18_fixed_basis_numeric.py')),'static_comparison_helper_sha256':sha(Path(__file__).with_name('task18_static_compare.py')),'config':asdict(c),'scope':'12unique shared training histories one/cell; UNFITTED full structured FeatureBatch transport cost only; no768fit/corpus preparation/scientifictraining','numeric_gate_sha256':sha(rootgate),'seal_sha256':a.seal_sha,'run_id':a.run_id,'config_hash':canonical(asdict(c)),'fitted_cache_identity':None,'feature_identity_v2_scope':'UNFITTED transport only; function/source/read-policy bound, no fake fit or manifest','schema_component_proof':seal['transport_schema_proof'],'prior_all6144_size_audit':{'summary_sha256':sha(audit/'summary.json'),'sizes_sha256':sha(audit/'sizes.json'),'max_record_bytes':oldmax,'total_bytes':sum(r['bytes'] for r in oldrows),'new_whole_numeric_feature_payload_bytes':new_payload,'conservative_per_record_bound':conservative_per_record,'conservative6144_bound':conservative_per_record*6144,'rationale':'prior exact ALL6144 metadata variation + entire new numeric feature payload; deliberately retains/doublecounts old numeric payload, not12record average; old audit is historical size evidence only, not current package cache authorization'},'net_limit':201326592,'disk_free_before_bytes':free,'power_override':False,'utc_start':utc.isoformat()};_write_immutable(out/'procedure.json',procedure)
rows=[]
try:
 tick=time.perf_counter();torch.manual_seed(c.seed);model=make_model(c).eval();construction=time.perf_counter()-tick;assert model.kernel.eps==c.model.epsilon==1e-6 and model.kernel.support_floor==c.model.numerical_support_floor==1e-8 and model.fit_provenance is None;read_policy={'epsilon':model.kernel.eps,'numerical_support_floor':model.kernel.support_floor};assert model._parameter_hash()==seal['cases'][a.family+'-00']['fixed_kernel_hash'];before=static_inventory(model,c);atomic_json(out/'static-inventory.json',before)
 for ordinal in range(12):
  tick=time.perf_counter();dc,hid=draw_config(c,ordinal);ep=generate_episode(dc,c.development.data_seed,hid);generation=time.perf_counter()-tick
  original=json.loads((gate/f'{a.family}-{ordinal:02d}/summary.json').read_text());assert ep.metadata['hashes']==original['raw_hashes'] and hid==original['history_id']
  tick=time.perf_counter();wire=feature_record(model,ep,'terminal');encoding=time.perf_counter()-tick;assert wire['values'].shape==(1,8,width) and wire['values'].dtype==torch.float64
  tick=time.perf_counter();buf=io.BytesIO();torch.save(wire,buf);payload=buf.getvalue();file=out/f'{ordinal:02d}.pt';file.write_bytes(payload);serialization=time.perf_counter()-tick
  tick=time.perf_counter();loaded=file.read_bytes();digest=hashlib.sha256(loaded).hexdigest();read_hash=time.perf_counter()-tick;assert digest==hashlib.sha256(payload).hexdigest()
  tick=time.perf_counter();restored=torch.load(io.BytesIO(loaded),weights_only=True);decode=time.perf_counter()-tick
  assert torch.equal(restored['values'],wire['values']) and restored['values'].dtype==torch.float64
  assert_exact_transport(restored,wire)
  assert restored['queries']['history_ids']==wire['queries']['history_ids'] and torch.equal(restored['queries']['query_ids'],ep.queries.query_ids) and torch.equal(restored['labels'],ep.labels)
  assert len(payload)<=oldrows[ordinal]['bytes']+new_payload and len(payload)<=conservative_per_record
  row={'values_shape':list(wire['values'].shape),'values_dtype':str(wire['values'].dtype),'ordinal':ordinal,'history_id':hid,'length':int(ep.events.lengths[0]),'regime':ep.metadata['regime'],'raw_hashes':ep.metadata['hashes'],'bytes':len(payload),'old_same_record_bytes':oldrows[ordinal]['bytes'],'delta_vs_old_raw_reader_bytes':len(payload)-oldrows[ordinal]['bytes'],'sha256':digest,'generation_seconds':generation,'encode_query_seconds':encoding,'serialize_write_seconds':serialization,'disk_read_sha_seconds':read_hash,'decode_seconds':decode,'actual_host_matrix_exponential_calls':0,'net_peak_bytes':max(0,resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*factor-base)};rows.append(row);append_jsonl(out/'records.jsonl',row);check_smoke_memory(c,row['net_peak_bytes']);del ep,wire,buf,payload,loaded,restored
 after=static_inventory(model,c);atomic_json(out/'static-after.json',after);comparison=compare_static(before,after);atomic_json(out/'static-comparison.json',comparison)
 fields=('generation_seconds','encode_query_seconds','serialize_write_seconds','disk_read_sha_seconds','decode_seconds');totals={k:sum(r[k] for r in rows) for k in fields};deltas=sorted(set(r['delta_vs_old_raw_reader_bytes'] for r in rows));assert 'famjet.analysis.statistics' not in sys.modules
 retained=sum(p.stat().st_size for root in Path('artifacts/task18').iterdir() if root.is_dir() and (root.name.startswith('cache') or root.name.startswith('features-')) for p in root.rglob('*') if p.is_file());free_after=shutil.disk_usage(out).free;peak=max(0,resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*factor-base);check_smoke_memory(c,peak);end=datetime.now(timezone.utc);elapsed=time.perf_counter()-start
 record={'status':'completed_bounded_structured_cost_probe_only','source':source,'family':a.family,'records':12,'seal_sha256':a.seal_sha,'run_id':a.run_id,'config_hash':canonical(asdict(c)),'epsilon':c.model.epsilon,'input_width':width,'transport_read_policy':read_policy,'fitted_cache_identity':None,'statistics_module_absent':True,'records_sha256':sha(out/'records.jsonl'),'artifact_hashes':{name:sha(out/(name+'.json')) for name in ('static-inventory','static-after','static-comparison')},'construction_seconds':construction,'actual_constructor_executions':1,'actual_probe_bytes':sum(r['bytes'] for r in rows),'observed_delta_vs_old_record_bytes':deltas,'conservative6144_feature_data_bytes':conservative_per_record*6144,'estimated6144_feature_data_bytes_if_observed_constant_delta_holds':sum(r['bytes'] for r in oldrows)+deltas[0]*6144 if len(deltas)==1 else None,'totals':totals,'projected6144_stage_seconds':{k:v*512 for k,v in totals.items()},'projection_scope':'timing linear12 balanced cells only; disk bound uses ALL6144 prior metadata maximum plus entire new feature payload; fullfit/manifest/hashscan/coldprofile/quality excluded','disk_read_scope':'actual file read+SHA immediately after write, warm OS cache, not cold-storage throughput','disk_free_after_bytes':free_after,'retained_task18_raw_and_feature_bytes':retained,'static_comparison':comparison,'static_inventory_sha256':sha(out/'static-inventory.json'),'parameter_accounting':parameter_accounting(model),'net_peak_bytes':peak,'perf_seconds':elapsed,'utc_start':utc.isoformat(),'utc_end':end.isoformat(),'utc_seconds':(end-utc).total_seconds(),'procedure_sha256':sha(out/'procedure.json'),'next':'fullprep/cold/science HELD pending root measured allocation'};atomic_json(out/'summary.json',record);print(json.dumps(record),flush=True)
except BaseException as exc:
 atomic_json(out/'failure.json',{'source':source,'status':'interrupted' if isinstance(exc,KeyboardInterrupt) else 'failed','seal_sha256':a.seal_sha,'run_id':a.run_id,'type':type(exc).__name__,'error':str(exc),'completed_records':len(rows),'perf_seconds':time.perf_counter()-start,'utc_end':datetime.now(timezone.utc).isoformat()});raise
