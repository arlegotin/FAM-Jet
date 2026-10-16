"""Fixed failed frontier: isolate coefficient quantization and arithmetic accumulation."""
import os,sys,json
os.environ['PYTORCH_ENABLE_MPS_FALLBACK']='0';os.environ['PYTORCH_MPS_FAST_MATH']='0'
sys.path.insert(0,os.getcwd());sys.path.insert(0,os.path.join(os.getcwd(),'tests'))
import numpy as np,torch
from scipy.linalg import expm
from test_multiscale import independent_system
from famjet.memory.multiscale import log_scale_system
n,m,eps,tau=4,2,1e-4,16.
s=log_scale_system(n,m,eps,tau);rng=np.random.default_rng(20261016)
gaps=rng.choice([0,1,2,4,16],2048);gaps[0]=0;times=np.cumsum(gaps,dtype=np.int64)
values=torch.tensor(rng.normal(size=(1,2048,1)),dtype=torch.float32).double().numpy()
A,G,B,K=independent_system(n,m,eps,tau)
injection=(s['B']@s['U']/tau).T
cache={g:np.stack([expm(A*gamma*float(g)/tau) for gamma in s['gamma']]) for g in (0,1,2,4,16)}
for length in (256,512,2048):
 expected=np.zeros((n*m,2))
 for j in range(length):expected+=(expm(K*float(times[length-1]-times[j]))@B.flatten(order='F')/tau)[:,None]*np.r_[values[0,j],1.]
 expected=np.einsum('mnv,mj->jnv',expected.reshape(m,n,2),s['U']).reshape(n*m,2)
 def report(kind,actual,device):
  actual=actual.reshape(n*m,2).cpu().double().numpy()
  return dict(length=length,mode=kind,device=device,max_absolute_error=float(abs(actual-expected).max()),
    max_tolerance_ratio=float((abs(actual-expected)/(1e-6+1e-5*abs(expected))).max()))
 for mode in ('true_E64_arithmetic64','E32_promoted64_arithmetic64'):
  p=torch.zeros(m,n,2,dtype=torch.float64);inj=torch.tensor(injection)
  matrices={g:torch.tensor(E if mode.startswith('true') else E.astype(np.float32).astype(np.float64)) for g,E in cache.items()}
  for j,g in enumerate(gaps[:length]):p=matrices[g]@p+inj[:,:,None]*torch.tensor(np.r_[values[0,j],1.])
  print(json.dumps(report(mode,p,'cpu')))
 for device in ('cpu','mps'):
  if device=='mps' and not torch.backends.mps.is_available():continue
  inj=torch.tensor(injection,dtype=torch.float32,device=device)
  for mode in ('stream','stream_incremental','terminal'):
   p=torch.zeros(m,n,2,device=device)
   matrices={g:torch.tensor(E-(np.eye(n) if mode=='stream_incremental' else 0),dtype=torch.float32,device=device) for g,E in cache.items()}
   for j,g in enumerate(gaps[:length]):
    X=torch.tensor(np.r_[values[0,j],1.],dtype=torch.float32,device=device)
    if mode=='terminal':
     E=torch.tensor(np.stack([expm(A*gamma*float(times[length-1]-times[j])/tau) for gamma in s['gamma']]),dtype=torch.float32,device=device)
     p=p+(E@inj[:,:,None])*X
    else:p=(p if mode=='stream_incremental' else 0)+matrices[g]@p+inj[:,:,None]*X
   print(json.dumps(report(mode,p,device)))
