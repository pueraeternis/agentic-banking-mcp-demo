"""Repository root and absolute paths for files under data/."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=1)
def get_repo_root() -> Path:
    """Return project root (directory with pyproject.toml and main.py)."""
    start = Path(__file__).resolve().parent
    for candidate in (start, *start.parents):
        if (candidate / "pyproject.toml").is_file() and (candidate / "main.py").is_file():
            return candidate

    return Path(__file__).resolve().parents[2]


def resolve_data_path(relative: str) -> Path:
    """Resolve config-relative paths (e.g. data/banking.db) to an absolute path."""
    normalized = relative.replace("\\", "/").strip()
    path = Path(normalized)
    if path.is_absolute():
        return path
    return get_repo_root() / path
