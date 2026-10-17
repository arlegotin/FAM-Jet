"""Strict version-1 resolved configuration. No pilot-dependent defaults."""
from dataclasses import MISSING, asdict, dataclass, field, fields, is_dataclass
import math
import json
from pathlib import Path
import types
from typing import Any, Union, get_args, get_origin, get_type_hints

import yaml

from famjet.artifacts import atomic_json
from famjet.provenance import canonical_json


@dataclass(frozen=True)
class GeneratorConfig:
    """Version-1 exploratory generation; protected roots are reservation-only."""
    namespace: str = 'training'
    population: str = 'primary'
    regime: str = 'balanced'
    key_load: int = 16
    feature_seed: int = 20261013
    query_seed: int = 0
    max_query_attempts: int = 4096
    delay_multiplier: float = 0.0
    robustness: str = 'standard'


@dataclass(frozen=True)
class BeijingConfig:
    archive_path: str = 'data/raw/beijing-uci501.zip'
    derived_path: str = 'data/derived/beijing_v1'
    query_grid_version: str = 'station_mean_contrast_widths_1_6_24_72_168_v1'


@dataclass(frozen=True)
class DataConfig:
    generator_version: str
    key_features: str
    key_dim: int
    value_dim: int
    length: int
    queries_per_history: int
    generator: GeneratorConfig = field(default_factory=GeneratorConfig)
    beijing: BeijingConfig | None = None


@dataclass(frozen=True)
class RateConfig:
    mode: str
    bounds: tuple[float, float]
    spacing: str


@dataclass(frozen=True)
class ReaderConfig:
    kind: str
    width: int
    layers: int
    activation: str
    rank: int | None = None
    max_parameters: int | None = None
    max_macs: int | None = None


@dataclass(frozen=True)
class PolynomialConfig:
    orders: tuple[int, ...]
    taus: tuple[float, ...]
    declared_gaps: tuple[float, ...] = (0., 1., 2., 4., 16.)


@dataclass(frozen=True)
class MultiscaleConfig:
    order: int
    scale_order: int
    epsilon: float
    tau0: float
    declared_gaps: tuple[float, ...] = (0., 1., 2., 4., 16.)


@dataclass(frozen=True)
class DeltaConfig:
    dim: int
    head_key_dim: int
    head_value_dim: int
    variant: str = 'gdn2'
    conv_length: int = 4
    decay_policy: str = 'raw_per_observed_event'
    erase_policy: str = 'raw_paper'
    allow_neg_eigval: bool = False


@dataclass(frozen=True)
class ModelConfig:
    method: str
    heads: int
    J: int | None
    K: int
    precision: str
    rates: RateConfig | None
    writer: str
    encode: str
    reader: ReaderConfig
    epsilon: float
    numerical_support_floor: float
    learned_abstention_threshold: float | None
    interpolation: bool
    probes: int
    polynomial: PolynomialConfig | None = None
    multiscale: MultiscaleConfig | None = None
    delta: DeltaConfig | None = None


@dataclass(frozen=True)
class TrainingConfig:
    microbatch: int
    effective_batch: int
    optimizer: str
    learning_rate: float
    weight_decay: float
    optimizer_steps: int


@dataclass(frozen=True)
class ResourceConfig:
    device: str
    cpu_threads: int
    reserved_fraction_of_derived_envelope: float
    training_envelope_bytes: int | None
    smoke_additional_allocation_limit_bytes: int
    resource_provenance: str
    checkpoint_retention: int
    cache_limit_bytes: int
    asset_disk_budget_bytes: int
    policy: str


@dataclass(frozen=True)
class NumericsConfig:
    reference: str
    rtol: float
    atol: float


@dataclass(frozen=True)
class ConfirmationConfig:
    status: str
    populations: Any
    splits: Any
    lengths: Any
    task_regime_weights: Any
    primary_pair_budget: Any
    comparator_configurations: Any
    training_stopping_seeds: Any
    metrics: Any
    resampling: Any
    failure_policy: Any
    support_behavior: Any
    timing_boundaries: Any
    resource_envelopes: Any
    independent_histories: int | None
    training_replicates: int | None
    multiple_testing: Any


