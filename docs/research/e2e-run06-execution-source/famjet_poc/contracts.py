"""Strict, finite public records and content-bound access grants."""
from dataclasses import asdict, dataclass
import hashlib
import json
import math
from pathlib import Path

from famjet.provenance import canonical_json


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _number(value, *, positive=False, nonnegative=False):
    return type(value) in (int, float) and math.isfinite(value) and (value > 0 if positive else value >= 0 if nonnegative else True)


def _sha(value):
    return type(value) is str and len(value) == 64 and all(c in '0123456789abcdef' for c in value)


@dataclass(frozen=True)
class ShapeSpec:
    key_dim: int
    value_dim: int

    def __post_init__(self):
        _require((type(self.key_dim), type(self.value_dim)) == (int, int) and
                 (self.key_dim, self.value_dim) in {(16, 8), (12, 1)}, 'unsupported shape')

    @classmethod
    def from_json(cls, value):
        _require(type(value) is dict and set(value) == {'key_dim', 'value_dim'}, 'invalid shape fields')
        return cls(**value)

    def to_json(self):
        return json.loads(canonical_json(asdict(self)))


@dataclass(frozen=True)
class PopulationSpec:
    version: str
    shape: ShapeSpec
    namespace: str
    seed: int
    lengths: tuple[int, ...]
    regimes: tuple[str, ...]
    queries_per_history: int
    max_query_attempts: int

    def __post_init__(self):
        from famjet.data._processes import REGIMES
        _require(self.version in {'poc_numeric_v1', 'legacy_golden_v1'}, 'unknown population version')
        _require(isinstance(self.shape, ShapeSpec), 'invalid shape')
        _require(self.namespace in {'training', 'development_fit', 'development_calibration', 'pilot', 'confirmation', 'replication', 'unit_test'}, 'unknown namespace')
        _require(type(self.seed) is int and 0 <= self.seed < 2**63, 'invalid seed')
        _require(type(self.lengths) is tuple and bool(self.lengths) and
                 all(type(n) is int and n > 0 for n in self.lengths), 'invalid lengths')
        _require(type(self.regimes) is tuple and bool(self.regimes) and
                 all(r in REGIMES for r in self.regimes), 'invalid regimes')
        _require(type(self.queries_per_history) is int and self.queries_per_history > 0 and
                 self.queries_per_history % 2 == 0, 'queries_per_history must be positive even')
        _require(type(self.max_query_attempts) is int and self.max_query_attempts > 0, 'invalid attempts')
        if self.version == 'legacy_golden_v1':
            _require(self.shape == ShapeSpec(16, 8) and len(self.lengths) == 1 and
                     len(self.regimes) == 4 and self.namespace in {'training', 'development_fit', 'development_calibration'},
                     'legacy golden only admits exploratory K16/V8 balanced mode')

    @classmethod
    def from_json(cls, value):
        _require(type(value) is dict and set(value) == set(cls.__dataclass_fields__), 'invalid population fields')
        return cls(**{**value, 'shape': ShapeSpec.from_json(value['shape']),
                      'lengths': tuple(value['lengths']), 'regimes': tuple(value['regimes'])})

    def to_json(self):
        return json.loads(canonical_json(asdict(self)))


@dataclass(frozen=True)
class ReaderSpec:
    version: str
    family: str
    query_width: int
    ridge: float
    alpha_min: float
    alpha_max: float
    epsilon: float
    support_floor: float

    def __post_init__(self):
        _require(self.version == 'ridge_v1' and self.family in {'jet', 'bank'} and
                 type(self.query_width) is int and self.query_width in {8, 16}, 'invalid reader version/family/width')
        _require(_number(self.ridge, positive=True) and _number(self.alpha_min, positive=True) and
                 _number(self.alpha_max, positive=True) and self.alpha_max > self.alpha_min and
                 _number(self.epsilon, positive=True) and _number(self.support_floor, nonnegative=True), 'invalid reader constants')

    @classmethod
    def from_json(cls, value):
        _require(type(value) is dict and set(value) == set(cls.__dataclass_fields__), 'invalid reader fields')
        return cls(**value)

    def to_json(self):
        return json.loads(canonical_json(asdict(self)))


@dataclass(frozen=True)
class AccessGrant:
    manifest_path: Path
    manifest_sha256: str
    phase: str
    split: str

    def __post_init__(self):
        _require(isinstance(self.manifest_path, Path) and self.manifest_path.is_file() and
                 _sha(self.manifest_sha256), 'grant requires existing content-identified manifest')
        _require(self.phase in {'pilot', 'confirmation', 'replication', 'test', 'unit_test'} and
                 self.split in {'pilot', 'confirmation', 'replication', 'test'}, 'invalid grant phase/split')

    @classmethod
    def from_json(cls, value):
        _require(type(value) is dict and set(value) == set(cls.__dataclass_fields__), 'invalid grant fields')
        return cls(Path(value['manifest_path']), value['manifest_sha256'], value['phase'], value['split'])

    def to_json(self):
        return json.loads(canonical_json({'manifest_path': str(self.manifest_path),
                                          'manifest_sha256': self.manifest_sha256,
                                          'phase': self.phase, 'split': self.split}))

    def verify(self, *, source_sha256, data_sha256, model_sha256=None, population=None, episode_id=None):
        """Manifest v1: exact phase/split/source/data and optional population/ID inventory.

        The caller must supply the observed source and data hashes. A test grant
        uses phase=unit_test and a separate unit_test namespace/root.
        """
        raw = self.manifest_path.read_bytes()
        _require(hashlib.sha256(raw).hexdigest() == self.manifest_sha256, 'grant manifest bytes changed')
        value = json.loads(raw)
        keys = {'schema_version', 'kind', 'phase', 'split', 'source_sha256', 'model_sha256', 'data_sha256',
                'population', 'episode_ids'}
        _require(type(value) is dict and set(value) == keys and value['schema_version'] == 1 and
                 value['kind'] == 'famjet_poc_access' and value['phase'] == self.phase and
                 value['split'] == self.split and value['source_sha256'] == source_sha256 and
                 value['data_sha256'] == data_sha256 and _sha(source_sha256) and _sha(data_sha256) and
                 _sha(value['model_sha256']),
                 'grant source/data/phase commitment mismatch')
        if model_sha256 is not None:
            _require(value['model_sha256'] == model_sha256, 'grant model commitment mismatch')
        if population is not None:
            _require(value['population'] == population.to_json(), 'grant population commitment mismatch')
        if episode_id is not None:
            _require(type(value['episode_ids']) is list and episode_id in value['episode_ids'] and
                     len(value['episode_ids']) == len(set(value['episode_ids'])), 'grant episode inventory mismatch')
        return value


def source_sha256():
    """Reader/data/contracts, frozen core files and lock; excludes future runners."""
    directory = Path(__file__).resolve().parent
    root = directory.parent
    paths = [directory / name for name in ('__init__.py', 'contracts.py', 'data.py', 'models.py')]
    paths += sorted((root / 'famjet').rglob('*.py'))
    paths += [root / 'requirements.lock']
    return hashlib.sha256(canonical_json({str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
                                         for path in paths})).hexdigest()
