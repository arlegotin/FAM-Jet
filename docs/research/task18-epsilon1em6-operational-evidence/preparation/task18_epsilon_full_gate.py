"""External fixed stage provenance checks; no model construction or compatibility rule."""
from pathlib import Path
import hashlib,json,os,subprocess,sys
EXPECTED='c71547932e2875468752db09e6f0a1e02c3e5650'
PACKAGE='57c0920f360e47f2c3978f056437143c4262b8ab9653b753df1321402ade9717'
ROOT=Path('artifacts/task18/epsilon1em6-operational-c715479')
TARGET='0cebf5f59f3b44f44875b73d582e6cb3c21a0ade54867edfabaebcab220dad21'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def canonical(x):return hashlib.sha256(json.dumps(x,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def preflight():
 path=os.environ['TASK18_FULL_SEAL'];digest=os.environ['TASK18_FULL_SEAL_SHA'];assert sha(path)==digest;s=read(path)
 assert s['source_commit']==EXPECTED and s['package_hash']==PACKAGE
 assert subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()==EXPECTED and not subprocess.check_output(['git','status','--porcelain'],text=True)
 files={str(p):sha(p) for p in sorted(Path('famjet').rglob('*.py'))};assert files==s['package_files'] and canonical(files)==PACKAGE
 for n,r in s['helpers'].items():assert sha(Path(__file__).with_name(n))==r['sha256']
 for p,r in s['dependencies'].items():assert sha(p)==r['sha256']
 for f,c in s['configs'].items():assert sha(c['path'])==c['sha256'] and canonical(c['config'])==c['config_hash']
 assert 'famjet.analysis.statistics' not in sys.modules
 return s

def source_ok(value):assert value=={'commit':EXPECTED,'diff':'','package_hash':PACKAGE,'untracked_package_files':{}}
def raw_ok():
 r=read(ROOT/'raw-preparation/summary.json');source_ok(r['source']);assert r['status']=='complete_shared_strict_raw' and r['all_prior_comparisons']
 p=ROOT/'raw-cache/manifest.json';m=read(p);assert r['cache_manifest']==str(p) and r['cache_manifest_hash']==canonical(m)
 assert m['status']=='complete' and len(m['entries'])==6144 and m['identity']['source_hash']==PACKAGE and m['total_bytes']==953874048
 assert r['preparation']['rss_highwater_additional_bytes']<=201326592
 return r,m

def prepared_ok(family):
 raw,m=raw_ok();r=read(ROOT/f'prepare-{family}/summary.json');source_ok(r['source']);assert r['family']==family and r['status']=='prepared_fit_and_features_only' and r['net_peak_bytes']<=201326592
 p=ROOT/f'prepare-{family}/calibration.yaml';assert r['config_path']==str(p) and r['config_sha256']==sha(p)
 import yaml
 c=yaml.safe_load(p.read_text());s=read(os.environ['TASK18_FULL_SEAL']);expected=json.loads(json.dumps(s['configs'][family]['config']))
 fp=ROOT/f'features-{family}/manifest.json';fm=read(fp);assert fm['status']=='complete' and len(fm['entries'])==6144 and r['feature_manifest']==str(fp) and r['feature_manifest_hash']==canonical(fm)
 expected['development'].update(cache_manifest_path=str(ROOT/'raw-cache/manifest.json'),cache_manifest_hash=canonical(m),feature_cache_manifest_path=str(fp),feature_cache_manifest_hash=canonical(fm));assert c==expected
 identity=fm['identity'];assert identity['version']==2 and identity['source_hash']==PACKAGE and identity['read_policy']=={'epsilon':1e-6,'numerical_support_floor':1e-8}
 assert identity['raw_manifest_hash']==canonical(m) and identity['target_statistics_hash']==TARGET and identity['fit_provenance']['history_count']==768 and identity['t_ref']==1. and identity['precision']=='float64' and identity['device']=='cpu'
 assert identity['input_dim']==(105 if family=='jet' else 113) and identity['corpus_histories']==6144
 assert fm['total_bytes']<=s['feature_caps'][family] and r['raw_manifest_hash']==canonical(m)
 fit=read(ROOT/f'prepare-{family}/fit.json');assert fit['fit_provenance']['history_count']==768 and fit['target_statistics_hash']==TARGET and fit['net_peak_bytes']<=201326592
 return r,c,fm

def cold_ok(family):
 prep,c,fm=prepared_ok(family);r=read(ROOT/f'cold-{family}/development.json');source_ok(r['source']);assert r['status']=='completed' and r['source_hash']==PACKAGE and r['config']==c
 assert r['training_run']['completed_step']==2 and r['configured_training_horizon']==32768 and r['execution_stop_at']==2 and r['rss_highwater_additional_bytes']<=201326592
 cp=ROOT/f'cold-{family}/training/checkpoint.pt';assert r['checkpoint']==str(cp) and cp.is_file() and Path(str(cp)+'.previous').is_file()
 records=[json.loads(x) for x in (ROOT/f'telemetry-{family}/stages.jsonl').read_text().splitlines()]
 fits=[x for x in records if x['stage']=='fit_end'];assert len(fits)==1 and fits[0]['target_statistics_hash']==TARGET and fits[0]['fit_provenance']['history_count']==768
 for stage in ('before_optimizer','after_optimizer'):assert [x['step'] for x in records if x['stage']==stage]==[1,2]
 for x in records:
  assert x['additional_since_external_start']<=201326592
  if x['stage']=='before_optimizer':assert x['all_gradients_finite'] and x['gradient_dtypes']==['torch.float64']
  if x['stage']=='after_optimizer':assert x['moment_dtypes']==['torch.float64'] and x['step_counter_dtypes']==['torch.float32']
 cost=read(ROOT/f'telemetry-{family}/cost.json');source_ok(cost['source']);assert cost['additional_since_external_start']<=201326592
 assert any(x['stage']=='profile_complete' for x in records) and not any(x['stage']=='profile_failed' for x in records)
 return r

def fitted_case_ok(family,step,ordinal):
 p=ROOT/f'fitted-{family}/step{step}-{ordinal:02d}';r=read(p/'summary.json');source_ok(r['source']);assert r['status']=='passed' and r['family']==family and r['ordinal']==ordinal and r['net_peak_bytes']<=201326592
 initial=read(f'artifacts/task18/epsilon1em6-initial-9aca1b/{family}-{ordinal:02d}/summary.json');assert r['history_id']==initial['history_id'] and r['raw_hashes']==initial['raw_hashes'] and r['candidate_reference_terminal_bitwise_replay']
 ck=r['checkpoint'];assert ck['step']==step and ck['target_hash']==TARGET and ck['fit_provenance']['history_count']==768 and ck['fixed_kernel_hash']==initial['fixed_kernel_hash']
 cp=ROOT/f'cold-{family}/training/checkpoint.pt';cp=Path(str(cp)+'.previous') if step==0 else cp
 assert ck['path']==str(cp) and ck['sha256']==sha(cp) and ck['config_sha256']==sha(ROOT/f'prepare-{family}/calibration.yaml')
 assert r['task_gradients_sha256']==sha(p/'task-gradients.pt') and len(r['metrics'])==13
 assert all(m['accepted'] for m in r['metrics']) and all(m['atol']==m['rtol']==1e-12 for m in r['metrics'] if m.get('scope')!='inactive_parameter')
 assert r['statistics_module_absent'] and r['seal_sha256']==os.environ['TASK18_FULL_SEAL_SHA']
 return r

def fitted_ok(family):
 r=read(ROOT/f'fitted-{family}/summary.json');source_ok(r['source']);assert r['status']=='all24_fitted_checkpoint_cells_passed' and r['family']==family and len(r['cases'])==24
 assert [(x['step'],x['ordinal']) for x in r['cases']]==[(s,i) for s in (0,2) for i in range(12)]
 for x in r['cases']:fitted_case_ok(family,x['step'],x['ordinal']);assert sha(x['summary'])==x['sha256']
 assert r['max_case_net_peak_bytes']<=201326592
 return r
