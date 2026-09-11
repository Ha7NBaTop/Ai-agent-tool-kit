"""Verify exported tracked tree without the CI checkout's Git metadata."""
import shutil
import tempfile
from pathlib import Path
from verify_export import ROOT, verify

with tempfile.TemporaryDirectory(prefix="controlled-agent-ci-") as temp:
    copy = Path(temp) / "export"
    shutil.copytree(ROOT, copy, ignore=shutil.ignore_patterns(".git"))
    print(verify(copy))
