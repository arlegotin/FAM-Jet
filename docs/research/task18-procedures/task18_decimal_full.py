from pathlib import Path
from dataclasses import replace
from decimal import Decimal,localcontext
import argparse,hashlib,json,time,resource,platform,math
import torch
from famjet.config import load_config
from famjet.analysis.development import draw_config
from famjet.data.synthetic import generate_episode
from famjet.train import move_episode,_source,check_smoke_memory
from famjet.artifacts import atomic_json
from famjet.eval.splits import _write_immutable
from famjet.readers.structured import query_inputs
P=argparse.ArgumentParser();P.add_argument('family',choices=['jet','bank']);P.add_argument('ordinal',type=int);args=P.parse_args()
torch.set_num_threads(4);out=Path('artifacts/task18/learned-rate-cpu64-decimal-full');out.mkdir(exist_ok=True);case=out/f'{args.family}-{args.ordinal:02d}';case.mkdir(exist_ok=False)
started=time.perf_counter();factor=1 if platform.system()=='Darwin' else 1024;base=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*factor
D=lambda x:Decimal.from_float(float(x));ZERO=Decimal(0);ONE=Decimal(1)
ALPHA=D(float(torch.tensor(.03)));BETA=D(float(torch.tensor(.07)))
def oracle(rates,keys,values,gates,ages,mask,jet,alpha=ALPHA,beta=BETA):
 n=len(keys);K=len(keys[0]);V=len(values[0]);J=len(rates)
 rr=list(map(D,rates));kk=[[D(x) for x in row] for row in keys];vv=[[D(x) for x in row]+[ONE] for row in values];gg=list(map(D,gates));aa=list(map(D,ages))
 active=[[k for k,x in enumerate(row) if x] for row in kk]
 ds=[[r*age for age in aa] for r in rr];ww=[[(-d).exp() for d in row] for row in ds]
 z=[[[ZERO for v in range(V+1)] for k in range(K)] for j in range(J)];h=[[[ZERO for v in range(V+1)] for k in range(K)] for j in range(J)];m2=[[[ZERO for v in range(V+1)] for k in range(K)] for j in range(J)]
 for j in range(J):
  for i in range(n):
   if not mask[i]:continue
   d=ds[j][i];weight=ww[j][i]*gg[i]
   for k in active[i]:
    w=weight*kk[i][k]
    for v in range(V+1):
     term=w*vv[i][v];z[j][k][v]+=term;h[j][k][v]+=d*term;m2[j][k][v]+=d*d*term
 A=[[[2*alpha*x for x in row] for row in plane] for plane in z]
 B=[[[2*beta*x if jet else ZERO for x in row] for row in plane] for plane in h]
 gr=[]
 for j in range(J):
  gr.append(sum((-A[j][k][v]*h[j][k][v]+B[j][k][v]*(h[j][k][v]-m2[j][k][v]))/rr[j] for k in range(K) for v in range(V+1)))
 gk=[[ZERO]*K for i in range(n)];gv=[[ZERO]*V for i in range(n)];ggate=[ZERO]*n
 for i in range(n):
  if not mask[i]:continue
  for k in range(K):
   # Write partials are shared by the three direct input derivatives.
   G=[sum(ww[j][i]*(A[j][k][v]+ds[j][i]*B[j][k][v]) for j in range(J)) for v in range(V+1)]
   dot=sum(x*y for x,y in zip(G,vv[i]));gk[i][k]=gg[i]*dot
   if kk[i][k]:
    ggate[i]+=kk[i][k]*dot
    for v in range(V):gv[i][v]+=gg[i]*kk[i][k]*G[v]
 return {'z':z,**({'h':h} if jet else {}),'gradient_rates':gr,'gradient_key':gk,'gradient_value':gv,'gradient_gate':ggate}
def flatten(x):
 if isinstance(x,list):return [v for item in x for v in flatten(item)]
 return [x]
