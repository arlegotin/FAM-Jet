"""New full structured composition only; accepted fixed-memory evidence is replayed."""
from pathlib import Path
from dataclasses import asdict,replace
from datetime import datetime,timezone
import argparse,ast,copy,hashlib,json,math,platform,resource,subprocess,time,sys
import torch
from famjet.config import load_config
from famjet.train import make_model,move_episode,_source,history_loss,check_smoke_memory
from famjet.analysis.development import draw_config,parameter_accounting
from famjet.data.synthetic import generate_episode,batch_hash
from famjet.eval.isolation import export_method
from famjet.eval.budgets import model_ledger
from famjet.eval.state_io import tensor_record
from famjet.eval.splits import _write_immutable
from famjet.artifacts import atomic_json
from famjet.types import FeatureBatch
from famjet.readers.structured import query_inputs
from famjet.provenance import canonical_hash
from task18_fixed_basis_numeric import metric,static_inventory
EXPECTED='9aca1b8514aea36d6da060fbd2db01c5a6b33bf7'
PACKAGE='57c0920f360e47f2c3978f056437143c4262b8ab9653b753df1321402ade9717'
ORIGIN='e7565155c07638ff0367e9a12062c5c69be95ad5'
ORIGIN_PACKAGE='ad542defda704e06dc9c88819b95afd6f483a882c792e82bf8c85dc27a6f6641'
ALPHA=float(torch.tensor(.03))
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def config(family):
 c=load_config(f'configs/development/{family}_fixed_cpu64_raw128_32768.yaml')
 return replace(c,model=replace(c.model,epsilon=1e-6,reader=replace(c.model.reader,kind='structured',width=125 if family=='jet' else 122)),development=replace(c.development,mode='calibration',calibration_path=None,calibration_hash=None,cache_manifest_path=None,cache_manifest_hash=None,feature_cache_manifest_path=None,feature_cache_manifest_hash=None))
def component_proof(seal):
 current={str(p):sha(p) for p in sorted(Path('famjet').rglob('*.py'))}
 assert current==seal['package_files'] and canonical_hash(current)==PACKAGE
 assert 'famjet.analysis.statistics' not in sys.modules
 for path,record in seal['dependencies'].items():assert sha(path)==record['sha256'],path
 return seal['source_component_proof']


def reference_structured(z,h,rates,eps,floor):
 # Independent application of the declared normalized-memory equations to direct
 # impulse sums. Query/task construction and the MLP remain shared production.
 mass=z[...,-1];u=z[...,:-1];finite=torch.isfinite(z).all(-1)&(mass>=0)
 if h is not None:finite=finite&torch.isfinite(h).all(-1)
 safe_mass=torch.where(finite,mass,torch.zeros_like(mass));den=safe_mass+eps
 den_ok=torch.isfinite(den)&(den>0);den=torch.where(den_ok,den,torch.ones_like(den))
 support=finite&(mass>floor);ratio=u/den[...,None];log_rate=torch.log(rates).expand_as(mass)
 if h is not None:
  b=h[...,-1];hv=h[...,:-1];derivative=(ratio*b[...,None]-hv)/den[...,None]
  smooth=b/den;exact=torch.where(support,b,torch.zeros_like(b))/torch.where(support,mass,torch.ones_like(mass))
  mean_age=exact/rates;parts=(ratio,derivative,torch.log1p(safe_mass)[...,None],smooth[...,None],log_rate[...,None],support.to(mass)[...,None])
 else:parts=(ratio,torch.log1p(safe_mass)[...,None],log_rate[...,None],support.to(mass)[...,None]);exact=None;mean_age=None
 features=torch.cat(parts,-1);failed=(~finite)|(~den_ok)|(~torch.isfinite(features).all(-1))
 if mean_age is not None:failed=failed|(~torch.isfinite(mean_age))
 features=torch.where(failed[...,None],torch.zeros_like(features),features)
 return features.flatten(1),((support&~failed).any(-1)),failed.any(-1),exact,mean_age

