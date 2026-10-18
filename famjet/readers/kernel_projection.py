"""Deterministic exponential-prior projection in canonical kernel coordinates.

Numerical eligibility is not factual interval support or a confidence estimate.
No query, coefficients, contracted state or history is retained on this module.
"""
import math
import torch
from torch import nn

EPSILON = 1e-8
MASS_FLOOR = 1e-8
CANCELLATION = 64 * 2.**-53
RIDGES = (1e-10, 1e-6, 1e-2)
# Short-circuit order is part of the diagnostic contract.
FAILURES = ('eligible', 'quarantined', 'nonfinite_input', 'negative_normalizer',
            'negative_mass', 'mass_floor', 'cancellation', 'nonfinite_result')


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _fp64(tensor):
    return (type(tensor) is torch.Tensor and tensor.dtype == torch.float64
            and tensor.device.type == 'cpu' and tensor.layout == torch.strided
            and not tensor.requires_grad and tensor.grad_fn is None)


def _log_local_integral(order, s, width):
    z = s*width
    if z > 50:
        # Relative discarded tail < 3e-19 for orders <=2; avoids inf products.
        return math.lgamma(order+1)-(order+1)*math.log(s)
    if z <= .5:
        term = 1.
        terms = []
        for k in range(128):
            add = term/(order+k+1)
            terms.append(add)
            if k and abs(add) <= 2.**-55*abs(math.fsum(terms)):
                break
            term *= -z/(k+1)
        else:
            raise ArithmeticError('window integral series did not converge')
        f = math.fsum(terms)
    elif order == 0:
        f = -math.expm1(-z)/z
    else:
        poly = math.fsum(z**k/math.factorial(k) for k in range(order+1))
        f = math.factorial(order)*(1-math.exp(-z)*poly)/z**(order+1)
    return (order+1)*math.log(width)+math.log(f)


def exponential_integral(order, s, lower, upper):
    """Closed positive integral of x**order exp(-s*x), orders0..2.

    Shift to the lower endpoint, use a convergent small-width series and sum
    positive terms in log coordinates. Complete decay never evaluates 0*inf.
    """
    _require(type(order) is int and 0 <= order <= 2, 'invalid integral order')
    _require(all(type(x) in (float,int) and math.isfinite(x) for x in (s,lower,upper))
             and s > 0 and 0 <= lower < upper, 'invalid integral bounds/rate')
    attenuation = s*lower
    if not math.isfinite(attenuation):
        return 0.
    terms = []
    for r in range(order+1):
        if lower == 0 and order != r:
            continue
        logterm = (math.log(math.comb(order,r)) +
                   ((order-r)*math.log(lower) if order != r else 0.) +
                   _log_local_integral(r,s,upper-lower)-attenuation)
        terms.append(math.exp(logterm))
    return math.fsum(terms)