def tensor(x):return torch.tensor([float(v) for v in flatten(x)],dtype=torch.float64)
def compare(name,candidate,reference):
 a=candidate.detach().double().flatten();b=tensor(reference);assert a.shape==b.shape
 diff=(a-b).abs();ratio=diff/(1e-12+1e-12*b.abs());idx=int(ratio.argmax());return {'name':name,'accepted':bool(torch.isfinite(a).all() and torch.isfinite(b).all() and (ratio<=1).all()),'max_pointwise_ratio':float(ratio.max()),'violating_elements':int((ratio>1).sum()),'max_absolute_error':float(diff.max()),'error_norm':float(torch.linalg.vector_norm(a-b)),'reference_norm':float(torch.linalg.vector_norm(b)),'worst_flat_index':idx,'worst_candidate':float(a[idx]),'worst_reference':str(flatten(reference)[idx]),'rtol':1e-12,'atol':1e-12}
def controls():
 with localcontext() as ctx:
  ctx.prec=80
  one=oracle([1],[[1]],[[2]],[1],[0],[True],True)
  expected={'z':[[[D(2),ONE]]],'h':[[[ZERO,ZERO]]],'gradient_rates':[ZERO],'gradient_key':[[10*ALPHA]],'gradient_value':[[4*ALPHA]],'gradient_gate':[10*ALPHA]}
  assert one==expected
  decay=oracle([1],[[1]],[[0]],[1],[1],[True],True);w=(-ONE).exp();tol=Decimal('1e-70')
  expected2={'z':[[[ZERO,w]]],'h':[[[ZERO,w]]],'gradient_rates':[-2*ALPHA*w*w],'gradient_key':[[2*(ALPHA+BETA)*w*w]],'gradient_value':[[ZERO]],'gradient_gate':[2*(ALPHA+BETA)*w*w]}
  assert all(abs(a-b)<tol for key in decay for a,b in zip(flatten(decay[key]),flatten(expected2[key])))
 return {'one_impulse':'exact equality','decayed_impulse':'analytic e^-1 signs/moment/gradient within1e-70','digits':80}
