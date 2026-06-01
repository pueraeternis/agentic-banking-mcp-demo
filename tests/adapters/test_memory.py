"""Unit tests for session memory helpers."""

from __future__ import annotations

from adapters.memory import SessionMemory


def test_get_dialog_messages_excludes_system_and_tool() -> None:
    """Router/simple must not see agent system or tool rows (Yandex single system at start)."""
    memory = SessionMemory()
    memory.ensure_system_prompt("Agent system prompt")
    memory.append({"role": "user", "content": "Привет"})
    memory.append({"role": "assistant", "content": "Здравствуйте"})
    memory.append({"role": "tool", "tool_call_id": "1", "content": "{}"})

    dialog = memory.get_dialog_messages()

    assert len(dialog) == 2
    assert all(m["role"] in {"user", "assistant"} for m in dialog)
