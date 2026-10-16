"""Finite log-rate HiPPO Zoo system, independent implementation of R07.

G is the finite Jacobi exponential, not exact projected infinite multiplication.
CPU FP64 preparation is explicit; native tensor column propagation uses Q=P U.
Event impulses and sampled-signal ZOH are deliberately separate interfaces.
"""
import math
import numpy as np
from scipy.linalg import expm, eigh
from scipy.special import ive, eval_legendre
import torch
from famjet.memory._fixed_writer import _require, _finite
from famjet.memory._coefficient import LinearCoefficientMemory
from famjet.memory.hippo import legendre_generator, impulse_transition, validate_allocation
from famjet.provenance import canonical_hash


def validate_system(order, scale_order, epsilon, tau0):
    """Bound dimensions before allocating matrices or reading wire tensors."""
    _require(type(order) is int and 1 <= order <= 256 and type(scale_order) is int
             and 1 <= scale_order <= 64 and order*scale_order <= 1024,
             'invalid bounded multiscale orders')
    _require(type(epsilon) in (int,float) and math.isfinite(epsilon) and 0 < epsilon < 1,
             'epsilon must be finite in (0,1)')
    _require(type(tau0) in (int,float) and math.isfinite(tau0) and tau0 > 0,
             'tau0 must be finite positive')


def log_scale_system(order: int, scale_order: int, epsilon: float, tau0: float) -> dict:
    """Construct the finite system in CPU FP64, with scaled Bessel projection.

    G and Jx share eigenvectors: diagonalizing Jx computes G's eigenbasis without
    losing tiny positive gamma to cancellation in a dense eigensolve of G.
    The single expm still constructs the specified finite G independently.
    """
    validate_system(order,scale_order,epsilon,tau0)
    A,b=legendre_generator(order)
    L=-math.log(epsilon); r=np.arange(1,scale_order,dtype=np.float64)
    off=r/np.sqrt((2*r-1)*(2*r+1))
    Jx=np.diag(off,1)+np.diag(off,-1)
    G=expm((L/2)*(Jx-np.eye(scale_order)))
    G=(G+G.T)/2
    eigen,U=eigh(Jx)
    gamma=np.exp((eigen-1)*(L/2))
    # Fix column signs for deterministic serialized Q coordinates.
    for j in range(scale_order):
        if U[np.argmax(np.abs(U[:,j])),j] < 0: U[:,j]*=-1
    r=np.arange(scale_order,dtype=np.float64)
    # sqrt(eps)*I_v(L/2) = ive(v,L/2); no overflowing 1/eps or Bessel.
    beta=np.sqrt((2*r+1)*math.pi)*ive(r+.5,L/2)
    B=np.outer(b,beta)
    _require(all(np.isfinite(x).all() for x in (G,beta,U,gamma,B)) and (gamma>0).all(),
             'unrepresentable CPU FP64 log-scale system')
    return dict(A=A,b=b,G=G,beta=beta,B=B,U=U,gamma=gamma,tau0=float(tau0),epsilon=float(epsilon))


def _dense_inputs(state,delta,write,system):
    _require(type(delta) in (int,float) and math.isfinite(delta) and delta >= 0,'invalid elapsed gap')
    state=np.asarray(state,dtype=np.float64);write=np.asarray(write,dtype=np.float64)
    n,m=system['B'].shape
    _require(state.shape == (n,m,*write.shape) and np.isfinite(state).all() and np.isfinite(write).all(),
             'state must have shape [temporal,scale,*write.shape] and finite values')
    K=np.kron(system['G'].T,system['A'])/system['tau0']
    c=system['B'].T.reshape(n*m)/system['tau0']
    return state,write,K,c


def multiscale_dense_step(state: np.ndarray, delta: float, write: np.ndarray, system: dict) -> np.ndarray:
    """Independent column-vector Kronecker oracle; impulse at interval end."""
    state,write,K,c=_dense_inputs(state,delta,write,system)
    n,m=state.shape[:2]
    result=expm(K*delta) @ state.swapaxes(0,1).reshape(n*m,-1)+c[:,None]*write.reshape(1,-1)
    _require(np.isfinite(result).all(),'nonfinite dense impulse result')
    return result.reshape(m,n,*write.shape).swapaxes(0,1)


def multiscale_zoh_step(state: np.ndarray, delta: float, write: np.ndarray, system: dict) -> np.ndarray:
    """Sampled constant signal over the interval; zero gap has zero injection."""
    state,write,K,c=_dense_inputs(state,delta,write,system)
    d=len(c); augmented=np.zeros((d+1,d+1));augmented[:d,:d]=K;augmented[:d,d]=c
    E=expm(augmented*delta)
    n,m=state.shape[:2]
    result=E[:d,:d] @ state.swapaxes(0,1).reshape(d,-1)+E[:d,d,None]*write.reshape(1,-1)
    _require(np.isfinite(result).all(),'nonfinite dense ZOH result')
    return result.reshape(m,n,*write.shape).swapaxes(0,1)


