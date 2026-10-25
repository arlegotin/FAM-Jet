"""Translated-Legendre event impulses, independently implemented from §8.

CPU FP64 constructs every propagator; native tensor matmul propagates states.
Only the declared gap alphabet is retained. Arbitrary-gap work is explicit,
uncached, and exposed by preparation_cost/prepare_transition for cost probes.
Physical coefficients have inverse-time units; readers receive t_ref * P.
"""
import math
import numpy as np
from scipy.linalg import expm
import torch
from famjet.memory._fixed_writer import _require, _finite
from famjet.memory._coefficient import LinearCoefficientMemory
from famjet.provenance import canonical_hash


def legendre_generator(order: int) -> tuple[np.ndarray, np.ndarray]:
    _require(type(order) is int and 1 <= order <= 256, 'order must be an integer in [1,256]')
    b = np.sqrt(2*np.arange(order, dtype=np.float64)+1)
    i, j = np.indices((order, order))
    signs = np.where((i < j) & ((j-i) % 2 == 1), -1., 1.)
    return -np.outer(b, b)*signs, b


def _matrix_inputs(A, delta, tau):
    _require(isinstance(A, np.ndarray) and A.ndim == 2 and A.shape[0] == A.shape[1]
             and A.shape[0] > 0 and np.isfinite(A).all(), 'A must be a finite square matrix')
    _require(type(delta) in (int, float) and math.isfinite(delta) and delta >= 0,
             'delta must be finite nonnegative')
    _require(type(tau) in (int, float) and math.isfinite(tau) and tau > 0,
             'tau must be finite positive')
    ratio = delta/tau
    _require(math.isfinite(ratio), 'delta/tau overflows CPU FP64 preparation')
    return np.asarray(A, dtype=np.float64), ratio


def impulse_transition(A: np.ndarray, delta: float, tau: float) -> np.ndarray:
    A, ratio = _matrix_inputs(A, delta, tau)
    if ratio == 0:
        return np.eye(len(A), dtype=np.float64)
    with np.errstate(over='ignore', invalid='ignore'):
        result = expm(A*ratio)
    _require(np.isfinite(result).all(), 'nonfinite CPU FP64 impulse transition')
    return result


def zoh_transition(A: np.ndarray, b: np.ndarray, delta: float, tau: float) -> tuple[np.ndarray, np.ndarray]:
    A, ratio = _matrix_inputs(A, delta, tau)
    _require(isinstance(b, np.ndarray) and b.shape == (len(A),) and np.isfinite(b).all(), 'b must match A')
    augmented = np.zeros((len(A)+1, len(A)+1), dtype=np.float64)
    augmented[:-1, :-1], augmented[:-1, -1] = A, b
    result = expm(augmented*ratio)
    _require(np.isfinite(result).all(), 'nonfinite CPU FP64 ZOH transition')
    return result[:-1, :-1], result[:-1, -1]


def validate_allocation(orders, taus, declared_gaps, cache_limit_bytes, itemsize):
    """Pure preallocation guard, also used on raw checkpoint descriptors."""
    _require(type(orders) in (list, tuple) and 0 < len(orders) <= 64
             and all(type(n) is int and 1 <= n <= 256 for n in orders)
             and sum(orders) <= 1024, 'invalid bounded polynomial orders')
    _require(type(taus) in (list, tuple) and len(taus) == len(orders)
             and all(type(t) in (int, float) and math.isfinite(t) and t > 0 for t in taus),
             'taus must be positive and match orders')
    _require(type(declared_gaps) in (list, tuple) and len(declared_gaps) <= 64
             and all(type(g) in (int, float) and math.isfinite(g) and g >= 0 for g in declared_gaps)
             and len(set(declared_gaps)) == len(declared_gaps), 'invalid declared gap alphabet')
    _require(type(cache_limit_bytes) is int and 0 <= cache_limit_bytes <= 2**63-1, 'invalid cache byte limit')
    required = len(declared_gaps)*sum(n*n for n in orders)*itemsize
    _require(required <= cache_limit_bytes, 'declared transition cache exceeds byte limit')
    return required


class PolynomialMemory(LinearCoefficientMemory):
    def __init__(self, orders, taus, key_dim, value_dim, *, declared_gaps=(0., 1., 2., 4., 16.),
                 cache_limit_bytes=1048576, t_ref=1., chunk_size=128, dtype=torch.float32, device='cpu'):
        super().__init__()
        _require(dtype in (torch.float32, torch.float64), 'polynomial precision must be FP32 or FP64')
        orders = (orders,) if type(orders) is int else orders
        taus = (taus,) if type(taus) in (int,float) else taus
        validate_allocation(orders, taus, declared_gaps, cache_limit_bytes, torch.empty((), dtype=dtype).element_size())
        _require(all(type(x) is int and 0 < x <= 2**63-1 for x in (key_dim, value_dim, chunk_size)), 'invalid polynomial dimensions')
        _require(type(t_ref) in (int, float) and (type(t_ref) is not int or t_ref <= 2**63-1)
                 and math.isfinite(t_ref) and t_ref > 0, 'invalid t_ref')
        self.orders, self.taus = tuple(orders), tuple(float(t) for t in taus)
        self.declared_gaps = tuple(float(g) for g in declared_gaps)
        self.cache_limit_bytes = cache_limit_bytes
        self.key_dim, self.value_dim, self.t_ref, self.chunk_size = key_dim, value_dim, float(t_ref), chunk_size
        injection = []
        for bank, (n, tau) in enumerate(zip(self.orders, self.taus)):
            A, b = legendre_generator(n)
            injection.extend(b/tau)
            matrices = np.stack([impulse_transition(A, gap, tau) for gap in self.declared_gaps]) if self.declared_gaps else np.empty((0,n,n))
            self.register_buffer(f'gap_bank_{bank}', torch.tensor(matrices, dtype=dtype, device=device))
        self.register_buffer('injection', torch.tensor(injection, dtype=dtype, device=device))
        for buffer in self.buffers():
            _finite(buffer, 'represented polynomial buffer')
        _require(bool((self.injection > 0).all()), 'impulse coefficients must remain positive in state precision')

    @property
    def reader_feature_spec(self):
        return dict(family='polynomial', coefficients=self.coefficient_count,
                    key_dim=self.key_dim, value_dim=self.value_dim)

    def _parameter_hash(self):
        from famjet.eval.state_io import tensor_record
        return canonical_hash(dict(kernel='legt-event-impulse-v1', orders=self.orders, taus=self.taus,
            key_dim=self.key_dim, value_dim=self.value_dim,
            buffers={name: tensor_record(t) for name,t in self.named_buffers()}))