@dataclass(frozen=True)
class DevelopmentConfig:
    mode: str
    lengths: tuple[int, ...]
    data_seed: int
    fit_histories_per_cell: int
    eval_histories_per_cell: int
    milestones: tuple[int, ...]
    calibration_path: str | None = None
    calibration_hash: str | None = None
    gradient_clip_norm: float | None = None
    cache_manifest_path: str | None = None
    cache_manifest_hash: str | None = None


@dataclass(frozen=True)
class RunConfig:
    schema_version: int
    phase: str
    seed: int
    data: DataConfig
    model: ModelConfig
    training: TrainingConfig
    resources: ResourceConfig
    numerics: NumericsConfig
    confirmation: ConfirmationConfig
    development: DevelopmentConfig | None = field(default=None, kw_only=True)

    def __post_init__(self) -> None:
        validate_config(self)


class _UniqueLoader(yaml.SafeLoader):
    pass


def _unique_mapping(loader, node, deep=False):
    result = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if not isinstance(key, str):
            raise ValueError('config keys must be strings')
        if key in result:
            raise ValueError(f'duplicate config field: {key}')
        result[key] = loader.construct_object(value_node, deep=deep)
    return result


_UniqueLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _unique_mapping)


def _parse(value, expected, name):
    if expected is Any:
        canonical_json(value)
        return value
    origin, args = get_origin(expected), get_args(expected)
    if origin in (types.UnionType, Union):
        if value is None and type(None) in args:
            return None
        choices = [arg for arg in args if arg is not type(None)]
        if len(choices) == 1:
            return _parse(value, choices[0], name)
    if is_dataclass(expected):
        if type(value) is not dict:
            raise ValueError(f'{name} must be an object')
        allowed = {f.name for f in fields(expected)}
        required = {f.name for f in fields(expected) if f.default is MISSING and f.default_factory is MISSING}
        unknown, missing = set(value) - allowed, required - set(value)
        if unknown or missing:
            raise ValueError(f'{name}: unknown fields {sorted(unknown)}, missing fields {sorted(missing)}')
        hints = get_type_hints(expected)
        return expected(**{key: _parse(item, hints[key], f'{name}.{key}') for key, item in value.items()})
    if origin is tuple and len(args) == 2 and args[1] is Ellipsis:
        if type(value) not in (list, tuple) or len(value) > 64:
            raise ValueError(f'{name} must be a bounded sequence')
        return tuple(_parse(item, args[0], name) for item in value)
    if origin is tuple:
        if type(value) not in (list, tuple) or len(value) != len(args):
            raise ValueError(f'{name} must have {len(args)} entries')
        return tuple(_parse(item, kind, name) for item, kind in zip(value, args))
    if expected is float:
        if type(value) not in (float, int) or not math.isfinite(value):
            raise ValueError(f'{name} must be a finite number')
        return float(value)
    if type(value) is not expected:
        raise ValueError(f'{name} must be {expected.__name__}')
    return value


def _positive(value, name, *, zero=False):
    if type(value) not in (int, float) or not math.isfinite(value) or (value < 0 if zero else value <= 0):
        raise ValueError(f'{name} must be finite and {"nonnegative" if zero else "positive"}')


