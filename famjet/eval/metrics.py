"""Training-only frozen target summaries; scoring is implemented separately."""
from collections import defaultdict
from collections.abc import Iterable
import numpy as np
from famjet.types import Episode
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
    for ep in episodes:
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
    return {'schema_version':1,'split':'training','variance_ddof':0,'pooling':'queries_within_task_then_coordinate_variances',
            'constant_policy':'include_in_scale_pool; report_absolute_error_separately; all_constant_scale_null','tasks':result}
