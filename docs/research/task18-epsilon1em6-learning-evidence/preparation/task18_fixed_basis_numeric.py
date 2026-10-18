"""External bounded initial gate; no training, fit, cache preparation or quality scoring."""
from pathlib import Path
from dataclasses import asdict,replace
from decimal import Decimal,localcontext
from datetime import datetime,timezone
import argparse,ast,copy,hashlib,json,math,platform,resource,sys,time
import numpy as np
from numpy.polynomial.legendre import leggauss,legvander
from scipy.linalg import expm
import torch
from famjet.config import load_config
from famjet.train import make_model,move_episode,_source,history_loss,check_smoke_memory
from famjet.analysis.development import draw_config,parameter_accounting
from famjet.data.synthetic import generate_episode,batch_hash
from famjet.eval.isolation import export_method
from famjet.eval.budgets import model_ledger
from famjet.eval.splits import _write_immutable
from famjet.artifacts import atomic_json
from famjet.types import FeatureBatch
from famjet.readers.structured import query_inputs
from famjet.provenance import canonical_hash

EXPECTED='e7565155c07638ff0367e9a12062c5c69be95ad5'
PACKAGE='ad542defda704e06dc9c88819b95afd6f483a882c792e82bf8c85dc27a6f6641'
D=lambda x:Decimal.from_float(float(x));ZERO=Decimal(0);ONE=Decimal(1)
ALPHA=D(float(torch.tensor(.03)));BETA=D(float(torch.tensor(.07)))

def config(family):
 c=load_config(Path('configs/development/'+('bank' if family=='bank' else 'jet')+'_learned_cpu64_width128_32768.yaml'))
 m=replace(c.model,rates=replace(c.model.rates,mode='fixed'))
 if family=='multiscale':
  p=load_config(Path('configs/multiscale-smoke.yaml')).model.multiscale
  m=replace(m,method='multiscale',rates=None,J=None,multiscale=replace(p,order=4,scale_order=2,epsilon=1e-4,tau0=16.,declared_gaps=()))
 return replace(c,model=m,development=replace(c.development,mode='calibration',calibration_path=None,calibration_hash=None,cache_manifest_path=None,cache_manifest_hash=None,feature_cache_manifest_path=None,feature_cache_manifest_hash=None))

def metric(name,a,b,rtol=1e-12,atol=1e-12):
 if a is None or b is None:return {'name':name,'accepted':a is None and b is None,'scope':'inactive_parameter' if a is None and b is None else 'missing_gradient'}
 a=a.detach().double().flatten();b=b.detach().double().flatten();assert a.shape==b.shape
 err=(a-b).abs();rat=err/(atol+rtol*b.abs());i=int(rat.argmax())
 return {'name':name,'accepted':bool(torch.isfinite(a).all() and torch.isfinite(b).all() and (rat<=1).all()),'rtol':rtol,'atol':atol,'max_pointwise_ratio':float(rat.max()),'max_absolute_error':float(err.max()),'violating_elements':int((rat>1).sum()),'worst_flat_index':i,'worst_candidate':float(a[i]),'worst_reference':float(b[i]),'error_norm':float(torch.linalg.vector_norm(a-b)),'reference_norm':float(torch.linalg.vector_norm(b))}

def load_functions(path,names,namespace):
 tree=ast.parse(Path(path).read_text());defs=[node for node in tree.body if isinstance(node,ast.FunctionDef) and node.name in names]
 assert {node.name for node in defs}==set(names)
 exec(compile(ast.Module(body=defs,type_ignores=[]),str(path),'exec'),namespace)
 return {'file':str(path),'sha256':hashlib.sha256(Path(path).read_bytes()).hexdigest(),'definitions':{node.name:hashlib.sha256(ast.dump(node,include_attributes=False).encode()).hexdigest() for node in defs}}

