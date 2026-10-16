import os,sys,json
os.environ['PYTORCH_ENABLE_MPS_FALLBACK']='0';os.environ['PYTORCH_MPS_FAST_MATH']='0'
sys.path.insert(0,os.getcwd());sys.path.insert(0,os.path.join(os.getcwd(),'tests'))
import numpy as np,torch
from scipy.linalg import expm
from test_multiscale import independent_system
from famjet.memory.multiscale import log_scale_system
n,m,eps,tau,length=4,2,1e-4,16.,2048
s=log_scale_system(n,m,eps,tau);rng=np.random.default_rng(20261016)
gaps=rng.choice([0,1,2,4,16],length);gaps[0]=0;times=np.cumsum(gaps,dtype=np.int64)
values=torch.tensor(rng.normal(size=(1,length,1)),dtype=torch.float32).double().numpy()
A,G,B,K=independent_system(n,m,eps,tau)
expected=np.zeros((n*m,2))
for j in range(length):expected+=(expm(K*float(times[-1]-times[j])) @ B.flatten(order='F')/tau)[:,None]*np.r_[values[0,j],1.]
expected=np.einsum('mnv,mj->jnv',expected.reshape(m,n,2),s['U']).reshape(n*m,2)
for incremental in (False,True):
 p=torch.zeros((m,n,2));inj=torch.tensor((s['B']@s['U']/tau).T,dtype=torch.float32)
 cache={g:torch.tensor(np.stack([expm(A*gamma*float(g)/tau)-(np.eye(n) if incremental else 0) for gamma in s['gamma']]),dtype=torch.float32) for g in (0,1,2,4,16)}
 for j,g in enumerate(gaps):p=(p if incremental else 0)+cache[g]@p+inj[:,:,None]*torch.tensor(np.r_[values[0,j],1.],dtype=torch.float32)
 actual=p.reshape(n*m,2).double().numpy()
 print(json.dumps({'incremental':incremental,'max_absolute_error':float(abs(actual-expected).max()),'max_ratio':float((abs(actual-expected)/(1e-6+1e-5*abs(expected))).max())}))
