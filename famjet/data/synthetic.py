"""Deterministic, deferred-query synthetic populations (initial_spec_v1).

The exploratory API opens training/development namespaces only. A later protected
runner must authorize a frozen manifest before adding an execution interface.
No history routine accepts a query, query seed or eventual target.
"""
from dataclasses import asdict,dataclass
import hashlib
import math

import numpy as np
import torch

from famjet.config import RunConfig,validate_config
from famjet.data._processes import (CATEGORICAL_REVISION_PROBABILITY,GAPS,GAP_PROBABILITIES,
                                   NUMERIC_LAW,REGIMES,ROBUSTNESS,categorical_values,draw_gaps,numeric_values)
from famjet.data.schema import validate_events,validate_queries
from famjet.eval.oracle import exact_targets,exact_time_difference
from famjet.provenance import canonical_hash,derive_seed
from famjet.types import Episode,EventBatch,QueryBatch

GENERATOR_VERSION='initial_spec_v1'
FEATURE_VERSION='squared_gaussian.pcg64_box_muller_v1'
SEED_VERSION='sha256_named_v1'
NAMESPACES=('training','development_fit','development_calibration','pilot','confirmation','replication')
PROTECTED=frozenset(NAMESPACES[3:])
POPULATIONS=('primary','delayed','latest','presence','interval_support','change_sign',
             'corrected_categorical','random_binding','boundary','constant','impulse',
             'random','full_history','empty','same_time')


@dataclass(frozen=True)
class QueryLaw:
    width_floor: float = 1.
    span_divisor: float = 128.
    max_width_fraction: float = .5


QUERY_LAW=QueryLaw()


def population_parameters():
    """Finite JSON descriptor of the versioned distributions actually consumed."""
    return {'numeric_law':asdict(NUMERIC_LAW),'query_law':asdict(QUERY_LAW),
            'categorical_law':{'classes':32,'revision_probability':CATEGORICAL_REVISION_PROBABILITY},
            'gaps':list(GAPS),'gap_probabilities':list(GAP_PROBABILITIES),
            'pilot_lengths':[128,512,2048],'regime_weights':[.25]*4,'delays':[0,.125,1,10]}


