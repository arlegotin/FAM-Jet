"""Versioned uniform reservoir and counted recent/reservoir ratio estimator.

Algorithm R uses unbiased bounded SplitMix64 counter draws, never a NumPy RNG.
Hybrid combines certain recent rows (weight1) with reservoir-only rows weighted
by inverse inclusion probability. This is a finite-sample biased ratio estimate,
not an unbiased mean or a confidence guarantee. Overlapping ordinals count once.
"""
import numpy as np
import torch

from famjet.memory.exact_store import PackedHistory, PackedHistoryMemory, _prepare_event, _id
from famjet.memory._fixed_writer import _require
from famjet.provenance import canonical_hash


def _precision(value, name):
    _require(type(value) is str and value in ('float32','float64'), f'{name} must be float32 or float64')


class Reservoir(PackedHistory):
    """Uniform sample of observed writes, with every restart field packed.

    value_dtype rounds each input once; accumulation_dtype declares temporary
    query sums. Seed is uint64; draw counter includes rejected bounded draws.
    Algorithm v1: SplitMix64(seed+golden_ratio*(counter+1)), reject x<2**64%n,
    otherwise return x%n. Fill C slots without draws, then draw from [0,n).
    """
    def __init__(self, capacity: int, value_dim: int, seed: int, *, value_dtype='float64', accumulation_dtype='float64'):
        super().__init__(capacity,value_dim,'recent',value_dtype=value_dtype)
        _precision(accumulation_dtype,'accumulation_dtype')
        seed=_id(seed,'seed')
        self.policy='reservoir'; self.seed=seed; self.accumulation_dtype=accumulation_dtype
        del self._data['cursor']
        self._data.update(total_writes=np.zeros(1,np.int64), rng_counter=np.zeros(1,np.uint64),
                          seed=np.array([seed],np.uint64), algorithm_version=np.array([1],np.int64),
                          write_ordinals=np.zeros(capacity,np.int64))

    def _select_slot(self, key):
        a=self._data; n=int(a['total_writes'][0])+1; counter=int(a['rng_counter'][0])
        if n <= self.capacity:
            chosen=n-1
        else:
            mask=(1<<64)-1; threshold=(1<<64)%n
            while True:
                _require(counter < mask, 'reservoir RNG counter exhausted uint64')
                x=(self.seed+0x9e3779b97f4a7c15*(counter+1))&mask; counter+=1
                x=((x^(x>>30))*0xbf58476d1ce4e5b9)&mask
                x=((x^(x>>27))*0x94d049bb133111eb)&mask; x^=x>>31
                if x >= threshold:
                    chosen=x%n; break
        a['total_writes'][0]=n; a['rng_counter'][0]=counter
        return chosen if chosen < self.capacity else None

    def _write_slot(self,slot,*args):
        super()._write_slot(slot,*args)
        self._data['write_ordinals'][slot]=self._data['total_writes'][0]

    def query(self, query):
        r=super().query(query,accumulation_dtype=self.accumulation_dtype)
        n=int(self._data['total_writes'][0]); size=int(self._data['size'][0])
        fraction=size/n if n else 1.
        r.diagnostics.update(sampling_fraction=torch.tensor([[fraction]],dtype=torch.float64),
                             sampling_uncertainty=torch.tensor([[n>size]]),
                             zero_sample=~(r.diagnostics['observed_counts'][:,:,0]>0).all(-1))
        return r

    def _validate_state(self):
        super()._validate_state()
        a=self._data; n=int(a['total_writes'][0]); occupied=a['occupied']; ordinals=a['write_ordinals'][occupied]
        _require(0 <= n <= int(a['seen'][0]) and int(a['size'][0])==min(n,self.capacity)
                 and int(a['discarded'][0])==n-int(a['size'][0]), 'invalid reservoir write counters')
        _require(int(a['seed'][0])==self.seed and int(a['algorithm_version'][0])==1,
                 'reservoir seed/algorithm mismatch')
        _require((ordinals>0).all() and (ordinals<=n).all() and np.unique(ordinals).size==ordinals.size,
                 'invalid reservoir ordinals')
        _require(int(a['rng_counter'][0]) >= max(0,n-self.capacity), 'invalid reservoir draw counter')