def static_inventory(model,c):
 # Local external report only: traverse actual instance-owned values, not modules'
 # process-global code/registries. Deduplicate object identity and full storage.
 rows=[];seen=set();storage=set();total=0
 def walk(x,path):
  nonlocal total
  if id(x) in seen:return
  seen.add(id(x));size=sys.getsizeof(x);kind=type(x).__name__;extra=0
  if isinstance(x,torch.Tensor):
   st=x.untyped_storage();sid=(str(x.device),st._cdata)
   if sid not in storage:storage.add(sid);extra=st.nbytes()
  elif isinstance(x,np.ndarray):
   # Owning NumPy getsizeof includes data; views recurse to their complete owner.
   if x.base is not None:walk(x.base,path+'.base')
  row={'path':path,'type':kind,'python_getsizeof_bytes':size,'extra_tensor_storage_bytes':extra}
  if isinstance(x,(torch.Tensor,np.ndarray)):row.update(shape=list(x.shape),dtype=str(x.dtype),logical_array_bytes=x.numel()*x.element_size() if isinstance(x,torch.Tensor) else x.nbytes)
  elif type(x) in (str,int,float,bool) or x is None:row['value']=x
  rows.append(row);total+=size+extra
  if isinstance(x,dict):
   for k,v in x.items():walk(k,path+'.key:'+str(k));walk(v,path+'.'+str(k))
  elif isinstance(x,(list,tuple,set)):
   for i,v in enumerate(x):walk(v,path+f'[{i}]')
  elif not isinstance(x,(torch.Tensor,np.ndarray)) and hasattr(x,'__dict__'):walk(vars(x),path+'.__dict__')
 walk(model,'model');walk(c,'external_RunConfig')
 wire=json.dumps(export_method(model),sort_keys=True,separators=(',',':')).encode();configwire=json.dumps(asdict(c),sort_keys=True,separators=(',',':')).encode()
 return {'scope':'actual instance-owned Python objects plus distinct tensor storage; external RunConfig explicit; process-global libraries/code excluded and measured by RSS; no claimed allocator/RSS equality','objects':rows,'owned_python_and_array_storage_bytes':total,'inference_export_json_bytes':len(wire),'inference_export_sha256':hashlib.sha256(wire).hexdigest(),'external_config_json_bytes':len(configwire),'external_config_sha256':hashlib.sha256(configwire).hexdigest(),'tensor_ledger':model_ledger(model),'reader_budget':parameter_accounting(model),'numpy_objects_retained':sum(row['type']=='ndarray' for row in rows)}

