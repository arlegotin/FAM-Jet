"""Packed retained-event references with CPU FP64 query arithmetic.

Exact is explicitly unbounded. Recent is an observed-write ring; latest_lru
keeps one whole observed event per key and evicts the least recently observed
key. Reads never refresh recency. Matching scans packed keys (no hidden index).
Missing retained evidence is NaN, not a training-mean fallback. Binary zero is
valid only when no observed event has been discarded. V32 categorical outputs
are uncalibrated one-hot scores; a later scoring wrapper owns confidence/loss.
"""
import math

import numpy as np
import torch

from famjet.data.schema import validate_events, validate_queries
from famjet.eval.oracle import exact_time_difference
from famjet.memory._fixed_writer import _digest_tensor, _pack_times, _require
from famjet.provenance import canonical_hash
from famjet.types import ReadResult, Snapshot

_NUMERIC = {'mean', 'contrast', 'latest', 'change_sign'}
_BINARY = {'presence', 'interval_support'}
_CATEGORY = {'corrected_categorical', 'random_binding'}


def _time(value):
    # Store the exact 64-bit representation, never a numerical int->float cast.
    if isinstance(value, np.generic):
        value = value.item()
    _require(type(value) in (int, float) and math.isfinite(value), 'timestamp must be finite int64/float64')
    tick = type(value) is int
    _require(not tick or -(2**63) <= value < 2**63, 'timestamp ticks outside int64')
    return np.array(value, dtype=np.int64 if tick else np.float64).view(np.uint64).item(), tick


def _decode(word, tick):
    return np.array(word, dtype=np.uint64).view(np.int64 if tick else np.float64).item()


def _id(value, name):
    _require(isinstance(value, (int, np.integer)) and not isinstance(value, (bool, np.bool_))
             and 0 <= int(value) < 2**64, f'{name} must be uint64')
    return int(value)


def _family(task):
    _require(task in _NUMERIC | _BINARY | _CATEGORY, 'unknown task')
    return 'categorical' if task in _CATEGORY else 'binary' if task in _BINARY else 'numeric'


def _prepare_event(store, event):
    """Validate a write transaction before any counted state can change."""
    a = store._data
    word,tick = _time(event['timestamp'])
    t = _decode(word,tick)
    key, eid = _id(event['key_id'], 'key_id'), _id(event['event_id'], 'event_id')
    value = np.asarray(event['value'], dtype=np.float64)
    observed = event.get('observed')
    observed = np.ones(store.value_dim, np.bool_) if observed is None else np.asarray(observed)
    _require(value.shape == (store.value_dim,) and np.isfinite(value).all(), 'value must be finite [V]')
    _require(observed.shape == (store.value_dim,) and observed.dtype == np.bool_, 'observed must be bool [V]')
    # Declared FP32 storage rounds once. Reject overflow before cursor,
    # recency, occupancy, timestamps or any other saved field can change.
    with np.errstate(over='ignore', invalid='ignore'):
        value = value.astype(store.value_dtype)
    _require(np.isfinite(value).all(), 'value is not finite representable in declared value_dtype')
    if a['last_valid'][0]:
        gap = exact_time_difference(t, store._last_time())
        _require(gap >= 0, 'event is before saved stream time')
        _require(gap != 0 or eid > int(a['last_event_id'][0]), 'timestamp ties require increasing event_id')
    _require(a['seen'][0] < np.iinfo(np.int64).max, 'event counter exhausted int64')
    return word,tick,key,eid,value,observed


