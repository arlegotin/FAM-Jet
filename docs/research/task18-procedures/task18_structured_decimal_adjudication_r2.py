"""ONE saved query6/key8155 forward-dual adjudication, not a replacement gate."""
from pathlib import Path
from dataclasses import replace
from datetime import datetime,timezone
from decimal import Decimal,localcontext
import hashlib,json,math,time,platform,resource
import torch
from famjet.config import load_config
from famjet.train import _source,identities,move_episode,check_smoke_memory
from famjet.analysis.development import resolve_policy
from famjet.checkpoint import load_checkpoint
from famjet.data.synthetic import batch_hash
from famjet.types import EventBatch,QueryBatch,Episode
from famjet.eval.state_io import tensor_from_record,tensor_record
from famjet.eval.splits import _write_immutable
from famjet.artifacts import atomic_json
from famjet.provenance import canonical_hash
from famjet.readers.structured import TASK_ORDER

def dec(x):return x if isinstance(x,Decimal) else Decimal.from_float(x) if isinstance(x,float) else Decimal(x)
class Dual:
 def __init__(self,v,d=0):self.v,self.d=dec(v),dec(d)
 def __add__(a,b):
  b=b if isinstance(b,Dual) else Dual(b);return Dual(a.v+b.v,a.d+b.d)
 __radd__=__add__
 def __neg__(a):return Dual(-a.v,-a.d)
 def __sub__(a,b):return a+(-b if isinstance(b,Dual) else -dec(b))
 def __rsub__(a,b):return -a+b
 def __mul__(a,b):
  b=b if isinstance(b,Dual) else Dual(b);return Dual(a.v*b.v,a.d*b.v+a.v*b.d)
 __rmul__=__mul__
 def __truediv__(a,b):
  b=b if isinstance(b,Dual) else Dual(b);return Dual(a.v/b.v,(a.d*b.v-a.v*b.d)/(b.v*b.v))
 def __rtruediv__(a,b):return Dual(b)/a
 def exp(a):
  v=a.v.exp();return Dual(v,v*a.d)
 def ln(a):return Dual(a.v.ln(),a.d/a.v)
 def silu(a):return a/(1+(-a).exp())
def pack(xs):return [{'value':str(x.v),'derivative':str(x.d)} for x in xs]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def controls(precision):
 x=Dual(0,1);z=Dual(2,1);cases=[('product',z*z,Decimal(4),Decimal(4)),('ratio',z/(z+1),Decimal(2)/3,Decimal(1)/9),('exp0',x.exp(),Decimal(1),Decimal(1)),('log1p0',(x+1).ln(),Decimal(0),Decimal(1)),('silu0',x.silu(),Decimal(0),Decimal(1)/2),('two_silu_chain0',(2*x.silu()).silu(),Decimal(0),Decimal(1)/2),('affine_squared',(3*x-1)*(3*x-1)/4,Decimal(1)/4,-Decimal(3)/2)];out=[]
 for name,y,value,gradient in cases:
  err=max(abs(y.v-value),abs(y.d-gradient));assert err<Decimal(10)**(-precision+5);out.append({'name':name,'actual':pack([y])[0],'expected_value':str(value),'expected_derivative':str(gradient),'error':str(err)})
 return out

