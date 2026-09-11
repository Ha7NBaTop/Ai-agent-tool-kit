"""Strict, dependency-free validation for the supported JSON-schema subset."""
import json
import re
from pathlib import Path
from .config import load
from .path_guard import relative, PathGuard, within, no_links
from .redaction import reject_secrets
from .router import route


def validate(value, schema, where="$"):
    types = {"object": dict, "array": list, "string": str, "integer": int, "boolean": bool, "null": type(None)}
    kind = schema.get("type")
    if kind and (type(value) is not types[kind]):
        raise ValueError(f"{where}: expected {kind}")
    if "enum" in schema and value not in schema["enum"]:
        raise ValueError(f"{where}: invalid enum")
    if isinstance(value, dict):
        props = schema.get("properties", {})
        if any(k not in value for k in schema.get("required", [])):
            raise ValueError(f"{where}: missing required field")
        if schema.get("additionalProperties") is False and set(value) - set(props):
            raise ValueError(f"{where}: unknown fields")
        for k, v in value.items():
            if k in props:
                validate(v, props[k], where + "." + k)
    if isinstance(value, list):
        for i, item in enumerate(value):
            validate(item, schema.get("items", {}), f"{where}[{i}]")


def load_task(folder):
    path = Path(folder)
    if path.is_dir():
        path = path / "task.json"
    no_links(path)
    if path.stat().st_size > 65536:
        raise ValueError("task too large")
    task = json.loads(path.read_text(encoding="utf-8"))
    validate(task, load("schemas/task.schema.json"))
    reject_secrets(task)
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,63}", task["task_id"]):
        raise ValueError("invalid task_id")
    if not task["owner"].strip() or not task["objective"].strip():
        raise ValueError("owner and objective required")
    relative(task["target_root"])
    root = (path.parent / task["target_root"]).absolute()
    guard = PathGuard(root, task["allowed_read_paths"], task["allowed_write_paths"], task["forbidden_paths"])
    if not guard.reads or not task["checks"]:
        raise ValueError("read scope and at least one check required")
    # Protect controller, owner-authored contract and check configuration from writes.
    for scope in guard.writes:
        if not any(within(scope, r) for r in guard.reads):
            raise ValueError("write scope must be contained in read scope")
        target = root / scope
        if path.resolve().is_relative_to(target.resolve()):
            raise ValueError("task contract may not be writable")
        from .config import ROOT, CODE
        protected = [CODE] + [ROOT / name for name in ("config", "schemas", "prompts", "scripts", "agent.ps1", "agent.sh", "agent.cmd", "pyproject.toml")]
        if any(p.is_relative_to(target.resolve()) or target.resolve().is_relative_to(p) for p in protected):
            raise ValueError("controller code may not be writable")
    if task["implementer_route"] != "worker_hard_case" or task["reviewer_route"] != "critical_reviewer":
        raise ValueError("exact implementer/reviewer routes required")
    route("writer"); route("reviewer")
    for k in ("input_tokens", "output_tokens", "model_calls", "tool_calls", "wall_seconds", "per_call_output_tokens"):
        if type(task["budget"].get(k)) is not int or task["budget"][k] <= 0:
            raise ValueError(f"positive integer budget required: {k}")
    if type(task["budget"].get("repair_cycles")) is not int or not 0 <= task["budget"]["repair_cycles"] <= 1:
        raise ValueError("repair_cycles must be 0 or 1")
    for name, profile in task["checks"].items():
        if not re.fullmatch(r"[a-z0-9_-]+", name):
            raise ValueError("invalid check profile name")
        if set(profile) != {"argv", "cwd", "timeout", "allowed_exit_codes", "assertions"}:
            raise ValueError("invalid check profile fields")
        if profile["argv"] != ["@python", "@builtin-check"] or profile["cwd"] != "." or profile["allowed_exit_codes"] != [0]:
            raise ValueError("only pinned builtin check argv/cwd/exit codes allowed; arbitrary execution denied")
        if type(profile["timeout"]) is not int or not 1 <= profile["timeout"] <= 30:
            raise ValueError("check timeout must be 1..30 seconds")
        if not isinstance(profile["assertions"], list) or not profile["assertions"]:
            raise ValueError("check needs assertions")
        for assertion in profile["assertions"]:
            if set(assertion) != {"path", "operation", "expected"} or assertion["operation"] not in {"equals", "contains", "sha256"} or not isinstance(assertion["expected"], str):
                raise ValueError("invalid declarative assertion")
            guard.path(assertion["path"])
    return task, guard