class PackedHistory:
    """Single-history container; all changing state is in ``arrays()``.

    Event dict: timestamp, event_id, key_id, value[V], optional observed[V]
    (None means all observed). Query dict: T, key_id, task(default mean),
    age_start(default0), age_end(default0); intervals are half-open ages.
    Result shapes are [1,1,V], [1,1,1] binary, or [1,1,32] scores.
    value_dtype explicitly selects float32 or float64 storage (default float64).
    Query operands accumulate in FP64 after the one declared storage rounding.

    Slot words: key/event uint64, time uint64 + bool tick tag, declared values,
    bool observations and occupancy. Indices/counts are int64. Only latest_lru
    allocates int64 recency. Exact grows by one slot per observed write, so
    appending reallocates O(N) bytes and querying scans O(N*V); bounded policies
    allocate once, scan O(capacity), and never persist query-specific caches.
    """
    def __init__(self, capacity: int | None, value_dim: int, policy: str, *, value_dtype='float64'):
        _require(policy in {'exact', 'recent', 'latest_lru'}, 'unknown storage policy')
        _require(type(value_dim) is int and value_dim > 0, 'value_dim must be positive integer')
        _require(capacity is None if policy == 'exact' else type(capacity) is int and capacity > 0,
                 'exact requires capacity=None; bounded policy requires positive capacity')
        _require(type(value_dtype) is str and value_dtype in ('float32', 'float64'),
                 'value_dtype must be float32 or float64')
        self.capacity, self.value_dim, self.policy = capacity, value_dim, policy
        self.value_dtype = value_dtype
        c = capacity or 0
        self._data = {
            'key_ids': np.zeros(c, np.uint64), 'event_ids': np.zeros(c, np.uint64),
            'time_words': np.zeros(c, np.uint64), 'time_is_tick': np.ones(c, np.bool_),
            'values': np.zeros((c, value_dim), np.dtype(value_dtype)),
            'observed': np.zeros((c, value_dim), np.bool_), 'occupied': np.zeros(c, np.bool_),
            'size': np.zeros(1, np.int64),
            'seen': np.zeros(1, np.int64), 'discarded': np.zeros(1, np.int64),
            'last_time_word': np.zeros(1, np.uint64), 'last_time_is_tick': np.ones(1, np.bool_),
            'last_valid': np.zeros(1, np.bool_), 'last_event_id': np.zeros(1, np.uint64),
        }
        if policy == 'latest_lru':
            self._data['recency'] = np.zeros(c, np.int64)
        if policy == 'recent':
            self._data['cursor'] = np.zeros(1, np.int64)

    def arrays(self) -> dict[str, np.ndarray]:
        """Owned packed inventory including every persistent counter/index."""
        return {k: v.copy() for k,v in self._data.items()}

    def _last_time(self):
        a = self._data
        return _decode(a['last_time_word'][0], a['last_time_is_tick'][0])

    def update(self, event: dict) -> None:
        a = self._data
        word,tick,key,eid,value,observed = _prepare_event(self,event)
        if observed.any():
            slot = self._select_slot(key)
            if slot is not None:
                self._write_slot(slot,word,tick,key,eid,value,observed)
            else:
                a['discarded'][0] += 1
        self._finish_event(word,tick,eid)

    def _select_slot(self, key):
        a = self._data
        if self.policy == 'exact':
            free = np.flatnonzero(~a['occupied'])
            slot = int(free[0]) if free.size else a['occupied'].size
            if not free.size:
                for name in ('key_ids','event_ids','time_words','time_is_tick','values','observed','occupied'):
                    x = a[name]
                    a[name] = np.concatenate((x, np.zeros((1,*x.shape[1:]),dtype=x.dtype)))
        elif self.policy == 'recent':
            slot = int(a['cursor'][0])
            a['cursor'][0] = (slot+1) % self.capacity
        else:
            matches = np.flatnonzero(a['occupied'] & (a['key_ids'] == key))
            free = np.flatnonzero(~a['occupied'])
            if matches.size:
                slot = int(matches[0])
            elif free.size:
                slot = int(free[0])
            else:
                slot = min(range(self.capacity), key=lambda j:(a['recency'][j],int(a['key_ids'][j])))
            a['recency'][slot] = a['seen'][0]+1
        return slot

    def _write_slot(self,slot,word,tick,key,eid,value,observed):
        a = self._data
        if a['occupied'][slot]:
            a['discarded'][0] += 1
        else:
            a['size'][0] += 1
        a['key_ids'][slot], a['event_ids'][slot] = key,eid
        a['time_words'][slot], a['time_is_tick'][slot] = word,tick
        a['values'][slot], a['observed'][slot] = value,observed
        a['occupied'][slot] = True

    def _finish_event(self,word,tick,eid):
        a = self._data
        a['seen'][0] += 1
        a['last_time_word'][0], a['last_time_is_tick'][0] = word,tick
        a['last_event_id'][0], a['last_valid'][0] = eid,True

    def _validate_state(self):
        a=self._data; c=a['occupied'].size; size=int(a['size'][0]); seen=int(a['seen'][0]); dropped=int(a['discarded'][0])
        _require(0 <= size <= c and size == int(a['occupied'].sum()) and seen >= size+dropped and dropped >= 0,
                 'invalid occupancy/counters')
        if self.policy == 'recent':
            _require(0 <= int(a['cursor'][0]) < c, 'invalid packed cursor')
        _require(not (a['observed'] & ~a['occupied'][:,None]).any()
                 and a['observed'][a['occupied']].any(axis=1).all(), 'invalid packed observation mask')
        if self.policy == 'exact':
            _require(dropped == 0, 'exact snapshot discarded evidence')
        if self.policy == 'latest_lru':
            keys=a['key_ids'][a['occupied']]
            _require(np.unique(keys).size == size and (a['recency'][a['occupied']] > 0).all()
                     and (a['recency'] <= seen).all(), 'invalid LRU keys/recency')
        for j in np.flatnonzero(a['occupied']):
            _time(_decode(a['time_words'][j],a['time_is_tick'][j]))
            _require(exact_time_difference(self._last_time(),_decode(a['time_words'][j],a['time_is_tick'][j])) >= 0,
                     'retained event after saved stream time')

    def query(self, query: dict, *, weights=None, accumulation_dtype='float64') -> ReadResult:
        a = self._data
        word,tick = _time(query['T'])
        T = _decode(word,tick)
        if a['last_valid'][0]:
            _require(exact_time_difference(T,self._last_time()) >= 0, 'query time is before saved stream time')
        key = _id(query['key_id'], 'key_id')
        task = query.get('task','mean'); family = _family(task)
        lo,hi = query.get('age_start',0.), query.get('age_end',0.)
        _require(all(isinstance(x,(int,float)) and math.isfinite(x) for x in (lo,hi))
                 and 0 <= lo <= hi, 'age endpoints must be finite nonnegative ordered')
        # Scanning keys is the explicit packed index. Only matching slots need ages.
        slots = np.flatnonzero(a['occupied'] & (a['key_ids'] == key))
        times = [_decode(a['time_words'][j],a['time_is_tick'][j]) for j in slots]
        ages = [exact_time_difference(T,t) for t in times]
        recent = [int(j) for j,age in zip(slots,ages) if lo <= age < hi]
        older = [int(j) for j,age in zip(slots,ages) if hi <= age < 2*hi-lo]
        if weights is None:
            counts = np.stack([a['observed'][indices].sum(axis=0,dtype=np.int64) for indices in (recent,older)])
        else:
            counts = np.stack([(a['observed'][indices]*weights[indices,None]).sum(axis=0,dtype=np.dtype(accumulation_dtype))
                               for indices in (recent,older)])
        complete = not bool(a['discarded'][0])
        supported = False
        label = None
        if task in {'latest'} | _CATEGORY:
            if slots.size:
                j = max(slots,key=lambda j:(_decode(a['time_words'][j],a['time_is_tick'][j]),int(a['event_ids'][j])))
                if a['observed'][j].all():
                    label = a['values'][j].astype(np.float64); supported = True
                    if family == 'categorical':
                        _require(self.value_dim == 32 and np.isin(label,[0.,1.]).all() and label.sum()==1,
                                 'categorical tasks require observed V32 one-hot values')
        elif task in _BINARY:
            supported = bool(slots.size) if task == 'presence' else bool((counts[0] > 0).all())
            if supported or complete:
                label = np.array([float(supported)])
        elif (counts[0] > 0).all() and (task == 'mean' or (counts[1] > 0).all()):
            supported = True
            with np.errstate(over='ignore', invalid='ignore'):
                label = (np.where(a['observed'][recent],a['values'][recent],0.) *
                         (1. if weights is None else weights[recent,None])).sum(axis=0,dtype=np.dtype(accumulation_dtype))/counts[0]
                if task != 'mean':
                    label -= (np.where(a['observed'][older],a['values'][older],0.) *
                              (1. if weights is None else weights[older,None])).sum(axis=0,dtype=np.dtype(accumulation_dtype))/counts[1]
                    if task == 'change_sign' and np.isfinite(label).all():
                        label = np.sign(label)
        failure = label is not None and not np.isfinite(label).all()
        valid = label is not None and not failure
        dim = 1 if family == 'binary' else self.value_dim
        output = torch.from_numpy((np.asarray(label,dtype=np.float64) if valid else np.full(dim,np.nan)).reshape(1,1,dim).copy())
        diagnostics = {
            'prediction_valid': torch.tensor([[valid]]), 'evidence_complete': torch.tensor([[complete]]),
            'observed_counts': torch.from_numpy(counts[None,None]),
            'retained_count': torch.tensor([[int(a['size'][0])]]),
            'scanned_slots': torch.tensor([[a['occupied'].size]]),
        }
        if family == 'categorical':
            diagnostics['category_index'] = torch.tensor([[int(label.argmax()) if valid else -1]])
        return ReadResult(output if family != 'categorical' else None, output if family == 'categorical' else None,
                          torch.tensor([[supported]]), torch.tensor([[failure]]), diagnostics)


