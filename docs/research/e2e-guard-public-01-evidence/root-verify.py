from pathlib import Path
import datetime,hashlib,json,shutil
w=Path('.superpowers/sdd/2026-10-16-famjet');out=Path('artifacts/e2e-guard-cadence-public-01');prep=Path('artifacts/e2e-guard-cadence-public-01-prep');d=Path('docs/research/e2e-guard-public-01-evidence');d.mkdir(exist_ok=False)
def rec(p):
 b=p.read_bytes();return {'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}
v=json.loads((out/'qualification.json').read_bytes());x=json.loads((prep/'exit-witness.json').read_bytes())
assert v['status']=='matched' and not v['failing_inputs'] and v['boundary']=='public_development_only_no_protected_access'
assert v['history_count']==16 and len(set(v['history_ids']))==16 and v['event_count_per_history']==2048
for regime in ['piecewise_stationary','trend_reset','periodic_impulses','irregular_revisions']:assert sum('-'+regime+'-' in s for s in v['history_ids'])==4
assert set(v['methods'])=={'jet','bank','laguerre','exact','recent','latest_lru','reservoir','buckets'}
verified=[]
for name,m in v['methods'].items():
 assert m['history_count']==16 and m['row_count']==128 and m['method']==name
 for field in ['rows_ref','old_public_rows_ref']:
  r=m[field];p=Path(r['path']);allowed=out if field=='rows_ref' else Path('artifacts/e2e-core-run-04/development_k16/study')
  assert p.resolve().is_relative_to(allowed.resolve());assert rec(p)=={k:r[k] for k in ['bytes','sha256']};verified.append(r)
 assert m['maximum_state_bytes']<=9345 or name=='exact'
for field in ['inner_guard_ref','outer_guard_ref']:
 r=v[field];p=Path(r['path']);assert p.resolve().is_relative_to(out.resolve());assert rec(p)=={k:r[k] for k in ['bytes','sha256']};g=json.loads(p.read_bytes());assert g['status']=='completed' and g['violation'] is None and g['forced_count']==2 and g['background_count']>0;assert g['maximum_sample_age_seconds']<=.25
assert v['guard_cadence']['inner']['reuse_count']>0
c=v['methods']['laguerre']['coordinate_diagnostic_summary'];assert c['state_checks']==c['mask_checks']=='PASSED' and c['strict_prediction_status']=='FAILED' and c['strict_prediction_failed_histories']==2
assert x['actual_returncode']==0 and x['guard_failure'] is None and x['source_after_clean'] and x['source_head']==x['source_after']=='da67fbef216ee61287a61541e2b6473731f65a10'
assert x['maximum_sampled_rss_sum_bytes']<1610612736 and x['elapsed_seconds']<180
shutil.copytree(out,d/'public-run');shutil.copytree(prep,d/'owner-witness');shutil.copyfile(w/'e2e-guard-public-01-allocation.json',d/'allocation.json');shutil.copyfile(w/'e2e-guard-public-root-verify.py',d/'root-verify.py')
files={}
for original,archived in [(out,d/'public-run'),(prep,d/'owner-witness')]:
 for p in original.rglob('*'):
  if p.is_file():
   q=archived/p.relative_to(original);assert p.read_bytes()==q.read_bytes();files[str(q.relative_to(d))]={'original':str(p),**rec(q)}
r={'schema_version':1,'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'status':'PASSED_public_native_parity_and_guard_only','source_revision':x['source_head'],'history_count':16,'events_per_history':2048,'methods':8,'row_count_per_method':128,'total_rows':1024,'matched_old_and_new_row_refs':len(verified),'guard_cadence':v['guard_cadence'],'elapsed_owner_seconds':x['elapsed_seconds'],'peak_owner_current_rss_sum_bytes':x['maximum_sampled_rss_sum_bytes'],'peak_inner_tree_rss_bytes':v['peak_sampled_tree_rss_bytes'],'guard_failure':None,'coordinate_strict_prediction_status':'FAILED_preserved_2_histories_4_scalars','files':files,'archive_file_count':len(files),'archive_bytes':sum(i['bytes'] for i in files.values()),'fresh_scientific_run':'NOT_RUN_NEXT_GATE','not_a_primary_accuracy_result':True}
(d/'index.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps({k:r[k] for k in r if k not in ['files','guard_cadence']},indent=2))
