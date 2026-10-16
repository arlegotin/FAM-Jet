"""Reproduce the seed-37 FP32 cancellation limit and actual task-loss checks."""
import os,sys,json,copy
os.environ['PYTORCH_ENABLE_MPS_FALLBACK']='0';os.environ['PYTORCH_MPS_FAST_MATH']='0'
sys.path.insert(0,os.getcwd());sys.path.insert(0,os.path.join(os.getcwd(),'tests'))
import torch
from test_multiscale import multiscale_config
from famjet import train
from famjet.data.synthetic import generate_episode
from famjet.memory.multiscale import MultiscaleMemory
from dataclasses import replace
c=multiscale_config(writer='learned');ep=train.move_episode(generate_episode(c,19,'gradient'),'cpu')
e,q=ep.events,ep.queries
e64=replace(e,key_features=e.key_features.double(),values=e.values.double(),auxiliary={k:v.double() for k,v in e.auxiliary.items()})
q64=replace(q,key_features=q.key_features.double());ep64=replace(ep,events=e64,queries=q64)
def collect(model,episode,mode,objective):
 model.zero_grad(set_to_none=True)
 result=model.read(model.encode(episode.events,mode=mode),episode.queries)
 loss=result.prediction.square().sum() if objective=='sum_squared_predictions' else train.history_loss(model,result,episode)
 loss.backward()
 return {n:p.grad.detach().cpu().double().clone() for n,p in model.named_parameters() if p.grad is not None},float(loss.detach()),float(result.prediction.detach().abs().max())
def compare(g,w,rtol=1e-5,atol=1e-6):
 ratios={n:float(((v-w[n]).abs()/(atol+rtol*w[n].abs())).max()) for n,v in g.items()};name=max(ratios,key=ratios.get)
 v=g[name];ref=w[name];index=int(((v-ref).abs()/(atol+rtol*ref.abs())).argmax())
 return dict(max_tolerance_ratio=ratios[name],tensor=name,max_absolute_error=float((v-ref).abs().max()),
  worst_cell_reference=float(ref.flatten()[index]),worst_cell_actual=float(v.flatten()[index]),
  frobenius_relative_error=float(torch.linalg.vector_norm(v-ref)/torch.linalg.vector_norm(ref)),
  actual_norm=float(torch.linalg.vector_norm(v)),reference_norm=float(torch.linalg.vector_norm(ref)),
  per_parameter_ratios=ratios)
def oracle(model):
 result=copy.deepcopy(model).double();p=c.model.multiscale
 result.kernel=MultiscaleMemory(p.order,p.scale_order,p.epsilon,p.tau0,c.model.K,c.data.value_dim,dtype=torch.float64,
  chunk_size=32,cache_limit_bytes=1024,t_ref=model.kernel.t_ref)
 return result
reports=[]
for standardized in (False,True):
 torch.manual_seed(37);model=train.make_model(c)
 if standardized:
  fit=train.move_episode(generate_episode(c,c.seed,'training_preprocessing_v1-000000000000'),'cpu')
  model.fit_statistics([fit])
 ref=oracle(model)
 for objective in ('sum_squared_predictions','actual_task_mean'):
  g,loss,scale=collect(model,ep,'stream',objective);h,tloss,tscale=collect(model,ep,'terminal',objective)
  want,rloss,rscale=collect(ref,ep64,'terminal',objective);wantstream,_,_=collect(ref,ep64,'stream',objective)
  reports.append(dict(seed=37,standardized=standardized,objective=objective,loss=loss,reference_loss=rloss,
    max_prediction=scale,reference_max_prediction=rscale,pair=compare(g,h),stream_reference=compare(g,want),
    terminal_reference=compare(h,want),cpu64_stream_terminal=compare(wantstream,want,1e-12,1e-12)))
 # Isolate reader arithmetic from recurrence: feed the SAME rounded exact
 # terminal features to FP32 and FP64 readers with identical represented weights.
 exact=ref.features(ref.encode(e64,mode='terminal'),q64).values.detach().float()
 readers=[]
 for reader,features in ((model.reader,exact),(ref.reader,exact.double())):
  reader.zero_grad(set_to_none=True);pred,_=reader(features);pred.square().sum().backward()
  readers.append({n:p.grad.detach().double().clone() for n,p in reader.named_parameters() if p.grad is not None})
 reports.append(dict(standardized=standardized,objective='same_represented_features_reader_only_sum',comparison=compare(*readers)))
print(json.dumps(reports,indent=2))
