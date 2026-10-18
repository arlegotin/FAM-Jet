"""External fresh-learning phase checks; no scientific computation or guard bypass."""
from pathlib import Path
import hashlib,json,os,subprocess,sys
EXPECTED='76e5f8cea0c4bfc763ecefcd35184950562caeb3'
PACKAGE='57c0920f360e47f2c3978f056437143c4262b8ab9653b753df1321402ade9717'
ROOT=Path('artifacts/task18/epsilon1em6-learning-76e5f8c')
PREP=Path('artifacts/task18-evidence/epsilon1em6-learning-preparation-76e5f8c')
OPS=Path('artifacts/task18/epsilon1em6-operational-c715479')
TARGET='0cebf5f59f3b44f44875b73d582e6cb3c21a0ade54867edfabaebcab220dad21'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def canonical(x):return hashlib.sha256(json.dumps(x,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def source_ok(x):assert x==dict(commit=EXPECTED,diff='',package_hash=PACKAGE,untracked_package_files={})
def preflight():
 path=os.environ['TASK18_LEARN_SEAL'];digest=os.environ['TASK18_LEARN_SEAL_SHA'];assert sha(path)==digest;s=read(path)
 assert s['source_commit']==EXPECTED and s['package_hash']==PACKAGE
 assert subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()==EXPECTED and not subprocess.check_output(['git','status','--porcelain'],text=True)
 files={str(p):sha(p) for p in sorted(Path('famjet').rglob('*.py'))};assert files==s['package_files'] and canonical(files)==PACKAGE
 for n,r in s['helpers'].items():assert sha(Path(__file__).with_name(n))==r['sha256']
 for p,r in s['dependencies'].items():assert sha(p)==r['sha256']
 for f,r in s['configs'].items():assert sha(r['path'])==r['sha256']
 assert 'famjet.analysis.statistics' not in sys.modules
 return s

def config_ok(f):
 from famjet.config import load_config
 from famjet.analysis.development import resolve_policy,execution_shape
 s=read(os.environ['TASK18_LEARN_SEAL']);c=load_config(PREP/f'{f}-learning.yaml');assert canonical(read_config(f))==s['configs'][f]['config_hash'];resolve_policy(c)
 old=load_config(OPS/f'prepare-{f}/calibration.yaml');assert canonical(execution_shape(c))==canonical(execution_shape(old))
 for p,h in [(c.development.cache_manifest_path,c.development.cache_manifest_hash),(c.development.feature_cache_manifest_path,c.development.feature_cache_manifest_hash)]:
  m=read(p);assert canonical(m)==h and m['status']=='complete' and len(m['entries'])==6144 and m['identity']['source_hash']==PACKAGE
 fm=read(c.development.feature_cache_manifest_path);assert fm['identity']['version']==2 and fm['identity']['read_policy']=={'epsilon':1e-6,'numerical_support_floor':1e-8} and fm['identity']['target_statistics_hash']==TARGET
 return c

def read_config(f):
 import yaml
 return yaml.safe_load((PREP/f'{f}-learning.yaml').read_text())

def learning_ok(f):
 c=config_ok(f);out=ROOT/f'learn-{f}';r=read(out/'development.json');source_ok(r['source']);assert r['source_hash']==PACKAGE and r['config']==read_config(f) and r['status']=='completed'
 assert r['execution_stop_at']==8192 and r['configured_training_horizon']==32768 and r['resume'] is None and r['rss_highwater_additional_bytes']<=201326592
 t=r['training_run'];source_ok(t['source']);assert t['status']=='completed' and t['completed_step']==8192 and t['resume'] is None
 ids=[f'train-{i:012d}' for i in range(24576)];assert t['consumed_episode_ids']==ids==t['attempted_episode_ids']
 assert t['corpus_progress']==dict(completed_passes=4,corpus_histories=6144,pass_offset=0,unique_histories=6144)
 fit=t['preprocessing']['fit_provenance'];assert fit['history_count']==768 and fit['t_ref']==1. and fit['target_hash']==TARGET
 assert t['feature_cache_verification']['boundary']=='actual_disk_read_sha256_all_feature_files'
 curves=[json.loads(x) for x in (out/'learning_curve.jsonl').read_text().splitlines()];assert [x['step'] for x in curves]==[0,128,512,1024,2048,4096,8192]
 assert all(x['target_statistics_hash']==TARGET for x in curves)
 cp=out/'training/checkpoint.pt';assert r['checkpoint']==str(cp) and cp.is_file()
 clock=read(ROOT/f'{f}-learning-clock.json');source_ok(clock['source']);assert clock['status']=='completed' and clock['exception_type'] is None
 return r

def endpoint_case_ok(f,step,i):
 assert step==8192;p=ROOT/f'endpoint-{f}/step8192-{i:02d}';r=read(p/'summary.json');source_ok(r['source']);assert r['status']=='passed' and r['family']==f and r['ordinal']==i and r['net_peak_bytes']<=201326592
 initial=read(f'artifacts/task18/epsilon1em6-initial-9aca1b/{f}-{i:02d}/summary.json');assert r['history_id']==initial['history_id'] and r['raw_hashes']==initial['raw_hashes'] and r['candidate_reference_terminal_bitwise_replay']
 ck=r['checkpoint'];cp=ROOT/f'learn-{f}/training/checkpoint.pt';assert ck['path']==str(cp) and ck['sha256']==sha(cp) and ck['step']==8192 and ck['config_sha256']==sha(PREP/f'{f}-learning.yaml')
 assert ck['target_hash']==TARGET and ck['fit_provenance']['history_count']==768 and ck['fixed_kernel_hash']==initial['fixed_kernel_hash']
 assert len(r['metrics'])==13 and all(m['accepted'] for m in r['metrics']) and all(m['atol']==m['rtol']==1e-12 for m in r['metrics'] if m.get('scope')!='inactive_parameter')
 assert r['task_gradients_sha256']==sha(p/'task-gradients.pt') and r['statistics_module_absent'] and r['seal_sha256']==os.environ['TASK18_LEARN_SEAL_SHA']
 return r

def endpoint_ok(f):
 learning_ok(f);r=read(ROOT/f'endpoint-{f}/summary.json');source_ok(r['source']);assert r['status']=='all12_trained_endpoint_cells_passed' and r['family']==f and [(x['step'],x['ordinal']) for x in r['cases']]==[(8192,i) for i in range(12)]
 for x in r['cases']:endpoint_case_ok(f,x['step'],x['ordinal']);assert sha(x['summary'])==x['sha256']
 return r

def risk_ok(f):
 endpoint_ok(f);out=ROOT/f'risk-{f}';r=read(out/'summary.json');source_ok(r['source']);assert r['status']=='completed' and r['family']==f and r['histories']==6144 and r['checkpoint_step']==8192 and r['rss_additional_bytes']<=201326592
 assert r['checkpoint_sha256']==sha(ROOT/f'learn-{f}/training/checkpoint.pt') and r['target_statistics_hash']==TARGET and all(v==0 for v in r['counts'].values())
 c=config_ok(f);assert r['cache_manifest_hash']==c.development.cache_manifest_hash and r['feature_manifest_hash']==c.development.feature_cache_manifest_hash and sha(out/'histories.jsonl')==r['rows_sha256']
 rows=[json.loads(x) for x in (out/'histories.jsonl').read_text().splitlines()];manifest=read(c.development.feature_cache_manifest_path);assert len(rows)==6144 and len(r['cell_counts'])==12 and set(r['cell_counts'].values())=={512}
 for i,(row,entry) in enumerate(zip(rows,manifest['entries'])):assert row['ordinal']==i and row['history_id']==entry['episode_id'] and row['raw_hashes']==entry['hashes'] and row['status']=='ok'
 return r
