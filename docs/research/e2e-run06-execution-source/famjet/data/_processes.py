"""Versioned value processes; all randomness is separate from query sampling."""
from dataclasses import dataclass
import numpy as np
from famjet.provenance import derive_seed

REGIMES = ('piecewise_stationary','trend_reset','periodic_impulses','irregular_revisions')
GAPS = (0,1,2,4,16)
GAP_PROBABILITIES = (.05,.55,.25,.10,.05)


@dataclass(frozen=True)
class NumericLaw:
    initial_level_sd: float = 1.
    piecewise_reset_probability: float = 1/32
    noise_sd: float = .1
    trend_slope_sd: float = .01
    trend_reset_probability: float = 1/128
    phase_min: float = 0.
    phase_max: float = 2*np.pi
    amplitude_min: float = .5
    amplitude_max: float = 1.5
    period_min: float = 16.
    period_max: float = 256.
    impulse_probability: float = 1/64
    impulse_sd: float = 2.
    excursion_probability: float = 1/64
    excursion_sd: float = 2.
    reversal_min: int = 1
    reversal_max: int = 16


NUMERIC_LAW=NumericLaw()
CATEGORICAL_REVISION_PROBABILITY=1/8

# Explicit robustness choices, exploratory until a later protected registration.
ROBUSTNESS = {
    'standard': {},
    'zipf': {'key_exponent':1.25},
    'lognormal_gaps': {'gap_log_mean':0.,'gap_log_sd':1.},
    'heavy_gaps': {'gap_pareto_shape':1.5},
    'heavy_noise': {'noise_student_df':3.,'noise_scale':.1},
    'fast_resets': {'reset_multiplier':4.},
    'broad_periods': {'period_min':4.,'period_max':1024.},
    'unseen_reversals': {'reversal_min':17,'reversal_max':64},
}


def draw_gaps(rng, n, robustness):
    if robustness=='lognormal_gaps':
        return rng.lognormal(0.,1.,n)
    if robustness=='heavy_gaps':
        return rng.pareto(1.5,n)+1.
    return rng.choice(GAPS,n,p=GAP_PROBABILITIES).astype(np.float64)


def numeric_values(times, key_indices, key_count, value_dim, seed, regime, robustness):
    """Per-key/coordinate independent process streams, with private excursion log."""
    values=np.empty((len(times),value_dim),dtype=np.float64)
    schedule=[]
    settings=ROBUSTNESS[robustness]
    law=NUMERIC_LAW
    for key in range(key_count):
        positions=np.flatnonzero(key_indices==key)
        for coord in range(value_dim):
            rng=np.random.Generator(np.random.PCG64(derive_seed(seed,'coordinate',f'{key}/{coord}')))
            level=float(rng.normal(0,law.initial_level_sd))
            slope=float(rng.normal(0,law.trend_slope_sd))
            origin=0.
            phase=rng.uniform(law.phase_min,law.phase_max)
            amplitude=rng.uniform(law.amplitude_min,law.amplitude_max)
            period=np.exp(rng.uniform(np.log(settings.get('period_min',law.period_min)),np.log(settings.get('period_max',law.period_max))))
            excursion=0.
            reverse_at=-1
            for obs,i in enumerate(positions):
                if regime in {'piecewise_stationary','irregular_revisions'}:
                    if rng.random()<settings.get('reset_multiplier',1.)*law.piecewise_reset_probability:
                        level=float(rng.normal(0,law.initial_level_sd))
                    value=level
                    if regime=='irregular_revisions':
                        if reverse_at==obs:
                            excursion=0.
                            reverse_at=-1
                        if reverse_at<0 and rng.random()<law.excursion_probability:
                            excursion=float(rng.normal(0,law.excursion_sd))
                            delay=int(rng.integers(settings.get('reversal_min',law.reversal_min),settings.get('reversal_max',law.reversal_max)+1))
                            reverse_at=obs+delay
                            schedule.append({'key_index':key,'coordinate':coord,'observation':obs,
                                             'reverse_observation':reverse_at,'amplitude':excursion})
                        value+=excursion
                elif regime=='trend_reset':
                    if rng.random()<settings.get('reset_multiplier',1.)*law.trend_reset_probability:
                        level=float(rng.normal(0,law.initial_level_sd))
                        slope=float(rng.normal(0,law.trend_slope_sd))
                        origin=float(times[i])
                    value=level+slope*(times[i]-origin)
                elif regime=='periodic_impulses':
                    value=level+amplitude*np.sin(2*np.pi*times[i]/period+phase)
                    if rng.random()<law.impulse_probability:
                        value+=rng.normal(0,law.impulse_sd)
                else:
                    raise ValueError('unknown numeric regime')
                noise=(rng.standard_t(3)*law.noise_sd if robustness=='heavy_noise' else rng.normal(0,law.noise_sd))
                values[i,coord]=value+noise
    return values,schedule


def categorical_values(key_indices,key_count,seed,revision):
    rng=np.random.Generator(np.random.PCG64(derive_seed(seed,'categorical','values')))
    categories=rng.integers(0,32,key_count)
    selected=[]
    for k in key_indices:
        if revision:
            if rng.random()<CATEGORICAL_REVISION_PROBABILITY:
                # Offset 1..31 makes each different category equally likely.
                categories[k]=(categories[k]+rng.integers(1,32))%32
            selected.append(categories[k])
        else:
            selected.append(rng.integers(0,32))
    return np.eye(32,dtype=np.float64)[np.asarray(selected,dtype=np.int64)]
