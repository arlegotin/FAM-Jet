"""Saved fitted8192 checkpoint composition; no streaming/Decimal/refit replay."""
from pathlib import Path
from datetime import datetime,timezone
from dataclasses import replace
import argparse,copy,hashlib,json,platform,resource,time
import numpy as np
from numpy.polynomial.legendre import leggauss,legvander
from scipy.linalg import expm
import torch
from task18_structured_fixed_numeric import config,metric,PACKAGE,ORIGIN,ORIGIN_PACKAGE,reference_structured,sha
EXPECTED='14956dc26e882ad04ff92547e0980b9ef856151f'
from famjet.train import make_model,move_episode,_source,history_loss,check_smoke_memory,identities,_reconstruct
from famjet.checkpoint import load_checkpoint
from famjet.config import load_config
from famjet.analysis.development import resolve_policy,parameter_accounting
from famjet.provenance import canonical_hash
from famjet.eval.budgets import model_ledger
from famjet.analysis.development import draw_config
from famjet.data.synthetic import generate_episode,batch_hash
from famjet.eval.isolation import export_method
from famjet.eval.splits import _write_immutable
from famjet.artifacts import atomic_json
from famjet.types import FeatureBatch
from famjet.readers.structured import query_inputs
p=argparse.ArgumentParser();p.add_argument('family',choices=['jet','bank']);p.add_argument('ordinal',type=int);p.add_argument('out');p.add_argument('--step',type=int,choices=[8192],required=True);args=p.parse_args();assert args.family=='jet' and args.ordinal==10 and args.step==8192
source=_source();assert source['commit']==EXPECTED and source['package_hash']==PACKAGE and not source['diff'] and not source['untracked_package_files'];torch.set_num_threads(4)
root=Path(f'artifacts/task18/fixed-basis-initial/{args.family}-{args.ordinal:02d}');old=json.loads((root/'summary.json').read_text());assert old['source']['commit']==ORIGIN and old['source']['package_hash']==ORIGIN_PACKAGE
newroot=Path(f'artifacts/task18/structured-fixed-initial/{args.family}-{args.ordinal:02d}');newsummary=json.loads((newroot/'summary.json').read_text());assert newsummary['source']['commit']=='7e0a798e8170583223bea1a49878f8569f65e8dd' and newsummary['source']['package_hash']==source['package_hash'] and not newsummary['source']['diff'] and newsummary['status']=='passed' and newsummary['origin_summary_sha256']==sha(root/'summary.json')
assert sha(newroot/'new-structured-capture.pt')==newsummary['capture_sha256'];newcapture=torch.load(newroot/'new-structured-capture.pt',weights_only=True)
out=Path(args.out);out.mkdir(parents=True,exist_ok=False);start=time.perf_counter();utc=datetime.now(timezone.utc);factor=1 if platform.system()=='Darwin' else 1024;base=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*factor
configpath=Path(f'configs/development/{args.family}_fixed_cpu64_structured_32768.yaml');c=load_config(configpath);identity,_=identities(c,resolve_policy(c));checkpoint=Path(f'artifacts/task18/learning-{args.family}-fixed-cpu64-structured-8192/training/checkpoint.pt'+('.previous' if args.step==0 else ''));ck=load_checkpoint(checkpoint,{**identity,'source':source});assert ck['completed_step']==args.step
m=_reconstruct(ck['model']).eval();assert canonical_hash(m.target_statistics)=='0cebf5f59f3b44f44875b73d582e6cb3c21a0ade54867edfabaebcab220dad21' and m.fit_provenance['history_count']==768 and m.kernel.t_ref==1.
assert all(x.dtype==torch.float64 for x in m.state_dict().values() if x.is_floating_point());assert m.persistent_nbytes(m.init_state(1,device='cpu',dtype='float64'))==9345
for st in ck['optimizer']['state'].values():assert st['exp_avg'].dtype==st['exp_avg_sq'].dtype==torch.float64 and st['step'].dtype==torch.float32
torch.manual_seed(c.seed);initial=make_model(c);assert initial._parameter_hash()==m._parameter_hash()==newsummary['fixed_kernel_hash'];del initial
exporthash=hashlib.sha256(json.dumps(export_method(m),sort_keys=True,separators=(',',':')).encode()).hexdigest()
checkpoint_record={'path':str(checkpoint),'sha256':hashlib.sha256(checkpoint.read_bytes()).hexdigest(),'step':args.step,'config_sha256':hashlib.sha256(configpath.read_bytes()).hexdigest(),'fit_provenance':m.fit_provenance,'target_hash':canonical_hash(m.target_statistics),'fixed_kernel_hash':m._parameter_hash(),'parameter_accounting':parameter_accounting(m),'ledger':model_ledger(m)};del ck
atomic_json(out/'checkpoint-verification.json',checkpoint_record)
prior=torch.load(root/'candidate.pt',weights_only=True);assert hashlib.sha256((root/'candidate.pt').read_bytes()).hexdigest()==old['candidate_sha256']
procedure={'diagnosis':'one exact saved failedcase; boundary captures and common-upstream VJP decomposition only; no reference/candidate/tolerance correction','original_failed_summary_sha256':sha('artifacts/task18/structured-fixed-endpoint8192-jet/step8192-10/summary.json'),'new_structured_initial_summary_sha256':sha(newroot/'summary.json'),'new_structured_capture_sha256':newsummary['capture_sha256'],'independent_equation_helper_sha256':sha('/tmp/task18_structured_fixed_numeric.py'),'old_memory_origin_source':old['source'],'source':source,'helper_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'common_helper_sha256':hashlib.sha256(Path('/tmp/task18_fixed_basis_numeric.py').read_bytes()).hexdigest(),'original_summary_sha256':hashlib.sha256((root/'summary.json').read_bytes()).hexdigest(),'original_candidate_sha256':old['candidate_sha256'],'fitted_model_export_sha256':exporthash,'checkpoint':checkpoint_record,'scope':'saved fitted reader task/prediction/key/value/gate/reader gradients all12cells; no stream/Decimal/refit replay; fixed kernel identity and exact terminal/direct-reference plus new structured-feature replay compose accepted old memory and new formula gates; original1e-12; common production reader/query inputs not independently certified','ordinal':args.ordinal,'family':args.family,'net_limit':201326592,'utc_start':utc.isoformat(),'power_override':False};_write_immutable(out/'procedure.json',procedure)
try:
 dc,hid=draw_config(c,args.ordinal);ep0=generate_episode(dc,c.development.data_seed,hid);assert ep0.metadata['hashes']==old['raw_hashes'];ep=move_episode(ep0,'cpu',dtype=torch.float64);e=ep.events;n=int(e.lengths[0]);ages=(e.timestamps[0,n-1]-e.timestamps[0,:n]).double();mask=e.present[0,:n]&e.observed[0,:n].all(-1)
 key=e.key_features.clone().requires_grad_();value=e.values.clone().requires_grad_();gate=torch.ones(e.present.shape,dtype=torch.float64,requires_grad=True);e=replace(e,key_features=key,values=value,auxiliary={**e.auxiliary,'gate':gate});ep=replace(ep,events=e);assert batch_hash(e)==old['events_hash']
 rk=key.detach().clone().requires_grad_();rv=value.detach().clone().requires_grad_();rg=gate.detach().clone().requires_grad_();aug=torch.cat((rv[0,:n],torch.ones(n,1,dtype=torch.float64)),-1);writes=rk[0,:n,:,None]*aug[:,None,:]*(rg[0,:n]*mask)[:,None,None]
 d=m.kernel.rates.detach()[0,:,None]*ages[None];weight=torch.exp(-d);ref={'z':torch.einsum('jn,nkv->jkv',weight,writes)[None,None]}
 if args.family=='jet':ref['h']=torch.einsum('jn,nkv->jkv',d*weight,writes)[None,None]
 state=m.encode(e,mode='terminal')
 for name in ref:assert torch.equal(state.payload[name].detach(),prior['terminal'][name]) and torch.equal(ref[name].detach(),prior['binary64_reference'][name])
 qkey=ep.queries.key_features[0];qinputs=query_inputs(ep.queries,1.)
 z=torch.einsum('qk,jkv->qjv',qkey,ref['z'][0,0]);h=torch.einsum('qk,jkv->qjv',qkey,ref['h'][0,0]) if 'h' in ref else None
 f=m.features(state,ep.queries);assert torch.equal(f.values.detach(),newcapture['new_features'])
 values,supported,failed,exact,mean_age=reference_structured(z,h,m.kernel.rates.detach()[0],c.model.epsilon,c.model.numerical_support_floor)
 rf=FeatureBatch(torch.cat((values[None],qinputs),-1),supported[None],{'failure':failed[None]});assert torch.equal(rf.values.detach(),newcapture['reference_new_features']) and torch.equal(f.supported,rf.supported) and torch.equal(f.diagnostics['failure'],rf.diagnostics['failure'])
 rm=copy.deepcopy(m);pred=m.read_features(f,ep.queries);rpred=rm.read_features(rf,ep.queries);loss=history_loss(m,pred,ep);rloss=history_loss(rm,rpred,ep)
 names,params=zip(*m.reader.named_parameters());rnames,rparams=zip(*rm.reader.named_parameters());assert names==rnames
 ga=torch.autograd.grad(loss,(key,value,gate,*params),allow_unused=True,retain_graph=True);gr=torch.autograd.grad(rloss,(rk,rv,rg,*rparams),allow_unused=True,retain_graph=True)
 old_grad_path=Path('artifacts/task18/structured-fixed-endpoint8192-jet/step8192-10/task-gradients.pt');old_grads=torch.load(old_grad_path,weights_only=True)
 for k,a,b in zip(('key','value','gate',*names),ga,gr):
  assert (a is None and old_grads['candidate'][k] is None) or torch.equal(a,old_grads['candidate'][k])
  assert (b is None and old_grads['reference'][k] is None) or torch.equal(b,old_grads['reference'][k])
 ua=torch.autograd.grad(loss,f.values,retain_graph=True)[0];ur=torch.autograd.grad(rloss,rf.values,retain_graph=True)[0]
 jc_ur=torch.autograd.grad(f.values,key,grad_outputs=ur,retain_graph=True)[0]
 jr_ua=torch.autograd.grad(rf.values,rk,grad_outputs=ua,retain_graph=True)[0]
 jc_ua=torch.autograd.grad(f.values,key,grad_outputs=ua,retain_graph=True)[0]
 jr_ur=torch.autograd.grad(rf.values,rk,grad_outputs=ur,retain_graph=True)[0]
 idx=8155;v=lambda x:float(x.detach().flatten()[idx]);query_terms=[]
 for qi in range(8):
  ca=torch.autograd.grad(f.values[:,qi],key,grad_outputs=ua[:,qi],retain_graph=True)[0]
  rr=torch.autograd.grad(rf.values[:,qi],rk,grad_outputs=ur[:,qi],retain_graph=True)[0]
  cr=torch.autograd.grad(rf.values[:,qi],rk,grad_outputs=ua[:,qi],retain_graph=True)[0]
  query_terms.append({'query':qi,'task':ep.queries.tasks[0][qi],'candidate':v(ca),'reference':v(rr),'reference_jacobian_candidate_upstream':v(cr)})
 standard=(f.values-m.reader.feature_mean)/m.reader.feature_scale;rstandard=(rf.values-rm.reader.feature_mean)/rm.reader.feature_scale
 hidden=m.reader.hidden(standard);rhidden=rm.reader.hidden(rstandard);numeric=m.reader.output(hidden);rnumeric=rm.reader.output(rhidden)
 raw_c=torch.cat([f.diagnostics['u'],f.diagnostics['h'],f.diagnostics['z'][...,None],f.diagnostics['b'][...,None]],-1).flatten(2)
 raw_r=torch.cat([z[...,:-1],h[...,:-1],z[...,-1:],h[...,-1:]],-1).flatten(1)[None]
 boundary_pairs={'raw_contractions':(raw_c,raw_r),'structured_features':(f.values,rf.values),'standardized_features':(standard,rstandard),'last_hidden':(hidden,rhidden),'numeric_logits':(numeric,rnumeric),'prediction':(pred.prediction,rpred.prediction),'loss':(loss,rloss),'feature_upstream':(ua,ur),'key_gradient':(ga[0],gr[0])}
 captures={k:{'candidate':a.detach(),'reference':b.detach()} for k,(a,b) in boundary_pairs.items()};captures['vjp']={k:x.detach() for k,x in {'Jc_Uc':jc_ua,'Jc_Ur':jc_ur,'Jr_Uc':jr_ua,'Jr_Ur':jr_ur}.items()};torch.save(captures,out/'boundary-captures.pt')
 diagnostics={'status':'original_failure_exactly_reproduced_diagnosis_only','original_gradient_capture_sha256':sha(old_grad_path),'boundaries':[metric(k,a,b) for k,(a,b) in boundary_pairs.items()],'flat_index':idx,'event_index':idx//16,'key_coordinate':idx%16,'candidate':v(ga[0]),'reference':v(gr[0]),'vjp_values':{k:v(x) for k,x in {'Jc_Uc':jc_ua,'Jc_Ur':jc_ur,'Jr_Uc':jr_ua,'Jr_Ur':jr_ur}.items()},'decomposition_using_candidate_upstream':{'jacobian_path_difference':v(jc_ua-jr_ua),'upstream_difference_on_reference_jacobian':v(jr_ua-jr_ur),'sum':v(jc_ua-jr_ur)},'query_terms':query_terms,'capture_sha256':sha(out/'boundary-captures.pt'),'no_candidate_reference_or_tolerance_change':True};atomic_json(out/'diagnosis.json',diagnostics)
 metrics=[metric('fitted_task_prediction',pred.prediction,rpred.prediction),metric('fitted_task_loss',loss,rloss)]+[metric('fitted_task_gradient_'+name,a,b) for name,a,b in zip(('key','value','gate',*names),ga,gr)]
 torch.save({'candidate':{name:a.detach() if a is not None else None for name,a in zip(('key','value','gate',*names),ga)},'reference':{name:a.detach() if a is not None else None for name,a in zip(('key','value','gate',*names),gr)}},out/'task-gradients.pt')
 peak=max(0,resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*factor-base);check_smoke_memory(c,peak);end=datetime.now(timezone.utc)
 summary={'status':'passed' if all(m['accepted'] for m in metrics) else 'failed_original_tolerance','source':source,'family':args.family,'ordinal':args.ordinal,'history_id':hid,'raw_hashes':ep0.metadata['hashes'],'metrics':metrics,'original_summary_sha256':procedure['original_summary_sha256'],'task_gradients_sha256':hashlib.sha256((out/'task-gradients.pt').read_bytes()).hexdigest(),'candidate_reference_terminal_bitwise_replay':True,'fitted_model_export_sha256':exporthash,'checkpoint':checkpoint_record,'perf_seconds':time.perf_counter()-start,'utc_start':utc.isoformat(),'utc_end':end.isoformat(),'utc_seconds':(end-utc).total_seconds(),'net_peak_bytes':peak};atomic_json(out/'summary.json',summary);print(json.dumps({k:v for k,v in summary.items() if k!='metrics'}),flush=True)
except BaseException as exc:
 atomic_json(out/'failure.json',{'source':source,'type':type(exc).__name__,'error':str(exc),'perf_seconds':time.perf_counter()-start});raise