def main():
 p=argparse.ArgumentParser();p.add_argument('family',choices=['jet','bank','multiscale']);p.add_argument('ordinal',type=int);p.add_argument('out');args=p.parse_args();assert 0<=args.ordinal<12
 source=_source();assert source['commit']==EXPECTED and source['package_hash']==PACKAGE and not source['diff'] and not source['untracked_package_files']
 torch.set_num_threads(4);out=Path(args.out);out.mkdir(parents=True,exist_ok=False);start=time.perf_counter();utc=datetime.now(timezone.utc);factor=1 if platform.system()=='Darwin' else 1024;base=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*factor
 c=config(args.family);torch.manual_seed(c.seed);m=make_model(c).eval()
 external_refs={};ns=dict(globals())
 if args.family!='multiscale':
  external_refs['decimal']=load_functions('docs/research/task18-procedures/task18_decimal_checkpoint.py',('oracle','flatten','tensor','compare','controls'),ns)
 else:
  external_refs['multiscale']=load_functions('tests/test_multiscale.py',('independent_system',),ns)
 procedure={'source':source,'helper_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'config':asdict(c),'family':args.family,'ordinal':args.ordinal,'reference_definitions':external_refs,'tolerances':{'rtol':1e-12,'atol':1e-12},'scope':'initial memory states/contractions/key/value/gate on12training cells; fixed rates have no trainable logit claim; shared query_inputs not independently certified; ordinal0 small unfitted shared-reader task gradient only','probe':{'jetbank_z':str(ALPHA),'jet_h':str(BETA),'multiscale':'sum(p**2) matching Task14 direct input controls'},'fit':'none; full768 fit deferred to separately allocated cold profiles','net_limit':201326592,'power_override':False,'utc_start':utc.isoformat()}
 _write_immutable(out/'procedure.json',procedure);atomic_json(out/'static-inventory.json',static_inventory(m,c))
 try:
  dc,hid=draw_config(c,args.ordinal);original=generate_episode(dc,c.development.data_seed,hid);ep=move_episode(original,'cpu',dtype=torch.float64);e=ep.events;n=int(e.lengths[0]);ages=(e.timestamps[0,n-1]-e.timestamps[0,:n]).double();mask=e.present[0,:n]&e.observed[0,:n].all(-1)
  key=e.key_features.clone().requires_grad_();value=e.values.clone().requires_grad_();gate=torch.ones(e.present.shape,dtype=torch.float64,requires_grad=True);e=replace(e,key_features=key,values=value,auxiliary={**e.auxiliary,'gate':gate});ep=replace(ep,events=e)
  rk=key.detach().clone().requires_grad_();rv=value.detach().clone().requires_grad_();rg=gate.detach().clone().requires_grad_()
  aug=torch.cat((rv[0,:n],torch.ones(n,1,dtype=torch.float64)),-1);writes=rk[0,:n,:,None]*aug[:,None,:]*(rg[0,:n]*mask)[:,None,None]
  controls={};binary=[];authoritative=[];reference80=None;convergence={};reference_seconds=[]
  if args.family=='multiscale':
   A,G,B,K=ns['independent_system'](4,2,1e-4,16.)
   from famjet.memory.multiscale import log_scale_system
   system=log_scale_system(4,2,1e-4,16.);L=-math.log(1e-4);betas=[]
   for count in (256,512):
    x,w=leggauss(count);betas.append((w*np.exp((x-1)*L/2))@legvander(x,1)*np.sqrt((2*np.arange(2)+1)*L)/2)
   basis=[metric('beta256_vs512',torch.tensor(betas[0]),torch.tensor(betas[1]),1e-10,1e-12),metric('Bessel_vs512',torch.tensor(system['beta']),torch.tensor(betas[1]),1e-10,1e-12),metric('finite_G',torch.tensor(system['G']),torch.tensor(G)),metric('eigenbasis_G',m.kernel.U@torch.diag(torch.tensor(system['gamma']))@m.kernel.U.T,torch.tensor(G))]
   controls={'basis_metrics':basis,'accepted':all(r['accepted'] for r in basis)}
   weights=torch.tensor(np.stack([expm(K*float(age))@B.flatten(order='F')/16. for age in ages]))
   P=torch.einsum('nc,nkv->ckv',weights,writes).reshape(2,4,16,9)
   ref={'p':torch.einsum('mnkv,mj->jnkv',P,m.kernel.U.detach()).reshape(1,1,8,16,9)}
   objective=lambda x:x['p'].square().sum()
  else:
   rates=m.kernel.rates.detach();d=rates[0,:,None]*ages[None];weight=torch.exp(-d)
   ref={'z':torch.einsum('jn,nkv->jkv',weight,writes)[None,None]}
   if args.family=='jet':ref['h']=torch.einsum('jn,nkv->jkv',d*weight,writes)[None,None]
   objective=lambda x:x['z'].square().sum()*float(ALPHA)+(x['h'].square().sum()*float(BETA) if 'h' in x else 0)
   controls=ns['controls']()
  state=m.encode(e,mode='terminal');actual={name:state.payload[name] for name in ref}
  ga=torch.autograd.grad(objective(actual),(key,value,gate),retain_graph=True);gr=torch.autograd.grad(objective(ref),(rk,rv,rg),retain_graph=True)
  with torch.no_grad():stream=m.encode(e,mode='stream')
  for name in ref:
   binary += [metric('terminal_'+name,actual[name],ref[name]),metric('stream_'+name,stream.payload[name],ref[name])]
  for name,a,b in zip(('key','value','gate'),ga,gr):binary.append(metric('memory_gradient_'+name,a,b))
  assert bool((ep.queries.T==e.timestamps[0,n-1]).all());qkey=ep.queries.key_features[0];qinputs=query_inputs(ep.queries,1.)
  if args.family=='multiscale':raw=torch.einsum('qk,ckv->qcv',qkey,ref['p'][0,0]).flatten(1)
  else:
   z=torch.einsum('qk,jkv->qjv',qkey,ref['z'][0,0]);h=torch.einsum('qk,jkv->qjv',qkey,ref['h'][0,0]) if 'h' in ref else None
   raw=torch.cat([z[...,:-1]]+([h[...,:-1]] if h is not None else [])+[z[...,-1:]]+([h[...,-1:]] if h is not None else []),-1).flatten(1)
  ref_features=torch.cat((raw[None],qinputs),-1);f=m.features(state,ep.queries)
  with torch.no_grad():sf=m.features(stream,ep.queries)
  binary += [metric('terminal_raw_features',f.values,ref_features),metric('stream_raw_features',sf.values,ref_features)]
  tensors={'terminal':{k:v.detach() for k,v in actual.items()},'stream':{k:stream.payload[k].detach() for k in ref},'binary64_reference':{k:v.detach() for k,v in ref.items()},'input_gradients':{k:v.detach() for k,v in zip(('key','value','gate'),ga)},'binary64_gradients':{k:v.detach() for k,v in zip(('key','value','gate'),gr)},'features':f.values.detach(),'stream_features':sf.values.detach()}
  if args.family=='multiscale':authoritative=binary
  else:
   results=[]
   for digits in (60,80):
    tick=time.perf_counter()
    with localcontext() as ctx:
     ctx.prec=digits;result=ns['oracle'](rates[0].tolist(),key[0].tolist(),value[0].tolist(),gate[0].tolist(),ages.tolist(),mask.tolist(),args.family=='jet')
     rows=[]
     for q in qkey.tolist():
      row=[]
      for j in range(c.model.J):
       z=[sum(D(q[k])*result['z'][j][k][v] for k in range(16)) for v in range(9)];h=[sum(D(q[k])*result['h'][j][k][v] for k in range(16)) for v in range(9)] if args.family=='jet' else None
       row.extend(z[:-1]);row.extend(h[:-1] if h is not None else []);row.append(z[-1]);row.extend([h[-1]] if h is not None else [])
      rows.append(row)
     result['raw_features']=[row+list(map(D,qi)) for row,qi in zip(rows,qinputs[0].tolist())]
    results.append(result);reference_seconds.append(time.perf_counter()-tick)
   with localcontext() as ctx:
    ctx.prec=80
    for name in results[0]:
     delta=max(abs(a-b) for a,b in zip(ns['flatten'](results[0][name]),ns['flatten'](results[1][name])));assert delta<Decimal('1e-45');convergence[name]=str(delta)
   reference80=results[1]
   for name in ref:
    authoritative += [ns['compare']('terminal_'+name,actual[name],reference80[name]),ns['compare']('stream_'+name,stream.payload[name],reference80[name])]
   for name,a in zip(('key','value','gate'),ga):authoritative.append(ns['compare']('memory_gradient_'+name,a,reference80['gradient_'+name]))
   authoritative += [ns['compare']('terminal_raw_features',f.values,reference80['raw_features']),ns['compare']('stream_raw_features',sf.values,reference80['raw_features'])]
   atomic_json(out/'reference80.json',{name:[str(x) for x in ns['flatten'](v)] for name,v in reference80.items()})
  task=[]
  if args.ordinal==0:
   rm=copy.deepcopy(m);rf=FeatureBatch(ref_features,f.supported,{'failure':torch.zeros_like(f.supported)})
   pred=m.read_features(f,ep.queries);rpred=rm.read_features(rf,ep.queries);loss=history_loss(m,pred,ep);rloss=history_loss(rm,rpred,ep)
   task += [metric('fresh_task_prediction',pred.prediction,rpred.prediction),metric('fresh_task_loss',loss,rloss)]
   names,params=zip(*m.reader.named_parameters());rnames,rparams=zip(*rm.reader.named_parameters());assert names==rnames
   tg=torch.autograd.grad(loss,(key,value,gate,*params),allow_unused=True);tr=torch.autograd.grad(rloss,(rk,rv,rg,*rparams),allow_unused=True)
   task += [metric('fresh_task_gradient_'+name,a,b) for name,a,b in zip(('key','value','gate',*names),tg,tr)]
   tensors['fresh_task_gradients']={name:(a.detach() if a is not None else None) for name,a in zip(('key','value','gate',*names),tg)}
  torch.save(tensors,out/'candidate.pt');peak=max(0,resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*factor-base);check_smoke_memory(c,peak)
  end=datetime.now(timezone.utc);ok=all(x['accepted'] for x in authoritative+task) and controls.get('accepted',True)
  summary={'status':'passed' if ok else 'failed_original_tolerance','source':source,'procedure_hash':canonical_hash(procedure),'family':args.family,'ordinal':args.ordinal,'history_id':hid,'raw_hashes':original.metadata['hashes'],'events_hash':batch_hash(e),'metrics':authoritative,'original_binary64_metrics':binary,'fresh_unfitted_reader_metrics':task,'controls':controls,'decimal60_80_convergence':convergence,'reference_seconds':reference_seconds,'candidate_sha256':hashlib.sha256((out/'candidate.pt').read_bytes()).hexdigest(),'static_inventory_sha256':hashlib.sha256((out/'static-inventory.json').read_bytes()).hexdigest(),'perf_seconds':time.perf_counter()-start,'utc_start':utc.isoformat(),'utc_end':end.isoformat(),'utc_seconds':(end-utc).total_seconds(),'net_peak_bytes':peak,'claim':'bounded initial numerical applicability; no fit/quality/convergence'}
  atomic_json(out/'summary.json',summary);print(json.dumps({k:v for k,v in summary.items() if k not in ('metrics','original_binary64_metrics','fresh_unfitted_reader_metrics','controls')}),flush=True)
 except BaseException as exc:
  atomic_json(out/'failure.json',{'source':source,'type':type(exc).__name__,'error':str(exc),'perf_seconds':time.perf_counter()-start});raise
if __name__=='__main__':main()
