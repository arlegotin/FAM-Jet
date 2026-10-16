"""Deterministic validity controls, never scientific comparison gains."""
import numpy as np
from famjet.config import RunConfig


def kernel_nullspace_fixture(ages: np.ndarray, jet_rates: np.ndarray, bank_rates: np.ndarray) -> dict:
    """Two nonnested fixed-linear kernel spans; bounded signed writes, fixed gates.

    Numerical evidence uses FP64 rank/condition limits chosen before the fixture.
    No theorem about a nonlinear learned writer or representative task dominance.
    """
    from famjet.memory.oracle import direct_moments
    ages,jr,br=(np.asarray(x,dtype=np.float64) for x in (ages,jet_rates,bank_rates))
    if any(x.ndim!=1 or not x.size or not np.isfinite(x).all() for x in (ages,jr,br)) or np.any(ages<0) or np.any(jr<=0) or np.any(br<=0):
        raise ValueError('finite nonnegative ages and positive rates required')
    zj=np.exp(-jr[:,None]*ages); hj=jr[:,None]*ages*zj; bank=np.exp(-br[:,None]*ages)
    jet=np.concatenate((zj,hj))
    result={'scope':'fixed_linear_writers','precision':'cpu_float64','ages':ages.tolist(),
            'jet_rates':jr.tolist(),'bank_rates':br.tolist(),
            'limits':{'maximum_condition':2000.,'erasure_absolute':1e-12,'minimum_other_response':.005,'rank_relative':1e-12}}
    for name,A,B in [('jet_erased',jet,bank),('bank_erased',bank,jet)]:
        _,s,vh=np.linalg.svd(A,full_matrices=True)
        rank=int(np.count_nonzero(s>s[0]*1e-12)); condition=float(s[0]/s[-1])
        if rank!=A.shape[0] or condition>2000 or A.shape[1]<=rank: raise ValueError('rank/condition limit exceeded')
        null=vh[rank:].T
        _,_,projection=np.linalg.svd(B@null,full_matrices=False)
        v=null@projection[0]; v/=max(abs(v))
        residual=float(np.linalg.norm(A@v)); response=float(np.linalg.norm(B@v))
        if residual>1e-12 or response<.005: raise ValueError('nullspace response condition failed')
        order=np.argsort(-ages); times=-ages[order]
        plus=np.column_stack((v[order],np.ones(len(v))))
        minus=np.column_stack((-v[order],np.ones(len(v))))
        zp,hp=direct_moments(times,plus,jr if name=='jet_erased' else br,0.)
        zm,hm=direct_moments(times,minus,jr if name=='jet_erased' else br,0.)
        direct=np.concatenate((zp-zm,hp-hm)) if name=='jet_erased' else zp-zm
        selected=(ages>=0)&(ages<16)
        if not selected.any(): raise ValueError('fixed diagnostic window has no events')
        result[name]={'values':v.tolist(),'rank':rank,'condition':condition,'singular_values':s.tolist(),
                      'erasure_residual':residual,'other_response':response,
                      'direct_sum_residual':float(np.linalg.norm(direct[:,0])),
                      'normalization_difference':float(np.max(abs(direct[:,1]))),
                      'window_mean_difference':float(2*v[selected].mean())}
    return result


def adversarial_events(*, load=3, span=1000.):
    """Fixed public events: rare keys/collisions, same times, gaps, signed writes.

    Load and span are independent knobs; no query or target reaches this writer.
    """
    import torch
    from famjet.types import EventBatch
    if type(load)!=int or load<2 or not np.isfinite(span) or span<=0: raise ValueError('positive span and load>=2 required')
    keys=[0,0,0]+list(range(1,load)); n=len(keys)
    times=np.concatenate(([0.,0.,span*.5],np.full(load-1,span)))
    values=np.array([3.,-3.,2.]+[float((-1)**k*(k+1)) for k in range(1,load)])
    return EventBatch(('adversarial',),torch.arange(n)[None],torch.from_numpy(times)[None],torch.tensor([keys]),
                      torch.ones(1,n,1),torch.from_numpy(values)[None,:,None],torch.tensor([n]),
                      torch.ones(1,n,dtype=torch.bool),torch.ones(1,n,1,dtype=torch.bool),'ticks')