def evaluate(precision,ep,weights,constants,epsilon,floor):
 with localcontext() as ctx:
  ctx.prec=precision;checks=controls(precision);e,q=ep.events,ep.queries;qi=6;event=509;keycoord=11;n=int(e.lengths[0]);ages=(e.timestamps[0,n-1]-e.timestamps[0,:n]).double();qkey=q.key_features[0,qi];assert float(qkey[keycoord])==1 and all(float(q.key_features[0,j,keycoord])==0 for j in range(8) if j!=qi)
  rates=weights['kernel._fixed_rates'][0].tolist();features=[];raw=[];support=[];state=[]
  for rate in rates:
   lam=dec(rate);Z=[Dual(0) for _ in range(9)];H=[Dual(0) for _ in range(9)]
   for i in range(n):
    mask=bool(e.present[0,i] and e.observed[0,i].all());k=math.fsum(float(a)*float(b) for a,b in zip(e.key_features[0,i],qkey));dk=int(i==event)*float(qkey[keycoord]);key=Dual(k,dk)
    if not mask or (k==0 and dk==0):continue
    age=dec(float(ages[i]));scaled=lam*age;w=(-scaled).exp();aug=e.values[0,i].tolist()+[1.]
    for v in range(9):
     term=key*dec(aug[v])*w;Z[v]=Z[v]+term;H[v]=H[v]+term*scaled
   mass=Z[-1];b=H[-1];den=mass+dec(epsilon);assert mass.v>=0 and den.v>0
   r=[u/den for u in Z[:8]];d=[(a*b-h)/den for a,h in zip(r,H[:8])];yes=mass.v>dec(floor);support.append(yes)
   features += r+d+[(1+mass).ln(),b/den,Dual(lam.ln()),Dual(int(yes))];raw += Z[:8]+H[:8]+[mass,b];state.append({'Z':pack(Z),'H':pack(H)})
  features += [Dual(float(x)) for x in constants];assert len(features)==105
  std=[(x-dec(float(mu)))/dec(float(sc)) for x,mu,sc in zip(features,weights['reader.feature_mean'],weights['reader.feature_scale'])]
  def linear(x,name):
   return [sum((v*dec(float(w)) for v,w in zip(x,row)),Dual(float(b))) for row,b in zip(weights[name+'.weight'],weights[name+'.bias'])]
  h1=[x.silu() for x in linear(std,'reader.hidden.0')];h2=[x.silu() for x in linear(h1,'reader.hidden.2')];numeric=linear(h2,'reader.output');support_logit=linear(h2,'reader.support');task=q.tasks[0][qi];assert task=='mean';tid=TASK_ORDER.index(task);scale=dec(float(weights['target_scale'][tid,0]));target_mean=weights['target_mean'][tid];prediction=[x*scale+dec(float(mu)) for x,mu in zip(numeric,target_mean)];labels=ep.labels[0,qi].to(torch.float32).to(torch.float64);active={t for t,yes in zip(q.tasks[0],q.present[0].tolist()) if yes};task_count=sum(t==task and yes for t,yes in zip(q.tasks[0],q.present[0].tolist()));assert task_count==4 and len(active)==2
  loss=sum((((p-dec(float(y)))/scale)*((p-dec(float(y)))/scale) for p,y in zip(prediction,labels)),Dual(0))/(8*task_count*len(active))
  return {'precision':precision,'controls':checks,'state':state,'raw':pack(raw),'features':pack(features),'standardized':pack(std),'hidden1':pack(h1),'hidden2':pack(h2),'numeric':pack(numeric),'support_logit':pack(support_logit),'prediction':pack(prediction),'query6_weighted_full_history_loss_contribution':pack([loss])[0],'support':support,'objective_weight_denominator':8*task_count*len(active),'derivative':str(loss.d)}