class PackedHistoryMemory:
    """CPU Snapshot adapter with declared FP32/FP64 values and FP64 queries.

    Only schema/policy lives on this object. Payload arrays stack B rows; all
    history identity, stream time, counters and retained events belong to the
    snapshot. encode/read/advance_copy own their returned storage. Public
    last_time uses the shared lossless homogeneous timestamp contract: a batch
    of mixed final times unrepresentable in one int64/float64 tensor rejects.
    Individual retained events may freely mix integer ticks and float times.
    """
    def __init__(self, capacity: int | None, value_dim: int, policy: str, *, key_dim: int, value_dtype='float64'):
        PackedHistory(capacity,value_dim,policy,value_dtype=value_dtype)
        _require(type(key_dim) is int and key_dim > 0, 'key_dim must be positive integer')
        self.capacity,self.value_dim,self.policy,self.key_dim = capacity,value_dim,policy,key_dim
        self.value_dtype = value_dtype

    def _new_store(self):
        return PackedHistory(self.capacity,self.value_dim,self.policy,value_dtype=self.value_dtype)

    def _parameter_hash(self):
        return canonical_hash({'method':'packed-history-v1','capacity':self.capacity,'value_dim':self.value_dim,
                               'policy':self.policy,'key_dim':self.key_dim,'value_dtype':self.value_dtype})

    def init_state(self, batch_size: int, *, device: str, dtype: str) -> Snapshot:
        _require(type(batch_size) is int and batch_size > 0, 'batch_size must be positive integer')
        _require(device == 'cpu' and dtype == self.value_dtype, 'state device/dtype must match declared CPU value_dtype')
        arrays = self._new_store().arrays()
        payload = {k:torch.from_numpy(np.stack([v]*batch_size)) for k,v in arrays.items()}
        payload.update(history_hash=torch.zeros(batch_size,32,dtype=torch.uint8),
                       time_unit_hash=torch.zeros(32,dtype=torch.uint8))
        return Snapshot(payload,torch.zeros(batch_size,dtype=torch.int64),torch.zeros(batch_size,dtype=torch.bool),
                        self._parameter_hash(),torch.zeros(batch_size,dtype=torch.int64))

    def _stores(self, state):
        _require(isinstance(state,Snapshot) and state.schema_version == 1
                 and state.parameter_hash == self._parameter_hash(), 'snapshot schema/parameter hash mismatch')
        b = state.last_time.numel()
        template = self._new_store()
        expected = template.arrays()
        _require(set(state.payload) == {*expected,'history_hash','time_unit_hash'}, 'invalid packed snapshot payload')
        _require(state.last_time.shape == state.valid.shape == state.event_offset.shape == (b,) and b > 0
                 and state.last_time.dtype in (torch.int64,torch.float64) and state.valid.dtype == torch.bool
                 and state.event_offset.dtype == torch.int64, 'invalid snapshot metadata layout')
        for t in (*state.payload.values(),state.last_time,state.valid,state.event_offset):
            _require(isinstance(t,torch.Tensor) and t.device.type == 'cpu' and bool(torch.isfinite(t).all()),
                     'snapshot tensors must be finite CPU tensors')
        _require(state.payload['history_hash'].shape == (b,32) and state.payload['history_hash'].dtype == torch.uint8
                 and state.payload['time_unit_hash'].shape == (32,) and state.payload['time_unit_hash'].dtype == torch.uint8,
                 'invalid snapshot identity layout')
        c = state.payload['occupied'].shape[-1] if self.policy == 'exact' else self.capacity
        for k,v in expected.items():
            shape = (c,*v.shape[1:]) if self.policy == 'exact' and k in {'key_ids','event_ids','time_words','time_is_tick','values','observed','occupied'} else v.shape
            tensor = state.payload[k]
            _require(tensor.shape == (b,*shape) and tensor.numpy().dtype == v.dtype, f'invalid packed layout: {k}')
        stores=[]
        for i in range(b):
            store = self._new_store()
            store._data = {k:state.payload[k][i].detach().numpy().copy() for k in expected}
            a=store._data; seen=int(a['seen'][0])
            _require(bool(a['last_valid'][0]) == bool(state.valid[i]) == (seen > 0)
                     and seen == int(state.event_offset[i]),
                     'snapshot stream metadata disagrees with packed state')
            _require(not state.valid[i] or store._last_time() == state.last_time[i].item(),
                     'snapshot last_time disagrees with packed state')
            store._validate_state()
            stores.append(store)
        return stores

    def _snapshot(self, stores, history_hash, unit_hash, last_time=None):
        # Exact batch rows share a physical padded capacity, counted in bytes.
        capacity = max(s._data['occupied'].size for s in stores) if self.policy == 'exact' else self.capacity
        payload={}
        for k in stores[0]._data:
            rows=[]
            for s in stores:
                x=s._data[k]
                if self.policy == 'exact' and k in {'key_ids','event_ids','time_words','time_is_tick','values','observed','occupied'}:
                    x=np.pad(x,((0,capacity-x.shape[0]), *((0,0) for _ in x.shape[1:])))
                rows.append(x)
            payload[k]=torch.from_numpy(np.stack(rows))
        payload.update(history_hash=history_hash.clone(),time_unit_hash=unit_hash.clone())
        return Snapshot(payload,_pack_times([s._last_time() for s in stores]) if last_time is None else last_time.clone(),
                        payload['last_valid'][:,0].clone(),self._parameter_hash(),payload['seen'][:,0].clone())

    def encode(self, events, state=None, *, mode='stream'):
        _require(mode in {'stream','terminal'}, 'mode must be stream or terminal')
        validate_events(events)
        _require(events.values.shape[-1] == self.value_dim and events.key_features.shape[-1] == self.key_dim,
                 'event feature dimensions mismatch')
        b=events.values.shape[0]
        if state is None: state=self.init_state(b,device='cpu',dtype=self.value_dtype)
        stores=self._stores(state)
        _require(len(stores) == b, 'snapshot batch size mismatch')
        identity=torch.stack([_digest_tensor(h) for h in events.history_ids]); unit=_digest_tensor(events.time_unit)
        if state.payload['time_unit_hash'].any():
            _require(torch.equal(identity,state.payload['history_hash']), 'snapshot history identity mismatch')
            _require(torch.equal(unit,state.payload['time_unit_hash']), 'snapshot time_unit mismatch')
        values=events.values.detach().cpu().to(torch.float64).numpy(); obs=events.observed.cpu().numpy()
        for i,s in enumerate(stores):
            for j in range(int(events.lengths[i])):
                s.update(dict(timestamp=events.timestamps[i,j].item(),event_id=events.event_ids[i,j].item(),
                              key_id=events.key_ids[i,j].item(),value=values[i,j],observed=obs[i,j]))
        return self._snapshot(stores,identity,unit)

    def advance_copy(self, state, query_time):
        stores=self._stores(state)
        if isinstance(query_time,torch.Tensor):
            _require(query_time.shape == state.last_time.shape and query_time.device.type == 'cpu'
                     and query_time.dtype in (torch.int64,torch.float64), 'query_time must be CPU int64/float64 [B]')
            targets=query_time.tolist()
        else:
            _time(query_time); targets=[query_time]*len(stores)
        for s,t in zip(stores,targets):
            word,tick=_time(t)
            if s._data['last_valid'][0]:
                _require(exact_time_difference(t,s._last_time()) >= 0, 'query time is before saved stream time')
                s._data['last_time_word'][0],s._data['last_time_is_tick'][0]=word,tick
        return self._snapshot(stores,state.payload['history_hash'],state.payload['time_unit_hash'])

    def read(self, state, queries):
        stores=self._stores(state)
        validate_queries(queries,state)
        _require(queries.key_features.shape[-1] == self.key_dim, 'query feature dimension mismatch')
        if state.payload['time_unit_hash'].any():
            _require(torch.equal(torch.stack([_digest_tensor(h) for h in queries.history_ids]),state.payload['history_hash']),
                     'query history identity mismatch')
        b,q=queries.T.shape
        families={_family(queries.tasks[i][j]) for i in range(b) for j in range(int(queries.lengths[i]))}
        _require(len(families) <= 1, 'tasks must have a homogeneous output family')
        family=next(iter(families),'numeric')
        dim=1 if family == 'binary' else self.value_dim
        output=torch.full((b,q,dim),float('nan'),dtype=torch.float64)
        support=torch.zeros(b,q,dtype=torch.bool); failure=torch.zeros_like(support)
        diagnostics={k:torch.zeros(b,q,dtype=torch.bool) for k in ('prediction_valid','evidence_complete')}
        diagnostics.update(observed_counts=torch.zeros(b,q,2,self.value_dim,dtype=torch.int64),
                           retained_count=torch.zeros(b,q,dtype=torch.int64), scanned_slots=torch.zeros(b,q,dtype=torch.int64))
        initialized=set()
        if family == 'categorical': diagnostics['category_index']=torch.full((b,q),-1,dtype=torch.int64)
        for i,s in enumerate(stores):
            for j in range(int(queries.lengths[i])):
                r=s.query(dict(T=queries.T[i,j].item(),key_id=queries.key_ids[i,j].item(),task=queries.tasks[i][j],
                               age_start=queries.age_start[i,j].item(),age_end=queries.age_end[i,j].item()))
                output[i,j]=(r.logits if family == 'categorical' else r.prediction)[0,0]
                support[i,j]=r.support[0,0]; failure[i,j]=r.failure[0,0]
                for k,v in r.diagnostics.items():
                    if k not in initialized:
                        diagnostics[k]=torch.zeros((b,q,*v.shape[2:]),dtype=v.dtype)
                        if k == 'category_index': diagnostics[k].fill_(-1)
                        initialized.add(k)
                    diagnostics[k][i,j]=v[0,0]
        return ReadResult(output if family != 'categorical' else None,output if family == 'categorical' else None,
                          support,failure,diagnostics)

    def persistent_nbytes(self, state):
        self._stores(state)
        return sum(t.numel()*t.element_size() for t in (*state.payload.values(),state.last_time,state.valid,state.event_offset))+40

    def parameter_nbytes(self):
        return 0
