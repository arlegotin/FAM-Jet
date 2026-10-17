from pathlib import Path
from dataclasses import replace,asdict
import argparse,copy,json,time,hashlib,resource,platform,gc,math
import torch
from famjet.config import load_config
from famjet.analysis.development import draw_config,resolve_policy
from famjet.data.synthetic import generate_episode,batch_hash
from famjet.train import make_model,move_episode,_source,check_smoke_memory,identities,history_loss,_reconstruct
from famjet.checkpoint import load_checkpoint
from famjet.memory.jet import JetMemory
from famjet.memory.expbank import ExpBankMemory
from famjet.readers.structured import query_inputs
from famjet.types import FeatureBatch
from famjet.provenance import canonical_hash
from famjet.artifacts import atomic_json,append_jsonl
from famjet.eval.splits import _write_immutable

parser=argparse.ArgumentParser();parser.add_argument('family',choices=['jet','bank']);parser.add_argument('out');parser.add_argument('--config');parser.add_argument('--checkpoint');parser.add_argument('--step',type=int);args=parser.parse_args()
torch.set_num_threads(4);out=Path(args.out);out.mkdir(exist_ok=False,parents=True)
factor=1 if platform.system()=='Darwin' else 1024;baseline=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*factor;started=time.perf_counter()
c=load_config(Path(args.config or f'configs/development/{args.family}_finite_raw_32768.yaml'))
if not args.checkpoint:
 c=replace(c,model=replace(c.model,precision='float64',rates=replace(c.model.rates,mode='learned',bounds=(1/5224,1.))),development=replace(c.development,mode='calibration',fit_histories_per_cell=64,eval_histories_per_cell=8,milestones=(0,128,512,1024,2048,4096,8192,16384,32768),cache_manifest_path=None,cache_manifest_hash=None,feature_cache_manifest_path=None,feature_cache_manifest_hash=None,calibration_path=None,calibration_hash=None))
torch.manual_seed(c.seed);source=_source();checkpoint_hash=None
if args.checkpoint:
 identity,_=identities(c,resolve_policy(c));ck=load_checkpoint(Path(args.checkpoint),{**identity,'source':source});assert ck['completed_step']==args.step
 m=_reconstruct(ck['model']).to('cpu');checkpoint_hash=hashlib.sha256(Path(args.checkpoint).read_bytes()).hexdigest()
 assert canonical_hash(m.target_statistics)=='0cebf5f59f3b44f44875b73d582e6cb3c21a0ade54867edfabaebcab220dad21'