class HybridStore:
    """Counted ring + uniform reservoir; all nested state is a flat array map.

    v1 read: deduplicate by observed-write ordinal; weight ring rows1 and old
    reservoir-only rows n/min(n,C_reservoir). If the union retains every write,
    all weights are1 (exact control). Means/contrasts normalize weighted sums
    per coordinate. No recent-window completeness shortcut is claimed: rings
    can split simultaneous events. Latest/category selects the latest union row.
    """
    def __init__(self, recent_capacity: int, reservoir_capacity: int, value_dim: int, seed: int,
                 *, value_dtype='float64', accumulation_dtype='float64'):
        recent=PackedHistory(recent_capacity,value_dim,'recent',value_dtype=value_dtype)
        reservoir=Reservoir(reservoir_capacity,value_dim,seed,value_dtype=value_dtype,accumulation_dtype=accumulation_dtype)
        recent._data['write_ordinals']=np.zeros(recent_capacity,np.int64)
        self.recent_capacity,self.reservoir_capacity=recent_capacity,reservoir_capacity
        self.value_dim,self.value_dtype,self.seed=value_dim,value_dtype,reservoir.seed
        self.accumulation_dtype=accumulation_dtype
        self._data={**{f'recent_{k}':v for k,v in recent.arrays().items()},
                    **{f'reservoir_{k}':v for k,v in reservoir.arrays().items()},
                    **{k:v.copy() for k,v in recent.arrays().items() if k.startswith('last_') or k=='seen'},
                    'algorithm_version':np.array([1],np.int64)}

    def arrays(self):
        return {k:v.copy() for k,v in self._data.items()}

    def _last_time(self):
        from famjet.memory.exact_store import _decode
        return _decode(self._data['last_time_word'][0],self._data['last_time_is_tick'][0])

    def _children(self):
        recent=PackedHistory(self.recent_capacity,self.value_dim,'recent',value_dtype=self.value_dtype)
        reservoir=Reservoir(self.reservoir_capacity,self.value_dim,self.seed,value_dtype=self.value_dtype,
                            accumulation_dtype=self.accumulation_dtype)
        for prefix,s in (('recent_',recent),('reservoir_',reservoir)):
            s._data={k[len(prefix):]:v.copy() for k,v in self._data.items() if k.startswith(prefix)}
        return recent,reservoir

    def update(self,event):
        _prepare_event(self,event)
        recent,reservoir=self._children()
        reservoir.update(event); recent.update(event)
        if np.asarray(event.get('observed') if event.get('observed') is not None else [True]).any():
            recent._data['write_ordinals'][(int(recent._data['cursor'][0])-1)%self.recent_capacity]=reservoir._data['total_writes'][0]
        for prefix,s in (('recent_',recent),('reservoir_',reservoir)):
            self._data.update({prefix+k:v for k,v in s.arrays().items()})
        for k in ('seen','last_time_word','last_time_is_tick','last_valid','last_event_id'):
            self._data[k]=recent._data[k].copy()

    def _union(self):
        recent,reservoir=self._children(); n=int(reservoir._data['total_writes'][0])
        rows=[]; ordinals=set(); overlap=0
        for source,s in enumerate((recent,reservoir)):
            for slot in np.flatnonzero(s._data['occupied']):
                ordinal=int(s._data['write_ordinals'][slot])
                if ordinal in ordinals:
                    overlap+=1; continue
                ordinals.add(ordinal); rows.append((ordinal,source,s,slot))
        rows.sort(key=lambda x:x[0]); complete=len(rows)==n
        union=PackedHistory(self.recent_capacity+self.reservoir_capacity,self.value_dim,'recent',value_dtype=self.value_dtype)
        a=union._data; weights=np.ones(a['occupied'].size,dtype=self.accumulation_dtype)
        for j,(_,source,s,slot) in enumerate(rows):
            for k in ('key_ids','event_ids','time_words','time_is_tick','values','observed','occupied'):
                a[k][j]=s._data[k][slot]
            if source and not complete: weights[j]=n/min(n,self.reservoir_capacity)
        a['size'][0]=len(rows); a['discarded'][0]=n-len(rows)
        for k in ('seen','last_time_word','last_time_is_tick','last_valid','last_event_id'):
            a[k]=self._data[k].copy()
        return union,weights,overlap,n

    def query(self,query):
        union,weights,overlap,n=self._union()
        r=union.query(query,weights=weights,accumulation_dtype=self.accumulation_dtype)
        r.diagnostics.update(overlap_count=torch.tensor([[overlap]]),
                             sampling_fraction=torch.tensor([[min(n,self.reservoir_capacity)/n if n else 1.]],dtype=torch.float64),
                             sampling_uncertainty=~r.diagnostics['evidence_complete'],
                             zero_sample=~(r.diagnostics['observed_counts'][:,:,0]>0).all(-1))
        return r

    def _validate_state(self):
        recent,reservoir=self._children()
        recent._validate_state(); reservoir._validate_state()
        _require(int(self._data['algorithm_version'][0])==1,'hybrid algorithm mismatch')
        for k in ('seen','last_valid','last_event_id'):
            _require(np.array_equal(self._data[k],recent._data[k]) and np.array_equal(self._data[k],reservoir._data[k]),
                     'hybrid stream metadata mismatch')
        # advance_copy changes only controller time; child times remain historical.
        from famjet.eval.oracle import exact_time_difference
        _require(not self._data['last_valid'][0] or
                 all(exact_time_difference(self._last_time(),s._last_time())>=0 for s in (recent,reservoir)),
                 'hybrid child time after controller time')
        n=int(reservoir._data['total_writes'][0]); ordinals=recent._data['write_ordinals'][recent._data['occupied']]
        _require(int(recent._data['size'][0])==min(n,self.recent_capacity)
                 and set(ordinals.tolist())==set(range(max(1,n-self.recent_capacity+1),n+1)),
                 'invalid hybrid recent ordinals')
        for j in np.flatnonzero(recent._data['occupied']):
            matches=np.flatnonzero(reservoir._data['occupied'] &
                                   (reservoir._data['write_ordinals']==recent._data['write_ordinals'][j]))
            for k in matches:
                _require(all(np.array_equal(recent._data[name][j],reservoir._data[name][k])
                             for name in ('key_ids','event_ids','time_words','time_is_tick','values','observed')),
                         'hybrid overlap ordinal disagrees on retained event')
        union,_,_,_=self._union()
        union._validate_state()