control=controls();root=Path(f'artifacts/task18/learned-rate-cpu64-numerics-initial-{args.family}');old=json.loads((root/'summary.json').read_text());procedure=json.loads((root/'procedure.json').read_text());prior=torch.load(root/f'case-{args.ordinal:02d}.pt',weights_only=True)
c=load_config(Path(f'configs/development/{args.family}_finite_raw_32768.yaml'));dc,hid=draw_config(c,args.ordinal);ep=move_episode(generate_episode(dc,c.development.data_seed,hid),'cpu',dtype=torch.float64);e=ep.events;n=int(e.lengths[0]);ages=(e.timestamps[0,n-1]-e.timestamps[0,:n]).tolist();mask=(e.present[0]&e.observed[0].all(-1)).tolist();rates=old['rates'][0];logits=torch.tensor(old['logits'],dtype=torch.float64);q=torch.sigmoid(logits)[0].tolist();span=math.log(1.)-math.log(1/5224)
_write_immutable(case/'procedure.json',{'source':_source(),'helper_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'original_procedure_hash':old['procedure_hash'],'original_candidate_file_sha256':hashlib.sha256((root/f'case-{args.ordinal:02d}.pt').read_bytes()).hexdigest(),'family':args.family,'ordinal':args.ordinal,'history_id':hid,'raw_hashes':ep.metadata['hashes'],'digits':[60,80],'probe_coefficients':{'z':str(ALPHA),'h':str(BETA)},'logit_chain':'exact represented rate * represented double log-span * represented sigmoid * (1 - represented sigmoid)','sigmoid':q,'span':span,'controls':control,'net_limit_bytes':201326592,'scope':'uniform full initial numerical reference, unchanged candidate/tolerance','protected':'closed'})
results=[];durations=[]
for digits in (60,80):
 tick=time.perf_counter()
 with localcontext() as ctx:
  ctx.prec=digits;result=oracle(rates,e.key_features[0].tolist(),e.values[0].tolist(),[1]*n,ages,mask,args.family=='jet')
  result['gradient_logits']=[g*D(r)*D(span)*D(s)*(ONE-D(s)) for g,r,s in zip(result['gradient_rates'],rates,q)]
  raw=[]
  for querykey in ep.queries.key_features[0].tolist():
   row=[]
   for j in range(len(rates)):
    cz=[sum(D(querykey[k])*result['z'][j][k][v] for k in range(16)) for v in range(9)]
    ch=[sum(D(querykey[k])*result['h'][j][k][v] for k in range(16)) for v in range(9)] if args.family=='jet' else None
    row.extend(cz[:-1]);row.extend(ch[:-1] if ch is not None else []);row.append(cz[-1]);row.extend([ch[-1]] if ch is not None else [])
   raw.append(row)
  qinputs=query_inputs(ep.queries,1.)[0].tolist();result['raw_features']=[row+list(map(D,qi)) for row,qi in zip(raw,qinputs)]
 results.append(result);durations.append(time.perf_counter()-tick)
 peak=max(0,resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*factor-base);check_smoke_memory(c,peak)
convergence={}
with localcontext() as ctx:
 ctx.prec=80
 for name in results[0]:
  deltas=[abs(a-b) for a,b in zip(flatten(results[0][name]),flatten(results[1][name]))];maximum=max(deltas);assert maximum<Decimal('1e-45');convergence[name]={'max_absolute60vs80':str(maximum),'elements':len(deltas)}
ref=results[1];metrics=[]
for name in ('z','h') if args.family=='jet' else ('z',):
 for mode in ('terminal','stream'):metrics.append(compare(mode+'_'+name,prior[mode][name],ref[name]))
for i,name in enumerate(('logits','key','value','gate')):metrics.append(compare('memory_gradient_'+name,prior['memory_gradient_actual'][i],ref['gradient_'+name]))
metrics.append(compare('terminal_raw_features',prior['features'],ref['raw_features']))
# Initial evidence stores stream states and references, so contract its actual
# state using the same nonnegative query keys without rerunning the candidate.
streamraw=[]
for querykey in ep.queries.key_features[0]:
 z=torch.einsum('k,jkv->jv',querykey,prior['stream']['z'][0,0]);h=torch.einsum('k,jkv->jv',querykey,prior['stream']['h'][0,0]) if args.family=='jet' else None
 parts=[z[:,:-1]]+([h[:,:-1]] if h is not None else [])+[z[:,-1:]]+([h[:,-1:]] if h is not None else [])
 streamraw.append(torch.cat(parts,-1).flatten())
streamfeatures=torch.cat((torch.stack(streamraw),query_inputs(ep.queries,1.)[0]),-1);metrics.append(compare('stream_raw_features',streamfeatures,ref['raw_features']))
reference_metrics=[]
for name in ('z','h') if args.family=='jet' else ('z',):reference_metrics.append(compare('original_reference_'+name,prior['reference'][name],ref[name]))
for i,name in enumerate(('logits','key','value','gate')):reference_metrics.append(compare('original_reference_gradient_'+name,prior['memory_gradient_reference'][i],ref['gradient_'+name]))
wire={name:[str(x) for x in flatten(value)] for name,value in ref.items()};atomic_json(case/'reference80.json',wire);torch.save({name:tensor(value) for name,value in ref.items()},case/'reference80.pt')
record={'source':_source(),'family':args.family,'ordinal':args.ordinal,'history_id':hid,'length':n,'controls':control,'status':'passed' if all(m['accepted'] for m in metrics) else 'failed_original_tolerance','metrics':metrics,'original_reference_metrics':reference_metrics,'convergence':convergence,'precision_seconds':durations,'total_seconds':time.perf_counter()-started,'rss_additional_bytes':max(0,resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*factor-base),'reference_file_sha256':hashlib.sha256((case/'reference80.json').read_bytes()).hexdigest(),'candidate_file_sha256':hashlib.sha256((root/f'case-{args.ordinal:02d}.pt').read_bytes()).hexdigest()};atomic_json(case/'summary.json',record);print(json.dumps({k:v for k,v in record.items() if k not in ('metrics','original_reference_metrics','convergence')}));print(json.dumps([m for m in metrics if not m['accepted']]))
