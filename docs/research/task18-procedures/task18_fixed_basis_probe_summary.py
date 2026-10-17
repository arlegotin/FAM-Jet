from pathlib import Path
import json,hashlib,shutil
from famjet.artifacts import atomic_json
from famjet.train import _source
root=Path('artifacts/task18');families={};mapping={}
def read(p):
 p=Path(p);mapping[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest();return json.loads(p.read_text())
for f in ('jet','bank','multiscale'):
 initial=[read(root/f'fixed-basis-initial/{f}-{i:02d}/summary.json') for i in range(12)]
 supplement=[read(root/f'fixed-basis-task-supplement/{f}-{i:02d}/summary.json') for i in range(1,12)]
 probe=read(root/f'fixed-basis-probe/{f}/summary.json');before=read(root/f'fixed-basis-probe/{f}/static-inventory.json');after=read(root/f'fixed-basis-probe/{f}/static-after.json')
 assert all(x['status']=='passed' for x in initial+supplement)
 families[f]={'memory_max_pointwise_ratio':max(m['max_pointwise_ratio'] for c in initial for m in c['metrics']),'fresh_task_max_pointwise_ratio':max(m.get('max_pointwise_ratio',0) for c in supplement for m in c['metrics']),'original_ordinal0_fresh_task_max':max(m.get('max_pointwise_ratio',0) for m in initial[0]['fresh_unfitted_reader_metrics']),'probe':probe,'static_before_bytes':before['owned_python_and_array_storage_bytes'],'static_after_bytes':after['owned_python_and_array_storage_bytes'],'inference_export_json_bytes':before['inference_export_json_bytes'],'external_config_json_bytes':before['external_config_json_bytes'],'retained_numpy_arrays':before['numpy_objects_retained'],'tensor_ledger':before['tensor_ledger'],'owned_object_paths':len(before['objects'])}
rawbytes=953874048;features=sum(f['probe']['projected6144_feature_data_bytes'] for f in families.values());manifest=4*6144*2048
profilemax=max(sum(x.stat().st_size for x in (root/f'calibration-{f}-width128').rglob('*') if x.is_file()) for f in ('jet','bank'))
casemax=max(sum(x.stat().st_size for x in p.rglob('*') if x.is_file()) for p in (root/'fixed-basis-task-supplement').glob('*-*') if p.is_dir())
oldraw=sum(x.stat().st_size for p in root.glob('cache*') if p.is_dir() for x in p.rglob('*') if x.is_file());oldfeatures=sum(x.stat().st_size for p in root.glob('features-finite6144-*') for x in p.rglob('*') if x.is_file())
proposal={'raw_payload_projection_bytes':rawbytes,'three_feature_payload_projection_bytes':features,'four_manifest_overhead_bytes':manifest,'three_profile_output_reserve_bytes':3*profilemax,'72_fitted_case_output_reserve_bytes':72*casemax,'current_free_bytes':shutil.disk_usage(root).free,'retained_raw_cache_bytes':oldraw,'retained_old_feature_cache_bytes':oldfeatures,'required_new_projection_bytes':rawbytes+features+manifest+3*profilemax+72*casemax,'reserve_derivation':'existing cache helpers2048B/entry manifest overhead; max actual width128 profile dir×3; max actual fresh-reader supplement case dir×72; all old copies retained; no new memory cap'}
rows=[json.loads(s) for s in (root/'fixed-basis-probe/multiscale/records.jsonl').read_text().splitlines()]
cost={k:sum(r['preparation'][k] for r in rows) for k in ('cpu_fp64_exponentials','matrix_cubic_work','encode_advances','query_advances')}
out={'source':_source(),'status':'bounded_numerics_and_cost_probes_complete; fullprep/coldprofiles/scientificlearning_unallocated','families':families,'artifact_sha256':mapping,'disk_projection':proposal,'multiscale_unique_forward_preparation_12':cost,'multiscale_projected6144_forward_preparation':{k:v*512 for k,v in cost.items()},'constructor_scope':'each model constructed once per probe; descriptor construction_exponentials1/eigendecompositions1 appears in each multiscale row but is NOT an execution count to sum; actual probe model constructor executed once; Jet sub-timer missing due preserved final reporting assertion, remains null','timing_scope':'warm OS disk reads after writes; generation projection sharedonce; current source numerical work/costs retained separately; no algorithm speed claim','next_requested':'source-frozen sharedraw6144 + three fitted featurecaches + sequential cold768/96/stop2 profiles and fitted0/2 checks; no scientific learning'}
atomic_json(root/'fixed-basis-probe-summary.json',out);print(json.dumps(proposal,indent=2))
