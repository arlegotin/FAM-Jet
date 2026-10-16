"""Training-only frozen target summaries; scoring is implemented separately."""
from collections import defaultdict
from fractions import Fraction
import math
from collections.abc import Iterable
import numpy as np
from famjet.types import Episode, PredictionBatch
from famjet.eval.oracle import TASKS, CATEGORICAL_TASKS, BINARY_TASKS


def relative_error(actual: np.ndarray, reference: np.ndarray) -> float:
    """Frobenius relative error, with explicit zero-reference convention."""
    a,r = np.asarray(actual,dtype=np.float64),np.asarray(reference,dtype=np.float64)
    if a.shape != r.shape or not np.isfinite(a).all() or not np.isfinite(r).all():
        raise ValueError('matching finite arrays required')
    error, norm = np.linalg.norm(a-r),np.linalg.norm(r)
    return float(error/norm) if norm else (0. if error == 0 else float('inf'))


def fit_target_statistics(episodes: Iterable[Episode]) -> dict:
    """Freeze query-pooled population moments within each task on training only.

    Coordinate variance is population variance about each coordinate's own mean.
    Scale squared is its arithmetic mean across ALL coordinates (including exact
    constants), not variance of flattened labels. Constants are flagged for later
    absolute-error reporting. All-constant tasks have scale=None; no arbitrary
    epsilon changes their metric. Unsupported arithmetic/fact labels never
    enter a fit. Binary presence/support labels remain valid even when factual
    support is false; every active binary query enters its class-prior fit.
    """
    data = defaultdict(list)
    versions=set()
    for ep in episodes:
        versions.add(ep.metadata.get('target_semantics','observed_event_targets_v1'))
        if ep.metadata.get('split') != 'training':
            raise ValueError('target statistics require explicit training split')
        validate_shape = tuple(ep.labels.shape[:2]) == tuple(ep.queries.T.shape) == tuple(ep.supported.shape)
        if not validate_shape or ep.labels.ndim not in (2,3):
            raise ValueError('labels/support shapes must match queries')
        labels=ep.labels.detach().cpu().numpy()
        for b in range(len(ep.queries.history_ids)):
            for q in range(int(ep.queries.lengths[b])):
                task=ep.queries.tasks[b][q]
                if task not in TASKS:
                    raise ValueError(f'unknown task {task}')
                data[task]  # preserve explicit no-supported-data status
                if task in BINARY_TASKS or ep.supported[b,q]:
                    x=np.atleast_1d(labels[b,q]).astype(np.float64)
                    if not np.isfinite(x).all():
                        raise ValueError('supported labels must be finite')
                    data[task].append(x)
    if len(versions)!=1: raise ValueError('mixed target semantics in training statistics')
    version=next(iter(versions))
    if version not in {'observed_event_targets_v1','observed_event_targets_v2'}: raise ValueError('unknown target semantics')
    result={}
    for task,rows in sorted(data.items()):
        if not rows:
            result[task]={'status':'no_supported_targets','count':0,'mean':None,'scale':None,'class_distribution':None,'constant_coordinates':None}
            continue
        x=np.stack(rows)
        if task in CATEGORICAL_TASKS | BINARY_TASKS:
            classes=32 if task in CATEGORICAL_TASKS else 2
            if x.shape[1] != 1 or not np.equal(x,np.floor(x)).all() or np.any((x<0)|(x>=classes)):
                raise ValueError('invalid categorical/binary labels')
            prior=(np.bincount(x[:,0].astype(int),minlength=classes)/len(x)).tolist()
        else:
            prior=None
        mean=x.mean(axis=0)
        variance=((x-mean)**2).mean(axis=0)
        pooled=float(variance.mean())
        result[task]={'status':'ok','count':len(x),'mean':mean.tolist(),'coordinate_variance':variance.tolist(),
                      'pooled_variance':pooled,'scale':float(np.sqrt(pooled)) if pooled>0 else None,
                      'constant_coordinates':np.all(x==x[0],axis=0).tolist(),'class_distribution':prior}
    return {'schema_version':2 if version=='observed_event_targets_v2' else 1,
            **({'target_semantics':version} if version=='observed_event_targets_v2' else {}),'split':'training','variance_ddof':0,'pooling':'queries_within_task_then_coordinate_variances',
            'constant_policy':'include_in_scale_pool; report_absolute_error_separately; all_constant_scale_null','tasks':result}


