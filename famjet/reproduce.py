"""Bounded, non-scientific supplementary source controls and exclusion records.

No entrypoint here registers a deferred-query memory or opens protected data.
The dedicated RunConfig subtype leaves ordinary config hashes/seals unchanged.
"""
import argparse
from dataclasses import asdict, dataclass
from decimal import Decimal, localcontext
from fractions import Fraction
import hashlib
import io
import math
from pathlib import Path
import platform
import resource
import time
import traceback
import numpy as np
import torch
import yaml
from famjet.artifacts import atomic_json, atomic_bytes, append_jsonl
from famjet.config import RunConfig, _UniqueLoader, _parse
from famjet.provenance import canonical_hash
from famjet.memory.gaver import stehfest_weights, gaver_rates, gaver_step, reconstruct
from famjet.memory.associative_hippo import OriginalAssociativeHiPPO, token_table, associative_episodes

ROOT=Path(__file__).resolve().parents[1]
SOURCES={
    'gaver':dict(record='R04/R22',repository='cogneuroai/time-local-transformer',
        commit='99a1a04eb67771a4b1c4b05f7909e1697b8b94ae',
        blob='a380990b7add55b4f0109ad03a8d2d40ae5b3b31',license='source permission unresolved',
        implementation='independent specification equations; no source reuse'),
    'associative':dict(record='R07',repository='jackgoffinet/hippo-zoo',
        commit='04e38b3cf246f4c50cb6c6a7e10597e2e37eebc7',
        model_blob='35acec2230e392d80e2fe8a68c3028cf97a8afd8',
        task_blob='496617838c7065f61252b8193e7cc90e6609c44a',
        script_blob='d7424b3c9037071ced23d0228477c9b4d6fba95c',
        license='MIT',copyright='2026 Jack Goffinet',implementation='independent equations; no source copied')}
EXCLUSIONS={
    'gaver_deferred':'No registered deferred-query writer/reader/snapshot adaptation or trained acceptance; equation control only.',
    'associative_deferred':'External query has no original source interface; causal adaptation and protocol/reader acceptance unentered, regardless of original control outcome.',
    'compact_gru_routing':'No evidence-based architecture/inclusion amendment; supplementary inventory narrowed before confirmation.',
    'gaver_source_reuse':'R22 has no established repository source license; source reuse blocked, independent equations permitted.'}


@dataclass(frozen=True)
class AssociativeControlPolicy:
    token_seed: int
    train_data_seed: int
    eval_data_seed: int
    initialization_seed: int
    train_draw_seed: int
    train_episodes: int
    eval_episodes: int
    max_steps: int
    learning_rate: float
    weight_decay: float
    min_retrieval_accuracy: float
    min_cosine: float
    max_prior_mse_fraction: float
    require_latest_b_improvement: bool


@dataclass(frozen=True)
class ReproductionPolicy:
    version: int
    purpose: str
    methods: tuple[str,...]
    gaver_evaluations: int
    gaver_lags: tuple[float,...]
    max_seconds: float
    additional_peak_limit_bytes: int
    pilot_steps: int
    associative: AssociativeControlPolicy


@dataclass(frozen=True)
class ReproductionRunConfig(RunConfig):
    reproduction: ReproductionPolicy

    def __post_init__(self):
        super().__post_init__()
        p=self.reproduction; a=p.associative
        if (self.phase!='smoke' or self.resources.device!='cpu' or p.version!=1
                or p.purpose!='standalone_source_controls_not_scientific_training'):
            raise ValueError('source controls require explicit version1 CPU smoke-only policy')
        if not p.methods or len(set(p.methods))!=len(p.methods) or any(m not in {*EXCLUSIONS,'gaver_equations','associative_original'} for m in p.methods):
            raise ValueError('unknown or duplicate reproduction method')
        if p.gaver_evaluations!=12 or p.gaver_lags!=(1.,2.):
            raise ValueError('registered numerical fixture requires N12 and lags1,2')
        if not 0<p.max_seconds<=600 or not 0<p.additional_peak_limit_bytes<=self.resources.smoke_additional_allocation_limit_bytes:
            raise ValueError('bounded time/allocation within existing smoke ceiling required')
        if not 1<=p.pilot_steps<=3 or not 1<=a.max_steps<=3500:
            raise ValueError('bounded pilot/fixed stopping required')
        if not 1<=a.train_episodes<=10000 or not 1<=a.eval_episodes<=256:
            raise ValueError('bounded source episode counts required')
        if any(not 0<=getattr(a,n)<2**63 for n in ('token_seed','train_data_seed','eval_data_seed','initialization_seed','train_draw_seed')):
            raise ValueError('source seeds must be nonnegative int64')
        if a.train_data_seed==a.eval_data_seed: raise ValueError('excluded evaluation seed required')
        if a.learning_rate!=.001 or a.weight_decay!=.0001:
            raise ValueError('source optimizer policy must be AdamW lr1e-3 decay1e-4')
        if (a.min_retrieval_accuracy!=.5 or a.min_cosine!=.5 or a.max_prior_mse_fraction!=.75
                or not a.require_latest_b_improvement):
            raise ValueError('predeclared final-Write acceptance thresholds may not be weakened')


