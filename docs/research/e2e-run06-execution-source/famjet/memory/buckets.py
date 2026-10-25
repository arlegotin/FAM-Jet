"""Fixed-capacity temporal buckets with an explicit overlap-fraction decoder.

No approximation bound: merged writes are spread uniformly over their span for
numeric interval reads. Estimated positive mass is not factual interval evidence.
All per-coordinate sums/counts, exact endpoint bits, recency and loss counters
are packed. ``arrays()`` exposes these same buckets for a future learned reader.
"""
import math

import numpy as np
import torch

from famjet.eval.oracle import exact_time_difference
from famjet.memory.exact_store import PackedHistory, _prepare_event, _time, _decode, _id, _family, _CATEGORY
from famjet.memory.reservoir import _SummaryMemory, _precision
from famjet.memory._fixed_writer import _require
from famjet.types import ReadResult


class TemporalBuckets(PackedHistory):
    """Singleton writes compacted by minimum-span adjacent same-key merges.

    Neighbors are within each key's chronological sequence, including the new
    singleton. Global ties order by oldest time, newest time, uint64 key, slots.
    With no pair, evict every bucket for the least-recently-observed existing key
    (tie uint64 key). Reads never refresh recency. Input value_dtype and stored
    sum/decoder accumulation_dtype are independent, explicit precision choices.
    """
    def __init__(self,capacity: int,value_dim: int,*,value_dtype='float64',accumulation_dtype='float64',normalization='independent'):
        super().__init__(capacity,value_dim,'recent',value_dtype=value_dtype)
        _precision(accumulation_dtype,'accumulation_dtype')
        _require(type(normalization) is str and normalization in ('shared','independent'),'normalization must be shared or independent')
        self.policy='buckets'; self.accumulation_dtype=accumulation_dtype; self.normalization=normalization
        del self._data['cursor']
        self._data['values']=np.zeros((capacity,value_dim),dtype=accumulation_dtype)
        width=1 if normalization=='shared' else value_dim
        self._data['observed']=np.zeros((capacity,width),np.bool_)
        self._data.update(end_time_words=np.zeros(capacity,np.uint64),end_time_is_tick=np.ones(capacity,np.bool_),
                          counts=np.zeros((capacity,width),np.int64),
                          recency=np.zeros(capacity,np.int64),sum_failed=np.zeros((capacity,value_dim),np.bool_),
                          total_writes=np.zeros(1,np.int64),merges=np.zeros(1,np.int64),
                          evicted_keys=np.zeros(1,np.int64),algorithm_version=np.array([1],np.int64))
        if normalization=='independent': self._data['event_counts']=np.zeros(capacity,np.int64)

    def _slot_fields(self):
        return ('key_ids','event_ids','time_words','time_is_tick','values','observed','occupied',
                'end_time_words','end_time_is_tick','counts','recency','sum_failed',
                *(('event_counts',) if self.normalization=='independent' else ()))

    def _event_counts(self,a):
        return a['counts'][:,0] if self.normalization=='shared' else a['event_counts']

    def update(self,event):
        word,tick,key,eid,value,observed=_prepare_event(self,event); a=self._data
        _require(self.normalization!='shared' or bool((observed==observed[0]).all()),
                 'shared normalization requires identical observation masks across coordinates')
        if not observed.any():
            self._finish_event(word,tick,eid); return
        # The extra singleton is temporary work, never surviving an update.
        temp={k:np.concatenate((a[k],np.zeros((1,*a[k].shape[1:]),dtype=a[k].dtype))) for k in self._slot_fields()}
        c=self.capacity; temp['occupied'][c]=True
        temp['key_ids'][c]=key; temp['event_ids'][c]=eid
        temp['time_words'][c]=temp['end_time_words'][c]=word
        temp['time_is_tick'][c]=temp['end_time_is_tick'][c]=tick
        temp['counts'][c]=observed[:1] if self.normalization=='shared' else observed
        temp['observed'][c]=temp['counts'][c]>0
        with np.errstate(over='ignore',invalid='ignore'):
            temp['values'][c]=np.where(observed,value,0.)
        if self.normalization=='independent': temp['event_counts'][c]=1
        temp['recency'][c]=a['seen'][0]+1
        # Narrower sums can overflow even if retained-value precision accepts.
        temp['sum_failed'][c]=~np.isfinite(temp['values'][c])
        temp['values'][c]=np.where(temp['sum_failed'][c],0.,temp['values'][c])
        merges=0; evicted_keys=0; discarded=0
        if int(a['size'][0])==c:
            pairs=[]
            for candidate in np.unique(temp['key_ids'][temp['occupied']]):
                slots=np.flatnonzero(temp['occupied'] & (temp['key_ids']==candidate)).tolist()
                slots.sort(key=lambda j:(_decode(temp['time_words'][j],temp['time_is_tick'][j]),
                                         _decode(temp['end_time_words'][j],temp['end_time_is_tick'][j]),
                                         int(temp['event_ids'][j])))
                for left,right in zip(slots,slots[1:]):
                    oldest=_decode(temp['time_words'][left],temp['time_is_tick'][left])
                    newest=_decode(temp['end_time_words'][right],temp['end_time_is_tick'][right])
                    pairs.append((exact_time_difference(newest,oldest),oldest,newest,int(candidate),left,right))
            if pairs:
                *_,left,right=min(pairs)
                with np.errstate(over='ignore',invalid='ignore'):
                    summed=temp['values'][left]+temp['values'][right]
                temp['sum_failed'][left] |= temp['sum_failed'][right] | ~np.isfinite(summed)
                temp['values'][left]=np.where(temp['sum_failed'][left],0.,summed)
                temp['counts'][left]+=temp['counts'][right]
                temp['observed'][left]=temp['counts'][left]>0
                if self.normalization=='independent': temp['event_counts'][left]+=temp['event_counts'][right]
                for k in ('end_time_words','end_time_is_tick','event_ids','recency'):
                    temp[k][left]=temp[k][right]
                temp['occupied'][right]=False; merges=1
            else:
                keys=np.unique(a['key_ids'][a['occupied']])
                evict=min(keys,key=lambda k:(int(a['recency'][a['occupied'] & (a['key_ids']==k)].max()),int(k)))
                slots=np.flatnonzero(temp['occupied'] & (temp['key_ids']==evict))
                discarded=int(self._event_counts(temp)[slots].sum()); temp['occupied'][slots]=False; evicted_keys=1
        # Compact occupied rows deterministically; unused rows are fully zeroed.
        slots=np.flatnonzero(temp['occupied']); size=slots.size
        for k in self._slot_fields():
            a[k].fill(0); a[k][:size]=temp[k][slots]
        a['size'][0]=size; a['total_writes'][0]+=1; a['merges'][0]+=merges
        a['discarded'][0]+=discarded; a['evicted_keys'][0]+=evicted_keys
        self._finish_event(word,tick,eid)

    def query(self,query):
        a=self._data; word,tick=_time(query['T']); T=_decode(word,tick)
        _require(not a['last_valid'][0] or exact_time_difference(T,self._last_time())>=0,
                 'query time is before saved stream time')
        key=_id(query['key_id'],'key_id'); task=query.get('task','mean'); family=_family(task)
        lo,hi=query.get('age_start',0.),query.get('age_end',0.)
        _require(all(isinstance(x,(int,float)) and math.isfinite(x) for x in (lo,hi)) and 0<=lo<=hi,
                 'age endpoints must be finite nonnegative ordered')
        slots=np.flatnonzero(a['occupied'] & (a['key_ids']==key))
        weights=np.zeros((2,self.capacity),dtype=self.accumulation_dtype)
        certificates=np.zeros((2,self.capacity),dtype=np.bool_); partial=np.zeros(2,dtype=np.bool_)
        for j in slots:
            young=exact_time_difference(T,_decode(a['end_time_words'][j],a['end_time_is_tick'][j]))
            old=exact_time_difference(T,_decode(a['time_words'][j],a['time_is_tick'][j]))
            for k,(start,end) in enumerate(((lo,hi),(hi,2*hi-lo))):
                inside=start<=young and old<end
                certificates[k,j]=inside
                if old==young:
                    weights[k,j]=float(start<=young<end)
                else:
                    overlap=max(0,exact_time_difference(min(old,end),max(young,start)))
                    weights[k,j]=float(overlap/exact_time_difference(old,young))
                    partial[k] |= bool(weights[k,j]>0 and not inside)
        with np.errstate(over='ignore',invalid='ignore',divide='ignore'):
            counts=weights@a['counts'].astype(self.accumulation_dtype)
            sums=weights@a['values']
        certified=np.stack([a['counts'][mask].sum(axis=0,dtype=np.int64) for mask in certificates])
        if self.normalization=='shared':
            counts=np.broadcast_to(counts,(2,self.value_dim)).copy()
            certified=np.broadcast_to(certified,(2,self.value_dim)).copy()
        complete=not bool(a['discarded'][0] or a['merges'][0]); supported=False; label=None; selected_failure=False
        if task in {'latest'} | _CATEGORY:
            if slots.size:
                j=max(slots,key=lambda j:(_decode(a['end_time_words'][j],a['end_time_is_tick'][j]),int(a['event_ids'][j])))
                if self._event_counts(a)[j]==1 and a['observed'][j].all():
                    label=a['values'][j].astype(np.float64); supported=True
                    selected_failure=bool(a['sum_failed'][j].any())
                    if family=='categorical' and not selected_failure:
                        _require(self.value_dim==32 and np.isin(label,[0.,1.]).all() and label.sum()==1,
                                 'categorical tasks require observed V32 one-hot values')
        elif family=='binary':
            supported=bool(slots.size) if task=='presence' else bool((certified[0]>0).all())
            if supported or complete: label=np.array([float(supported)])
        else:
            contrast=task!='mean'; needed=2 if contrast else 1
            supported=bool((certified[:needed]>0).all())
            if (counts[:needed]>0).all():
                with np.errstate(over='ignore',invalid='ignore',divide='ignore'):
                    label=sums[0]/counts[0]
                    if contrast: label=label-sums[1]/counts[1]
                    if task=='change_sign' and np.isfinite(label).all(): label=np.sign(label)
        relevant=2 if task in {'contrast','change_sign'} else 1
        arithmetic_failure=bool(((weights[:relevant,:,None]>0)&a['sum_failed'][None]).any()) if family=='numeric' and task!='latest' else False
        failure=selected_failure or arithmetic_failure or (label is not None and not np.isfinite(label).all())
        valid=label is not None and not failure; dim=1 if family=='binary' else self.value_dim
        output=torch.from_numpy((np.asarray(label,dtype=np.float64) if valid else np.full(dim,np.nan)).reshape(1,1,dim).copy())
        diagnostics=dict(prediction_valid=torch.tensor([[valid]]),evidence_complete=torch.tensor([[complete]]),
                         observed_counts=torch.from_numpy(counts.astype(np.float64)[None,None]),
                         estimated_count=torch.from_numpy(counts.astype(np.float64)[None,None]),
                         certified_counts=torch.from_numpy(certified[None,None]),certified_support=torch.tensor([[supported]]),
                         partial_overlap=torch.tensor([[bool(partial[:relevant].any()) if family=='numeric' and task!='latest' else bool(partial[0]) if task=='interval_support' else False]]),approximate=torch.tensor([[bool(a['merges'][0])]]),
                         retained_count=torch.tensor([[int(a['size'][0])]]),scanned_slots=torch.tensor([[self.capacity]]))
        if family=='categorical': diagnostics['category_index']=torch.tensor([[int(label.argmax()) if valid else -1]])
        return ReadResult(output if family!='categorical' else None,output if family=='categorical' else None,
                          torch.tensor([[supported]]),torch.tensor([[failure]]),diagnostics)

    def _validate_state(self):
        super()._validate_state(); a=self._data; occupied=a['occupied']; n=int(a['total_writes'][0]); event_counts=self._event_counts(a)
        _require(int(a['algorithm_version'][0])==1,'bucket algorithm mismatch')
        _require(0<=n<=int(a['seen'][0]) and int(a['merges'][0])>=0 and int(a['evicted_keys'][0])>=0
                 and int(event_counts.sum())+int(a['discarded'][0])==n,'invalid bucket counters')
        _require((a['counts']>=0).all() and (a['counts']<=event_counts[:,None]).all()
                 and np.array_equal(a['observed'],a['counts']>0) and (event_counts[occupied]>0).all()
                 and (event_counts[~occupied]==0).all(),'invalid bucket coordinate counts')
        _require((a['recency'][occupied]>0).all() and (a['recency']<=a['seen'][0]).all(),'invalid bucket recency')
        for j in np.flatnonzero(occupied):
            newest=_decode(a['end_time_words'][j],a['end_time_is_tick'][j]); _time(newest)
            _require(exact_time_difference(newest,_decode(a['time_words'][j],a['time_is_tick'][j]))>=0
                     and exact_time_difference(self._last_time(),newest)>=0,'invalid bucket endpoints')


class TemporalBucketsMemory(_SummaryMemory):
    def __init__(self,capacity,value_dim,*,key_dim,value_dtype='float64',accumulation_dtype='float64',normalization='independent'):
        super().__init__(TemporalBuckets,dict(capacity=capacity,value_dim=value_dim,value_dtype=value_dtype,
                                             accumulation_dtype=accumulation_dtype,normalization=normalization),key_dim=key_dim,capacity=capacity)

    def bucket_arrays(self,state):
        """Owned per-history packed bucket features; no privileged raw-event view."""
        return tuple(store.arrays() for store in self._stores(state))