def key_features(key_id: int,feature_seed: int,key_dim: int) -> np.ndarray:
    """Public uint64 -> nonnegative FP32 features, independent of split/activity.

    SHA-256(version prefix, little-endian uint64 seed, little-endian uint64 ID)
    seeds PCG64 with its full little-endian digest. Consecutive uniform pairs use
    Box-Muller (1-u, v), cosine then sine; squared FP64 coordinates are L1
    normalized before one FP32 cast. Golden vectors pin the implementation.
    """
    if type(key_id) is not int or not 0<=key_id<2**64:
        raise ValueError('key_id must be uint64')
    if type(feature_seed) is not int or not 0<=feature_seed<2**63:
        raise ValueError('feature_seed must fit nonnegative int64')
    if type(key_dim) is not int or key_dim<1:
        raise ValueError('key_dim must be positive')
    payload=b'famjet.'+FEATURE_VERSION.encode()+b'\0'+feature_seed.to_bytes(8,'little')+key_id.to_bytes(8,'little')
    seed=int.from_bytes(hashlib.sha256(payload).digest(),'little')
    rng=np.random.Generator(np.random.PCG64(seed))
    coordinates=[]
    for u,v in rng.random(((key_dim+1)//2,2)):
        radius=math.sqrt(-2*math.log(1-u))
        angle=2*math.pi*v
        coordinates.extend((radius*math.cos(angle),radius*math.sin(angle)))
    squares=[x*x for x in coordinates[:key_dim]]
    total=sum(squares)
    if total==0:
        raise ArithmeticError('degenerate feature transform')
    return np.asarray([x/total for x in squares],dtype=np.float32)


def _check_exploratory(config):
    validate_config(config)
    if config.data.generator_version!=GENERATOR_VERSION:
        raise ValueError('unsupported generator version')
    if config.phase in {'pilot','confirmation','replication'} or config.data.generator.namespace in PROTECTED:
        raise ValueError('protected generation requires a future frozen-manifest runner')
    d,g=config.data,config.data.generator
    if d.queries_per_history%2:
        raise ValueError('balanced populations require an even query count')
    if d.key_features=='one_hot' and (d.key_dim!=16 or g.key_load!=16):
        raise ValueError('one_hot population requires 16 public coordinates/load')
    if g.population in {'corrected_categorical','random_binding'}:
        if d.value_dim!=32:
            raise ValueError('categorical populations require separate V32 configuration')
    elif d.value_dim!=8:
        raise ValueError('numeric populations require V8 configuration')
    if g.population!='delayed' and g.delay_multiplier!=0:
        raise ValueError('delays require the separately named delayed population')


def _root(config,split_seed):
    return derive_seed(split_seed,GENERATOR_VERSION,config.data.generator.namespace)


def _rng(seed,namespace,identity):
    return np.random.Generator(np.random.PCG64(derive_seed(seed,namespace,identity)))


def _universe(config,root):
    d,g=config.data,config.data.generator
    if d.key_features=='one_hot':
        return list(range(16))
    # One byte is split-owned; all low 56 bits have the same ID distribution for
    # written and absent keys. High-bit IDs are retained as genuine uint64.
    prefix=(NAMESPACES.index(g.namespace)+128)<<56
    size=g.key_load+max(4,g.key_load//4)
    ids=[]
    rng=_rng(root,'public_ids','universe')
    while len(ids)<size:
        k=prefix|int(rng.integers(0,2**56,dtype=np.uint64))
        if k not in ids:
            ids.append(k)
    return ids


def _features(ids,config):
    if config.data.key_features=='one_hot':
        return np.eye(16,dtype=np.float32)[np.asarray(ids,dtype=np.int64)]
    return np.stack([key_features(int(k),config.data.generator.feature_seed,config.data.key_dim) for k in ids]) if len(ids) else np.empty((0,config.data.key_dim),np.float32)


def _history(config,root,episode_id):
    d,g=config.data,config.data.generator
    seed=derive_seed(root,'history',episode_id)
    universe=_universe(config,root)
    keys=_rng(seed,'keys','active').permutation(len(universe))
    count=12 if g.population=='presence' and d.key_features=='one_hot' else g.key_load
    active=[universe[int(i)] for i in keys[:count]]
    n=0 if g.population=='empty' else d.length
    rng=_rng(seed,'events','keys')
    p=None
    if g.robustness=='zipf':
        p=np.arange(1,count+1,dtype=np.float64)**-1.25
        p/=p.sum()
    indices=rng.choice(count,n,p=p)
    # Presence requires twelve actually written one-hot keys. A uniformly
    # permuted coverage prefix makes the finite fixture explicit, never retries
    # or examines values. Primary histories remain iid uniform-frequency.
    if g.population=='presence':
        covered=min(n,count)
        indices[:covered]=rng.permutation(count)[:covered]
    gaps=draw_gaps(_rng(seed,'events','gaps'),max(0,n-1),g.robustness)
    times=np.r_[0.,np.cumsum(gaps)] if n else np.empty(0)
    if g.population=='same_time':
        times[:]=0
    regime=(REGIMES[derive_seed(root,'regime',episode_id)%4] if g.regime=='balanced' else g.regime)
    value_seed=derive_seed(seed,'events','values')
    schedule=[]
    if g.population in {'corrected_categorical','random_binding'}:
        values=categorical_values(indices,count,value_seed,g.population=='corrected_categorical')
    else:
        values,schedule=numeric_values(times,indices,count,d.value_dim,value_seed,regime,g.robustness)
        if g.population=='constant':
            values[:]=1
        elif g.population=='impulse':
            values[:]=0
            if n:
                values[n//2]=1
        elif g.population=='random':
            values=_rng(value_seed,'fixture','iid').normal(size=(n,d.value_dim))
    ids=[active[int(i)] for i in indices]
    events=EventBatch((episode_id,),torch.arange(n,dtype=torch.int64)[None],
                      torch.from_numpy(times[None]),torch.tensor([ids],dtype=torch.uint64),
                      torch.from_numpy(_features(ids,config)[None]),torch.from_numpy(values[None]),
                      torch.tensor([n],dtype=torch.int64),torch.ones((1,n),dtype=torch.bool),
                      torch.ones((1,n,d.value_dim),dtype=torch.bool),'generator_reference_1')
    validate_events(events)
    return events,regime,schedule


def _supported(events,k,T,a,b,contrast):
    ids=events.key_ids[0].tolist()
    times=events.timestamps[0].tolist()
    obs=events.observed[0].numpy()
    masks=[]
    for lower,upper in ([(a,b),(b,2*b-a)] if contrast else [(a,b)]):
        mask=np.asarray([int(key)==k and lower<=exact_time_difference(T,t)<upper for key,t in zip(ids,times)],dtype=bool)
        masks.append(bool((obs & mask[:,None]).any(axis=0).all()))
    return all(masks)


def queries_for_history(events: EventBatch,config: RunConfig,split_seed: int,episode_id: str):
    """Value-blind post-history query sampler; returns queries and diagnostics.

    Only observed masks, timestamps and public IDs determine sampling support.
    Failed attempts keep their actual query and count; the oracle marks the
    unsupported label. Primary span failures return an explicit zero-query batch.
    """
    _check_exploratory(config)
    validate_events(events)
    d,g=config.data,config.data.generator
    root=_root(config,split_seed)
    rng=_rng(derive_seed(root,'queries',episode_id),'query_seed',str(g.query_seed))
    n=int(events.lengths[0])
    last=float(events.timestamps[0,n-1]) if n else 0.
    span=last-float(events.timestamps[0,0]) if n else 0.
    T=last+(g.delay_multiplier*span if g.population=='delayed' else 0.)
    A=T-float(events.timestamps[0,0]) if n else 0.
    population=g.population
    supported_keys=sorted({int(k) for k,o in zip(events.key_ids[0].tolist(),events.observed[0].any(-1).tolist()) if o})
    universe=_universe(config,root)
    absent=[k for k in universe if k not in supported_keys]
    tasks=[]; ids=[]; starts=[]; ends=[]
    attempts=0; failed=0
    numeric_windows=population in {'primary','delayed','change_sign','constant','impulse','random'}
    status='insufficient_span' if numeric_windows and A<2 else 'ok'
    shortfall=max(0,(12 if d.key_features=='one_hot' else g.key_load)-len(supported_keys)) if population=='presence' else 0
    if shortfall:
        status='insufficient_active_keys'
    count=0 if status=='insufficient_span' else d.queries_per_history
    # Permutation prevents query ordinal/task metadata from encoding presence.
    presence_choices=rng.permutation([True]*(count//2)+[False]*(count//2))
    for q in range(count):
        task=('mean' if q%2==0 else 'contrast') if numeric_windows else population
        if population=='change_sign': task='change_sign'
        if population in {'boundary','full_history'}: task='mean'
        if population in {'empty','same_time'}: task='presence'
        a=0.; b=0.; k=int(rng.choice(supported_keys or universe))
        if task=='presence':
            choices=(supported_keys if presence_choices[q] else absent) if population=='presence' else (supported_keys or universe)
            if not choices:
                failed+=1
                choices=universe
            k=int(rng.choice(choices))
        elif task=='interval_support':
            # Independent absent-window population, deliberately no rejection.
            k=int(rng.choice(universe))
            a=float(rng.uniform(0,max(A,1)))
            b=a+float(np.exp(rng.uniform(0,np.log(max(1,A/2)))))
        elif population=='full_history':
            b=float(np.nextafter(A,np.inf))
        elif population=='boundary':
            matching=[T-float(t) for t,key in zip(events.timestamps[0],events.key_ids[0].tolist()) if key==k]
            edge=float(rng.choice(matching or [0.]))
            if presence_choices[q]:
                a=max(0.,float(np.nextafter(edge,-np.inf)))
                b=float(np.nextafter(edge,np.inf))
            else:
                a=float(np.nextafter(edge,np.inf))
                b=float(np.nextafter(a,np.inf))
        elif numeric_windows:
            contrast=task in {'contrast','change_sign'}
            ok=False
            for _ in range(g.max_query_attempts):
                attempts+=1
                k=int(rng.choice(universe))
                w=float(np.exp(rng.uniform(np.log(max(QUERY_LAW.width_floor,A/QUERY_LAW.span_divisor)),
                                           np.log(A*QUERY_LAW.max_width_fraction))))
                a=float(rng.uniform(0,max(0,A-(2 if contrast else 1)*w)))
                b=a+w
                if _supported(events,k,T,a,b,contrast):
                    ok=True
                    break
            if not ok:
                failed+=1
        tasks.append(task);ids.append(k);starts.append(a);ends.append(b)
    if failed and status=='ok':
        status='sampling_exhausted'
    queries=QueryBatch(events.history_ids,torch.arange(count,dtype=torch.int64)[None],
                       torch.full((1,count),T,dtype=torch.float64),torch.tensor([ids],dtype=torch.uint64),
                       torch.from_numpy(_features(ids,config)[None]),(tuple(tasks),),
                       torch.tensor([starts],dtype=torch.float64),torch.tensor([ends],dtype=torch.float64),
                       torch.ones((1,count),dtype=torch.bool),torch.tensor([count],dtype=torch.int64))
    validate_queries(queries)
    return queries,{'status':status,'attempts':attempts,'failed_queries':failed,'requested_queries':d.queries_per_history,
                    'generated_queries':count,'history_span':span,'query_age_span':A,'active_key_shortfall':shortfall}


def batch_hash(batch):
    """Content hash with dtype/shape/bytes; preserves uint64 and NaN bit patterns."""
    result={}
    for name,value in vars(batch).items():
        if name=='validation':
            continue
        if isinstance(value,torch.Tensor):
            arr=value.detach().cpu().contiguous().numpy()
            result[name]={'dtype':str(arr.dtype),'shape':list(arr.shape),'sha256':hashlib.sha256(arr.tobytes()).hexdigest()}
        elif isinstance(value,dict):
            result[name]={k:(batch_hash_tensor(v) if isinstance(v,torch.Tensor) else v) for k,v in value.items()}
        else:
            result[name]=value
    return canonical_hash(result)


def batch_hash_tensor(value):
    arr=value.detach().cpu().contiguous().numpy()
    return {'dtype':str(arr.dtype),'shape':list(arr.shape),'sha256':hashlib.sha256(arr.tobytes()).hexdigest()}


def generate_episode(config: RunConfig,split_seed: int,episode_id: str) -> Episode:
    """Pure exploratory episode; sole labels come from raw-event exact_targets."""
    _check_exploratory(config)
    if type(episode_id) is not str or not episode_id:
        raise ValueError('episode_id must be nonempty')
    root=_root(config,split_seed)
    events,regime,schedule=_history(config,root,episode_id)
    queries,diagnostics=queries_for_history(events,config,split_seed,episode_id)
    oracle=exact_targets(events,queries)
    metadata={'generator_version':GENERATOR_VERSION,'seed_version':SEED_VERSION,'feature_version':FEATURE_VERSION,
              'namespace':config.data.generator.namespace,'split':config.data.generator.namespace,
              'split_root':root,'population':config.data.generator.population,
              'regime':regime,'regime_weight':.25,'robustness':config.data.generator.robustness,
              'robustness_parameters':ROBUSTNESS[config.data.generator.robustness],
              'population_parameters':population_parameters(),
              'status':diagnostics['status'],'diagnostics':diagnostics,
              'target_valid':oracle.metadata['target_valid'],'observed_counts':oracle.metadata['observed_counts'],
              'private_generator':{'excursions':schedule},
              'hashes':{'events':batch_hash(events),'queries':batch_hash(queries),'oracle':batch_hash(oracle)}}
    return Episode(events,queries,oracle.target,oracle.supported,metadata)
