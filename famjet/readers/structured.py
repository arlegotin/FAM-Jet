"""Explicit reader schemas; generic controls retain raw amplitude/state."""
import torch
from famjet.readers.mlp import NumericReader
from famjet.eval.oracle import TASKS

TASK_ORDER = tuple(sorted(TASKS))
# Sign uses the contrast predictor; never allocate an always-zero sign input.
QUERY_TASK_ORDER = tuple(sorted(TASKS - {'change_sign'}))
KINDS = {'structured', 'generic_contracted', 'generic_full', 'fixed_scale',
         'bank_raw', 'bank_normalized', 'query_only'}


def fixed_anchor(kind):
    if kind == 'fixed_scale':
        return 0
    if kind.startswith('fixed_scale:') and kind.split(':')[1].isdigit():
        return int(kind.split(':')[1])
    raise ValueError('invalid fixed-scale anchor')


def input_width(kind, feature_spec, query_spec):
    selected_anchor = fixed_anchor(kind) if kind.startswith('fixed_scale') else None
    kind = 'fixed_scale' if selected_anchor is not None else kind
    if kind not in KINDS:
        raise ValueError('unknown reader kind')
    if set(feature_spec) != {'family', 'anchors', 'key_dim', 'value_dim'} or set(query_spec) != {'key_dim'}:
        raise ValueError('invalid reader feature/query schema')
    family, j, k, v = (feature_spec[n] for n in ('family', 'anchors', 'key_dim', 'value_dim'))
    if family not in {'jet', 'bank'} or any(type(x) is not int or x <= 0 for x in (j, k, v)) or query_spec['key_dim'] != k:
        raise ValueError('invalid reader dimensions/family')
    if selected_anchor is not None and selected_anchor >= j:
        raise ValueError('fixed-scale anchor outside retained rates')
    if kind.startswith('bank_') and family != 'bank':
        raise ValueError('bank reader requires bank kernel')
    widths = {'structured': j*(2*v+4 if family == 'jet' else v+3),
              'generic_contracted': j*(2*v+2 if family == 'jet' else v+1),
              'generic_full': j*k*(v+1)*(2 if family == 'jet' else 1),
              'bank_raw': j*(v+1), 'bank_normalized': j*(v+1),
              'fixed_scale': v+1, 'query_only': 0}
    return widths[kind] + k + len(QUERY_TASK_ORDER) + 2


def make_reader(kind: str, feature_spec: dict, query_spec: dict, budget: dict):
    """Budget selects an actual first-layer rank; never adds dummy weights.

    max_parameters/max_macs are optional ceilings. rank, if supplied, is exact.
    Schemas and the chosen rank survive strict numeric inference reconstruction.
    """
    if set(budget) - {'width', 'hidden_layers', 'rank', 'max_parameters', 'max_macs'} or not {'width', 'hidden_layers'} <= set(budget):
        raise ValueError('invalid reader budget')
    dim = input_width(kind, feature_spec, query_spec)
    width, layers = budget['width'], budget['hidden_layers']
    for name in ('max_parameters', 'max_macs', 'rank'):
        if name in budget and (type(budget[name]) is not int or budget[name] <= 0):
            raise ValueError('invalid reader budget')
    schema = dict(kind=kind, feature_spec=dict(feature_spec), query_spec=dict(query_spec), budget=dict(budget))
    ranks = [budget['rank']] if 'rank' in budget else [None]
    if 'rank' not in budget and kind == 'generic_full' and layers:
        ranks += list(range(min(dim, width), 0, -1))
    # Check analytic counts before allocating large readers or consuming RNG.
    for rank in ranks:
        first = dim*width if rank is None else rank*(dim+width)
        hidden_weights = first + max(0, layers-1)*width*width if layers else 0
        last = width if layers else dim
        params = hidden_weights + layers*width + (last+1)*(feature_spec['value_dim']+1)
        macs = hidden_weights + last*(feature_spec['value_dim']+1)
        if params <= budget.get('max_parameters', float('inf')) and macs <= budget.get('max_macs', float('inf')):
            return NumericReader(dim, feature_spec['value_dim'], width, layers, rank=rank, schema=schema)
    raise ValueError('reader cannot fit parameter/compute budget')


def query_inputs(queries, t_ref):
    """Public task, key and continuous dimensionless endpoints; never IDs/epochs."""
    key = queries.key_features
    indices = []
    for row, present in zip(queries.tasks, queries.present.cpu().tolist()):
        values = []
        for task, active in zip(row, present):
            if active and task not in TASK_ORDER:
                raise ValueError(f'unknown task {task}')
            task = 'contrast' if task == 'change_sign' else task
            values.append(QUERY_TASK_ORDER.index(task) if task in QUERY_TASK_ORDER else 0)
        indices.append(values)
    ids = torch.tensor(indices, device=key.device, dtype=torch.long).reshape(key.shape[:2])
    tasks = torch.nn.functional.one_hot(ids, len(QUERY_TASK_ORDER)).to(key)
    endpoints = torch.stack((queries.age_start/t_ref, queries.age_end/t_ref), -1).to(key)
    return torch.cat((key, tasks, endpoints), -1)


def memory_inputs(kind, features, full_state=None):
    d = features.diagnostics
    if kind == 'query_only':
        return features.values[..., :0]
    if kind == 'structured':
        return features.values
    if kind == 'generic_full':
        return full_state
    if kind in {'generic_contracted', 'bank_raw'}:
        parts = [d['u']]
        if 'h' in d: parts.append(d['h'])
        parts.append(d['z'][..., None])
        if 'b' in d: parts.append(d['b'][..., None])
        return torch.cat(parts, -1).flatten(2)
    if kind == 'bank_normalized':
        return torch.cat((d['r'], d['anchor_support'][..., None].to(d['r'])), -1).flatten(2)
    if kind.startswith('fixed_scale'):
        # Public caller-order anchor; plain fixed_scale is smoke-default zero.
        anchor = fixed_anchor(kind)
        return torch.cat((d['r'][:, :, 0, anchor], d['anchor_support'][:, :, 0, anchor, None].to(d['r'])), -1)
    raise ValueError('unknown reader kind')
