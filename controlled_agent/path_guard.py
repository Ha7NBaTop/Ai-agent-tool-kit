"""Conservative relative paths; no links/reparse points or special files."""
import os
from pathlib import Path, PureWindowsPath
import stat


class Denied(ValueError):
    pass


def relative(value):
    if not isinstance(value, str) or not value or "\\" in value:
        raise Denied("use a nonempty relative POSIX path")
    if PureWindowsPath(value).drive or value.startswith("/") or ":" in value:
        raise Denied("absolute paths and alternate data streams are forbidden")
    parts = value.split("/")
    if any(p in {"", ".."} or p.endswith((" ", ".")) and p != "." for p in parts):
        raise Denied("path traversal or ambiguous path")
    if any(any(ord(c) < 32 for c in p) for p in parts):
        raise Denied("control character in path")
    reserved = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(10)), *(f"LPT{i}" for i in range(10))}
    if any(p.split(".")[0].upper() in reserved for p in parts):
        raise Denied("reserved device path")
    return "/".join(p for p in parts if p != ".") or "."


def within(path, scope):
    # Case-insensitive scope matching on Windows; exact on POSIX.
    if os.name == "nt":
        path, scope = path.casefold(), scope.casefold()
    return scope == "." or path == scope or path.startswith(scope + "/")


def no_links(path):
    path = Path(path).absolute()
    for part in reversed((path, *path.parents)):
        if part.exists() or part.is_symlink():
            info = part.lstat()
            if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
                raise Denied("symlink/junction/reparse point forbidden")
            if not (stat.S_ISDIR(info.st_mode) or stat.S_ISREG(info.st_mode)):
                raise Denied("special file forbidden")
            if stat.S_ISREG(info.st_mode) and info.st_nlink > 1:
                raise Denied("hard-linked input forbidden")
    return path


class PathGuard:
    def __init__(self, root, reads, writes, forbidden):
        self.root = no_links(root).resolve(strict=True)
        if not self.root.is_dir():
            raise Denied("target_root must be a directory")
        self.reads = [relative(p) for p in reads]
        self.writes = [relative(p) for p in writes]
        self.forbidden = [relative(p) for p in forbidden]

    def path(self, value, write=False):
        rel = relative(value)
        for p in rel.split("/"):
            if p.lower() in {".git", ".controlled-agent", ".ai", "__pycache__"} or p.lower().startswith(".env") or p.lower().endswith((".pem", ".key")):
                raise Denied("reserved/secret/runtime path")
        if any(within(rel, p) for p in self.forbidden):
            raise Denied("forbidden path")
        if not any(within(rel, p) for p in (self.writes if write else self.reads)):
            raise Denied("path outside declared scope")
        path = no_links(self.root / rel)
        if not path.resolve().is_relative_to(self.root):
            raise Denied("path escapes target_root")
        return path

    def files(self):
        found = set()
        visited = set()
        examined = 0
        for scope in self.reads:
            start = self.path(scope)
            candidates = [start]
            while candidates:
                candidate = candidates.pop()
                rel = candidate.relative_to(self.root).as_posix()
                try:
                    path = self.path(rel)
                except Denied:
                    continue
                if path.is_file():
                    found.add(rel)
                elif path.is_dir() and path not in visited:
                    visited.add(path)
                    # Never enumerate denied directories or follow reparse points.
                    with os.scandir(self.path(rel)) as entries:
                        for entry in entries:
                            examined += 1
                            if examined > 10000:
                                raise Denied("directory scan exceeds 10000 entries")
                            candidates.append(path / entry.name)
                if len(found) > 200:
                    raise Denied("read scope exceeds 200 files; narrow task scope")
        return sorted(found)
