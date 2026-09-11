"""Isolated declarative check process. Never imports or executes target code."""
import hashlib
import json
import sys


def main():
    request = json.loads(sys.stdin.read(1048577))
    checks = []
    for item in request:
        text = item["content"]
        operation = item["operation"]
        actual = hashlib.sha256(text.encode("utf-8")).hexdigest() if operation == "sha256" else text
        ok = item["expected"] in actual if operation == "contains" else actual == item["expected"]
        checks.append({"path": item["path"], "operation": operation, "ok": ok})
    print(json.dumps({"ok": all(c["ok"] for c in checks), "assertions": checks}))
    return 0 if all(c["ok"] for c in checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
