"""Atomic checkpoints and immutable content-addressed documents."""
import hashlib
import json
import os
from pathlib import Path
import tempfile
from .path_guard import no_links


def encoded(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")


def digest(data):
    return hashlib.sha256(data).hexdigest()


def object_hash(value):
    return digest(encoded(value))


def atomic_bytes(path, data, *, create=False):
    path = no_links(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=".agent-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        if create:
            os.link(temporary, path)  # exclusive publication; never overwrite
        else:
            os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def atomic_json(path, value):
    atomic_bytes(path, encoded(value))


def freeze(directory, value):
    data = encoded(value)
    name = digest(data)
    path = Path(directory) / (name + ".json")
    try:
        atomic_bytes(path, data, create=True)
    except FileExistsError:
        if no_links(path).read_bytes() != data:
            raise ValueError("immutable document corrupted")
    return name


def thaw(directory, ref):
    if len(ref) != 64 or any(c not in "0123456789abcdef" for c in ref):
        raise ValueError("invalid content-addressed reference")
    data = no_links(Path(directory) / (ref + ".json")).read_bytes()
    if digest(data) != ref:
        raise ValueError("immutable document hash mismatch")
    return json.loads(data)
