"""Verify a closed candidate inventory, content hashes and distribution hygiene."""
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = "EXPORT-MANIFEST.json"
MODULES = "__init__ cli contracts config router permissions path_guard tools tool_loop openai_provider fake_provider orchestrator state_store ledger manifests redaction budget check_runner".split()
REQUIRED = set("AGENTS.md README.md README_RU.md SECURITY.md CONTRIBUTING.md CHANGELOG.md LICENSE-CHOICE.md pyproject.toml .gitignore agent.ps1 agent.sh".split())
REQUIRED.update("controlled_agent/" + m + ".py" for m in MODULES)
REQUIRED.update("config/" + m + ".json" for m in ("models", "permissions", "budgets"))
REQUIRED.update("schemas/" + m + ".schema.json" for m in ("task", "worker_result", "reviewer_result", "run_manifest"))
REQUIRED.update("prompts/" + m + ".md" for m in ("implementer", "critical_reviewer"))
REQUIRED.update("docs/" + m + ".md" for m in ("QUICKSTART_RU", "API_SETUP_RU", "ARCHITECTURE", "THREAT_MODEL", "RELEASE_CHECKLIST_RU"))
REQUIRED.update({"templates/task.json", "templates/acceptance.md", "examples/hello-safe-edit/task.json",
                 "agent.cmd",
                 "examples/hello-safe-edit/input/request.txt", "examples/hello-safe-edit/expected/hello.txt",
                 "scripts/build_export.py", "scripts/verify_export.py", "scripts/wheel_backend.py",
                 "tests/test_toolkit.py", ".github/workflows/tests.yml"})
KEY = re.compile(r"\bsk-" + r"[A-Za-z0-9_-]{16,}")
ABSOLUTE = re.compile(r"(?<![A-Za-z0-9])[A-Za-z]:[\\/]|/(?:Users|home)/[^\s/]+/")


def inventory(root):
    root = Path(root).resolve()
    files = {}
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root).as_posix()
        parts = [p.casefold() for p in path.relative_to(root).parts]
        if path.is_symlink() or getattr(path.lstat(), "st_file_attributes", 0) & 0x400:
            raise ValueError("export contains link/reparse point: " + rel)
        if any(p.startswith(".env") or p in {".git", ".ai", ".controlled-agent", "__pycache__", "sources", "context", "raw", "logs", "node_modules", "dist", "build"} for p in parts):
            raise ValueError("forbidden export path: " + rel)
        if path.suffix.casefold() in {".pyc", ".pyo", ".log", ".jsonl", ".sqlite", ".sqlite3", ".db", ".blob", ".pem", ".key", ".whl"}:
            raise ValueError("forbidden export artifact: " + rel)
        if not path.is_file():
            continue
        data = path.read_bytes()
        if len(data) > 1024 * 1024 or b"\x00" in data:
            raise ValueError("oversized/binary export file: " + rel)
        text = data.decode("utf-8")
        if KEY.search(text) or ABSOLUTE.search(text):
            raise ValueError("secret-like value or absolute host path in: " + rel)
        if rel != MANIFEST:
            files[rel] = {"sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}
    missing = REQUIRED - set(files)
    if missing:
        raise ValueError("missing required files: " + ", ".join(sorted(missing)))
    return files


def verify(root=ROOT):
    files = inventory(root)
    document = json.loads((Path(root) / MANIFEST).read_text(encoding="utf-8"))
    expected = {"format": 1, "scope": "standalone tracked candidates; excludes this manifest", "files": files}
    if document != expected:
        raise ValueError("export hash/inventory mismatch")
    return {"verification": "PASS", "files": len(files), "manifest_sha256": hashlib.sha256((Path(root) / MANIFEST).read_bytes()).hexdigest()}


if __name__ == "__main__":
    try:
        print(json.dumps(verify(), indent=2))
    except (OSError, ValueError) as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(1)
