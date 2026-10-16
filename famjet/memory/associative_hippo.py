"""Original scalar-location associative HiPPO component, independently written.

R07 / HiPPO Zoo Appendix C.3. Signed source tokens are native arrays; this API
does not accept EventBatch and is not registered as a scientific MemoryMethod.
History S and associative C are explicit outputs and both count as state.
"""
import math
import numpy as np
import torch
from torch import nn
from famjet.memory.hippo import legendre_generator, zoh_transition


def location_basis(location, order):
    if type(order) is not int or not 1<=order<=256:
        raise ValueError('order must be an integer in [1,256]')
    z=2*location-1
    polys=[torch.ones_like(z)]
    if order>1: polys.append(z)
    for r in range(2,order):
        polys.append(((2*r-1)*z*polys[-1]-(r-1)*polys[-2])/r)
    return torch.stack([p*((-1)**r)*math.sqrt(2*r+1) for r,p in enumerate(polys)],-1)


def minimum_norm_delta(C, location, value, gate):
    k=location_basis(location,C.shape[-1])
    error=value-torch.einsum('bcn,bn->bc',C,k)
    scale=gate/(k.square().sum(-1,keepdim=True)+1e-8)
    return C+(scale*error)[...,None]*k[:,None]


class _Gate(nn.Module):
    def __init__(self,width,hidden):
        super().__init__()
        self.hidden=nn.Linear(width,hidden)
        self.out=nn.Linear(hidden,1)
        self.skip=nn.Linear(width,1)

    def forward(self,s):
        return torch.sigmoid(self.out(torch.tanh(self.hidden(s)))+self.skip(s))


class OriginalAssociativeHiPPO(nn.Module):
    """CPU FP32 native source control with global scalar locations/gates.

    Initializer: torch Linear uniform(-1/sqrt(fan_in),1/sqrt(fan_in)) for
    weights AND present biases, explicitly seeded locally; not Flax RNG parity.
    """
    def __init__(self, *, embedding_dim=24, channels=32, history_order=32,
                 associative_order=32, hidden=256, timescale=2., seed=42):
        super().__init__()
        if any(type(x) is not int or not 1<=x<=256 for x in
               (embedding_dim,channels,history_order,associative_order,hidden)):
            raise ValueError('bounded integer native component dimensions required')
        if type(seed) is not int or not 0<=seed<2**63: raise ValueError('invalid seed')
        self.channels,self.history_order,self.associative_order=channels,history_order,associative_order
        A,b=legendre_generator(history_order)
        Ad,bd=zoh_transition(A,b,1.,timescale)
        self.register_buffer('Ad',torch.tensor(Ad,dtype=torch.float32))
        self.register_buffer('bd',torch.tensor(bd,dtype=torch.float32))
        # Do not mutate caller RNG; the explicit native initializer is reproducible.
        with torch.random.fork_rng(devices=[]):
            torch.manual_seed(seed)
            self.input=nn.Linear(embedding_dim,channels,bias=False)
            self.write_gate=_Gate(channels*history_order,hidden)
            self.output_gate=_Gate(channels*history_order,hidden)
            self.value=nn.Linear(channels,channels)
            self.key=nn.Linear(channels*history_order,1)
            self.query=nn.Linear(channels*history_order,1)
            self.output=nn.Linear(channels,embedding_dim)
            for layer in self.modules():
                if isinstance(layer,nn.Linear):
                    limit=1/math.sqrt(layer.in_features)
                    nn.init.uniform_(layer.weight,-limit,limit)
                    if layer.bias is not None: nn.init.uniform_(layer.bias,-limit,limit)

    def forward(self,x,state=None):
        if x.ndim!=3 or x.shape[-1]!=self.input.in_features or x.dtype!=torch.float32 or x.device.type!='cpu':
            raise ValueError('native component requires CPU FP32 [batch,time,embedding]')
        if state is None:
            S=x.new_zeros((len(x),self.channels,self.history_order))
            C=x.new_zeros((len(x),self.channels,self.associative_order))
        else: S,C=state
        outputs=[]
        for xt in x.unbind(1):
            u=self.input(xt)
            S=S@self.Ad.T+u[...,None]*self.bd
            s=S.flatten(1)
            key=torch.sigmoid(self.key(s)).squeeze(-1)
            query=torch.sigmoid(self.query(s)).squeeze(-1)
            C=minimum_norm_delta(C,key,self.value(u),self.write_gate(s))
            read=torch.einsum('bcn,bn->bc',C,location_basis(query,self.associative_order))
            outputs.append(self.output_gate(s)*self.output(read))
        return torch.stack(outputs,1),(S,C)


def token_table(seed, vocabulary=12, embedding_dim=24):
    rng=np.random.default_rng(seed)
    tokens=rng.standard_normal((2*vocabulary+1,embedding_dim)).astype(np.float32)
    return tokens/(np.linalg.norm(tokens,axis=1,keepdims=True)+1e-8)


def associative_episodes(tokens, count, seed):
    """Five A/B pairs, a query A, Write; latest matching A chooses its B."""
    if type(count) is not int or not 1<=count<=10000: raise ValueError('bounded episode count required')
    if tokens.shape!=(25,24) or tokens.dtype!=np.float32 or not np.isfinite(tokens).all():
        raise ValueError('source fixture requires one public FP32 25x24 token table')
    rng=np.random.default_rng(seed)
    ids=np.empty((count,12),dtype=np.int64)
    targets=np.zeros((count,12,24),dtype=np.float32)
    for i in range(count):
        a=rng.integers(0,12,size=5); b=rng.integers(12,24,size=5)
        query=rng.integers(0,12)
        if query not in a: a[rng.integers(0,5)]=query
        ids[i,0:10:2],ids[i,1:10:2]=a,b
        ids[i,-2:]=query,24
        targets[i,-1]=tokens[b[np.flatnonzero(a==query)[-1]]]
    return tokens[ids],targets,ids