class _SummaryMemory(PackedHistoryMemory):
    """Shared Task8 Snapshot machinery; only public constructor schema persists."""
    def __init__(self, factory, kwargs, *, key_dim, capacity):
        _require(type(key_dim) is int and key_dim>0,'key_dim must be positive integer')
        factory(**kwargs)  # Validate static schema before a snapshot can exist.
        self._factory,self._store_kwargs=factory,dict(kwargs)
        self.capacity,self.value_dim,self.value_dtype=capacity,kwargs['value_dim'],kwargs['value_dtype']
        self.key_dim,self.policy=key_dim,factory.__name__

    def _new_store(self):
        return self._factory(**self._store_kwargs)

    def _parameter_hash(self):
        return canonical_hash({'method':self.policy,'algorithm_version':1,'key_dim':self.key_dim,**self._store_kwargs})


class ReservoirMemory(_SummaryMemory):
    def __init__(self,capacity,value_dim,seed,*,key_dim,value_dtype='float64',accumulation_dtype='float64'):
        super().__init__(Reservoir,dict(capacity=capacity,value_dim=value_dim,seed=seed,value_dtype=value_dtype,
                                       accumulation_dtype=accumulation_dtype),key_dim=key_dim,capacity=capacity)


class HybridMemory(_SummaryMemory):
    def __init__(self,recent_capacity,reservoir_capacity,value_dim,seed,*,key_dim,value_dtype='float64',accumulation_dtype='float64'):
        super().__init__(HybridStore,dict(recent_capacity=recent_capacity,reservoir_capacity=reservoir_capacity,
                                         value_dim=value_dim,seed=seed,value_dtype=value_dtype,accumulation_dtype=accumulation_dtype),
                         key_dim=key_dim,capacity=recent_capacity+reservoir_capacity)