else:m=make_model(c)
m.eval();assert m.kernel.chunk_size==32
procedure={'date':'2026-10-17','kind':'learned_rate_CPU64_numerical_frontier','family':args.family,'source':source,'helper_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'config':asdict(c),'checkpoint':args.checkpoint,'checkpoint_sha256':checkpoint_hash,'completed_step':args.step,'fit_provenance':m.fit_provenance,'target_statistics_hash':canonical_hash(m.target_statistics) if m.target_statistics else None,'threads':4,'candidate_precision':'CPU float64','reference':'independent CPU64 direct event sums at exact represented candidate inputs/rates','rtol':1e-12,'atol':1e-12,'cpu64_state_rtol':1e-12,'cpu64_state_atol':1e-12,'common_MLP_gradient_rule':'CPU64 original pointwise1e-12/1e-12; norm envelope descriptive only','fixture':'first12 ordered training draws, one per length/regime; unit gate inserted to probe default-gate derivative','reader_validation':bool(args.checkpoint),'encode':'terminal full gradients; causal stream no_grad values','net_allocation_limit_bytes':201326592,'rates':m.kernel.rates.detach().tolist(),'logits':m.kernel.rate_source.logits.detach().tolist(),'protected_namespaces':'closed','claim':'configuration/fixture applicability only; no model quality interpretation'}
_write_immutable(out/'procedure.json',procedure);records=[]
def memory():return max(0,resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*factor-baseline)
def metric(name,a,b,*,rtol=1e-12,atol=1e-12,norm=False):
 if a is None or b is None:return {'name':name,'accepted':a is None and b is None,'status':'objective_inactive' if a is None and b is None else 'gradient_missing'}
 a=a.detach().cpu().double();b=b.detach().cpu().double();finite=bool(torch.isfinite(a).all() and torch.isfinite(b).all());error=(a-b).abs();ratio=error/(atol+rtol*b.abs());flat=int(ratio.argmax()) if ratio.numel() else 0;errnorm=float(torch.linalg.vector_norm(a-b));refnorm=float(torch.linalg.vector_norm(b));worst=float(ratio.max()) if ratio.numel() else 0
 return {'name':name,'accepted':finite and (errnorm<=atol+rtol*refnorm if norm else worst<=1),'criterion':'frobenius' if norm else 'pointwise','rtol':rtol,'atol':atol,'finite':finite,'max_absolute_error':float(error.max()) if error.numel() else 0,'max_pointwise_ratio':worst,'violating_elements':int((ratio>1).sum()),'error_norm':errnorm,'reference_norm':refnorm,'worst_flat_index':flat,'worst_candidate':float(a.flatten()[flat]) if a.numel() else None,'worst_reference':float(b.flatten()[flat]) if b.numel() else None,'shape':list(a.shape)}
def direct(e,rates,key,value,gate):
 n=int(e.lengths[0]);age=(e.timestamps[0,n-1]-e.timestamps[0,:n]).double()
 aug=torch.cat((value[0,:n],torch.ones(n,1,dtype=torch.float64)),-1)
 writes=key[0,:n,:,None]*aug[:,None,:]*(gate[0,:n]*e.observed[0,:n].all(-1)*e.present[0,:n])[:,None,None]
 d=rates[0,:,None]*age[None];weight=torch.exp(-d)
 z=torch.einsum('jn,nkv->jkv',weight,writes)[None,None]
 h=torch.einsum('jn,nkv->jkv',d*weight,writes)[None,None]
 return {'z':z,**({'h':h} if args.family=='jet' else {})}
def objective(payload):
 return payload['z'].square().sum()*float(torch.tensor(.03))+(payload['h'].square().sum()*float(torch.tensor(.07)) if 'h' in payload else 0)
def detached(x):
 if isinstance(x,torch.Tensor):return x.detach().cpu()
 if isinstance(x,dict):return {k:detached(v) for k,v in x.items()}
 if isinstance(x,(list,tuple)):return [detached(v) for v in x]
 return x
try:
 for i in range(12):
  tick=time.perf_counter();dc,history_id=draw_config(c,i);original=generate_episode(dc,c.development.data_seed,history_id);ep=move_episode(original,'cpu',dtype=torch.float64);e=ep.events
  key=e.key_features.detach().clone().requires_grad_();value=e.values.detach().clone().requires_grad_();gate=torch.ones(e.present.shape,dtype=torch.float64,requires_grad=True)
  e=replace(e,key_features=key,values=value,auxiliary={**e.auxiliary,'gate':gate});ep=replace(ep,events=e)
  rates=m.kernel.rates;logits=m.kernel.rate_source.logits;q=torch.sigmoid(logits).detach().double();span=float(torch.tensor(m.kernel.rate_source.log_max-m.kernel.rate_source.log_min,dtype=torch.float64));jac=rates.detach().double()*span*q*(1-q)
  r64=rates.detach().double().requires_grad_();k64=key.detach().double().requires_grad_();v64=value.detach().double().requires_grad_();g64=gate.detach().double().requires_grad_()
  ref=direct(e,r64,k64,v64,g64);state=m.encode(e,mode='terminal');actual={k:state.payload[k] for k in ref};metrics=[metric('terminal_'+k,actual[k],ref[k]) for k in ref]
  actual_grad=torch.autograd.grad(objective(actual),(logits,key,value,gate),retain_graph=True)
  ref_grad=torch.autograd.grad(objective(ref),(r64,k64,v64,g64),retain_graph=True);ref_grad=(ref_grad[0]*jac,*ref_grad[1:])
  for name,a,b in zip(('logits','key','value','gate'),actual_grad,ref_grad):metrics.append(metric('memory_gradient_'+name,a,b))
  with torch.no_grad():stream=m.encode(e,mode='stream')
  for k in ref:metrics.append(metric('stream_'+k,stream.payload[k],ref[k]))
  # Independent event sum versus CPU64 production recurrence also checks the
  # reference's state convention, without allowing FP32 rounding into the oracle.
  kernel64=(JetMemory if args.family=='jet' else ExpBankMemory)(r64.detach(),16,8,chunk_size=32)
  e64=replace(e,key_features=k64.detach(),values=v64.detach(),auxiliary={'gate':g64.detach()})
  with torch.no_grad():state64=kernel64.encode(e64,mode='terminal')
  for k in ref:metrics.append(metric('cpu64_terminal_'+k,state64.payload[k],ref[k],rtol=1e-12,atol=1e-12))
  assert bool((ep.queries.T==e.timestamps[0,int(e.lengths[0])-1]).all())
  qkey=ep.queries.key_features[0].double();cz=torch.einsum('qk,jkv->qjv',qkey,ref['z'][0,0]);parts=[cz[...,:-1]]
  if 'h' in ref:
   ch=torch.einsum('qk,jkv->qjv',qkey,ref['h'][0,0]);parts.append(ch[...,:-1])
  parts.append(cz[...,-1:])
  if 'h' in ref:parts.append(ch[...,-1:])
  ref_features=torch.cat((torch.cat(parts,-1).flatten(1)[None],query_inputs(ep.queries,m.kernel.t_ref).double()),-1)
  features=m.features(state,ep.queries)
  with torch.no_grad():stream_features=m.features(stream,ep.queries)
  metrics.extend((metric('terminal_raw_features',features.values,ref_features),metric('stream_raw_features',stream_features.values,ref_features)))
  tensors={'terminal':actual,'stream':{k:stream.payload[k] for k in ref},'reference':ref,'memory_gradient_actual':actual_grad,'memory_gradient_reference':ref_grad,'features':features.values,'reference_features':ref_features}
  if args.checkpoint:
   reference_model=copy.deepcopy(m).double();reference_features=FeatureBatch(ref_features,features.supported,{'failure':torch.zeros_like(features.supported)})
   prediction=m.read_features(features,ep.queries);reference_prediction=reference_model.read_features(reference_features,ep.queries)
   loss=history_loss(m,prediction,ep);ref_loss=history_loss(reference_model,reference_prediction,ep)
   metrics.extend((metric('task_prediction',prediction.prediction,reference_prediction.prediction),metric('task_loss',loss,ref_loss)))
   named=list(m.reader.named_parameters());ref_named=list(reference_model.reader.named_parameters());assert [n for n,_ in named]==[n for n,_ in ref_named]
   ga=torch.autograd.grad(loss,(logits,key,value,gate,*[p for _,p in named]),allow_unused=True)
   gr=torch.autograd.grad(ref_loss,(r64,k64,v64,g64,*[p for _,p in ref_named]),allow_unused=True);gr=(gr[0]*jac,*gr[1:])
   for name,a,b in zip(('logits','key','value','gate'),ga[:4],gr[:4]):metrics.append(metric('task_gradient_'+name,a,b))
   for (name,_),a,b in zip(named,ga[4:],gr[4:]):metrics.append(metric('reader_gradient_'+name,a,b))
   tensors.update(task_gradient_actual=ga,task_gradient_reference=gr,prediction=prediction.prediction,reference_prediction=reference_prediction.prediction)
  tensor_path=out/f'case-{i:02d}.pt';torch.save(detached(tensors),tensor_path)
  record={'ordinal':i,'history_id':history_id,'length':int(e.lengths[0]),'regime':original.metadata['regime'],'raw_hashes':original.metadata['hashes'],'candidate_events_hash':batch_hash(e),'accepted':all(x['accepted'] for x in metrics),'metrics':metrics,'seconds':time.perf_counter()-tick,'rss_additional_bytes':memory(),'tensors':str(tensor_path),'tensors_sha256':hashlib.sha256(tensor_path.read_bytes()).hexdigest()}
  records.append(record);append_jsonl(out/'cases.jsonl',record);check_smoke_memory(c,memory())
  del state,stream,state64,kernel64,ref,actual,actual_grad,ref_grad,features,stream_features,ref_features,tensors,ep,e,key,value,gate,r64,k64,v64,g64
  if args.checkpoint:del reference_model,reference_features,prediction,reference_prediction,loss,ref_loss,ga,gr,named,ref_named
  gc.collect()
 summary={'status':'passed' if all(r['accepted'] for r in records) else 'failed_original_tolerance','family':args.family,'procedure_hash':canonical_hash(procedure),'source':source,'checkpoint_sha256':checkpoint_hash,'cases':len(records),'failures':[{'history_id':r['history_id'],'metrics':[x for x in r['metrics'] if not x['accepted']]} for r in records if not r['accepted']],'max_pointwise_ratio':max(x.get('max_pointwise_ratio',0) for r in records for x in r['metrics']),'total_seconds':time.perf_counter()-started,'rss_additional_bytes':memory(),'rates':procedure['rates'],'logits':procedure['logits'],'reader_validation':bool(args.checkpoint),'claim':'bounded_numerical_applicability_only_not_accuracy_or_convergence'}
 atomic_json(out/'summary.json',summary);print(json.dumps(summary),flush=True)
except BaseException as exc:
 atomic_json(out/'failure.json',{'type':type(exc).__name__,'error':str(exc),'completed_cases':len(records),'seconds':time.perf_counter()-started,'rss_additional_bytes':memory(),'source':source});raise
