import torch
torch.set_num_threads(1); torch.manual_seed(1515)
for j in range(500):
 k=torch.randn(10000,4)*torch.exp(-torch.rand(10000,4)*20); k=k/(k.square().sum(-1,keepdim=True)+1e-6).sqrt()
 b=torch.exp(-torch.rand_like(k)*30)*2
 if j%2: b=2-b
 g=-torch.exp(-torch.rand(10000,1)*45)
 n=k.square().sum(-1,keepdim=True); a=(b*k.square()).sum(-1,keepdim=True); nu=(b.square()*k.square()).sum(-1,keepdim=True)
 r2=(n*nu-a.square()).clamp_min(0); inv=torch.exp(2*g); R=((1/inv-1)*(1-(1-a).square()*inv)).clamp_min(0)
 mu=a/n.clamp_min(1e-20); eta=((31/32)*R/r2.clamp_min(1e-30)).sqrt().clamp(0,1)
 candidate=torch.where((n>1e-20)&(r2>R),mu+eta*(b-mu),b)
 a2=(candidate*k.square()).sum(-1,keepdim=True); nu2=(candidate.square()*k.square()).sum(-1,keepdim=True)
 rr=(n*nu2-a2.square()).clamp_min(0); RR=((1/inv-1)*(1-(1-a2).square()*inv)).clamp_min(0)
 fallback=rr>RR+4*torch.finfo(b.dtype).eps*(n*nu2+a2.square())
 if fallback.any():
  i=fallback[:,0].nonzero()[0].item(); print('j',j,'k',k[i].tolist(),'b',b[i].tolist(),'g',g[i].item()); print('mu',mu[i].item(),'candidate',candidate[i].tolist(),'residual',rr[i].item(),'bound',RR[i].item()); break
else: print('no fallback found')