class KernelProjection(nn.Module):
    """FP64 spectral factors; general small bases support analytic unit controls.

    The production wrapper restricts admission to the adopted fixed Jet4/Bank8.
    Export reconstruction loads exact supplied factors, never refactorizes them.
    """
    array_names = ('alpha', 'gram', 'diagonal', 'eigenvectors', 'eigenvalues', 'inverse_shifted')
    config_names = ('family','t_ref','prior_scale','ridge','epsilon','mass_floor','cancellation')

    def __init__(self, rates, family, t_ref, *, prior_scale=5224., ridge=1e-6):
        super().__init__()
        _require(_fp64(rates) and rates.ndim == 1 and 0 < rates.numel() <= 8
                 and bool(torch.isfinite(rates).all()) and bool((rates > 0).all()), 'invalid projection rates')
        self._set_policy(family,t_ref,prior_scale,ridge)
        alpha = rates*t_ref
        _require(bool(torch.isfinite(alpha).all()) and bool((alpha > 0).all()), 'nonrepresentable dimensionless rates')
        if family == 'jet':
            alpha = alpha.repeat_interleave(2)
        self.register_buffer('alpha',alpha.clone())
        g = self._gram()
        d = torch.sqrt(torch.diagonal(g))
        r = g/d[:,None]/d[None,:]
        eigenvalues, q = torch.linalg.eigh(r)
        self.register_buffer('gram',g)
        self.register_buffer('diagonal',d.clone())
        self.register_buffer('eigenvectors',q.clone())
        self.register_buffer('eigenvalues',eigenvalues.clone())
        self.register_buffer('inverse_shifted',1/(eigenvalues+ridge))
        self.validate_statics()

    def _set_policy(self,family,t_ref,prior_scale,ridge,epsilon=EPSILON,mass_floor=MASS_FLOOR,cancellation=CANCELLATION):
        _require(type(family) is str and family in ('jet','bank'), 'invalid projection family')
        _require(all(type(x) in (float,int) and math.isfinite(x) and x > 0 for x in (t_ref,prior_scale))
                 and type(ridge) is float and ridge in RIDGES, 'invalid projection prior/ridge')
        _require(all(type(x) is float for x in (epsilon,mass_floor,cancellation))
                 and (epsilon,mass_floor,cancellation)==(EPSILON,MASS_FLOOR,CANCELLATION), 'invalid numerical policy')
        self.epsilon,self.mass_floor,self.cancellation=epsilon,mass_floor,cancellation
        self.family,self.t_ref,self.prior_scale,self.ridge = family,float(t_ref),float(prior_scale),ridge
        _require(math.isfinite(self.eta) and self.eta > 0, 'nonrepresentable prior')

    @property
    def eta(self):
        return self.t_ref/self.prior_scale

    def _orders(self):
        return [i % 2 if self.family == 'jet' else 0 for i in range(self.alpha.numel())]

    def _gram(self):
        a = self.alpha.tolist(); orders = self._orders()
        return torch.tensor([[math.exp(math.log(self.eta)+q*math.log(x)+p*math.log(y)+
            math.lgamma(q+p+1)-(q+p+1)*math.log(x+y+self.eta))
            for y,p in zip(a,orders)] for x,q in zip(a,orders)],dtype=torch.float64)

    def validate_statics(self):
        _require(_fp64(self.alpha) and self.alpha.ndim == 1 and 0 < self.alpha.numel() <= 16
                 and bool((self.alpha > 0).all()), 'invalid canonical alpha')
        m = self.alpha.numel()
        if self.family == 'jet':
            _require(m % 2 == 0 and torch.equal(self.alpha[::2],self.alpha[1::2]), 'invalid Jet channel pairing')
        for name in self.array_names:
            x = getattr(self,name)
            shape = (m,m) if name in ('gram','eigenvectors') else (m,)
            _require(_fp64(x) and x.shape == shape and bool(torch.isfinite(x).all()), 'invalid static factor layout/value')
        _require(bool((self.diagonal > 0).all()) and bool((self.eigenvalues >= 0).all())
                 and bool((self.eigenvalues+self.ridge > 0).all()),
                 'factor applicability: minimum eigenvalue='+repr(self.eigenvalues.min().item()))
        _require(torch.equal(self.gram,self._gram()) and torch.equal(self.diagonal,torch.sqrt(self.gram.diagonal()))
                 and torch.equal(self.inverse_shifted,1/(self.eigenvalues+self.ridge)), 'static factor formula mismatch')
        r = self.gram/self.diagonal[:,None]/self.diagonal[None,:]
        q = self.eigenvectors
        residual = torch.linalg.matrix_norm(r@q-q*self.eigenvalues)/max(1.,torch.linalg.matrix_norm(r).item())
        _require(residual.item() <= 1e-12 and torch.allclose(q.T@q,torch.eye(m,dtype=torch.float64),atol=1e-12,rtol=1e-12), 'static spectral residual')

    def factor_diagnostics(self):
        r = self.gram/self.diagonal[:,None]/self.diagonal[None,:]
        residual = torch.linalg.matrix_norm(r@self.eigenvectors-self.eigenvectors*self.eigenvalues)
        return dict(minimum_eigenvalue=self.eigenvalues.min().item(),
                    factor_residual=(residual/max(1.,torch.linalg.matrix_norm(r).item())).item(),
                    condition_estimate=((self.eigenvalues.max()+self.ridge)/
                                        (self.eigenvalues.min()+self.ridge)).item())

    @classmethod
    def from_statics(cls,config,arrays):
        _require(type(config) is dict and set(config) == set(cls.config_names)
                 and type(arrays) is dict and set(arrays) == set(cls.array_names), 'invalid projection static schema')
        obj = cls.__new__(cls); nn.Module.__init__(obj)
        obj._set_policy(**config)
        for name in cls.array_names:
            _require(_fp64(arrays[name]), 'invalid static precision/device')
            obj.register_buffer(name,arrays[name].clone())
        obj.validate_statics()
        return obj

    def window_vector(self,lower,upper):
        _require(all(type(x) in (float,int) and math.isfinite(x) for x in (lower,upper))
                 and 0 <= lower < upper, 'invalid projection window')
        return torch.tensor([self.eta*(alpha**order)*exponential_integral(order,alpha+self.eta,lower,upper)
            for alpha,order in zip(self.alpha.tolist(),self._orders())],dtype=torch.float64)

    def coefficients(self,lower,upper):
        h = self.window_vector(lower,upper)/self.diagonal
        theta = self.eigenvectors@((self.eigenvectors.T@h)*self.inverse_shifted)
        r = self.gram/self.diagonal[:,None]/self.diagonal[None,:]
        residual = torch.linalg.vector_norm(r@theta+self.ridge*theta-h)
        if not math.isfinite(residual.item()) or residual.item()/max(1.,torch.linalg.vector_norm(h).item()) > 1e-12:
            raise ArithmeticError('canonical ridge solve residual')
        return theta/self.diagonal

    def window(self,normalizers,numerators,lower,upper,*,quarantined=False):
        m = self.alpha.numel()
        _require(_fp64(normalizers) and normalizers.shape == (m,) and _fp64(numerators)
                 and numerators.ndim == 2 and numerators.shape[0] == m, 'invalid canonical contractions')
        self.window_vector(lower,upper)  # reject malformed query before numerical fallback
        def failed(code,mass=math.nan,bound=math.nan):
            return None,dict(code=code,mass=mass,cancellation_bound=bound)
        if quarantined: return failed(1)
        if not bool(torch.isfinite(normalizers).all() and torch.isfinite(numerators).all()): return failed(2)
        if bool((normalizers < 0).any()): return failed(3)
        try:
            c = self.coefficients(lower,upper)
            if not bool(torch.isfinite(c).all()): return failed(7)
            weights = c.tolist(); n = normalizers.tolist()
            mass = math.fsum(x*y for x,y in zip(weights,n))
            if not math.isfinite(mass): return failed(7,mass)
            if mass < 0: return failed(4,mass)
            if not mass > self.mass_floor: return failed(5,mass)
            bound = self.cancellation*math.fsum(abs(x)*y for x,y in zip(weights,n))
            if not math.isfinite(bound): return failed(7,mass,bound)
            if not mass > bound: return failed(6,mass,bound)
            sums = [math.fsum(x*y for x,y in zip(weights,col)) for col in numerators.T.tolist()]
            value = torch.tensor(sums,dtype=torch.float64)/(mass+self.epsilon)
            if not bool(torch.isfinite(value).all()): return failed(7,mass,bound)
            return value,dict(code=0,mass=mass,cancellation_bound=bound)
        except (ArithmeticError,RuntimeError,ValueError):
            return failed(7)
