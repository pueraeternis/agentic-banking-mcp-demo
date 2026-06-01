"""Unit tests for repository path resolution."""

from __future__ import annotations

from pathlib import Path

from adapters.paths import get_repo_root, resolve_data_path


def test_get_repo_root_contains_pyproject_and_main() -> None:
    root = get_repo_root()
    assert (root / "pyproject.toml").is_file()
    assert (root / "main.py").is_file()
    assert (root / "src" / "adapters").is_dir()


def test_resolve_data_path_relative_under_repo() -> None:
    root = get_repo_root()
    resolved = resolve_data_path("data/bank_services.md")
    assert resolved == root / "data" / "bank_services.md"
    assert resolved.is_file()


def test_resolve_data_path_absolute_unchanged(tmp_path: Path) -> None:
    absolute = tmp_path / "custom.db"
    absolute.touch()
    assert resolve_data_path(str(absolute)) == absolute