out=Path('artifacts/task18/structured-fixed-decimal-adjudication-r2');out.mkdir(exist_ok=False);started=time.perf_counter();utc=datetime.now(timezone.utc);factor=1 if platform.system()=='Darwin' else 1024;base=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*factor
source=_source();assert source['commit']=='14956dc26e882ad04ff92547e0980b9ef856151f' and not source['diff'] and source['package_hash']=='18785561574bfb4d246f703bc1e2caff9f7764ff0b0d8d7f641bef978f4957e0';torch.set_num_threads(4)
cfg=load_config('configs/development/jet_fixed_cpu64_structured_32768.yaml');identity,_=identities(cfg,resolve_policy(cfg));cp=Path('artifacts/task18/learning-jet-fixed-cpu64-structured-8192/training/checkpoint.pt');ck=load_checkpoint(cp,{**identity,'source':source});assert ck['completed_step']==8192;weights={k:tensor_from_record(v) for k,v in ck['model']['weights'].items()};del ck
rate_path=Path('artifacts/task18/structured-fixed-initial/jet-10/procedure.json');rate_record=json.loads(rate_path.read_text());rates=torch.tensor(rate_record['represented_rates'],dtype=torch.float64);assert canonical_hash(tensor_record(rates))==rate_record['rate_tensor_hash'];verification_path=Path('artifacts/task18/structured-fixed-endpoint8192-jet/step8192-10/checkpoint-verification.json');verification=json.loads(verification_path.read_text());assert verification['fixed_kernel_hash']==rate_record['fixed_kernel_hash'] and verification['sha256']==sha(cp);weights['kernel._fixed_rates']=rates[None]
rawpath=Path('artifacts/task18/cache-structured-fixed-6144/000000000010.pt');manifest=json.loads(Path(cfg.development.cache_manifest_path).read_text());assert canonical_hash(manifest)==cfg.development.cache_manifest_hash and sha(rawpath)==manifest['entries'][10]['sha256'];wire=torch.load(rawpath,weights_only=True);ep0=Episode(EventBatch(**wire.pop('events')),QueryBatch(**wire.pop('queries')),**wire);ep=move_episode(ep0,'cpu',dtype=torch.float64);ep=replace(ep,events=replace(ep.events,auxiliary={**ep.events.auxiliary,'gate':torch.ones(ep.events.present.shape,dtype=torch.float64)}));old=json.load(open('artifacts/task18/fixed-basis-initial/jet-10/summary.json'));assert batch_hash(ep.events)==old['events_hash'] and ep0.metadata['hashes']==old['raw_hashes']
cap_path=Path('artifacts/task18/structured-fixed-keygrad-diagnosis/jet10/boundary-captures.pt');cap=torch.load(cap_path,weights_only=True);constants=cap['structured_features']['candidate'][0,6,80:];assert torch.equal(constants,cap['structured_features']['reference'][0,6,80:]);failed_path=Path('artifacts/task18/structured-fixed-endpoint8192-jet/step8192-10/summary.json');failed=json.loads(failed_path.read_text());miss=next(x for x in failed['metrics'] if x['name']=='fitted_task_gradient_key');candidate=miss['worst_candidate'];reference=miss['worst_reference'];assert float(cap['key_gradient']['candidate'].flatten()[8155])==candidate and float(cap['key_gradient']['reference'].flatten()[8155])==reference
inputs={'key_features':ep.events.key_features,'values':ep.events.values,'timestamps':ep.events.timestamps,'represented_ages':ep.events.timestamps[0,-1]-ep.events.timestamps[0],'gate':ep.events.auxiliary['gate'],'query_features':ep.queries.key_features,'query6_shared_constants':constants,'query6_presented_labels':ep.labels[0,6].to(torch.float32).to(torch.float64)}
procedure={'fixed_rates_extraction':{'origin_procedure':str(rate_path),'origin_sha256':sha(rate_path),'rate_tensor_hash':rate_record['rate_tensor_hash'],'checkpoint_verification_sha256':sha(verification_path),'fixed_kernel_hash':verification['fixed_kernel_hash'],'scope':'exact accepted actualrepresentedrates; fixedkernel identity binds savedcheckpoint; not a nonexistent inference-export weight'},'source':source,'helper_sha256':sha(__file__),'checkpoint_sha256':sha(cp),'failed_summary_sha256':sha(failed_path),'boundary_capture_sha256':sha(cap_path),'raw_file_sha256':sha(rawpath),'presented_event_batch_hash_equal_failed_replay':True,'input_hashes':{k:canonical_hash(tensor_record(v)) for k,v in inputs.items()},'weight_hashes':{k:canonical_hash(tensor_record(v)) for k,v in weights.items()},'precision_digits':[60,80],'coordinate':8155,'query':6,'candidate':candidate,'binary64_reference':reference,'atol':1e-12,'rtol':1e-12,'scope':'one full query6 fitted directional derivative and full-history objective weighting; shared queryconstants exact; no independentquery oracle, refit, updates, tolerance/reference replacement or broadergate acceptance','convergence_criterion':'abs(d60-d80)<=1e-45*max(1,abs(d80))','net_limit':201326592,'utc_start':utc.isoformat()};_write_immutable(out/'procedure.json',procedure);torch.save(inputs,out/'presented-inputs.pt')
try:
 results=[]
 for precision in (60,80):
  tick=time.perf_counter();result=evaluate(precision,ep,weights,constants,cfg.model.epsilon,cfg.model.numerical_support_floor);result['seconds']=time.perf_counter()-tick;atomic_json(out/f'decimal{precision}.json',result);results.append(result);check_smoke_memory(cfg,max(0,resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*factor-base))
 with localcontext() as ctx:
  ctx.prec=90;d60,d80=(Decimal(r['derivative']) for r in results);difference=abs(d60-d80);assert difference<=Decimal('1e-45')*max(Decimal(1),abs(d80));bound=Decimal('1e-12')*(1+abs(d80));comparisons={}
  for name,value in [('candidate',candidate),('binary64_reference',reference)]:
   error=abs(Decimal.from_float(value)-d80);comparisons[name]={'value':repr(value),'absolute_error':str(error),'pointwise_bound':str(bound),'ratio':str(error/bound),'passes_original_bound':error<=bound}
  boundary_convergence={k:str(max(abs(Decimal(a[f])-Decimal(b[f])) for a,b in zip(results[0][k],results[1][k]) for f in ('value','derivative'))) for k in ('raw','features','standardized','hidden1','hidden2','numeric','prediction')}
 end=datetime.now(timezone.utc);record={'status':'single_coordinate_adjudication_complete_not_full_gate','source':source,'converged_derivative':str(d80),'decimal60_80_difference':str(difference),'boundary60_80_max_differences':boundary_convergence,'comparisons':comparisons,'support':results[1]['support'],'precision_seconds':[r['seconds'] for r in results],'perf_seconds':time.perf_counter()-started,'utc_start':utc.isoformat(),'utc_end':end.isoformat(),'utc_seconds':(end-utc).total_seconds(),'net_peak_bytes':max(0,resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*factor-base),'procedure_sha256':sha(out/'procedure.json'),'precision_result_sha256':{str(n):sha(out/f'decimal{n}.json') for n in (60,80)},'presented_inputs_sha256':sha(out/'presented-inputs.pt'),'all_other_work_held':True};atomic_json(out/'summary.json',record);print(json.dumps(record),flush=True)
except BaseException as exc:atomic_json(out/'failure.json',{'type':type(exc).__name__,'message':str(exc),'seconds':time.perf_counter()-started,'source':source});raise
