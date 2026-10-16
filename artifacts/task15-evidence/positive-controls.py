"""Tiny exploratory learning controls; not convergence/competitiveness evidence."""
import json,sys,time,resource
from pathlib import Path
import torch
from dataclasses import replace
from famjet.memory.delta import DeltaMixer
from famjet.train import make_model,make_optimizer
from famjet.config import load_config,DeltaConfig
from famjet.types import EventBatch,QueryBatch,Episode

torch.set_num_threads(1); torch.manual_seed(1501)
out=Path(sys.argv[1]); rows=[]
# Native D-token event mixer: retain a signed random value across a neutral token.
# Random orthogonal basis activates dense native input/output coordinates.
rotation=torch.linalg.qr(torch.randn(8,8)).Q
train_rng=torch.Generator().manual_seed(1502); held_rng=torch.Generator().manual_seed(1503)
def native_batch(rng,b):
    value=torch.randn(b,generator=rng)
    raw=torch.zeros(b,4,8)
    raw[:,0,0]=value; raw[:,0,1]=1
    raw[:,1:3,2]=1; raw[:,3,3]=1
    return raw @ rotation, value[:,None]*rotation[4]
held=native_batch(held_rng,128)
m=DeltaMixer(3,1,dim=8,head_key_dim=4,head_value_dim=4,erase_policy='pinned_guarded')
native_params=[p for n,p in m.named_parameters() if not n.startswith(('event_adapter','query_adapter'))]
opt=torch.optim.AdamW(native_params,lr=.01,weight_decay=0)
def native_loss(batch):
    y,_=m.native_sequence(batch[0]); return (y[:,-1]-batch[1]).square().mean()
start=time.perf_counter()
with torch.no_grad(): initial=float(native_loss(held))
for step in range(201):
    if step:
        opt.zero_grad(); loss=native_loss(native_batch(train_rng,16)); loss.backward(); opt.step()
    if step%50==0:
        with torch.no_grad(): rows.append({'control':'native_event_mixer_signed_retention','step':step,'heldout_mse':float(native_loss(held))})
with torch.no_grad(): final=float(native_loss(held))
rows.append({'control':'native_event_mixer_signed_retention','initial':initial,'final':final,
             'seconds':time.perf_counter()-start,'steps':200,'seeds':[1501,1502,1503],
             'active_parameters':sum(p.numel() for p in native_params),'adapter_parameters_excluded_from_native_control':sum(p.numel() for n,p in m.named_parameters() if n.startswith(('event_adapter','query_adapter'))),
             'claim':'excluded-episode retention control only; no scientific convergence'})
# Deferred adaptation: full-window mean of four independent values, same key.
c=load_config(Path('configs/smoke.yaml'))
c=replace(c,data=replace(c.data,key_dim=1,key_features='dense',value_dim=1,length=4,queries_per_history=2),
    model=replace(c.model,method='delta',K=1,J=None,rates=None,writer='native_delta',encode='stream',
        delta=DeltaConfig(dim=8,head_key_dim=4,head_value_dim=4,erase_policy='pinned_guarded'),
        reader=replace(c.model.reader,kind='delta_mixer',width=16,layers=1)))
train_rng=torch.Generator().manual_seed(1505); held_rng=torch.Generator().manual_seed(1506)
def deferred_batch(rng,b,prefix):
    val=torch.randn(b,4,1,generator=rng)
    ids=tuple(f'{prefix}-{i}' for i in range(b))
    e=EventBatch(ids,torch.arange(4).expand(b,-1).clone(),torch.arange(4).expand(b,-1).clone(),
        torch.zeros(b,4,dtype=torch.int64),torch.ones(b,4,1),val,torch.full((b,),4),
        torch.ones(b,4,dtype=torch.bool),torch.ones(b,4,1,dtype=torch.bool),'ticks')
    q=QueryBatch(ids,torch.zeros(b,1,dtype=torch.int64),torch.full((b,1),4),torch.zeros(b,1,dtype=torch.int64),
        torch.ones(b,1,1),tuple(('mean',) for _ in range(b)),torch.zeros(b,1,dtype=torch.float64),
        torch.full((b,1),4.,dtype=torch.float64),torch.ones(b,1,dtype=torch.bool),torch.ones(b,dtype=torch.int64))
    return Episode(e,q,val.mean(1,keepdim=True),torch.ones(b,1,dtype=torch.bool),metadata={'split':'training' if prefix=='train' else 'development_fit'})
torch.manual_seed(1504); m=make_model(c); opt=make_optimizer(m,replace(c,training=replace(c.training,learning_rate=.003,weight_decay=0)))
m.fit_statistics([deferred_batch(train_rng,16,'train')])
held=deferred_batch(held_rng,64,'held')
def deferred_loss(ep): return (m(ep.events,ep.queries,encode_mode='stream').prediction-ep.labels).square().mean()
with torch.no_grad(): initial=float(deferred_loss(held))
start=time.perf_counter()
for step in range(151):
    if step:
        ep=deferred_batch(train_rng,8,'train'); opt.zero_grad(); loss=deferred_loss(ep); loss.backward(); opt.step()
    if step%50==0:
        with torch.no_grad(): rows.append({'control':'deferred_full_window_mean','step':step,'heldout_mse':float(deferred_loss(held))})
with torch.no_grad(): final=float(deferred_loss(held))
rows.append({'control':'deferred_full_window_mean','initial':initial,'final':final,'seconds':time.perf_counter()-start,
             'steps':150,'seeds':[1504,1505,1506],'allocated_parameters':sum(p.numel() for p in m.parameters()),
             'claim':'excluded-history basic learning only; no scientific convergence'})
rows.append({'cpu_rss_highwater_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
             'precision':'float32','device':'cpu','scope':'tiny synthetic development controls; fallback0/fastmath0; no protected data'})
out.write_text(json.dumps(rows,indent=2)+'\n'); print(json.dumps(rows,indent=2))
assert all(r['final']<r['initial']*.5 for r in rows if 'initial' in r)
