from pathlib import Path
import datetime,hashlib,json,shutil,runpy
from famjet_poc.execution_policy import execution_source_sha256
from famjet_poc.study import load_score_rows
w=Path('.superpowers/sdd/2026-10-16-famjet');out=Path('artifacts/e2e-guard-cadence-public-02');prep=Path('artifacts/e2e-guard-cadence-public-02-prep');d=Path('docs/research/e2e-guard-public-02-evidence');d.mkdir(exist_ok=False)
def rec(p):
 b=p.read_bytes();return {'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}
v=json.loads((out/'qualification.json').read_bytes());x=json.loads((prep/'exit-witness.json').read_bytes());driver=runpy.run_path('docs/research/e2e-guard-cadence-public-check.py')
assert v['status']=='matched' and not v['failing_inputs'] and v['boundary']=='public_development_only_no_protected_access'
assert v['execution_source_sha256']==execution_source_sha256()
assert v['source_sha256']==rec(Path('docs/research/e2e-guard-cadence-public-check.py'))['sha256']
assert v['history_count']==16 and len(set(v['history_ids']))==16 and v['event_count_per_history']==2048
for regime in driver['REGIMES']:assert sum('-'+regime+'-' in s for s in v['history_ids'])==4
assert set(v['methods'])==set(driver['METHODS'])
journal=json.loads(Path(v['old_public_journal_ref']['path']).read_bytes());verified=[]
for name,m in v['methods'].items():
 assert m['history_count']==16 and m['row_count']==128 and m['method']==name
 for field in ['rows_ref','old_public_rows_ref']:
  r=m[field];p=Path(r['path']);allowed=out if field=='rows_ref' else Path('artifacts/e2e-core-run-04/development_k16/study')
  assert p.resolve().is_relative_to(allowed.resolve());assert rec(p)=={k:r[k] for k in ['bytes','sha256']};verified.append(r)
 source=journal['selected'][name]['config_hash'] if name in ('jet','bank') else name
 match=driver['compare_scientific_rows'](load_score_rows(m['old_public_rows_ref']),load_score_rows(m['rows_ref']),v['history_ids'],name,source_method=source)
 assert match['projection_sha256']==m['projection_sha256']
 assert m['maximum_state_bytes']<=9345 or name=='exact'
roots={'outer':out,'inner':out/'runs','fullscale':Path('artifacts/e2e-core-run-04/development_k16')}
for name,root in roots.items():
 assert Path(v['guard_roots'][name])==root.resolve()
 r=v['guard_refs'][name];p=Path(r['path']);assert p.resolve().is_relative_to(out.resolve());assert rec(p)=={k:r[k] for k in ['bytes','sha256']};g=json.loads(p.read_bytes())
 assert g['status']=='completed' and g['violation'] is None and g['forced_count']==2 and g['background_count']>0
 assert g['maximum_reused_sample_age_seconds']<=.25 and g['maximum_observer_operation_seconds']<5 and g['observer_timeout_seconds']==5
 assert all(s.get('tree_rss_bytes',0)<=1610612736 for s in g['samples'])
 assert g['allocation']['max_disk_bytes']==(512 if name=='fullscale' else 128)*2**20
assert v['guard_cadence']['inner']['reuse_count']>0
scale=driver['verified_public_scale_tree'](Path('artifacts/e2e-core-run-04'))
assert scale==v['old_public_fullscale_tree'] and scale['file_count']>=1000 and scale['file_bytes']>=350000000
c=v['methods']['laguerre']['coordinate_diagnostic_summary'];assert c['state_checks']==c['mask_checks']=='PASSED' and c['strict_prediction_status']=='FAILED' and c['strict_prediction_failed_histories']==2 and c['strict_prediction_failed_scalars']==4
assert x['actual_returncode']==0 and x['guard_failure'] is None and x['source_after_clean'] and x['source_head']==x['source_after']=='b4fff2dace4866e41ffc4f07340eb2729de1bf50'
assert x['maximum_sampled_rss_sum_bytes']<1610612736 and x['elapsed_seconds']<180
shutil.copytree(out,d/'public-run');shutil.copytree(prep,d/'owner-witness');shutil.copyfile(w/'e2e-guard-public-02-allocation.json',d/'allocation.json');shutil.copyfile(w/'e2e-guard-public-02-root-verify.py',d/'root-verify.py')
files={}
for original,archived in [(out,d/'public-run'),(prep,d/'owner-witness')]:
 for p in original.rglob('*'):
  if p.is_file():
   q=archived/p.relative_to(original);assert p.read_bytes()==q.read_bytes();files[str(q.relative_to(d))]={'original':str(p),**rec(q)}
r={'schema_version':1,'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'status':'PASSED_public_native_exact_parity_and_three_guards','source_revision':x['source_head'],'execution_source_sha256':v['execution_source_sha256'],'history_count':16,'events_per_history':2048,'methods':8,'row_count_per_method':128,'total_rows':1024,'matched_old_and_new_row_refs':len(verified),'guard_roots':v['guard_roots'],'guard_cadence':v['guard_cadence'],'fullscale_public_input':scale,'elapsed_owner_seconds':x['elapsed_seconds'],'peak_owner_current_rss_sum_bytes':x['maximum_sampled_rss_sum_bytes'],'peak_inner_tree_rss_bytes':v['peak_sampled_tree_rss_bytes'],'guard_failure':None,'coordinate_strict_prediction_status':'FAILED_preserved_2_histories_4_scalars','files':files,'archive_file_count':len(files),'archive_bytes':sum(i['bytes'] for i in files.values()),'fresh_scientific_run':'NOT_RUN_NEXT_GATE','not_a_primary_accuracy_result':True}
(d/'index.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps({k:r[k] for k in r if k not in ['files','guard_cadence','guard_roots']},indent=2))