def validate_config(config: RunConfig) -> None:
    """Scientific confirmation completeness is stricter than smoke execution.

    Detailed protected-manifest acceptance and pilot evidence remain separate
    later gates; a non-null field alone does not establish scientific validity.
    """
    # Check direct construction too, rather than relying only on the file parser.
    def check_types(obj, prefix):
        for f in fields(obj):
            val = getattr(obj, f.name)
            expected = get_type_hints(type(obj))[f.name]
            optional = [kind for kind in get_args(expected) if kind is not type(None)]
            if len(optional) == 1 and is_dataclass(optional[0]) and val is not None:
                if type(val) is not optional[0]:
                    raise ValueError(f'{prefix}.{f.name} has wrong config type')
                check_types(val, f'{prefix}.{f.name}')
            if is_dataclass(expected):
                if type(val) is not expected:
                    raise ValueError(f'{prefix}.{f.name} has wrong config type')
                check_types(val, f'{prefix}.{f.name}')
            else:
                _parse(asdict(val) if is_dataclass(val) else val, expected, f'{prefix}.{f.name}')
    check_types(config, 'config')
    if config.schema_version != 1:
        raise ValueError('unsupported config schema_version')
    if config.phase not in {'smoke', 'development', 'pilot', 'confirmation', 'replication'}:
        raise ValueError('unknown phase')
    if not 0 <= config.seed < 2**63:
        raise ValueError('seed must fit nonnegative signed int64')
    d, m, t, r, n, c = config.data, config.model, config.training, config.resources, config.numerics, config.confirmation
    for name in ('key_dim', 'value_dim', 'length', 'queries_per_history'):
        _positive(getattr(d, name), f'data.{name}')
    if not d.generator_version or d.key_features not in {'one_hot', 'dense'}:
        raise ValueError('data requires generator version and known key_features')
    if d.beijing is not None and (not d.beijing.archive_path or not d.beijing.derived_path):
        raise ValueError('Beijing archive/derived paths must be nonempty')
    if d.beijing is not None and d.beijing.query_grid_version != 'station_mean_contrast_widths_1_6_24_72_168_v1':
        raise ValueError('unknown Beijing query_grid_version')
    g = d.generator
    if g.namespace not in {'training','development_fit','development_calibration','pilot','confirmation','replication'}:
        raise ValueError('unknown generator namespace')
    if g.population not in {'primary','delayed','latest','presence','interval_support','change_sign',
                            'corrected_categorical','random_binding','boundary','constant','impulse',
                            'random','full_history','empty','same_time'}:
        raise ValueError('unknown generator population')
    if g.regime not in {'balanced','piecewise_stationary','trend_reset','periodic_impulses','irregular_revisions'}:
        raise ValueError('unknown generator regime')
    if g.robustness not in {'standard','zipf','lognormal_gaps','heavy_gaps','heavy_noise','fast_resets','broad_periods','unseen_reversals'}:
        raise ValueError('unknown generator robustness')
    if g.key_load not in {8,16,64}:
        raise ValueError('generator key_load must be 8, 16 or 64')
    for name in ('feature_seed','query_seed'):
        if not 0 <= getattr(g,name) < 2**63:
            raise ValueError(f'generator {name} must fit nonnegative int64')
    _positive(g.max_query_attempts,'generator.max_query_attempts')
    if g.delay_multiplier not in {0,.125,1,10}:
        raise ValueError('generator delay_multiplier must be 0, 1/8, 1 or 10')
    for name in ('heads', 'K', 'probes', 'epsilon', 'numerical_support_floor'):
        _positive(getattr(m, name), f'model.{name}')
    if m.K != d.key_dim:
        raise ValueError('model.K must equal data.key_dim')
    if m.precision not in {'float32', 'float64'}:
        raise ValueError('precision requires float32 or float64; frontier needs registration')
    if m.method != 'delta' and (m.delta is not None or m.writer == 'native_delta'):
        raise ValueError('native delta allocation/writer requires delta family')
    if m.method == 'delta':
        if any(x is not None for x in (m.J,m.rates,m.polynomial,m.multiscale)) or m.delta is None:
            raise ValueError('delta requires typed allocation and null J/rates/polynomial/multiscale')
        from famjet.memory.delta import validate_delta
        validate_delta(heads=m.heads,**asdict(m.delta))
        if m.writer != 'native_delta' or m.reader.kind != 'delta_mixer' or m.encode != 'stream':
            raise ValueError('delta requires native_delta writer, delta_mixer reader and stream recompute')
    elif m.method == 'multiscale':
        if m.J is not None or m.rates is not None or m.polynomial is not None or m.multiscale is None:
            raise ValueError('multiscale requires typed allocation and explicit null J/rates/polynomial')
        from famjet.memory.multiscale import validate_system
        from famjet.memory.hippo import validate_allocation
        p=m.multiscale
        validate_system(p.order,p.scale_order,p.epsilon,p.tau0)
        validate_allocation((p.order,)*p.scale_order,(p.tau0,)*p.scale_order,p.declared_gaps,r.cache_limit_bytes,
                            8 if m.precision == 'float64' else 4)
        if m.reader.kind not in {'generic_contracted','generic_full','query_only'}:
            raise ValueError('multiscale requires full coefficient generic reader')
    elif m.method == 'polynomial':
        if m.multiscale is not None:
            raise ValueError('polynomial requires null multiscale allocation')
        if m.J is not None or m.rates is not None or m.polynomial is None:
            raise ValueError('polynomial requires typed allocation and explicit null J/rates')
        p = m.polynomial
        if (not p.orders or len(p.orders) != len(p.taus) or any(n <= 0 or n > 256 for n in p.orders)
                or sum(p.orders) > 1024 or any(t <= 0 for t in p.taus)
                or any(g < 0 for g in p.declared_gaps) or len(set(p.declared_gaps)) != len(p.declared_gaps)):
            raise ValueError('invalid polynomial allocation/gap alphabet')
        if m.reader.kind not in {'generic_contracted','generic_full','query_only'}:
            raise ValueError('polynomial requires full coefficient generic reader')
    else:
        if m.polynomial is not None or m.multiscale is not None or m.J is None or m.rates is None:
            raise ValueError('non-polynomial methods require J/rates and null polynomial allocation')
        _positive(m.J, 'model.J')
        if m.rates.mode not in {'fixed', 'learned'} or m.rates.spacing not in {'log', 'linear'}:
            raise ValueError('unknown rates mode/spacing')
        low, high = m.rates.bounds
        if not 0 < low <= high:
            raise ValueError('rate bounds must be positive and ordered')
    if m.writer not in {'fixed', 'learned', 'native_delta'} or m.encode not in {'terminal', 'stream'}:
        raise ValueError('unknown writer/encode mode')
    if not m.method or not m.reader.kind or m.reader.activation not in {'silu', 'relu', 'gelu', 'tanh'}:
        raise ValueError('method/reader/activation required')
    _positive(m.reader.width, 'reader.width')
    _positive(m.reader.layers, 'reader.layers')
    if m.learned_abstention_threshold is not None and not 0 <= m.learned_abstention_threshold <= 1:
        raise ValueError('learned abstention threshold must be in [0,1]')
    for name in ('microbatch', 'effective_batch', 'learning_rate', 'optimizer_steps'):
        _positive(getattr(t, name), f'training.{name}')
    _positive(t.weight_decay, 'weight_decay', zero=True)
    if t.effective_batch % t.microbatch:
        raise ValueError('effective_batch must be divisible by microbatch')
    if t.optimizer != 'AdamW':
        raise ValueError('unregistered optimizer')
    if r.device not in {'cpu', 'mps'}:
        raise ValueError('device must be cpu or mps')
    for name in ('cpu_threads', 'smoke_additional_allocation_limit_bytes', 'checkpoint_retention'):
        _positive(getattr(r, name), f'resources.{name}')
    for name in ('cache_limit_bytes', 'asset_disk_budget_bytes'):
        _positive(getattr(r, name), f'resources.{name}', zero=True)
    if not 0 <= r.reserved_fraction_of_derived_envelope < 1:
        raise ValueError('reserve fraction must be in [0,1)')
    if r.training_envelope_bytes is not None:
        _positive(r.training_envelope_bytes, 'training_envelope_bytes')
    if not r.resource_provenance or not r.policy:
        raise ValueError('resource provenance and policy required')
    if n.reference != 'cpu_float64':
        raise ValueError('reference must be cpu_float64')
    _positive(n.rtol, 'rtol', zero=True)
    _positive(n.atol, 'atol', zero=True)
    for name in ('independent_histories', 'training_replicates'):
        if getattr(c, name) is not None:
            _positive(getattr(c, name), f'confirmation.{name}')
    for name in ('rank','max_parameters','max_macs'):
        if getattr(m.reader,name) is not None: _positive(getattr(m.reader,name),'reader.'+name)
    dev=config.development
    if dev is not None:
        if config.phase!='development' or dev.mode not in {'calibration','simple','learning'}:
            raise ValueError('development policy requires explicit development phase/mode')
        if not dev.lengths or len(set(dev.lengths))!=len(dev.lengths) or min(dev.lengths)<=0:
            raise ValueError('invalid development length population')
        if d.length not in dev.lengths or not 0<=dev.data_seed<2**63:
            raise ValueError('development length/data seed mismatch')
        for name in ('fit_histories_per_cell','eval_histories_per_cell'):
            _positive(getattr(dev,name),'development.'+name)
        if not dev.milestones or tuple(sorted(set(dev.milestones)))!=dev.milestones or dev.milestones[0]!=0 or dev.milestones[-1]!=t.optimizer_steps:
            raise ValueError('development milestones must span immutable training horizon')
        if dev.gradient_clip_norm is not None: _positive(dev.gradient_clip_norm,'gradient_clip_norm')
        if (dev.cache_manifest_path is None)!=(dev.cache_manifest_hash is None):
            raise ValueError('cache manifest path and hash must be paired')
        if (dev.calibration_path is None)!=(dev.calibration_hash is None):
            raise ValueError('calibration path and hash must be paired')
    if config.phase in {'confirmation', 'replication'}:
        def unresolved(value):
            if value is None or value == '' or value == [] or value == {}:
                return True
            if isinstance(value, dict):
                return any(unresolved(v) for v in value.values())
            if isinstance(value, (tuple, list)):
                return any(unresolved(v) for v in value)
            return False
        missing = [f.name for f in fields(c) if f.name != 'status' and unresolved(getattr(c, f.name))]
        if c.status != 'frozen' or missing or r.training_envelope_bytes is None:
            raise ValueError(f'confirmation requires pilot freeze and resource envelope; unresolved: {missing}')


