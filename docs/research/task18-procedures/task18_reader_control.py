from pathlib import Path
from dataclasses import replace
from datetime import datetime,timezone
import argparse,json,time,hashlib,resource,platform,math
import numpy as np
import torch
from famjet.types import EventBatch,QueryBatch,Episode,FeatureBatch
from famjet.config import load_config
from famjet.train import make_model,history_loss,identities,_source,check_smoke_memory
from famjet.analysis.development import resolve_policy
from famjet.checkpoint import load_checkpoint
from famjet.train import _reconstruct
from famjet.eval.oracle import exact_targets
from famjet.artifacts import atomic_json,append_jsonl
from famjet.eval.splits import _write_immutable
from famjet.provenance import canonical_hash
from famjet.data.synthetic import batch_hash,batch_hash_tensor
P=argparse.ArgumentParser();P.add_argument('family',choices=['jet','bank']);a=P.parse_args();family=a.family
out=Path(f'artifacts/task18/reader-sufficiency-{family}');out.mkdir(exist_ok=False)
start=time.perf_counter();utc=datetime.now(timezone.utc);torch.set_num_threads(4);factor=1 if platform.system()=='Darwin' else 1024;base=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*factor
c=load_config(Path(f'configs/development/{family}_learned_cpu64_raw_32768.yaml'));source=_source();ckpath=Path(f'artifacts/task18/learning-{family}-cpu64-8192/training/checkpoint.pt');ckhash=hashlib.sha256(ckpath.read_bytes()).hexdigest();ns='task18-reader-sufficiency-v1'
def seed(split,i):return int.from_bytes(hashlib.sha256(f'{ns}/{split}/{i:012d}'.encode()).digest()[:8],'big')
def mem():return max(0,resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*factor-base)
def guard():check_smoke_memory(c,mem())
procedure={'source':source,'helper_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'checkpoint_sha256':ckhash,'checkpoint_step':8192,'root_approval':'2026-10-17 known-sufficient reader control; sentinel corrected prospectively to timestamp1','namespace':ns,'train_histories':1024,'heldout_histories':256,'timestamps':[1,2,3],'T':3,'query_slices':['older_mean[1,2)','recent_mean[0,1)','contrast[0,1)_minus_[1,2)'],'query_keys':'ordinal modulo16; sentinel next key modulo16','values':'independent standard normal8D from per-split/ordinal SHA256 seed; FP32 presentation thenFP64','rates':'actual saved8192 rates frozen; fresh production reader','feature_transport':'external only because all upstream frozen; training-only control stats, no benchmark replacement','training':{'updates':4096,'batch':32,'lr':.001,'weight_decay':0,'milestones':[0,128,512,1024,2048,4096],'order':'128 independently shuffled passes over1024 histories; shared across families'},'criterion':'both train/heldout all mean+contrast task/coordinate MSE <= .01 times training-only coordinate prior MSE; zero failures','analytic_and_transport_tolerance':{'rtol':1e-12,'atol':1e-12},'net_cap_bytes':201326592,'power_override':False,'start_utc':utc.isoformat(),'forecast_execution_seconds_pair':[60,180]}
_write_immutable(out/'procedure.json',procedure)
def fixture(split,n):
 ids=tuple(f'{ns}-{split}-{i:012d}' for i in range(n));v=np.stack([np.random.default_rng(seed(split,i)).standard_normal((2,8)).astype(np.float32) for i in range(n)])
 values=torch.zeros(n,3,8,dtype=torch.float64);values[:,1:]=torch.from_numpy(v).double();keys=torch.arange(n)%16;eventkeys=torch.stack(((keys+1)%16,keys,keys),1)
 e=EventBatch(ids,torch.arange(3).expand(n,-1).clone(),torch.tensor([1.,2.,3.],dtype=torch.float64).expand(n,-1).clone(),eventkeys,torch.nn.functional.one_hot(eventkeys,16).double(),values,torch.full((n,),3,dtype=torch.long),torch.ones(n,3,dtype=torch.bool),torch.ones(n,3,8,dtype=torch.bool),'seconds')
 q=QueryBatch(ids,torch.arange(3).expand(n,-1).clone(),torch.full((n,3),3.,dtype=torch.float64),keys[:,None].expand(-1,3).clone(),torch.nn.functional.one_hot(keys,16).double()[:,None].expand(-1,3,-1).clone(),tuple(('mean','mean','contrast') for _ in ids),torch.tensor([1.,0.,0.],dtype=torch.float64).expand(n,-1).clone(),torch.tensor([2.,1.,1.],dtype=torch.float64).expand(n,-1).clone(),torch.ones(n,3,dtype=torch.bool),torch.full((n,),3,dtype=torch.long))
 truth=exact_targets(e,q);assert truth.supported.all() and not truth.failure.any()
 return Episode(e,q,truth.target.float(),truth.supported,{'split':'training' if split=='train' else 'development','namespace':ns}),truth.target

def subset(ep,idx):
 ids=tuple(ep.events.history_ids[i] for i in idx.tolist());e=ep.events;q=ep.queries
 ee=replace(e,history_ids=ids,event_ids=e.event_ids[idx],timestamps=e.timestamps[idx],key_ids=e.key_ids[idx],key_features=e.key_features[idx],values=e.values[idx],lengths=e.lengths[idx],present=e.present[idx],observed=e.observed[idx])
 qq=replace(q,history_ids=ids,query_ids=q.query_ids[idx],T=q.T[idx],key_ids=q.key_ids[idx],key_features=q.key_features[idx],tasks=tuple(q.tasks[i] for i in idx.tolist()),age_start=q.age_start[idx],age_end=q.age_end[idx],present=q.present[idx],lengths=q.lengths[idx])
 return replace(ep,events=ee,queries=qq,labels=ep.labels[idx],supported=ep.supported[idx])
def fsubset(f,idx):return FeatureBatch(f.values[idx],f.supported[idx],{k:v[idx] for k,v in f.diagnostics.items()})
def metric(candidate,reference):
 ratio=(candidate-reference).abs()/(1e-12+1e-12*reference.abs());return {'max_ratio':float(ratio.max()),'accepted':bool(torch.isfinite(ratio).all() and (ratio<=1).all()),'max_absolute':float((candidate-reference).abs().max())}
def analytic(model,ep,truth):
 with torch.no_grad():
  s=model.encode(ep.events,mode='terminal');keys=ep.queries.key_ids[:,0];ix=torch.arange(len(keys));rates=model.kernel.rates[0];z=s.payload['z']
  if family=='jet':
   rate=rates[-1];Z=z[ix,0,-1,keys,:8];H=s.payload['h'][ix,0,-1,keys,:8];old=H/(rate*torch.exp(-rate));new=Z-H/rate
  else:
   low,high=rates[0],rates[-1];Z0=z[ix,0,0,keys,:8];Z1=z[ix,0,-1,keys,:8];aa,bb=torch.exp(-low),torch.exp(-high);old=(Z0-Z1)/(aa-bb);new=Z0-aa*old
  recovered=torch.stack((old,new,new-old),1);return metric(recovered,truth),s
try:
 identity,_=identities(c,resolve_policy(c));ck=load_checkpoint(ckpath,{**identity,'source':source});assert ck['completed_step']==8192
 saved=_reconstruct(ck['model']);torch.manual_seed(c.seed);model=make_model(c,resolve_policy(c));model.kernel.load_state_dict(saved.kernel.state_dict());model.kernel.t_ref=saved.kernel.t_ref;del saved
 for p in model.kernel.parameters():p.requires_grad_(False)
 assert model.writer is None and model.query_map is None and all(n.startswith('reader.') or not p.requires_grad for n,p in model.named_parameters());upstream=model._parameter_hash();guard()
 tiny,truth=fixture('fixture-check',8);test,state=analytic(model,tiny,truth);atomic_json(out/'analytic-tiny.json',test);assert test['accepted'];del state
 tick=time.perf_counter();train,traintruth=fixture('train',1024);held,heldtruth=fixture('heldout',256);assert set(train.events.history_ids).isdisjoint(held.events.history_ids);assert len({seed(s,i) for s,n in [('train',1024),('heldout',256)] for i in range(n)})==1280;guard()
 fixture_identity={name:{'events':batch_hash(ep.events),'queries':batch_hash(ep.queries),'labels':batch_hash_tensor(ep.labels),'exact_labels':batch_hash_tensor(truth)} for name,ep,truth in [('train',train,traintruth),('heldout',held,heldtruth)]};atomic_json(out/'fixture-identity.json',fixture_identity)
 fullanalytic={}
 for name,ep,truth in [('train',train,traintruth),('heldout',held,heldtruth)]:
  fullanalytic[name],state=analytic(model,ep,truth);assert fullanalytic[name]['accepted'];del state;guard()
 atomic_json(out/'analytic.json',fullanalytic)
 model.fit_statistics([train]);assert model.kernel.t_ref==1 and model.fit_provenance['history_count']==1024
 with torch.no_grad():features={name:model.features(model.encode(ep.events,mode='terminal'),ep.queries) for name,ep in [('train',train),('heldout',held)]}
 assert upstream==model._parameter_hash();guard();prep=time.perf_counter()-tick
 payload={'features':features,'train':train,'heldout':held,'fixture_identity':fixture_identity,'fit_provenance':model.fit_provenance,'target_statistics':model.target_statistics,'upstream_hash':upstream,'rates':model.kernel.rates.detach().tolist(),'source':source};torch.save(payload,out/'external-features.pt');transport_sha=hashlib.sha256((out/'external-features.pt').read_bytes()).hexdigest()
 idx=torch.arange(4);small=subset(train,idx);direct=model.read(model.encode(small.events,mode='terminal'),small.queries);loss1=history_loss(model,direct,small);params=list(model.reader.parameters());grads1=torch.autograd.grad(loss1,params,allow_unused=True);cached=model.read_features(fsubset(features['train'],idx),small.queries);loss2=history_loss(model,cached,small);grads2=torch.autograd.grad(loss2,params,allow_unused=True);checks={'prediction':metric(cached.prediction,direct.prediction),'loss':metric(loss2,loss1),'reader_gradients':[metric(x,y) if x is not None and y is not None else {'accepted':x is None and y is None,'both_inactive':x is None and y is None} for x,y in zip(grads2,grads1)]};atomic_json(out/'transport-check.json',checks);assert all(v['accepted'] for k,v in checks.items() if k!='reader_gradients') and all(v['accepted'] for v in checks['reader_gradients']);del direct,cached,grads1,grads2,loss1,loss2
 order=np.stack([np.random.default_rng(seed('order',i)).permutation(1024).reshape(32,32) for i in range(128)]).reshape(4096,32);np.save(out/'order.npy',order);orderhash=hashlib.sha256((out/'order.npy').read_bytes()).hexdigest()
 prior={};
 for task,cols in [('mean',[0,1]),('contrast',[2])]:
  y=train.labels[:,cols].double().reshape(-1,8);prior[task]=((y-y.mean(0)).square().mean(0));assert bool((prior[task]>0).all())
 optimizer=torch.optim.AdamW(params,lr=.001,weight_decay=0.);milestones=procedure['training']['milestones'];curve=[];updates=[]
 def evaluate(step):
  result={'step':step,'splits':{}}
  model.eval()
  with torch.no_grad():
   for name,ep in [('train',train),('heldout',held)]:
    prediction=model.read_features(features[name],ep.queries);res=(prediction.prediction-ep.labels.double()).square();tasks={task:{'mse_per_coordinate':res[:,cols].mean((0,1)).tolist(),'relative_to_training_prior':(res[:,cols].mean((0,1))/prior[task]).tolist()} for task,cols in [('mean',[0,1]),('contrast',[2])]};slices={label:res[:,i].mean(0).tolist() for i,label in enumerate(('older_mean','recent_mean','contrast'))};fail=int(prediction.failure.sum());invalid=int((~prediction.diagnostics['prediction_valid']).sum());result['splits'][name]={'tasks':tasks,'slice_mse_per_coordinate':slices,'objective':float(history_loss(model,prediction,ep)),'failure_queries':fail,'invalid_queries':invalid,'competent':not(fail or invalid) and all(max(x['relative_to_training_prior'])<=.01 for x in tasks.values())}
  model.train();append_jsonl(out/'curve.jsonl',result);curve.append(result);guard();return result
 evaluate(0);training_start=time.perf_counter()
 for step,row in enumerate(order,1):
  tick=time.perf_counter();idx=torch.from_numpy(row);ep=subset(train,idx);f=fsubset(features['train'],idx);optimizer.zero_grad(set_to_none=True);prediction=model.read_features(f,ep.queries);loss=history_loss(model,prediction,ep);loss.backward();norm=torch.linalg.vector_norm(torch.stack([p.grad.norm() for p in params if p.grad is not None]));optimizer.step();elapsed=time.perf_counter()-tick;updates.append(elapsed);append_jsonl(out/'training.jsonl',{'step':step,'loss':float(loss.detach()),'gradient_norm':float(norm),'seconds':elapsed,'order_row':step-1});guard()
  if step in milestones:
   evaluate(step)
   if step==128:
    record={'step':128,'preparation_seconds':prep,'update_seconds':sum(updates),'median_update_seconds':float(np.median(updates)),'projected4096_update_seconds':sum(updates)*32,'elapsed_perf_counter_seconds':time.perf_counter()-start,'rss_additional_bytes':mem()};atomic_json(out/'first128-profile.json',record);print(json.dumps(record),flush=True)
 assert upstream==model._parameter_hash() and source==_source();assert all(p.grad is None for p in model.kernel.parameters());torch.save({'reader_state':model.reader.state_dict(),'optimizer':optimizer.state_dict(),'step':4096,'source':source,'procedure_hash':canonical_hash(procedure),'rates':model.kernel.rates.detach(),'upstream_hash':upstream,'fit_provenance':model.fit_provenance,'target_statistics':model.target_statistics,'order_sha256':orderhash},out/'diagnostic-final.pt')
 end=datetime.now(timezone.utc);summary={'status':'competent' if all(v['competent'] for v in curve[-1]['splits'].values()) else 'criterion_not_met','family':family,'source':source,'checkpoint_sha256':ckhash,'procedure_hash':canonical_hash(procedure),'fixture_identity':fixture_identity,'train_prior_mse':{k:v.tolist() for k,v in prior.items()},'fit_provenance':model.fit_provenance,'target_statistics':model.target_statistics,'final':curve[-1],'rates':model.kernel.rates.detach().tolist(),'feature_bytes':sum(f.values.numel()*f.values.element_size() for f in features.values()),'external_transport_file_bytes':(out/'external-features.pt').stat().st_size,'external_transport_sha256':transport_sha,'order_sha256':orderhash,'preparation_seconds':prep,'training_and_observer_seconds':time.perf_counter()-training_start,'update_seconds':sum(updates),'start_utc':utc.isoformat(),'end_utc':end.isoformat(),'utc_interval_seconds':(end-utc).total_seconds(),'perf_counter_seconds':time.perf_counter()-start,'rss_additional_bytes':mem(),'scope':'reader competence on known-sufficient fixture only; no hard-window convergence/information-ceiling or headline gain claim'};atomic_json(out/'summary.json',summary);print(json.dumps(summary),flush=True)
except BaseException as exc:
 atomic_json(out/'failure.json',{'type':type(exc).__name__,'message':str(exc),'source':source,'seconds':time.perf_counter()-start,'rss_additional_bytes':mem(),'end_utc':datetime.now(timezone.utc).isoformat()});raise
