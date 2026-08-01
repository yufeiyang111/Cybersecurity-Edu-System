"""Read-only snapshot path containment helpers."""
from __future__ import annotations

from pathlib import Path
import re

_DRIVE_PATH = re.compile(r"^[A-Za-z]:")

def _snapshot_root(snapshot_root: str | Path) -> Path | None:
    try:
        root = Path(snapshot_root).resolve()
    except (OSError, TypeError, ValueError):
        return None
    return root if root.is_dir() else None


def _safe_target(snapshot_root: Path, relative_path: str) -> Path | None:
    candidate = snapshot_root.joinpath(*relative_path.split("/"))
    try:
        resolved = candidate.resolve()
        resolved.relative_to(snapshot_root)
    except (OSError, ValueError):
        return None
    if not candidate.is_file() or candidate.is_symlink():
        return None
    return resolved




def _normalize_relative_path(value: str, *, allow_diff_prefix: bool) -> str | None:
    if not isinstance(value, str):
        return None
    path = value.strip()
    if not path or path == "/dev/null" or "\x00" in path or "\\" in path:
        return None
    if allow_diff_prefix and path[:2] in {"a/", "b/"}:
        path = path[2:]
    if path.startswith("/") or path.startswith("~") or _DRIVE_PATH.match(path):
        return None
    parts = path.split("/")
    if not parts or any(part in {"", ".", ".."} for part in parts):
        return None
    return "/".join(parts)
