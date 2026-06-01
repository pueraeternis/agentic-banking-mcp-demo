"""LLM request/response/error helpers for file diagnostics (plan 03)."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from openai import APIError

logger = logging.getLogger(__name__)

_SECRET_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"(?i)(authorization\s*[:=]\s*bearer\s+)(\S+)"),
    re.compile(r"(?i)(yc_api_key\s*[:=]\s*)(\S+)"),
    re.compile(r"(?i)(api[_-]?key\s*[:=]\s*)(\S+)"),
    re.compile(r"(Api-Key\s+)(\S+)", re.IGNORECASE),
)

INFO_TRUNCATE = 500
DEBUG_TRUNCATE = 8000


def truncate_for_log(text: str, limit: int = INFO_TRUNCATE) -> str:
    """Truncate long text for INFO-level logs."""
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def redact_secrets(text: str) -> str:
    """Mask API keys and Authorization headers in log strings."""
    redacted = text
    for pattern in _SECRET_PATTERNS:
        redacted = pattern.sub(r"\1***REDACTED***", redacted)
    return redacted


def _format_body(body: object | None) -> str:
    if body is None:
        return ""
    if isinstance(body, (dict, list)):
        return redact_secrets(json.dumps(body, ensure_ascii=False))
    return redact_secrets(str(body))


def _status_code(exc: BaseException) -> int | None:
    code = getattr(exc, "status_code", None)
    return code if isinstance(code, int) else None


def log_llm_error(exc: BaseException, *, phase: str, model: str) -> None:
    """Log Yandex/OpenAI failure with status_code and response body when available."""
    parts = [
        f"LLM error phase={phase}",
        f"model={model}",
        f"type={type(exc).__name__}",
    ]
    status = _status_code(exc)
    if status is not None:
        parts.append(f"status_code={status}")

    message = getattr(exc, "message", None)
    if isinstance(message, str) and message:
        parts.append(f"message={redact_secrets(message)}")
    else:
        parts.append(f"message={redact_secrets(str(exc))}")

    if isinstance(exc, APIError):
        body_text = _format_body(exc.body)
        if body_text:
            parts.append(f"body={truncate_for_log(body_text, 4000)}")

        response = getattr(exc, "response", None)
        if response is not None:
            try:
                raw = response.text
            except Exception:
                raw = ""
            if raw:
                parts.append(f"response_text={truncate_for_log(redact_secrets(raw), 4000)}")

    logger.error(" ".join(parts))


def log_llm_request(
    *,
    phase: str,
    model: str,
    message_count: int,
    context_chars: int,
) -> None:
    """Log an outbound chat completion (no message bodies at INFO)."""
    logger.info(
        "LLM request phase=%s model=%s messages=%s context_chars=%s",
        phase,
        model,
        message_count,
        context_chars,
    )


def log_llm_response(
    *,
    phase: str,
    model: str,
    usage: Any,
    content_len: int,
) -> None:
    """Log completion metadata after a successful call."""
    usage_repr = repr(usage) if usage is not None else "none"
    logger.info(
        "LLM response phase=%s model=%s usage=%s content_len=%s",
        phase,
        model,
        usage_repr,
        content_len,
    )


def _message_content(message: dict[str, Any] | Any) -> object | None:
    """Read content from a dict message or an OpenAI message object."""
    if isinstance(message, dict):
        return message.get("content")
    return getattr(message, "content", None)


def messages_context_chars(messages: list[dict[str, Any]]) -> int:
    """Approximate character count of message contents for logging."""
    total = 0
    for message in messages:
        content = _message_content(message)
        if isinstance(content, str):
            total += len(content)
        elif content is not None:
            total += len(str(content))
    return total


def log_messages_debug(phase: str, messages: list[dict[str, Any]]) -> None:
    """Dump messages at DEBUG with redaction and length cap."""
    if not logger.isEnabledFor(logging.DEBUG):
        return
    payload = redact_secrets(json.dumps(messages, ensure_ascii=False))
    logger.debug(
        "LLM context phase=%s messages=%s",
        phase,
        truncate_for_log(payload, DEBUG_TRUNCATE),
    )