def run_controls(config: RunConfig) -> dict:
    """Small fixed controls; independent retraining explicitly remains Task18."""
    from famjet.memory.exact_store import PackedHistory
    from famjet.memory.oracle import direct_moments
    from famjet.eval.isolation import export_method
    from famjet.models.task_model import TaskModel
    exact=PackedHistory(None,1,'exact'); ring=PackedHistory(1,1,'recent')
    for i,value in enumerate([0.,2.,10.]):
        event=dict(timestamp=float(i),event_id=i,key_id=1,value=np.array([value]),observed=np.array([True]))
        exact.update(event); ring.update(event)
    query=dict(T=2.,key_id=1,task='mean',age_start=0.,age_end=3.)
    truth=4.; e=exact.query(query).prediction.item(); r=ring.query(query).prediction.item()
    # Exercise the same scoring/paired-effect boundary used by evaluation.
    import torch
    from famjet.types import PredictionBatch
    from famjet.eval.metrics import score_predictions,history_effects
    from famjet.provenance import canonical_hash
    statistics={'schema_version':2,'split':'training','target_semantics':'observed_event_targets_v2',
                'tasks':{'mean':{'status':'ok','mean':[4.],'scale':1.,'pooled_variance':1.,
                                 'constant_coordinates':[False],'class_distribution':None}}}
    policy={'version':2,'primary_tasks':['mean'],'support_calibration':None,
            'expected_inventory':[{'history_id':'control','replicate':0,'regime':'fixed','tasks':{'mean':[0]}}],
            'task_weights':{'mean':1.},'regime_weights':{'fixed':1.}}
    scored=[]
    for method,value in [('exact',e),('ring',r),('exact_copy',e)]:
        context={'version':2,'output_convention':'numeric','present':[[True]],'tasks':[['mean']],
                 'target_valid':[[True]],'numeric_supported':[[True]],'prediction_valid':[[True]],
                 'quarantined':[[False]],'quarantine_trigger':None,'method':method,'replicate':0,'regime':'fixed',
                 'target_semantics':'observed_event_targets_v2','manifest_hash':canonical_hash({'fixture':'ring-v1'}),
                 'statistics_hash':canonical_hash(statistics)}
        batch=PredictionBatch(('control',),torch.tensor([[0]]),torch.tensor([[[value]]]),torch.tensor([[[truth]]]),
                              torch.ones(1,1,dtype=torch.bool),torch.zeros(1,1,dtype=torch.bool),torch.zeros(1,1,dtype=torch.bool),{'scoring_v2':context})
        scored.extend(score_predictions(batch,statistics,policy))
    effect=history_effects(scored,('ring','exact')).item()
    aa=history_effects(scored,('exact','exact_copy')).item()
    aa_swapped=history_effects(scored,('exact_copy','exact')).item()
    # Recent mean10 minus preceding mean2=8; reversing interval labels gives -8.
    contrast=exact.query({**query,'task':'contrast','age_end':1.}).prediction.item()
    z,h=direct_moments(np.array([0.,1.]),np.array([[2.],[3.]]),np.array([.5]),2.)
    hand=.5*2*np.exp(-1)*2+.5*np.exp(-.5)*3
    wrong_moment_error=float(abs(-h.item()-hand))
    class QueryLeakingWriter(TaskModel):
        pass
    from famjet.train import make_model
    from dataclasses import replace
    cpu=replace(config,resources=replace(config.resources,device='cpu'))
    base=make_model(cpu)
    leaked=QueryLeakingWriter(base.kernel,base.reader,cpu)
    leaked.eventual_query=query  # forbidden history-time access even before a read
    try: export_method(leaked)
    except ValueError: leak_status='rejected'
    else: leak_status='FAILED'
    return {'schema_version':1,'fixture':'deterministic_harness_v1','seed':None,'scientific_comparison':False,
            'aa':{'expected':0.,'effect':aa},
            'aa_swapped':{'expected':0.,'effect':aa_swapped},
            'exact_vs_ring':{'expected':'positive','effect':effect,'target':truth,'exact':e,'ring':r},
            'wrong_moment_sign':{'expected':'detected','status':'detected' if wrong_moment_error>1 else 'FAILED','error':wrong_moment_error},
            'reversed_temporal_labels':{'expected':'detected','status':'detected' if abs(-contrast-8)>1 else 'FAILED','correct':contrast,'reversed':-contrast},
            'leaked_writer':{'expected':'rejected','status':leak_status,'boundary':'closed isolated writer registry'},
            'independent_retraining':{'status':'pending_task18','reason':'requires independent real training runs; no label-bias claim'}}
