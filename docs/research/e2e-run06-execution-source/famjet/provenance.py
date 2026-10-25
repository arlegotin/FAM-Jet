"""Stable JSON identities and explicitly named random-seed namespaces."""
from dataclasses import asdict
import hashlib
import json
import math
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from famjet.config import RunConfig


def _check_json(value: object) -> None:
    if value is None or type(value) in (str, bool, int):
        return
    if type(value) is float:
        if not math.isfinite(value):
            raise ValueError('JSON numbers must be finite')
        return
    if type(value) in (list, tuple):
        for item in value:
            _check_json(item)
        return
    if type(value) is dict:
        for key, item in value.items():
            if type(key) is not str:
                raise TypeError('JSON object keys must be strings')
            _check_json(item)
        return
    raise TypeError(f'Unsupported JSON value: {type(value).__name__}')


def canonical_json(value: object) -> bytes:
    """Version-1 encoding: sorted keys, UTF-8, no spaces, finite JSON only."""
    _check_json(value)
    return json.dumps(value, sort_keys=True, ensure_ascii=False,
                      separators=(',', ':'), allow_nan=False).encode('utf-8')


def canonical_hash(value: object) -> str:
    return hashlib.sha256(canonical_json(value)).hexdigest()


def derive_seed(root: int, namespace: str, identity: str) -> int:
    """SHA-256(versioned canonical object), first 8 bytes big-endian, low 63 bits.

    The nonnegative signed-64-bit result is accepted by Python/NumPy/torch seed
    entry points. No global RNG is seeded or changed by this function.
    """
    if type(root) is not int or not 0 <= root < 2**63:
        raise ValueError('root must be a nonnegative signed-64-bit seed')
    if not isinstance(namespace, str) or not namespace or not isinstance(identity, str) or not identity:
        raise ValueError('namespace and identity must be nonempty strings')
    digest = hashlib.sha256(canonical_json(dict(schema_version=1, root=root,
                                               namespace=namespace, identity=identity))).digest()
    return int.from_bytes(digest[:8], 'big') & (2**63 - 1)


def build_provenance(*, config: 'RunConfig', source_revision: str, source_diff: str,
                     data_identity: dict, parameters: dict, lock_path: Path,
                     environment: dict) -> dict:
    """Caller supplies observed source/data identities; never invent Git state.

    Lock hashes are SHA-256 of exact bytes; other content uses canonical JSON.
    Parameter identity is independent of source, config, and data identities.
    """
    if not isinstance(source_revision, str) or not source_revision:
        raise ValueError('source_revision must be explicit')
    data_identity = json.loads(canonical_json(data_identity))
    environment = json.loads(canonical_json(environment))
    return dict(schema_version=1,
                source=dict(revision=source_revision,
                            diff_hash=hashlib.sha256(source_diff.encode('utf-8')).hexdigest(),
                            status='clean' if not source_diff else 'modified'),
                config_hash=canonical_hash(asdict(config)),
                data_hash=canonical_hash(data_identity),
                parameter_hash=canonical_hash(parameters),
                lock_hash=hashlib.sha256(lock_path.read_bytes()).hexdigest(),
                environment_hash=canonical_hash(environment),
                data_identity=data_identity, environment=environment)
