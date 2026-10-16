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
e=ep.events;q=ep.queries
e64=replace(e,key_features=e.key_features.double(),values=e.values.double(),auxiliary={k:v.double() for k,v in e.auxiliary.items()})
q64=replace(q,key_features=q.key_features.double())
def grads(m,e,q,mode):
 m.zero_grad(set_to_none=True);m.read(m.encode(e,mode=mode),q).prediction.square().sum().backward()
 return {n:p.grad.detach().cpu().double().clone() for n,p in m.named_parameters() if p.grad is not None}
def compare(g,w):
 results={n:float(((v-w[n]).abs()/(1e-6+1e-5*w[n].abs())).max()) for n,v in g.items()}
 return max(results.values()),max(results,key=results.get),results
for seed in range(1000):
 torch.manual_seed(seed);m=train.make_model(c)
 g=grads(m,e,q,'stream');h=grads(m,e,q,'terminal');pair=compare(g,h)
 if pair[0]>1:
  torch.save(m.state_dict(),'artifacts/task14-evidence/gradient-failing-model.pt')
  oracle=copy.deepcopy(m).double();p=c.model.multiscale
  oracle.kernel=MultiscaleMemory(p.order,p.scale_order,p.epsilon,p.tau0,c.model.K,c.data.value_dim,dtype=torch.float64,chunk_size=32,cache_limit_bytes=1024)
  ref=grads(oracle,e64,q64,'terminal')
  print(json.dumps({'seed':seed,'fixture':'generate_episode(config,19,gradient)','pair':pair,'stream_reference':compare(g,ref),'terminal_reference':compare(h,ref)}))
  break
else:print('No failing seeds 0..999')
