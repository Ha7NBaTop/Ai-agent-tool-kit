"""Bounded local functions with write-ahead hash-based recovery."""
import json
import os
import subprocess
import sys
from .config import ROOT, CODE, load
from .contracts import validate
from .manifests import atomic_bytes, digest, object_hash
from .permissions import require_tool
from .redaction import reject_secrets, clean

MAX_FILE = 65536


def definition(name, fields):
    return {"type": "function", "name": name, "description": "Scoped local " + name,
            "strict": True, "parameters": {"type": "object", "properties": fields, "required": list(fields), "additionalProperties": False}}


TEXT = {"type": "string"}
INTEGER = {"type": "integer"}
TOOL_DEFINITIONS = [
    definition("list_files", {}),
    definition("read_file", {"path": TEXT, "offset": INTEGER, "limit": INTEGER}),
    definition("search_text", {"path": TEXT, "text": TEXT}),
    definition("create_file", {"path": TEXT, "content": TEXT}),
    definition("replace_text", {"path": TEXT, "expected_sha256": TEXT, "old": TEXT, "new": TEXT}),
    definition("run_check", {"profile": TEXT}),
]


def read_bytes(path):
    with path.open("rb") as stream:
        data = stream.read(MAX_FILE + 1)
    if len(data) > MAX_FILE:
        raise ValueError("file exceeds 65536 bytes; narrow task inputs")
    data.decode("utf-8")
    reject_secrets(data.decode("utf-8"))
    return data


class Tools:
    def __init__(self, guard, task, store, ledger, budget, *, fault=None):
        self.guard, self.task, self.store, self.ledger, self.budget = guard, task, store, ledger, budget
        self.fault = fault or (lambda stage: None)

    def snapshot(self):
        result = {}
        total = 0
        for rel in self.guard.files():
            data = read_bytes(self.guard.path(rel))
            total += len(data)
            if total > 524288:
                raise ValueError("packet scope exceeds 512 KiB")
            result[rel] = {"sha256": digest(data), "content": data.decode("utf-8")}
        return result

    def check(self, name):
        if name not in self.task["checks"]:
            raise ValueError("unknown check profile")
        profile = self.task["checks"][name]
        items = []
        for assertion in profile["assertions"]:
            path = self.guard.path(assertion["path"])
            if not path.is_file():
                return {"profile": name, "ok": False, "reason": "check input missing"}
            items.append({**assertion, "content": read_bytes(path).decode("utf-8")})
        runner = CODE / "check_runner.py"
        # Isolated Python excludes cwd/PYTHONPATH/user site; target content is stdin data.
        argv = [sys.executable, "-I", "-B", str(runner)]
        timeout = min(profile["timeout"], self.budget.remaining_seconds())
        if timeout <= 0:
            self.budget.check()
        environment = {k: os.environ[k] for k in ("SYSTEMROOT", "WINDIR") if k in os.environ}
        try:
            result = subprocess.run(argv, input=json.dumps(items), cwd=self.guard.root, timeout=timeout,
                                    shell=False, capture_output=True, text=True, encoding="utf-8", env=environment)
        except subprocess.TimeoutExpired:
            return {"profile": name, "ok": False, "reason": "timeout"}
        parsed = json.loads(result.stdout)
        return {"profile": name, "ok": result.returncode in profile["allowed_exit_codes"] and parsed["ok"],
                "exit_code": result.returncode, "assertions": parsed["assertions"],
                "argv": profile["argv"], "cwd": profile["cwd"], "timeout": profile["timeout"]}

    def invoke(self, role, name, arguments, operation_id):
        require_tool(role, name)
        schema = next(d["parameters"] for d in TOOL_DEFINITIONS if d["name"] == name)
        validate(arguments, schema)
        reject_secrets(arguments)
        signature = object_hash({"tool": name, "arguments": arguments})
        operations = self.store.data["operations"]
        previous = operations.get(operation_id)
        if previous and previous["signature"] != signature:
            raise ValueError("idempotency operation conflict")
        if previous and previous["status"] == "DONE":
            return previous["result"]
        if not previous:
            self.budget.tool()
        if name in {"create_file", "replace_text"}:
            result = self._mutate(name, arguments, operation_id, signature, previous)
        elif name == "list_files":
            result = {"files": self.guard.files()}
        elif name == "read_file":
            if arguments["offset"] < 0 or not 1 <= arguments["limit"] <= 16384:
                raise ValueError("invalid chunk bounds")
            data = read_bytes(self.guard.path(arguments["path"]))
            text = data.decode("utf-8")
            offset, limit = arguments["offset"], arguments["limit"]
            result = {"content": text[offset:offset+limit], "sha256": digest(data), "total_characters": len(text)}
        elif name == "search_text":
            if not arguments["text"] or len(arguments["text"]) > 1024:
                raise ValueError("literal search needs 1..1024 characters")
            text = read_bytes(self.guard.path(arguments["path"])).decode("utf-8")
            result = {"lines": [{"line": i, "text": line[:512]} for i, line in enumerate(text.splitlines(), 1) if arguments["text"] in line][:100]}
        else:
            result = self.check(arguments["profile"])
        reject_secrets(result)
        operation = operations.get(operation_id, {"signature": signature, "tool": name, "sequence": len(operations)})
        operation.update(status="DONE", result=result)
        operations[operation_id] = operation
        self.store.save()
        self.ledger.append({"operation_id": operation_id, "tool": name, "arguments_hash": signature, "result_hash": object_hash(result), "status": "DONE"})
        return result

    def _mutate(self, name, args, operation_id, signature, previous):
        path = self.guard.path(args["path"], write=True)
        current = read_bytes(path) if path.exists() else None
        before = digest(current) if current is not None else None
        if previous and before == previous["after_sha256"]:
            return {"path": args["path"], "before_sha256": previous["before_sha256"], "after_sha256": before, "recovered": True}
        if previous and before != previous["before_sha256"]:
            raise ValueError("recovery input changed; mutation blocked")
        if name == "create_file":
            if current is not None:
                raise ValueError("create_file requires an absent target")
            data = args["content"].encode("utf-8")
        else:
            if current is None or before != args["expected_sha256"]:
                raise ValueError("expected_sha256 conflict")
            text = current.decode("utf-8")
            if not args["old"] or text.count(args["old"]) != 1:
                raise ValueError("old text must occur exactly once")
            data = text.replace(args["old"], args["new"], 1).encode("utf-8")
        if len(data) > MAX_FILE:
            raise ValueError("write exceeds maximum file bytes")
        after = digest(data)
        sequence = previous["sequence"] if previous else len(self.store.data["operations"])
        intent = {"signature": signature, "tool": name, "path": args["path"], "before_sha256": before, "after_sha256": after, "status": "INTENT", "sequence": sequence}
        self.store.data["operations"][operation_id] = intent
        self.store.save()
        self.ledger.append({"operation_id": operation_id, **intent})
        self.fault("before_write")
        # Revalidate immediately before publication. Concurrent hostile OS users are outside threat model.
        path = self.guard.path(args["path"], write=True)
        if (digest(read_bytes(path)) if path.exists() else None) != before:
            raise ValueError("input changed before publication")
        atomic_bytes(path, data, create=name == "create_file")
        self.fault("after_write")
        if digest(read_bytes(self.guard.path(args["path"]))) != after:
            raise ValueError("post-write hash mismatch")
        return {"path": args["path"], "before_sha256": before, "after_sha256": after, "recovered": False}