TARGET_SEMANTICS = 'observed_event_targets_v2'


def _finite_json(value):
    if isinstance(value, np.ndarray): return _finite_json(value.tolist())
    if isinstance(value, list): return [_finite_json(x) for x in value]
    if isinstance(value, float) and not np.isfinite(value): return None
    return value


def _rational_loss(value):
    """Represent an exceptional exact nonnegative loss, retaining true overflow."""
    try:
        return float(value)
    except OverflowError:
        return float('inf')


def _loss_mean(values, weights=None):
    """Mean, or frozen weighted sum, without overflowing finite partial sums.

    Exact rationals are only a fallback for exceptional finite reductions. These
    are scoring scalars, not model/state arithmetic or a change of weights.
    """
    values=list(map(float,values))
    if not values or any(math.isnan(v) for v in values): return float('nan')
    if any(math.isinf(v) for v in values): return float('inf')
    terms=values if weights is None else [v*w for v,w in zip(values,weights)]
    try:
        result=math.fsum(terms)
        if math.isfinite(result): return result/len(values) if weights is None else result
    except OverflowError:
        pass
    if weights is None:
        exact=sum(map(Fraction,values))/len(values)
    else:
        exact=sum(Fraction(v)*Fraction(w) for v,w in zip(values,weights))
    return _rational_loss(exact)


def _numeric_errors(prediction, target, scale):
    """Compute native and scaled errors independently of intermediate overflow.

    On the ordinary path, divide residuals by scale before squaring. If a
    difference or an individual square overflows, exact represented-value
    arithmetic distinguishes a finite coordinate mean from true overflow.
    """
    with np.errstate(over='ignore',invalid='ignore'):
        difference=prediction-target
        absolute=np.abs(difference)
        squares=np.square(difference)
        scaled_squares=np.square(difference/scale) if scale is not None else None
    exact=None
    def exact_errors():
        nonlocal exact
        if exact is None: exact=[Fraction(float(x))-Fraction(float(y)) for x,y in zip(prediction,target)]
        return exact
    mse=(_loss_mean(squares) if np.isfinite(squares).all() else
         _rational_loss(sum(x*x for x in exact_errors())/len(prediction)))
    mae=(_loss_mean(absolute) if np.isfinite(absolute).all() else
         _rational_loss(sum(abs(x) for x in exact_errors())/len(prediction)))
    normalized=None
    if scale is not None:
        normalized=(_loss_mean(scaled_squares) if np.isfinite(scaled_squares).all() else
                    _rational_loss(sum((x/Fraction(scale))**2 for x in exact_errors())/len(prediction)))
    return absolute,mse,mae,normalized


