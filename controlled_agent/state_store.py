"""Root-wide OS lease and atomic persistent state. A crash releases the OS lock."""
from contextlib import contextmanager
import json
import os
from pathlib import Path
import time
from .manifests import atomic_json
from .path_guard import no_links
from .redaction import reject_secrets

TRANSITIONS = {
    "PENDING": {"PLANNED"}, "PLANNED": {"IMPLEMENTING"},
    "IMPLEMENTING": {"VALIDATING"}, "VALIDATING": {"PACKET_FROZEN", "IMPLEMENTING"},
    "PACKET_FROZEN": {"REVIEWING"}, "REVIEWING": {"READY_FOR_HUMAN", "IMPLEMENTING"},
    "READY_FOR_HUMAN": {"ACCEPTED", "REJECTED"},
    "ACCEPTED": set(), "REJECTED": set(), "BLOCKED": set(), "FAILED": set(), "PARTIAL": set(),
}


@contextmanager
def lease(root):
    directory = no_links(Path(root) / ".controlled-agent")
    directory.mkdir(exist_ok=True)
    lock = no_links(directory / "master.lock")
    with lock.open("a+b") as stream:
        stream.seek(0, 2)
        if not stream.tell():
            stream.write(b"0"); stream.flush()
        stream.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            raise ValueError("master/writer lease already held for target root") from None
        try:
            yield
        finally:
            stream.seek(0)
            if os.name == "nt":
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream, fcntl.LOCK_UN)


class StateStore:
    def __init__(self, root, task_id, task_hash, mode):
        self.directory = no_links(Path(root) / ".controlled-agent" / task_id)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.path = no_links(self.directory / "checkpoint.json")
        if self.path.exists():
            self.data = json.loads(self.path.read_text(encoding="utf-8"))
            if self.data["task_hash"] != task_hash or self.data["mode"] != mode:
                raise ValueError("task or fake/live mode changed; use new task_id")
        else:
            self.data = {"task_hash": task_hash, "mode": mode, "state": "PENDING", "calls": {},
                         "operations": {}, "packets": [], "cycle": 0, "history": ["PENDING"],
                         "started": time.time(), "usage": {"input_tokens": 0, "output_tokens": 0, "model_calls": 0, "tool_calls": 0, "repairs": 0},
                         "unresolved": []}
            self.save()

    def save(self):
        reject_secrets(self.data)
        no_links(self.path)
        atomic_json(self.path, self.data)

    def transition(self, state, *, human=False):
        current = self.data["state"]
        if state in {"ACCEPTED", "REJECTED"} and not human:
            raise ValueError("named human decision required")
        if state not in TRANSITIONS[current] and not (state in {"BLOCKED", "FAILED", "PARTIAL"} and current not in {"ACCEPTED", "REJECTED"}):
            raise ValueError(f"invalid state transition: {current} -> {state}")
        self.data["state"] = state
        self.data["history"].append(state)
        self.save()
