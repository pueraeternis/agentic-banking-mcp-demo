"""Repository root and absolute paths for files under data/."""

from __future__ import annotations

from pathlib import Path

_REPO_ROOT: Path | None = None


def get_repo_root() -> Path:
    """Return project root (directory with pyproject.toml and main.py)."""
    global _REPO_ROOT
    if _REPO_ROOT is not None:
        return _REPO_ROOT

    start = Path(__file__).resolve().parent
    for candidate in (start, *start.parents):
        if (candidate / "pyproject.toml").is_file() and (candidate / "main.py").is_file():
            _REPO_ROOT = candidate
            return _REPO_ROOT

    _REPO_ROOT = Path(__file__).resolve().parents[2]
    return _REPO_ROOT


def resolve_data_path(relative: str) -> Path:
    """Resolve config-relative paths (e.g. data/banking.db) to an absolute path."""
    normalized = relative.replace("\\", "/").strip()
    path = Path(normalized)
    if path.is_absolute():
        return path
    return get_repo_root() / path