def score_predictions(predictions: PredictionBatch, statistics: dict, policy: dict) -> list[dict]:
    """Score all active queries under an explicit external v2 evaluation contract.

    Output convention is numeric, binary_probability, binary_logit, categorical_logits,
    or categorical_probability. Logit CE is evaluated before probability rounding.
    Abstention never changes the primary loss. No untrained support confidence is
    exposed; calibrated support requires a separately frozen calibration identity.
    """
    import math
    from famjet.provenance import canonical_hash
    c=predictions.metadata.get('scoring_v2')
    if not isinstance(c,dict) or c.get('version')!=2:
        raise ValueError('explicit scoring_v2 contract required')
    required={'version','output_convention','present','tasks','target_valid','numeric_supported','prediction_valid','quarantined',
              'quarantine_trigger','method','replicate','regime','target_semantics','manifest_hash','statistics_hash'}
    if required!=c.keys(): raise ValueError('incomplete scoring_v2 contract')
    if type(c['replicate']) is not int or c['replicate']<0 or any(type(c[k]) is not str or not c[k] for k in ('method','regime')):
        raise ValueError('explicit method/replicate/regime required')
    if any(type(c[k]) is not str or len(c[k])!=64 or any(v not in '0123456789abcdef' for v in c[k]) for k in ('manifest_hash','statistics_hash')):
        raise ValueError('invalid scoring provenance hash')
    if statistics.get('schema_version')!=2 or statistics.get('split')!='training' or statistics.get('target_semantics')!=TARGET_SEMANTICS or c['target_semantics']!=TARGET_SEMANTICS:
        raise ValueError('current training target semantics required')
    if c['statistics_hash']!=canonical_hash(statistics): raise ValueError('statistics hash mismatch')
    if policy.get('version')!=2 or not {'primary_tasks','expected_inventory','task_weights','regime_weights','support_calibration'}<=policy.keys():
        raise ValueError('complete scoring policy required')
    if policy['support_calibration'] is not None:
        raise ValueError('support calibration unavailable until separate development calibration is implemented')
    for weights in (policy['task_weights'],policy['regime_weights']):
        if not weights or any(not np.isfinite(x) or x<=0 for x in weights.values()) or not math.isclose(sum(weights.values()),1.,abs_tol=1e-12):
            raise ValueError('frozen positive normalized weights required')
    shape=tuple(predictions.query_ids.shape)
    if len(shape)!=2 or len(predictions.history_ids)!=shape[0]: raise ValueError('prediction shape mismatch')
    for field in ('present','tasks','target_valid','numeric_supported','prediction_valid','quarantined'):
        if np.asarray(c[field]).shape!=shape: raise ValueError('scoring field shape mismatch: '+field)
        if field!='tasks' and np.asarray(c[field]).dtype!=np.bool_: raise ValueError('boolean scoring masks required')
    for t in (predictions.prediction,predictions.target,predictions.supported,predictions.failure,predictions.abstained):
        if tuple(t.shape[:2])!=shape: raise ValueError('prediction shape mismatch')
    rows=[]
    raw=predictions.prediction.detach().cpu().numpy().astype(float)
    targets=predictions.target.detach().cpu().numpy().astype(float)
    for b,h in enumerate(predictions.history_ids):
        for q in range(shape[1]):
            if not c['present'][b][q]: continue
            task=c['tasks'][b][q]
            if task not in TASKS: raise ValueError('unknown task')
            target=np.atleast_1d(targets[b,q]); pred=np.atleast_1d(raw[b,q])
            valid=bool(c['target_valid'][b][q])
            if valid and not np.isfinite(target).all(): raise ValueError('valid target must be finite')
            if not valid and task in policy['primary_tasks']: raise ValueError('missing primary target')
            st=statistics['tasks'].get(task)
            if not st or st.get('status')!='ok': raise ValueError('missing training prior')
            categorical=task in CATEGORICAL_TASKS|BINARY_TASKS
            if not categorical and task in policy['primary_tasks'] and (st['scale'] is None or not np.isfinite(st['scale']) or st['scale']<=0):
                raise ValueError('primary scale must be finite positive')
            convention=c['output_convention']
            allowed={'categorical_logits','categorical_probability'} if task in CATEGORICAL_TASKS else {'binary_probability','binary_logit'} if task in BINARY_TASKS else {'numeric'}
            if convention not in allowed: raise ValueError('invalid output convention')
            reasons=[]
            if c['quarantined'][b][q]: reasons.append('quarantined_state')
            if bool(predictions.failure[b,q]): reasons.append('failed_output')
            if not np.isfinite(pred).all(): reasons.append('nonfinite_output')
            if not c['prediction_valid'][b][q]: reasons.append('unusable_prediction')
            if convention.endswith('probability') and np.isfinite(pred).all():
                if np.any((pred<0)|(pred>1)) or (convention=='categorical_probability' and not np.isclose(pred.sum(),1.,rtol=0,atol=1e-12)):
                    reasons.append('invalid_probability')
            fallback=bool(reasons)
            row={'schema_version':2,'method':c['method'],'replicate':c['replicate'],'history_id':h,
                 'query_id':int(predictions.query_ids[b,q]),'regime':c['regime'],'task':task,
                 'target_semantics':TARGET_SEMANTICS,'manifest_hash':c['manifest_hash'],
                 'statistics_hash':c['statistics_hash'],'policy_hash':canonical_hash(policy),'policy':policy,
                 'target':target.tolist() if valid else None,'raw_prediction':_finite_json(pred),
                 'factual_supported':bool(predictions.supported[b,q]),'numeric_supported':bool(c['numeric_supported'][b][q]),
                 'prediction_valid':bool(c['prediction_valid'][b][q]),'eligible':valid,
                 'fallback':fallback,'fallback_reasons':reasons,'failure':bool(predictions.failure[b,q]),
                 'nonfinite':not bool(np.isfinite(pred).all()),'quarantined':bool(c['quarantined'][b][q]),
                 'quarantine_trigger':c['quarantine_trigger'],'abstained':bool(predictions.abstained[b,q]),
                 'accepted':not bool(predictions.abstained[b,q]),'support_calibration_status':'unavailable',
                 'loss':None,'normalized_error':None,'native_mse':None,'native_mae':None,
                 'constant_absolute_error':None,'infinite_loss':False,'loss_status':'ineligible'}
            if categorical:
                classes=32 if task in CATEGORICAL_TASKS else 2
                prior=np.asarray(st['class_distribution'],float)
                if prior.shape!=(classes,) or not np.isfinite(prior).all() or np.any(prior<0) or not np.isclose(prior.sum(),1.,rtol=0,atol=1e-12):
                    raise ValueError('invalid training class distribution')
                if pred.size!=(classes if task in CATEGORICAL_TASKS else 1): raise ValueError('output dimension mismatch')
                logp=None
                if fallback: final=prior
                elif convention=='binary_logit':
                    x=float(pred[0]); logp=np.array([-np.logaddexp(0,x),-np.logaddexp(0,-x)]); final=np.exp(logp)
                elif convention=='categorical_logits':
                    shifted=pred-pred.max(); logp=shifted-np.log(np.exp(shifted).sum()); final=np.exp(logp)
                elif convention=='binary_probability': final=np.array([1-pred[0],pred[0]])
                else: final=pred
                row.update(prediction=final.tolist(),predicted_class=int(final.argmax()))
                if valid:
                    if target.size!=1 or target[0]!=int(target[0]) or not 0<=target[0]<classes: raise ValueError('invalid class target')
                    y=int(target[0]); loss=float(-logp[y]) if logp is not None else (-math.log(final[y]) if final[y]>0 else float('inf'))
                    row.update(accuracy=float(final.argmax()==y),brier=float(np.square(final-np.eye(classes)[y]).sum()),
                               confidence=float(final.max()))
            else:
                prior=np.asarray(st['mean'],float)
                if prior.shape!=target.shape or not np.isfinite(prior).all(): raise ValueError('invalid numeric training prior')
                final=prior if fallback else pred
                if final.shape!=target.shape or not np.isfinite(final).all(): raise ValueError('invalid numeric training prior/output dimension')
                row['prediction']=final.tolist()
                if valid:
                    absolute,mse,mae,loss=_numeric_errors(final,target,st['scale'])
                    constants=np.asarray(st['constant_coordinates'],bool)
                    row.update(native_mse=mse if np.isfinite(mse) else None,native_mae=mae if np.isfinite(mae) else None,
                               native_mse_infinite=not np.isfinite(mse),native_mae_infinite=not np.isfinite(mae),
                               constant_absolute_error=_finite_json(absolute[constants]))
                    if task=='change_sign': row['sign_accuracy']=float(np.equal(np.sign(final),target).mean())
                    row['normalized_error']=loss if loss is not None and np.isfinite(loss) else None
            if valid:
                row['loss_status']='undefined_loss' if loss is None else 'infinite_loss' if not np.isfinite(loss) else 'ok'
                row['loss']=loss if loss is not None and np.isfinite(loss) else None
                row['infinite_loss']=loss is not None and not np.isfinite(loss)
            rows.append(row)
    return rows


