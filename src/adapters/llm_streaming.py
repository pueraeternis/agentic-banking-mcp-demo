"""Stream final assistant text to the user (OpenAI-compatible chat completions)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from openai import OpenAI

TokenHandler = Callable[[str], None]


def stream_chat_text(
    client: OpenAI,
    *,
    model: str,
    messages: list[Any],
    temperature: float,
    on_token: TokenHandler,
) -> tuple[str, Any]:
    """Stream a text-only completion; invoke on_token for each content delta."""
    stream = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
        stream=True,
    )
    parts: list[str] = []
    usage: Any = None
    for chunk in stream:
        if chunk.usage is not None:
            usage = chunk.usage
        if not chunk.choices:
            continue
        delta = chunk.choices[0].delta
        if delta.content:
            parts.append(delta.content)
            on_token(delta.content)
    return "".join(parts), usage
