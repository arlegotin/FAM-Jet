"""Independent §8 equations, not a registered deferred-query MemoryMethod.

All lag/rate pairs survive, including coincident rates. Impulse input represents
an event measure; zoh_current_interval assigns the CURRENT sample to the entire
preceding interval, a discrete source convention, not a causal previous hold.
"""
import math
import numpy as np


def stehfest_weights(evaluations: int) -> np.ndarray:
    """CPU FP64 log-factorial evaluation of the specified finite factorial sum."""
    if type(evaluations) is not int or evaluations < 2 or evaluations > 64 or evaluations % 2:
        raise ValueError('evaluations must be an even integer in [2,64]')
    m=evaluations//2
    weights=[]
    for k in range(1,evaluations+1):
        terms=[]
        for j in range((k+1)//2,min(k,m)+1):
            logterm=((m+1)*math.log(j)+math.lgamma(2*j+1)-math.lgamma(m-j+1)
                     -2*math.lgamma(j+1)-math.lgamma(k-j+1)-math.lgamma(2*j-k+1))
            terms.append(math.exp(logterm))
        weights.append(math.log(2)*(-1)**(k+m)*math.fsum(terms))
    return np.asarray(weights,dtype=np.float64)


def gaver_rates(lags, evaluations: int, *, dtype=np.float64) -> np.ndarray:
    stehfest_weights(evaluations)
    taus=np.asarray(lags,dtype=np.float64)
    if taus.ndim!=1 or not 0<len(taus)<=64 or not np.isfinite(taus).all() or (taus<=0).any():
        raise ValueError('lags must be finite positive vector with at most64 entries')
    if np.dtype(dtype) not in (np.dtype('float32'),np.dtype('float64')):
        raise ValueError('precision must be float32 or float64')
    rates=(np.arange(1,evaluations+1)*math.log(2)/taus[:,None]).astype(dtype)
    if not np.isfinite(rates).all() or (rates<=0).any():
        raise ValueError('rates must remain representable and positive')
    return rates


def gaver_step(state, value, delta, rates, *, mode):
    """One bounded native array update; no hidden cache or deduplicated storage."""
    if mode not in {'impulse','zoh_current_interval'}:
        raise ValueError('unknown input convention')
    if type(delta) not in (int,float) or not math.isfinite(delta) or delta<0:
        raise ValueError('delta must be finite nonnegative')
    if (not isinstance(state,np.ndarray) or state.ndim!=3 or state.dtype not in (np.float32,np.float64)
            or not isinstance(rates,np.ndarray) or rates.shape!=state.shape[:2] or rates.dtype!=state.dtype
            or not isinstance(value,np.ndarray) or value.shape!=(state.shape[-1],) or value.dtype!=state.dtype
            or not all(np.isfinite(x).all() for x in (state,rates,value)) or (rates<=0).any()):
        raise ValueError('finite matching [lag,N,channel] state, rates and input required')
    with np.errstate(over='ignore'):
        z=-rates*delta
    decay=np.exp(z)
    injection=np.ones_like(rates) if mode=='impulse' else -np.expm1(z)/rates
    result=decay[...,None]*state+injection[...,None]*value
    if not np.isfinite(result).all(): raise FloatingPointError('nonfinite Gaver state')
    return result


def reconstruct(state, lags, *, mode, t_ref=1.):
    """Signed reconstruction, never a positive association normalization ratio.

    Impulse outputs have inverse-time units and multiply t_ref; sampled ZOH
    outputs already have signal units. This transformation adds no information.
    """
    if mode not in {'impulse','zoh_current_interval'}:
        raise ValueError('unknown input convention')
    if type(t_ref) not in (int,float) or not math.isfinite(t_ref) or t_ref<=0:
        raise ValueError('t_ref must be finite positive')
    if not isinstance(state,np.ndarray) or state.ndim!=3 or not np.isfinite(state).all():
        raise ValueError('finite [lag,N,channel] state required')
    gaver_rates(lags,state.shape[1],dtype=state.dtype)
    if len(lags)!=state.shape[0]: raise ValueError('lag count mismatch')
    weights=stehfest_weights(state.shape[1]).astype(state.dtype)
    scale=np.asarray(lags,dtype=state.dtype)
    result=np.sum(state*weights[None,:,None],axis=1)/scale[:,None]
    if mode=='impulse': result=result*t_ref
    if not np.isfinite(result).all(): raise FloatingPointError('nonfinite Gaver reconstruction')
    return result
