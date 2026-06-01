"""Central file logging for the REPL session (plan 03)."""

from __future__ import annotations

import logging
import os
from datetime import datetime
from pathlib import Path

from adapters.paths import get_repo_root

_LOG_FILE: Path | None = None
_DEFAULT_FORMAT = "%(asctime)s %(levelname)s %(name)s %(message)s"


def get_session_log_path() -> Path | None:
    """Return the log file path for the current REPL session, if configured."""
    return _LOG_FILE


def _parse_log_level(raw: str) -> tuple[int, bool]:
    """Return (logging level, invalid_flag)."""
    name = raw.strip().upper()
    level = logging.getLevelNamesMapping().get(name)
    if isinstance(level, int):
        return level, False
    return logging.INFO, True


def setup_logging() -> Path:
    """Configure root logger with a UTF-8 file handler under repo_root/logs/."""
    global _LOG_FILE  # noqa: PLW0603

    repo_root = get_repo_root()
    logs_dir = repo_root / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().astimezone().strftime("%Y%m%d-%H%M%S")
    log_path = logs_dir / f"repl-{timestamp}.log"
    _LOG_FILE = log_path

    level, invalid = _parse_log_level(os.getenv("LOG_LEVEL", "INFO"))

    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(level)

    handler = logging.FileHandler(log_path, encoding="utf-8")
    handler.setFormatter(logging.Formatter(_DEFAULT_FORMAT))
    root.addHandler(handler)

    setup_logger = logging.getLogger(__name__)
    if invalid:
        setup_logger.warning(
            "Invalid LOG_LEVEL=%r, using INFO",
            os.getenv("LOG_LEVEL"),
        )
    setup_logger.info("Logging to %s (level=%s)", log_path, logging.getLevelName(level))

    return log_path