def _inventory(rows):
    from famjet.provenance import canonical_hash
    if not rows: raise ValueError('empty inventory')
    p=rows[0]['policy']; digest=canonical_hash(p)
    if any(r['policy_hash']!=digest or canonical_hash(r['policy'])!=digest for r in rows): raise ValueError('inventory policy mismatch')
    expected={}
    for cell in p['expected_inventory']:
        for task,queries in cell['tasks'].items():
            for q in queries:
                key=(cell['history_id'],cell['replicate'],task,q)
                if key in expected: raise ValueError('duplicate declared inventory')
                expected[key]=cell['regime']
        if set(cell['tasks'])!=set(p['task_weights']): raise ValueError('inventory task mismatch')
    actual={}
    for r in rows:
        key=(r['history_id'],r['replicate'],r['task'],r['query_id'])
        if key in actual: raise ValueError('duplicate query inventory')
        actual[key]=r['regime']
    if actual!=expected: raise ValueError('incomplete or mismatched query inventory')
    histories=sorted({k[0] for k in expected}); replicates=sorted({k[1] for k in expected})
    regimes={h:{v for k,v in expected.items() if k[0]==h} for h in histories}
    if any(len(v)!=1 for v in regimes.values()): raise ValueError('history regime mismatch')
    regimes={h:next(iter(v)) for h,v in regimes.items()}
    if set(regimes.values())!=set(p['regime_weights']): raise ValueError('incomplete regime inventory')
    if {(k[0],k[1]) for k in expected}!={(h,s) for h in histories for s in replicates}: raise ValueError('incomplete crossed inventory')
    weights=[p['regime_weights'][regimes[h]]/sum(v==regimes[h] for v in regimes.values()) for h in histories]
    return p,histories,replicates,weights


