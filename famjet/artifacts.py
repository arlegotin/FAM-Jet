"""Atomic finite JSON writes; null/status are preserved verbatim."""
import os
from pathlib import Path
import tempfile

from famjet.provenance import canonical_json


def atomic_json(path: Path, value: dict) -> None:
    """Replace one JSON artifact only after serialization and fsync succeed.

    A failed serialization leaves the previous file intact. Temporary files
    live beside the target so os.replace stays on the same filesystem.
    """
    if not isinstance(value, dict):
        raise TypeError('artifact must be a JSON object')
    payload = canonical_json(value) + b'\n'
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f'.{path.name}.', suffix='.tmp', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def atomic_bytes(path: Path, payload: bytes) -> None:
    """Durable same-filesystem replacement for checksummed binary artifacts."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f'.{path.name}.', suffix='.tmp', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        descriptor = os.open(path.parent, os.O_RDONLY)
        try: os.fsync(descriptor)
        finally: os.close(descriptor)
    finally:
        if os.path.exists(temporary): os.unlink(temporary)


def append_jsonl(path: Path, record: dict) -> None:
    """Append and sync complete finite records; interrupted trailing lines reject."""
    payload = canonical_json(record) + b'\n'
    with Path(path).open('ab') as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())
