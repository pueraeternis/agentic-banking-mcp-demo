"""Tests for REPL file logging setup and LLM error redaction."""

from __future__ import annotations

import logging
from pathlib import Path

import httpx
import pytest
from openai import APIError

from adapters import logging_setup
from adapters.llm_logging import log_llm_error, redact_secrets


@pytest.fixture
def isolated_repo_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Minimal repo layout so setup_logging writes under tmp_path/logs/."""
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'test'\n", encoding="utf-8")
    (tmp_path / "main.py").write_text("# test\n", encoding="utf-8")
    monkeypatch.setattr(logging_setup, "_LOG_FILE", None)
    monkeypatch.setattr("adapters.logging_setup.get_repo_root", lambda: tmp_path)
    return tmp_path


def test_setup_logging_creates_file_and_file_handler(isolated_repo_root: Path) -> None:
    log_path = logging_setup.setup_logging()

    assert log_path.parent == isolated_repo_root / "logs"
    assert log_path.is_file()
    assert log_path.name.startswith("repl-")
    assert log_path.suffix == ".log"

    root = logging.getLogger()
    assert any(isinstance(handler, logging.FileHandler) for handler in root.handlers)
    console_handlers = [
        handler
        for handler in root.handlers
        if isinstance(handler, logging.StreamHandler) and not isinstance(handler, logging.FileHandler)
    ]
    assert not console_handlers

    root.info("setup_logging test marker")
    assert "setup_logging test marker" in log_path.read_text(encoding="utf-8")


def test_log_llm_error_redacts_api_key(isolated_repo_root: Path) -> None:
    _ = isolated_repo_root
    secret = "super-secret-yandex-key-12345"  # noqa: S105
    logging_setup.setup_logging()
    request = httpx.Request("POST", "https://ai.api.cloud.yandex.net/v1/chat/completions")
    exc = APIError(
        "401 Unauthorized",
        request,
        body={"error": {"message": f"YC_API_KEY={secret} is invalid"}},
    )

    log_llm_error(exc, phase="router", model="gpt://folder/model/latest")

    root = logging.getLogger()
    messages = []
    for handler in root.handlers:
        if isinstance(handler, logging.FileHandler):
            handler.flush()
            messages.append(Path(handler.baseFilename).read_text(encoding="utf-8"))

    combined = "\n".join(messages)
    assert secret not in combined
    assert "***REDACTED***" in combined or "REDACTED" in redact_secrets(secret)


def test_invalid_log_level_defaults_to_info(
    isolated_repo_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LOG_LEVEL", "NOT_A_LEVEL")
    log_path = logging_setup.setup_logging()
    text = log_path.read_text(encoding="utf-8")
    assert "Invalid LOG_LEVEL" in text
    assert logging.getLogger().level == logging.INFO
