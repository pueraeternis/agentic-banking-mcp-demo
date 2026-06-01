"""Tests for streaming text-only chat completions (no live API)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from adapters.llm_streaming import stream_chat_text


def _chunk(*, content: str | None = None, usage: object | None = None) -> SimpleNamespace:
    delta = SimpleNamespace(content=content)
    return SimpleNamespace(
        choices=[SimpleNamespace(delta=delta)] if content is not None else [],
        usage=usage,
    )


def test_stream_chat_text_assembles_and_invokes_on_token() -> None:
    usage = SimpleNamespace(prompt_tokens=1, completion_tokens=2)
    chunks = [
        _chunk(content="Привет"),
        _chunk(content=", мир"),
        SimpleNamespace(choices=[], usage=usage),
    ]
    client = MagicMock()
    client.chat.completions.create.return_value = chunks

    tokens: list[str] = []
    text, returned_usage = stream_chat_text(
        client,
        model="gpt://folder/model/latest",
        messages=[{"role": "user", "content": "test"}],
        temperature=0.3,
        on_token=tokens.append,
    )

    assert text == "Привет, мир"
    assert tokens == ["Привет", ", мир"]
    assert returned_usage is usage
    client.chat.completions.create.assert_called_once_with(
        model="gpt://folder/model/latest",
        messages=[{"role": "user", "content": "test"}],
        temperature=0.3,
        stream=True,
    )
