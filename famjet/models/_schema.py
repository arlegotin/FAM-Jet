"""Closed bounded inference metadata; full RunConfig stays in external run state.

These are static training summaries, not a serialization channel for arbitrary
scientific config, histories or annotations. Vectors are bounded by declared V
or the fixed 2/32-class task vocabularies; all other fields have fixed size.
"""
from copy import deepcopy
import math
from famjet.eval.oracle import TASKS, BINARY_TASKS, CATEGORICAL_TASKS
from famjet.provenance import canonical_hash


def _require(condition):
    if not condition:
        raise ValueError('invalid bounded inference metadata/provenance/statistics schema')


def _keys(value, names):
    _require(type(value) is dict and all(type(k) is str for k in value) and set(value) == set(names))


def _integer(value, *, minimum=0):
    _require(type(value) is int and minimum <= value <= 2**63-1)


def _number(value, *, minimum=None, positive=False):
    _require(type(value) in (float, int))
    if type(value) is int:
        _require(-2**63 <= value <= 2**63-1)
    _require(math.isfinite(value))
    _require(minimum is None or value >= minimum)
    _require(not positive or value > 0)


def _digest(value):
    _require(type(value) is str and len(value) == 64 and all(c in '0123456789abcdef' for c in value))


def _vector(value, length, *, boolean=False, nonnegative=False):
    _require(type(value) is list and len(value) == length)
    for x in value:
        if boolean:
            _require(type(x) is bool)
        else:
            _number(x, minimum=0 if nonnegative else None)


def inference_config(value):
    """Only map construction/rate-source mode is not already in kernel/reader."""
    _keys(value, ('schema_version', 'writer', 'rate_mode'))
    _require(type(value['schema_version']) is int and value['schema_version'] == 1)
    for field in ('writer', 'rate_mode'):
        _require(type(value[field]) is str and value[field] in {'fixed', 'learned'})
    return dict(value)


def training_metadata(provenance, statistics, value_dim):
    """Validate the complete Task3 summary tree before copying or hashing it."""
    if provenance is None and statistics is None:
        return None, None
    _keys(provenance, ('split', 'history_identity_hash', 'history_count', 't_ref',
                      'reference_source', 'feature_rows', 'writer_hash', 'target_hash'))
    _require(type(provenance['split']) is str and provenance['split'] == 'training')
    for field in ('history_identity_hash', 'writer_hash', 'target_hash'):
        _digest(provenance[field])
    for field in ('history_count', 'feature_rows'):
        _integer(provenance[field], minimum=1)
    _number(provenance['t_ref'], positive=True)
    _require(type(provenance['reference_source']) is str and provenance['reference_source'] in
             {'median_positive_training_gap', 'explicit_duration'})
    _keys(statistics, ('schema_version', 'split', 'variance_ddof', 'pooling', 'constant_policy', 'tasks'))
    _require(type(statistics['schema_version']) is int and statistics['schema_version'] == 1)
    _require(type(statistics['variance_ddof']) is int and statistics['variance_ddof'] == 0)
    _require(type(statistics['split']) is str and statistics['split'] == 'training')
    _require(type(statistics['pooling']) is str and statistics['pooling'] == 'queries_within_task_then_coordinate_variances')
    _require(type(statistics['constant_policy']) is str and statistics['constant_policy'] ==
             'include_in_scale_pool; report_absolute_error_separately; all_constant_scale_null')
    tasks = statistics['tasks']
    _require(type(tasks) is dict and 0 < len(tasks) <= len(TASKS) and all(type(k) is str for k in tasks) and set(tasks) <= TASKS)
    base = {'status', 'count', 'mean', 'scale', 'class_distribution', 'constant_coordinates'}
    for task, record in tasks.items():
        _require(type(record) is dict and type(record.get('status')) is str)
        if record.get('status') == 'no_supported_targets':
            _keys(record, base)
            _integer(record['count'])
            _require(record['count'] == 0 and all(record[k] is None for k in base - {'status', 'count'}))
            continue
        _keys(record, base | {'coordinate_variance', 'pooled_variance'})
        _require(record['status'] == 'ok')
        _integer(record['count'], minimum=1)
        categorical = task in BINARY_TASKS | CATEGORICAL_TASKS
        dimension = 1 if categorical else value_dim
        _vector(record['mean'], dimension)
        _vector(record['coordinate_variance'], dimension, nonnegative=True)
        _vector(record['constant_coordinates'], dimension, boolean=True)
        _number(record['pooled_variance'], minimum=0)
        if record['pooled_variance'] == 0:
            _require(record['scale'] is None)
        else:
            _number(record['scale'], positive=True)
        if categorical:
            prior = record['class_distribution']
            _vector(prior, 32 if task in CATEGORICAL_TASKS else 2, nonnegative=True)
            _require(all(x <= 1 for x in prior) and math.isclose(sum(prior), 1., rel_tol=1e-12, abs_tol=1e-12))
        else:
            _require(record['class_distribution'] is None)
    _require(provenance['target_hash'] == canonical_hash(statistics))
    return deepcopy(provenance), deepcopy(statistics)