def _cell_loss(rows,field='loss'):
    flag='infinite_loss' if field=='loss' else field+'_infinite'
    if any(r.get(flag) for r in rows): return float('inf')
    if any(not r['eligible'] or r.get(field) is None for r in rows): return float('nan')
    return _loss_mean(r[field] for r in rows)


def aggregate_scores(rows: list[dict]) -> dict:
    """Complete fixed hierarchy; native units remain separate for each task."""
    if not rows: raise ValueError('empty inventory')
    if len({r['method'] for r in rows})!=1: raise ValueError('aggregate one method at a time')
    p,hs,ss,weights=_inventory(rows)
    def task_value(task,field):
        return _loss_mean([_loss_mean(_cell_loss([r for r in rows if r['history_id']==h and r['replicate']==s and r['task']==task],field) for s in ss) for h in hs],weights)
    loss=_loss_mean([task_value(t,'loss') for t in p['task_weights']],list(p['task_weights'].values()))
    native={}
    for t in p['task_weights']:
        if t in CATEGORICAL_TASKS|BINARY_TASKS: continue
        mse,mae=task_value(t,'native_mse'),task_value(t,'native_mae')
        def native_status(value,field):
            if any(r['task']==t and r.get(field+'_infinite') for r in rows):
                return 'unavailable_nonrepresentable_row_metric'
            return 'undefined_loss' if np.isnan(value) else 'nonrepresentable_aggregate' if np.isinf(value) else 'ok'
        native[t]={'rmse':float(np.sqrt(mse)) if np.isfinite(mse) else None,'mae':float(mae) if np.isfinite(mae) else None,
                   'mse_status':native_status(mse,'native_mse'),
                   'mae_status':native_status(mae,'native_mae')}
    categorical={}
    for task in p['task_weights']:
        if task not in CATEGORICAL_TASKS|BINARY_TASKS: continue
        selected=[r for r in rows if r['task']==task]
        if any(not r['eligible'] for r in selected):
            categorical[task]={'status':'undefined_target'}; continue
        weighted=[]
        for h,w in zip(hs,weights):
            for seed in ss:
                cell=[r for r in selected if r['history_id']==h and r['replicate']==seed]
                weighted.extend((r,w/len(ss)/len(cell)) for r in cell)
        bins=[]; ece=0.
        for i in range(10):
            members=[(r,w) for r,w in weighted if min(int(r['confidence']*10),9)==i]
            mass=sum(w for _,w in members)
            accuracy=sum(r['accuracy']*w for r,w in members)/mass if mass else None
            confidence=sum(r['confidence']*w for r,w in members)/mass if mass else None
            if mass: ece+=mass*abs(accuracy-confidence)
            bins.append({'lower':i/10,'upper':(i+1)/10,'weight':mass,'accuracy':accuracy,'confidence':confidence})
        categorical[task]={'status':'ok','accuracy':sum(r['accuracy']*w for r,w in weighted),
                           'brier':sum(r['brier']*w for r,w in weighted),'ece':ece,
                           'calibration_bins':bins,'calibration_scope':'class_distribution_diagnostic_not_support_confidence'}
    accepted=[r for r in rows if r['accepted'] and r['eligible']]
    return {'status':'undefined_loss' if np.isnan(loss) else 'infinite_loss' if np.isinf(loss) else 'ok',
            'loss':float(loss) if np.isfinite(loss) else None,'infinite_loss_count':sum(r['infinite_loss'] for r in rows),
            'query_count':len(rows),'fallback_count':sum(r['fallback'] for r in rows),
            'native_by_task':native,'categorical_by_task':categorical,'coverage':len(accepted)/len(rows),
            'selective_risk':_finite_json(_cell_loss(accepted)) if accepted else None,
            'coverage_weighting':'query_diagnostic_only','history_order':hs,'replicate_order':ss,'history_weights':weights}