def scale_basis(scale_order: int, epsilon: float, rate: float) -> np.ndarray:
    """du-orthonormal psi(log(rate)); caller explicitly chooses a represented rate.

    No implicit clipping or exact reconstruction claim outside [epsilon,1].
    """
    validate_system(1,scale_order,epsilon,1.)
    _require(type(rate) in (int,float) and math.isfinite(rate) and epsilon <= rate <= 1,
             'query rate must be in [epsilon,1]')
    L=-math.log(epsilon);r=np.arange(scale_order)
    return np.sqrt((2*r+1)/L)*eval_legendre(r,1+2*math.log(rate)/L)


class MultiscaleMemory(LinearCoefficientMemory):
    """Store all Q columns, packed scale-major as [B,1,m*n,K,V+1].

    tau0 and epsilon are fixed static scalars; no learned-scale gradient claim.
    The all-coefficient readers see dimensionless t_ref*Q, including signed data.
    """
    def __init__(self,order,scale_order,epsilon,tau0,key_dim,value_dim,*,
                 declared_gaps=(0.,1.,2.,4.,16.),cache_limit_bytes=1048576,
                 t_ref=1.,chunk_size=128,dtype=torch.float32,device='cpu'):
        super().__init__()
        validate_system(order,scale_order,epsilon,tau0)
        _require(dtype in (torch.float32,torch.float64),'multiscale precision must be FP32 or FP64')
        validate_allocation((order,)*scale_order,(tau0,)*scale_order,declared_gaps,
                            cache_limit_bytes,torch.empty((),dtype=dtype).element_size())
        _require(all(type(x) is int and 0 < x <= 2**63-1 for x in (key_dim,value_dim,chunk_size)),
                 'invalid multiscale dimensions')
        _require(type(t_ref) in (int,float) and (type(t_ref) is not int or t_ref <= 2**63-1)
                 and math.isfinite(t_ref) and t_ref>0,'invalid t_ref')
        system=log_scale_system(order,scale_order,epsilon,tau0)
        self.order,self.scale_order,self.epsilon,self.tau0=order,scale_order,float(epsilon),float(tau0)
        self.orders=(order,)*scale_order
        self.taus=tuple(float(tau0/gamma) for gamma in system['gamma'])
        _require(all(math.isfinite(t) and t>0 for t in self.taus),'effective timescales overflow CPU FP64')
        self.declared_gaps=tuple(float(g) for g in declared_gaps)
        self.cache_limit_bytes=cache_limit_bytes
        self.key_dim,self.value_dim,self.t_ref,self.chunk_size=key_dim,value_dim,float(t_ref),chunk_size
        for j,tau in enumerate(self.taus):
            matrices=np.stack([impulse_transition(system['A'],gap,tau) for gap in self.declared_gaps]) if self.declared_gaps else np.empty((0,order,order))
            self.register_buffer(f'gap_bank_{j}',torch.tensor(matrices,dtype=dtype,device=device))
        injection=(system['B'] @ system['U']/tau0).T.reshape(-1)
        self.register_buffer('injection',torch.tensor(injection,dtype=dtype,device=device))
        self.register_buffer('U',torch.tensor(system['U'],dtype=dtype,device=device))
        for buffer in self.buffers():_finite(buffer,'represented multiscale buffer')

    @property
    def reader_feature_spec(self):
        return dict(family='multiscale',coefficients=self.coefficient_count,key_dim=self.key_dim,value_dim=self.value_dim)

    def _parameter_hash(self):
        from famjet.eval.state_io import tensor_record
        return canonical_hash(dict(kernel='legt-log-jacobi-event-impulse-v1',order=self.order,
            scale_order=self.scale_order,epsilon=self.epsilon,tau0=self.tau0,
            key_dim=self.key_dim,value_dim=self.value_dim,
            buffers={name:tensor_record(t) for name,t in self.named_buffers()}))

    def preparation_cost(self,gaps):
        cost=super().preparation_cost(gaps)
        return {**cost,'construction_exponentials':cost['construction_exponentials']+1,
                'construction_eigendecompositions':1,'construction_scale_order':self.scale_order,
                'static_basis_bytes':self.U.numel()*self.U.element_size(),
                'construction_scope':'CPU_FP64_finite_Jacobi_expm_eigenbasis_scaled_Bessel_and_gap_matrices'}

    def scale_features(self,state,queries,rate):
        """Return dimensionless temporal coefficients Q (U^T psi) per query.

        Generic readers additionally retain every scale/temporal coefficient.
        Query propagation and numerical support follow the same snapshot path.
        """
        psi=torch.tensor(scale_basis(self.scale_order,self.epsilon,rate),dtype=self.U.dtype,device=self.U.device)
        features=self.features(state,queries)
        if queries.T.shape[1] == 0:
            return features.values.new_empty((state.last_time.numel(),0,self.order,self.value_dim+1))
        coefficients=features.diagnostics['coefficients'][:,:,0]
        q=coefficients.reshape(*coefficients.shape[:2],self.scale_order,self.order,self.value_dim+1)
        return torch.einsum('bqmnv,m->bqnv',q,self.U.T @ psi)
