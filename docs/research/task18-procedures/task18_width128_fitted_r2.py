from pathlib import Path
import argparse,json,time,hashlib,subprocess,torch
from famjet.config import load_config
from famjet.train import _source,identities,_reconstruct
from famjet.analysis.development import resolve_policy,parameter_accounting
from famjet.checkpoint import load_checkpoint
from famjet.provenance import canonical_hash
from famjet.eval.budgets import model_ledger
from famjet.artifacts import atomic_json
from famjet.eval.splits import _write_immutable
P=argparse.ArgumentParser();P.add_argument('family',choices=['jet','bank']);a=P.parse_args();family=a.family
out=Path(f'artifacts/task18/width128-verification-{family}-r2');out.mkdir(exist_ok=False);start=time.perf_counter();source=_source();configpath=Path(f'artifacts/task18/width128-preparation/calibration-{family}.yaml');c=load_config(configpath);identity,_=identities(c,resolve_policy(c));expected={**identity,'source':source};checkpoints={0:Path(f'artifacts/task18/calibration-{family}-width128/training/checkpoint.pt.previous'),2:Path(f'artifacts/task18/calibration-{family}-width128/training/checkpoint.pt')}
_write_immutable(out/'procedure.json',{'source':source,'helper_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'config_sha256':hashlib.sha256(configpath.read_bytes()).hexdigest(),'scope':'verify actualcoldfit step0/2, fitted task/MLP/input gradients atoriginal1e-12, exact initial memory composition, uniform step2 Decimal remains separate','no_refit':True});verified={};checks={}
for step,p in checkpoints.items():
 ck=load_checkpoint(p,expected);assert ck['completed_step']==step;assert ck['config']['training']['optimizer_steps']==32768;m=_reconstruct(ck['model']);assert canonical_hash(m.target_statistics)=='0cebf5f59f3b44f44875b73d582e6cb3c21a0ade54867edfabaebcab220dad21';assert m.fit_provenance['history_count']==768 and m.kernel.t_ref==1.;assert all(v.dtype==torch.float64 for v in m.state_dict().values() if v.is_floating_point())
 for s in ck['optimizer']['state'].values():assert s['exp_avg'].dtype==s['exp_avg_sq'].dtype==torch.float64 and s['step'].dtype==torch.float32
 assert m.persistent_nbytes(m.init_state(1,device='cpu',dtype='float64'))==9345;ledger=model_ledger(m);assert ledger['parameter_bytes']==(241768 if family=='jet' else 241800)
 verified[str(step)]={'checkpoint_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'step':step,'target_hash':canonical_hash(m.target_statistics),'fit_provenance':m.fit_provenance,'rates':m.kernel.rates.detach().tolist(),'logits':m.kernel.rate_source.logits.detach().tolist(),'parameters':parameter_accounting(m),'ledger':ledger};del ck,m
 atomic_json(out/'checkpoint-verification.json',verified)
 path=Path(f'artifacts/task18/width128-fitted-{family}-step{step}');log=Path(f'artifacts/task18-evidence/width128-fitted-{family}-step{step}.txt')
 with log.open('w') as target:r=subprocess.run(['.venv/bin/python','/tmp/task18_learned_numeric64.py',family,str(path),'--config',str(configpath),'--checkpoint',str(p),'--step',str(step)],stdout=target,stderr=subprocess.STDOUT)
 if r.returncode:raise SystemExit(r.returncode)
 rows=[json.loads(v) for v in (path/'cases.jsonl').read_text().splitlines()];metrics=[v for row in rows for v in row['metrics'] if v['name'].startswith(('task_','reader_')) or v['name'] in ('terminal_raw_features','stream_raw_features')];checks[str(step)]={'accepted':all(v['accepted'] for v in metrics),'max_ratio':max(v.get('max_pointwise_ratio',0) for v in metrics),'failures':[v for v in metrics if not v['accepted']],'original_binary64_summary':json.loads((path/'summary.json').read_text())};atomic_json(out/'fitted-checks.json',checks)
 if not checks[str(step)]['accepted']:raise RuntimeError('fitted task/reader numerical gate failed')
 if step==0:
  initial=Path(f'artifacts/task18/width128-initial-{family}');oldrows=[json.loads(v) for v in (initial/'cases.jsonl').read_text().splitlines()];oldsummary=json.loads((initial/'summary.json').read_text());assert oldsummary['source']==source and oldsummary['rates']==verified['0']['rates'];matches=[]
  for i,(old,new) in enumerate(zip(oldrows,rows)):
   assert old['history_id']==new['history_id'] and old['candidate_events_hash']==new['candidate_events_hash'] and old['raw_hashes']==new['raw_hashes']
   x=torch.load(initial/f'case-{i:02d}.pt',weights_only=True);y=torch.load(path/f'case-{i:02d}.pt',weights_only=True)
   def equal(a,b):
    if isinstance(a,torch.Tensor):return torch.equal(a,b)
    if isinstance(a,dict):return a.keys()==b.keys() and all(equal(a[k],b[k]) for k in a)
    return len(a)==len(b) and all(equal(u,v) for u,v in zip(a,b))
   fields=('terminal','stream','memory_gradient_actual','features');assert all(equal(x[k],y[k]) for k in fields);matches.append({'ordinal':i,'fields':fields,'initial_sha256':old['tensors_sha256'],'fitted_sha256':new['tensors_sha256']});del x,y
  atomic_json(out/'step0-reference-composition.json',{'source':source,'status':'all12_captured_memory_fields_bitwise_equal_to_accepted_initial','checkpoint_sha256':verified['0']['checkpoint_sha256'],'initial_gate_sha256':hashlib.sha256(Path('artifacts/task18/width128-initial-gate/accepted-gate.json').read_bytes()).hexdigest(),'matches':matches,'scope':'accepted initial Decimal memory fields reused only at identical represented rates/inputs/probe; fitted task/reader checked separately; oldbinaryrows retained'})
atomic_json(out/'summary.json',{'status':'fitted0and2_passed_step0_memory_composed_step2_decimal_pending','source':source,'family':family,'verified':verified,'checks':checks,'seconds':time.perf_counter()-start});print(json.dumps({'family':family,'status':'fitted0and2_passed','checks':{k:v['max_ratio'] for k,v in checks.items()},'seconds':time.perf_counter()-start}),flush=True)