def history_effects_inventory(rows: list[dict], pair: tuple[str,str]) -> dict:
    if len(pair)!=2 or pair[0]==pair[1]: raise ValueError('distinct baseline,candidate pair required')
    selected=[[r for r in rows if r['method']==method] for method in pair]
    a,b=(_inventory(rs) for rs in selected)
    if a!=b: raise ValueError('paired inventory mismatch')
    for left,right in zip(sorted(selected[0],key=lambda r:(r['history_id'],r['replicate'],r['task'],r['query_id'])), sorted(selected[1],key=lambda r:(r['history_id'],r['replicate'],r['task'],r['query_id']))):
        if any(left[k]!=right[k] for k in ('target','target_semantics','manifest_hash','statistics_hash','eligible')):
            raise ValueError('paired target/provenance inventory mismatch')
    p,hs,ss,weights=a
    return {'pair':list(pair),'orientation':'baseline_minus_candidate','history_order':hs,'replicate_order':ss,'history_weights':weights,'policy':p}


def history_effects(rows: list[dict], pair: tuple[str,str]) -> np.ndarray:
    inventory=history_effects_inventory(rows,pair); p=inventory['policy']
    def value(method,h,s):
        return _loss_mean([_cell_loss([r for r in rows if r['method']==method and r['history_id']==h and r['replicate']==s and r['task']==t]) for t in p['task_weights']],list(p['task_weights'].values()))
    result=np.asarray([[value(pair[0],h,s)-value(pair[1],h,s) for s in inventory['replicate_order']] for h in inventory['history_order']])
    if not np.isfinite(result).all(): raise ValueError('undefined/infinite losses block comparable history effects')
    return result