def load_config(path: Path) -> RunConfig:
    path = Path(path)
    def unique_pairs(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f'duplicate config field: {key}')
            result[key] = value
        return result
    try:
        text = path.read_text(encoding='utf-8')
        value = (json.loads(text, object_pairs_hook=unique_pairs) if path.suffix == '.json'
                 else yaml.load(text, Loader=_UniqueLoader))
    except yaml.YAMLError as exc:
        raise ValueError(f'invalid configuration: {exc}') from exc
    return _parse(value, RunConfig, 'config')


def save_resolved_config(path: Path, config: RunConfig) -> None:
    validate_config(config)
    atomic_json(path, asdict(config))


def config_documents_equal(left, right):
    """After seal checks, permit ONLY known absent/default-null polynomial/multiscale/delta additions.

    Parsing validates both complete schemas. No generic missing/null stripping,
    unknown fields, scientific changes or original seal/hash rewrite is allowed.
    """
    from copy import deepcopy
    for document in (left, right):
        _parse(document, RunConfig, 'config')
    left, right = deepcopy(left), deepcopy(right)
    for document in (left, right):
        document['model'].setdefault('polynomial', None)
        document['model'].setdefault('multiscale', None)
        document['model'].setdefault('delta', None)
        document.setdefault('development', None)
        if document['development'] is not None:
            for key in ('cache_manifest_path','cache_manifest_hash'):
                document['development'].setdefault(key,None)
        for key in ('rank','max_parameters','max_macs'):
            document['model']['reader'].setdefault(key,None)
    return canonical_json(left) == canonical_json(right)
