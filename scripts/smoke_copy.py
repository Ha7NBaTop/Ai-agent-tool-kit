"""Full-suite and launcher smoke from a temporary clean standalone copy; no installation."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from verify_export import ROOT, verify


def main():
    verify(ROOT)
    environment = {k: v for k, v in os.environ.items() if k not in {"OPENAI_API_KEY", "PYTHONPATH", "PYTHONHOME"}}
    environment.update(PYTHONDONTWRITEBYTECODE="1", CONTROLLED_AGENT_LIVE_ENABLED="0")
    with tempfile.TemporaryDirectory(prefix="controlled agent standalone smoke ") as temporary:
        copy = Path(temporary) / "independent toolkit with spaces"
        shutil.copytree(ROOT, copy)
        commands = [
            [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"],
            [sys.executable, "-m", "controlled_agent.cli", "demo"],
            [sys.executable, "-m", "controlled_agent.cli", "doctor"],
            [sys.executable, "-m", "controlled_agent.cli", "task", "validate", "examples/hello-safe-edit"],
            [sys.executable, "-m", "controlled_agent.cli", "plan", "examples/hello-safe-edit"],
        ]
        commands.append(["powershell", "-NoProfile", "-File", "agent.ps1", "demo"] if os.name == "nt" else ["sh", "agent.sh", "demo"])
        if os.name == "nt":
            commands.append(["cmd", "/d", "/c", "agent.cmd", "demo"])
        for command in commands:
            result = subprocess.run(command, cwd=copy, env=environment, capture_output=True, text=True, encoding="utf-8", timeout=120)
            print("COMMAND:", " ".join(["python" if command[0] == sys.executable else command[0], *command[1:]]))
            print(result.stdout)
            print(result.stderr)
            if result.returncode:
                if command[0] == "powershell" and any(marker in result.stderr for marker in ("PSSecurityException", "running scripts is disabled")):
                    print("SKIPPED: host PowerShell execution policy; unchanged. Testing agent.cmd instead.")
                    continue
                return result.returncode
        print("TEMPORARY_COPY:", verify(copy))
    print("PASS: standalone copy removed; no installation, live API, Git or publication")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