def main():
 p=argparse.ArgumentParser();p.add_argument('family',choices=['jet','bank']);p.add_argument('ordinal',type=int);p.add_argument('out');p.add_argument('--seal',required=True);p.add_argument('--seal-sha',required=True);p.add_argument('--run-id',required=True);a=p.parse_args();assert 0<=a.ordinal<12
 assert sha(a.seal)==a.seal_sha;seal=json.loads(Path(a.seal).read_text());assert sha(__file__)==seal['helpers'][Path(__file__).name]['sha256']
 assert a.run_id and 'famjet.analysis.statistics' not in sys.modules
 source=_source();assert source['commit']==EXPECTED and source['package_hash']==PACKAGE and not source['diff'] and not source['untracked_package_files'];torch.set_num_threads(4)
 out=Path(a.out);out.mkdir(parents=True,exist_ok=False);tick=time.perf_counter();utc=datetime.now(timezone.utc);factor=1 if platform.system()=='Darwin' else 1024;base=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*factor
 c=config(a.family);assert canonical_hash(asdict(c))==seal['configs'][a.family]['config_hash'];assert c.model.epsilon==1e-6 and c.model.numerical_support_floor==1e-8
 expected_case=seal['cases'][f'{a.family}-{a.ordinal:02d}'];assert Path(a.out)==Path(seal['output_root'])/f'{a.family}-{a.ordinal:02d}'
 origin=Path(f'artifacts/task18/fixed-basis-initial/{a.family}-{a.ordinal:02d}');old=json.loads((origin/'summary.json').read_text());op=json.loads((origin/'procedure.json').read_text());oldkernel=Path(f'artifacts/task18/fixed-basis-fitted-{a.family}/step0-{a.ordinal:02d}/checkpoint-verification.json');kernel=json.loads(oldkernel.read_text())
 assert old['status']=='passed' and old['source']['commit']==ORIGIN and old['source']['package_hash']==ORIGIN_PACKAGE
 expected_config=copy.deepcopy(op['config']);expected_config['model']['epsilon']=1e-6;expected_config['model']['reader'].update(kind='structured',width=125 if a.family=='jet' else 122)
 assert expected_config==json.loads(json.dumps(asdict(c)))
 for path_key,hash_key in (('origin_summary_path','origin_summary_sha256'),('origin_procedure_path','origin_procedure_sha256'),('origin_kernel_record_path','origin_kernel_record_sha256')):assert sha(expected_case[path_key])==expected_case[hash_key]
 assert old['candidate_sha256']==expected_case['origin_capture_recorded_sha256'] and kernel['fixed_kernel_hash']==expected_case['fixed_kernel_hash']
 proof=component_proof(seal);assert 'famjet.analysis.statistics' not in sys.modules;torch.manual_seed(c.seed);m=make_model(c).eval();assert m._parameter_hash()==kernel['fixed_kernel_hash'] and m.kernel.t_ref==1.
 rates=m.kernel.rates.detach()[0];expected=torch.logspace(math.log10(op['config']['model']['rates']['bounds'][0]),0,op['config']['model']['J'],dtype=torch.float64);assert torch.equal(rates,expected)
 assert sha(origin/'candidate.pt')==old['candidate_sha256'];prior=torch.load(origin/'candidate.pt',weights_only=True)
 for item in op['reference_definitions'].values():assert sha(item['file'])==item['sha256']
 procedure={'preparation_seal_sha256':a.seal_sha,'run_id':a.run_id,'epsilon':c.model.epsilon,'config_hash':canonical_hash(asdict(c)),'source':source,'helper_sha256':sha(__file__),'common_metric_static_helper_sha256':sha(Path(__file__).with_name('task18_fixed_basis_numeric.py')),'source_component_proof':proof,'reference_origin_source':old['source'],'origin_summary_sha256':sha(origin/'summary.json'),'origin_procedure_sha256':sha(origin/'procedure.json'),'origin_capture_sha256':old['candidate_sha256'],'origin_fitted_kernel_record_sha256':sha(oldkernel),'fixed_kernel_hash':m._parameter_hash(),'represented_rates':rates.tolist(),'rate_tensor_hash':canonical_hash(tensor_record(rates)),'config':asdict(c),'family':a.family,'ordinal':a.ordinal,'feature_probe':'represented float32 .03 promoted toCPU64 times sum of squares of all structured MEMORY features; excludes shared query inputs','tolerances':{'rtol':1e-12,'atol':1e-12},'scope':'NEWfullstructured features and key/value/gate feature-probe +task/common-production-reader gradients all12cells/family; exact unchanged oldmemory composition, no stream/Decimal/refit/quality; fixedrates no logit gradients; sharedqueryinputs/MLP not independently certified','net_limit':201326592,'power_override':False,'utc_start':utc.isoformat()};_write_immutable(out/'procedure.json',procedure)
 try:
  dc,hid=draw_config(c,a.ordinal);ep0=generate_episode(dc,c.development.data_seed,hid);assert hid==expected_case['history_id'] and ep0.metadata['hashes']==old['raw_hashes']==expected_case['raw_hashes'];ep=move_episode(ep0,'cpu',dtype=torch.float64);e=ep.events;n=int(e.lengths[0]);ages=(e.timestamps[0,n-1]-e.timestamps[0,:n]).double();mask=e.present[0,:n]&e.observed[0,:n].all(-1)
  key=e.key_features.clone().requires_grad_();value=e.values.clone().requires_grad_();gate=torch.ones(e.present.shape,dtype=torch.float64,requires_grad=True);e=replace(e,key_features=key,values=value,auxiliary={**e.auxiliary,'gate':gate});ep=replace(ep,events=e);assert batch_hash(e)==old['events_hash']
  rk=key.detach().clone().requires_grad_();rv=value.detach().clone().requires_grad_();rg=gate.detach().clone().requires_grad_();aug=torch.cat((rv[0,:n],torch.ones(n,1,dtype=torch.float64)),-1);writes=rk[0,:n,:,None]*aug[:,None,:]*(rg[0,:n]*mask)[:,None,None]
  scaled=rates[:,None]*ages[None];weights=torch.exp(-scaled);ref={'z':torch.einsum('jn,nkv->jkv',weights,writes)[None,None]}
  if a.family=='jet':ref['h']=torch.einsum('jn,nkv->jkv',scaled*weights,writes)[None,None]
  state=m.encode(e,mode='terminal')
  for name in ref:assert torch.equal(state.payload[name].detach(),prior['terminal'][name]) and torch.equal(ref[name].detach(),prior['binary64_reference'][name])
  assert bool((ep.queries.T==e.timestamps[0,n-1]).all());qkey=ep.queries.key_features[0];qinputs=query_inputs(ep.queries,1.)
  z=torch.einsum('qk,jkv->qjv',qkey,ref['z'][0,0]);h=torch.einsum('qk,jkv->qjv',qkey,ref['h'][0,0]) if a.family=='jet' else None
  f=m.features(state,ep.queries);raw_parts=[f.diagnostics['u']]+([f.diagnostics['h']] if h is not None else [])+[f.diagnostics['z'][...,None]]+([f.diagnostics['b'][...,None]] if h is not None else [])
  raw_candidate=torch.cat((torch.cat(raw_parts,-1).flatten(2),qinputs),-1);assert torch.equal(raw_candidate.detach(),prior['features'])
  values,supported,failed,exact,mean_age=reference_structured(z,h,rates,c.model.epsilon,c.model.numerical_support_floor);rf=FeatureBatch(torch.cat((values[None],qinputs),-1),supported[None],{'failure':failed[None]})
  assert torch.equal(f.supported,rf.supported) and torch.equal(f.diagnostics['failure'],rf.diagnostics['failure'])
  metrics=[metric('new_structured_features',f.values,rf.values)]
  if h is not None:metrics += [metric('diagnostic_exact_dimensionless_age',f.diagnostics['dimensionless_age'].flatten(),exact.flatten()),metric('diagnostic_exact_physical_mean_age',f.diagnostics['mean_age'].flatten(),mean_age.flatten())]
  memory_width=80 if a.family=='jet' else 88
  ga=torch.autograd.grad(ALPHA*f.values[...,:memory_width].square().sum(),(key,value,gate),retain_graph=True);gr=torch.autograd.grad(ALPHA*values.square().sum(),(rk,rv,rg),retain_graph=True)
  metrics += [metric('new_feature_input_gradient_'+name,x,y) for name,x,y in zip(('key','value','gate'),ga,gr)]
  rm=copy.deepcopy(m);pred=m.read_features(f,ep.queries);rpred=rm.read_features(rf,ep.queries);loss=history_loss(m,pred,ep);rloss=history_loss(rm,rpred,ep);names,params=zip(*m.reader.named_parameters());rnames,rparams=zip(*rm.reader.named_parameters());assert names==rnames
  tg=torch.autograd.grad(loss,(key,value,gate,*params),allow_unused=True);tr=torch.autograd.grad(rloss,(rk,rv,rg,*rparams),allow_unused=True)
  metrics += [metric('fresh_task_prediction',pred.prediction,rpred.prediction),metric('fresh_task_loss',loss,rloss)]+[metric('fresh_task_gradient_'+name,x,y) for name,x,y in zip(('key','value','gate',*names),tg,tr)]
  tensors={'new_features':f.values.detach(),'reference_new_features':rf.values.detach(),'feature_input_gradients':{k:x.detach() for k,x in zip(('key','value','gate'),ga)},'reference_feature_input_gradients':{k:x.detach() for k,x in zip(('key','value','gate'),gr)},'task_gradients':{k:x.detach() if x is not None else None for k,x in zip(('key','value','gate',*names),tg)},'reference_task_gradients':{k:x.detach() if x is not None else None for k,x in zip(('key','value','gate',*names),tr)}};torch.save(tensors,out/'new-structured-capture.pt')
  assert 'famjet.analysis.statistics' not in sys.modules
  peak=max(0,resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*factor-base);check_smoke_memory(c,peak);end=datetime.now(timezone.utc)
  summary={'preparation_seal_sha256':a.seal_sha,'run_id':a.run_id,'epsilon':c.model.epsilon,'config_hash':canonical_hash(asdict(c)),'statistics_module_absent':True,'case_count':1,'status':'passed' if all(x['accepted'] for x in metrics) else 'failed_original_tolerance','source':source,'family':a.family,'ordinal':a.ordinal,'history_id':hid,'raw_hashes':ep0.metadata['hashes'],'events_hash':old['events_hash'],'fixed_kernel_hash':m._parameter_hash(),'origin_source':old['source'],'origin_summary_sha256':sha(origin/'summary.json'),'accepted_memory_composition':'unchanged sourcecomponents+exactrepresentedrates/kernel+events/query/oracle+terminal/raw/direct-reference replay','metrics':metrics,'max_ratio':max(x.get('max_pointwise_ratio',0) for x in metrics),'model_ledger':model_ledger(m),'parameter_accounting':parameter_accounting(m),'capture_sha256':sha(out/'new-structured-capture.pt'),'procedure_sha256':sha(out/'procedure.json'),'perf_seconds':time.perf_counter()-tick,'utc_start':utc.isoformat(),'utc_end':end.isoformat(),'utc_seconds':(end-utc).total_seconds(),'net_peak_bytes':peak};atomic_json(out/'summary.json',summary);print(json.dumps({'family':a.family,'ordinal':a.ordinal,'status':summary['status'],'max_ratio':summary['max_ratio'],'seconds':summary['perf_seconds'],'net_peak':peak}),flush=True)
  if summary['status']!='passed':raise RuntimeError('original pointwise tolerance failed; downstream remains held')
 except BaseException as exc:atomic_json(out/'failure.json',{'source':source,'run_id':a.run_id,'preparation_seal_sha256':a.seal_sha,'type':type(exc).__name__,'error':str(exc),'perf_seconds':time.perf_counter()-tick});raise
if __name__=='__main__':main()