def load_reproduction_config(path: Path) -> ReproductionRunConfig:
    value=yaml.load(Path(path).read_text(),Loader=_UniqueLoader)
    return _parse(value,ReproductionRunConfig,'config')


def _hash_array(x):
    return hashlib.sha256(x.tobytes(order='C')).hexdigest()


def _peak_bytes():
    peak=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return int(peak if platform.system()=='Darwin' else peak*1024)


def _high_precision(n, *, age=.7, lag=1., transform='impulse'):
    """Independent exact factorial rationals, then Decimal80 transcendental math."""
    with localcontext() as ctx:
        ctx.prec=80
        m=n//2; total=Decimal(0); coeff=[]
        tau=Decimal(str(lag)); age=Decimal(str(age)); ln2=Decimal(2).ln()
        for k in range(1,n+1):
            rational=sum((Fraction(j**(m+1)*math.factorial(2*j),
                math.factorial(m-j)*math.factorial(j)**2*math.factorial(k-j)*math.factorial(2*j-k))
                for j in range((k+1)//2,min(k,m)+1)),Fraction())*(-1)**(k+m)
            eta=Decimal(rational.numerator)/Decimal(rational.denominator)*ln2
            coeff.append(float(eta)); s=Decimal(k)*ln2/tau
            if transform=='impulse': F=(-s*age).exp()
            elif transform=='exponential': F=1/(s+1)
            elif transform=='constant_zoh': F=(1-(-s*age).exp())/s
            else: raise ValueError('unknown reference transform')
            total+=eta*F/tau
        return float(total),coeff


def _gaver_control(p):
    n=p.gaver_evaluations; taus=p.gaver_lags
    reference,weights=_high_precision(n)
    rows=[]; errors={}; passed=True
    for dtype in (np.float32,np.float64):
        start=time.perf_counter(); rates=gaver_rates(taus,n,dtype=dtype)
        eta=stehfest_weights(n).astype(dtype)
        preparation=time.perf_counter()-start
        initial=np.zeros((len(taus),n,1),dtype=dtype)
        state=gaver_step(initial,np.ones(1,dtype=dtype),0.,rates,mode='impulse')
        state=gaver_step(state,np.zeros(1,dtype=dtype),.7,rates,mode='impulse')
        prediction=reconstruct(state,taus,mode='impulse')[0,0].item()
        errors[np.dtype(dtype).name]=abs(prediction-reference)
        zoh=gaver_step(initial,np.ones(1,dtype=dtype),1.,rates,mode='zoh_current_interval')
        zoh_value=reconstruct(zoh,taus,mode='zoh_current_interval')[0,0].item()
        zoh_reference,_=_high_precision(n,age=1.,transform='constant_zoh')
        exprecon=float(np.sum(eta/(rates[0]+1)))
        exponential_reference,_=_high_precision(n,transform='exponential')
        start=time.perf_counter()
        for _ in range(200):
            gaver_step(initial,np.ones(1,dtype=dtype),1.,rates,mode='impulse')
        ingest_seconds=(time.perf_counter()-start)/200
        start=time.perf_counter()
        for _ in range(200): reconstruct(state,taus,mode='impulse')
        read_seconds=(time.perf_counter()-start)/200
        if dtype==np.float64:
            passed &= (errors['float64']<1e-8 and abs(zoh_value-zoh_reference)<1e-8
                       and abs(exprecon-exponential_reference)<1e-8)
        rows.append(dict(precision=np.dtype(dtype).name,device='cpu',state_bytes=state.nbytes,
            static_rates_bytes=rates.nbytes,static_weights_bytes=eta.nbytes,
            static_lags_bytes=len(taus)*np.dtype(dtype).itemsize,
            retained_rate_count=int(rates.size),deduplication=False,
            preparation_seconds=preparation,mean_ingest_seconds=ingest_seconds,mean_reconstruct_seconds=read_seconds,
            timing_repetitions=200,impulse_prediction=prediction,zoh_prediction=zoh_value,
            zoh_absolute_error=abs(zoh_value-zoh_reference),
            exponential_inverse_prediction=exprecon,exponential_finite_N_error=abs(exprecon-math.exp(-1))))
    return dict(status='component_passed' if passed else 'component_unaccepted',
        modes=['impulse','zoh_current_interval'],precision_frontier=rows,
        cancellation=dict(reference=reference,float32_absolute_error=errors['float32'],float64_absolute_error=errors['float64']),
        coefficient_max_absolute_error=float(np.max(np.abs(stehfest_weights(n)-weights))),
        reference='exact factorial Fraction + Decimal80; finite-N kernel, not Dirac pointwise label',
        input_units=dict(impulse='event measure; dimensionless reader uses t_ref*fhat',zoh_current_interval='current sample covers preceding interval; fhat already signal units'),
        acceptance='CPU FP64 impulse, ZOH and exponential-transform finite-N errors <1e-8; FP32 cancellation reported, not accepted as equivalent')


def _source_fixture_policy(a):
    return dict(episode_length=12,A_tokens=12,B_tokens=12,embedding_dim=24,channels=32,
        history_order=32,associative_order=32,timescale=2.,gate_hidden=256,precision='cpu_float32',
        discretization='exact ZOH dt1',initializer='all Linear weights and present biases uniform +-1/sqrt(fan_in), torch local seed',
        numpy_rng='default_rng: separate token table/train episode/eval episode/train draw streams',
        torch_version=str(torch.__version__),numpy_version=np.__version__,optimizer='AdamW',
        optimizer_betas=[.9,.999],optimizer_eps=1e-8,amsgrad=False,foreach=False,fused=False,
        batch_size=1,loss='mean all12 steps and24 coordinates',schedule='constant',gradient_clip=None,
        stopping='fixed max_steps; only resource/nonfinite failures may stop early',
        gradient='full12-step autograd; no detach/truncation',evaluation='final only, excluded histories using same token table',
        resolved=asdict(a))


def _associative_control(p, out):
    a=p.associative; start=time.perf_counter(); peak0=_peak_bytes()
    result=dict(status='component_unaccepted',steps_completed=0,state_bytes=32*(32+32)*4,
                fixture=_source_fixture_policy(a),failure=None)
    ledger=out/'trials.jsonl'
    def guard(stage):
        observation=dict(stage=stage,elapsed_seconds=time.perf_counter()-start,
                         process_peak_bytes=_peak_bytes(),additional_peak_bytes=max(0,_peak_bytes()-peak0))
        if observation['elapsed_seconds']>p.max_seconds or observation['additional_peak_bytes']>p.additional_peak_limit_bytes:
            append_jsonl(ledger,dict(event='resource_failure',**observation))
            raise RuntimeError('bounded source-control resource guard exceeded')
        return observation
    def optimizer(model):
        return torch.optim.AdamW(model.parameters(),lr=a.learning_rate,weight_decay=a.weight_decay,
                                 betas=(.9,.999),eps=1e-8,foreach=False,fused=False)
    def update(model,opt,x,y):
        opt.zero_grad(set_to_none=True)
        prediction,_=model(x)
        loss=(prediction-y).square().mean()
        if not torch.isfinite(loss): raise FloatingPointError('nonfinite source loss')
        loss.backward()
        if any(p.grad is None or not torch.isfinite(p.grad).all() for p in model.parameters()):
            raise FloatingPointError('nonfinite or missing source gradient')
        opt.step()
        return loss.item()
    try:
        tokens=token_table(a.token_seed)
        x,y,ids=associative_episodes(tokens,a.train_episodes,a.train_data_seed)
        ex,ey,eids=associative_episodes(tokens,a.eval_episodes,a.eval_data_seed)
        overlap=set(map(tuple,ids)) & set(map(tuple,eids))
        if overlap: raise ValueError('evaluation episodes overlap training; control rejected')
        result['data']=dict(token_hash=_hash_array(tokens),train_hash=_hash_array(ids),eval_hash=_hash_array(eids),
                            train_episodes=len(ids),eval_episodes=len(eids),duplicate_cross_split_episodes=0,
                            stored_array_bytes=sum(v.nbytes for v in (tokens,x,y,ids,ex,ey,eids)))
        xt,yt=torch.from_numpy(x),torch.from_numpy(y)
        model=OriginalAssociativeHiPPO(seed=a.initialization_seed); opt=optimizer(model)
        result['parameter_bytes']=sum(v.numel()*v.element_size() for v in model.parameters())
        result['static_buffer_bytes']=sum(v.numel()*v.element_size() for v in model.buffers())
        result['state_inventory']=[dict(name='history',shape=[1,32,32],dtype='float32',bytes=4096),
                                   dict(name='associative',shape=[1,32,32],dtype='float32',bytes=4096)]
        result['baseline_process_peak_bytes']=peak0
        guard('before_pilot')
        for i in range(p.pilot_steps):
            loss=update(model,opt,xt[i%len(x):i%len(x)+1],yt[i%len(x):i%len(x)+1])
            append_jsonl(ledger,dict(event='pilot_step',step=i+1,loss=loss,**guard('pilot')))
        result['pilot']=guard('pilot_passed')
        # Pilot is separate work; restore the exact native initialization/optimizer.
        del opt,model
        model=OriginalAssociativeHiPPO(seed=a.initialization_seed); opt=optimizer(model)
        draws=np.random.default_rng(a.train_draw_seed)
        for step in range(1,a.max_steps+1):
            index=int(draws.integers(len(x)))
            loss=update(model,opt,xt[index:index+1],yt[index:index+1])
            result['steps_completed']=step
            observation=guard('training')
            append_jsonl(ledger,dict(event='training_step',step=step,episode_index=index,loss=loss,**observation))
        # No held-out losses have been opened before this final fixed-stopping read.
        predictions=[]
        with torch.no_grad():
            for begin in range(0,len(ex),16):
                pred,_=model(torch.from_numpy(ex[begin:begin+16])); predictions.append(pred.numpy())
                guard('final_evaluation')
        pred=np.concatenate(predictions)
        if not np.isfinite(pred).all(): raise FloatingPointError('nonfinite final prediction')
        final=pred[:,-1]; target=ey[:,-1]
        prior=y[:,-1].mean(0)
        normal=lambda v: v/(np.linalg.norm(v,axis=-1,keepdims=True)+1e-8)
        cosine=np.sum(normal(final)*normal(target),axis=-1)
        retrieval=np.argmax(normal(final)@normal(tokens[12:24]).T,axis=-1)
        truth=np.argmax(normal(target)@normal(tokens[12:24]).T,axis=-1)
        prior_retrieval=int(np.argmax(normal(prior)@normal(tokens[12:24]).T))
        latest=ex[:,-3]
        latest_retrieval=eids[:,9]-12
        metrics=dict(all_step_mse=float(np.mean((pred-ey)**2)),final_write_mse=float(np.mean((final-target)**2)),
            final_write_cosine=float(cosine.mean()),b_retrieval_accuracy=float(np.mean(retrieval==truth)),
            prior_final_write_mse=float(np.mean((prior-target)**2)),prior_b_retrieval_accuracy=float(np.mean(prior_retrieval==truth)),
            latest_b_final_write_mse=float(np.mean((latest-target)**2)),
            latest_b_retrieval_accuracy=float(np.mean(latest_retrieval==truth)),
            latest_b_cosine=float(np.sum(normal(latest)*normal(target),axis=-1).mean()),
            chance_b_retrieval_accuracy=1/12)
        buffer=io.BytesIO()
        np.savez_compressed(buffer,predictions=pred,targets=ey,episode_ids=eids,token_table=tokens,
                            training_prior=prior,latest_b=latest)
        atomic_bytes(out/'final_predictions.npz',buffer.getvalue())
        result['raw_predictions_sha256']=hashlib.sha256(buffer.getvalue()).hexdigest()
        result['metrics']=metrics
        accepted=(metrics['final_write_mse']<a.max_prior_mse_fraction*metrics['prior_final_write_mse']
                  and metrics['b_retrieval_accuracy']>=max(a.min_retrieval_accuracy,metrics['prior_b_retrieval_accuracy']+.1)
                  and metrics['final_write_cosine']>=a.min_cosine
                  and metrics['final_write_mse']<metrics['latest_b_final_write_mse']
                  and metrics['b_retrieval_accuracy']>metrics['latest_b_retrieval_accuracy'])
        result['status']='component_passed' if accepted else 'component_unaccepted'
        result['acceptance']='MSE <.75 training-prior MSE; B retrieval >=max(.5,prior+.1); cosine >=.5; beat latest-B MSE and retrieval on excluded final-Write targets'
        result['optimizer_state_bytes']=sum(v.numel()*v.element_size() for s in opt.state.values() for v in s.values() if isinstance(v,torch.Tensor))
        result['gradient_bytes']=sum(v.grad.numel()*v.grad.element_size() for v in model.parameters() if v.grad is not None)
        result['final_parameter_hash']=canonical_hash({n:_hash_array(v.detach().numpy()) for n,v in model.state_dict().items()})
        append_jsonl(ledger,dict(event='final_evaluation',status=result['status'],metrics=metrics))
    except Exception as exc:
        result['status']='component_failed'
        result['failure']=dict(type=type(exc).__name__,reason=str(exc),traceback=traceback.format_exc())
        append_jsonl(ledger,dict(event='failure',**result['failure']))
    result['resources']=dict(elapsed_seconds=time.perf_counter()-start,process_peak_bytes=_peak_bytes(),
        additional_peak_bytes=max(0,_peak_bytes()-peak0),additional_peak_limit_bytes=p.additional_peak_limit_bytes,
        max_seconds=p.max_seconds,device='cpu',native_mps='not entered; FP64 unavailable; existing CPU fallback preserved',
        peak_measurement='process ru_maxrss high-water delta; bounded pilot, not a fresh allocator peak or scientific envelope')
    return result


def reproduce_baseline(name: str, config: RunConfig, out: Path) -> dict:
    if type(config) is not ReproductionRunConfig:
        raise ValueError('explicit dedicated reproduction config required')
    config.__post_init__()
    if name not in {*EXCLUSIONS,'gaver_equations','associative_original'}: raise ValueError('unknown reproduction method')
    folder=Path(out)/name
    if folder.exists(): raise FileExistsError(f'refusing to replace prior evidence: {folder}')
    folder.mkdir(parents=True)
    resolved=asdict(config)
    atomic_json(folder/'resolved.json',resolved)
    torch.set_num_threads(config.resources.cpu_threads)
    record=dict(schema_version=1,name=name,integrated_competitor=False,config_hash=canonical_hash(resolved),
        source=SOURCES['associative' if name.startswith('associative') else 'gaver'] if name!='compact_gru_routing' else None,
        implementation_hashes={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in
            ['famjet/reproduce.py','famjet/memory/gaver.py','famjet/memory/associative_hippo.py']},
        dependency_lock_sha256=hashlib.sha256((ROOT/'requirements.lock').read_bytes()).hexdigest())
    if name in EXCLUSIONS:
        record.update(status='excluded_preconfirmation',reason=EXCLUSIONS[name])
    elif name=='gaver_equations': record.update(_gaver_control(config.reproduction))
    else: record.update(_associative_control(config.reproduction,folder))
    atomic_json(folder/'report.json',record)
    return record


def main(argv: list[str] | None = None) -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',required=True,type=Path)
    parser.add_argument('--out',type=Path,default=Path('artifacts/baseline_reproduction'))
    args=parser.parse_args(argv)
    config=load_reproduction_config(args.config)
    results=[reproduce_baseline(name,config,args.out) for name in config.reproduction.methods]
    atomic_json(args.out/'inventory.json',dict(config_hash=canonical_hash(asdict(config)),
        status='source_controls_only',results=[dict(name=r['name'],status=r['status'],integrated_competitor=False) for r in results]))
    for r in results: print(f"{r['name']}: {r['status']}")
    # An unaccepted control is an explicit recorded exclusion, not a successful reproduction.
    return 2 if any(r['status'] in {'component_failed','component_unaccepted'} for r in results) else 0


if __name__=='__main__': raise SystemExit(main())
