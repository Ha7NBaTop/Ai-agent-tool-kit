"""Minimal stdlib-only PEP 517 wheel backend; no installation during the build task."""
import base64
import csv
import hashlib
import io
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
DIST = "controlled_ai_agent_toolkit-0.1.0.dist-info"


def get_requires_for_build_wheel(config_settings=None):
    return []


def build_wheel(wheel_directory, config_settings=None, metadata_directory=None):
    files = {"controlled_agent/" + p.name: p.read_bytes() for p in (ROOT / "controlled_agent").glob("*.py")}
    for folder in ("config", "schemas", "prompts", "templates", "examples"):
        for p in sorted((ROOT / folder).rglob("*")):
            if p.is_file() and not any(part in {".controlled-agent", "output", "__pycache__"} for part in p.parts):
                files["controlled_agent/_resources/" + p.relative_to(ROOT).as_posix()] = p.read_bytes()
    files[DIST + "/METADATA"] = b"Metadata-Version: 2.1\nName: controlled-ai-agent-toolkit\nVersion: 0.1.0\nRequires-Python: >=3.11\n\nLicense choice pending owner decision.\n"
    files[DIST + "/WHEEL"] = b"Wheel-Version: 1.0\nGenerator: controlled-agent-stdlib\nRoot-Is-Purelib: true\nTag: py3-none-any\n"
    files[DIST + "/entry_points.txt"] = b"[console_scripts]\ncontrolled-agent = controlled_agent.cli:main\n"
    record = io.StringIO(newline="")
    writer = csv.writer(record)
    for name, data in sorted(files.items()):
        value = base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b"=").decode()
        writer.writerow([name, "sha256=" + value, len(data)])
    writer.writerow([DIST + "/RECORD", "", ""])
    files[DIST + "/RECORD"] = record.getvalue().encode()
    name = "controlled_ai_agent_toolkit-0.1.0-py3-none-any.whl"
    output = Path(wheel_directory)
    output.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output / name, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path, data in sorted(files.items()):
            info = zipfile.ZipInfo(path, (2020, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, data)
    return name
