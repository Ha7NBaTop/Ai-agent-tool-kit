"""Versioned resource loading, independent of the process working directory."""
import json
from pathlib import Path
from .manifests import digest

ROOT = Path(__file__).resolve().parent.parent
CODE = Path(__file__).resolve().parent
if (CODE / "_resources").is_dir():
    ROOT = CODE / "_resources"


def resource(path):
    return (ROOT / path).read_text(encoding="utf-8")


def load(path):
    return json.loads(resource(path))


def hashes():
    result = {p.relative_to(ROOT).as_posix(): digest(p.read_bytes())
              for folder in ("config", "prompts", "schemas")
              for p in sorted((ROOT / folder).rglob("*")) if p.is_file()}
    result.update({"controlled_agent/" + p.name: digest(p.read_bytes()) for p in sorted(CODE.glob("*.py"))})
    return result
