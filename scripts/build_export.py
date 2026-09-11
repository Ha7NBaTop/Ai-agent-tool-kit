"""Freeze a deterministic inventory after tests. Does not copy or publish anything."""
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from verify_export import inventory, ROOT, MANIFEST, verify


def build(root=ROOT):
    document = {"format": 1, "scope": "standalone tracked candidates; excludes this manifest", "files": inventory(root)}
    data = (json.dumps(document, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")
    destination = Path(root) / MANIFEST
    temporary = destination.with_suffix(".tmp")
    temporary.write_bytes(data)
    temporary.replace(destination)
    return verify(root)


if __name__ == "__main__":
    print(json.dumps(build(), indent=2))
