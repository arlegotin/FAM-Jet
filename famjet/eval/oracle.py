"""Raw observed-event arithmetic: sole label source for compressed methods."""
from fractions import Fraction

import numpy as np
import torch
from famjet.data.schema import validate_events, validate_queries
from famjet.types import EventBatch, QueryBatch, PredictionBatch

NUMERIC_TASKS = frozenset({'mean', 'contrast', 'latest', 'change_sign'})
BINARY_TASKS = frozenset({'presence', 'interval_support'})
CATEGORICAL_TASKS = frozenset({'corrected_categorical', 'random_binding'})
TASKS = NUMERIC_TASKS | BINARY_TASKS | CATEGORICAL_TASKS


def exact_time_difference(newer: int | float, older: int | float) -> int | Fraction:
    """Subtract validated finite scalar timestamps without mixed-dtype rounding.

    Python ints retain their full tick value; each float denotes its exact stored
    binary value, not an inferred decimal or rounded integer timestamp. Returning
    a rational for any float operand preserves exact age/endpoint comparisons.
    This host oracle helper is not a floating-point streaming kernel operation.
    """
    if isinstance(newer, int) and isinstance(older, int):
        return newer - older
    return Fraction(newer) - Fraction(older)


def exact_targets(events: EventBatch, queries: QueryBatch) -> PredictionBatch:
    """CPU FP64 labels with NaN unsupported tensors and null JSON metadata.

    Numeric tasks return [B,Q,V], binary [B,Q,1], categorical [B,Q].
    Binary labels are always valid on active queries; their support denotes
    factual evidence, so absent presence has label 0, support false, abstained
    false. metadata.target_valid distinguishes label validity from evidence.
    Mixed event/query time dtypes retain exact represented values through
    exact_time_difference; integer ticks are never coerced to floats.
    Batches may mix tasks only within one output family. Shared query support
    requires every value coordinate; independent observations are averaged per
    coordinate. Latest uses the entire vector of the latest observed event,
    and is unsupported if that vector has missing coordinates.
    """
    validate_events(events)
    validate_queries(queries)
    if events.history_ids != queries.history_ids or events.key_features.shape[2] != queries.key_features.shape[2]:
        raise ValueError('history/key-feature schemas must match')
    active = {queries.tasks[b][q] for b in range(len(queries.history_ids)) for q in range(int(queries.lengths[b]))}
    if active - TASKS:
        raise ValueError(f'unknown task: {sorted(active - TASKS)}')
    families = {('categorical' if t in CATEGORICAL_TASKS else 'binary' if t in BINARY_TASKS else 'numeric') for t in active}
    if len(families) > 1:
        raise ValueError('tasks must have a homogeneous output family')
    family = next(iter(families), 'numeric')
    B,Q = queries.T.shape
    shape = (B,Q) if family == 'categorical' else (B,Q,1 if family == 'binary' else events.values.shape[2])
    target = np.full(shape, np.nan, dtype=np.float64)
    support = np.zeros((B,Q), dtype=bool)
    valid = np.zeros((B,Q), dtype=bool)
    counts = np.zeros((B,Q,2,events.values.shape[2]), dtype=np.int64)
    rows = [[None for _ in range(Q)] for _ in range(B)]
    vals = events.values.detach().cpu().numpy().astype(np.float64)
    obs = events.observed.detach().cpu().numpy()
    for b in range(B):
        n = int(events.lengths[b])
        times = events.timestamps[b,:n].tolist()
        ids = events.key_ids[b,:n].tolist()
        for q in range(int(queries.lengths[b])):
            task = queries.tasks[b][q]
            T = queries.T[b,q].item()
            age = [exact_time_difference(T,t) for t in times]
            match = np.array([ids[i] == queries.key_ids[b,q].item() and age[i] >= 0 for i in range(n)],dtype=bool)
            written = match & obs[b,:n].any(axis=1)
            lo,hi = queries.age_start[b,q].item(),queries.age_end[b,q].item()
            recent = match & np.array([lo <= a < hi for a in age],dtype=bool)
            older = match & np.array([hi <= a < 2*hi-lo for a in age],dtype=bool)
            c0 = (obs[b,:n] & recent[:,None]).sum(axis=0)
            c1 = (obs[b,:n] & older[:,None]).sum(axis=0)
            counts[b,q] = [c0,c1]
            label = None
            if task == 'presence':
                label = [float(written.any())]
            elif task == 'interval_support':
                label = [float((c0 > 0).all())]
            elif task in {'latest'} | CATEGORICAL_TASKS:
                candidates = np.flatnonzero(written)
                if candidates.size:
                    i = max(candidates, key=lambda i: (times[i],events.event_ids[b,i].item()))
                    if obs[b,i].all():
                        label = vals[b,i].copy()
                        if task in CATEGORICAL_TASKS:
                            if label.size != 32 or not np.isin(label,[0.,1.]).all() or label.sum() != 1:
                                raise ValueError('categorical tasks require observed V32 one-hot values')
                            label = float(label.argmax())
            elif (c0 > 0).all() and (task == 'mean' or (c1 > 0).all()):
                label = np.where(obs[b,:n] & recent[:,None],vals[b,:n],0.).sum(axis=0)/c0
                if task != 'mean':
                    label -= np.where(obs[b,:n] & older[:,None],vals[b,:n],0.).sum(axis=0)/c1
                    if task == 'change_sign':
                        label = np.sign(label)
            if label is not None:
                target[b,q] = label
                valid[b,q] = True
                support[b,q] = bool(label[0]) if task in BINARY_TASKS else True
                rows[b][q] = np.asarray(label).tolist()
    t = torch.from_numpy(target)
    s = torch.from_numpy(support)
    return PredictionBatch(events.history_ids,queries.query_ids.clone(),t.clone(),t,s,torch.zeros_like(s),torch.from_numpy(~valid),
                           {'oracle_version':1,'targets':rows,'observed_counts':counts.tolist(),'output_family':family,'target_valid':valid.tolist()})
