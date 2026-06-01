"""In-memory chat history for one REPL session."""

from __future__ import annotations

from typing import Any


class SessionMemory:
    """Shared message list for router and agent paths."""

    def __init__(self) -> None:
        self._messages: list[dict[str, Any]] = []

    def append(self, message: dict[str, Any]) -> None:
        """Append a chat message."""
        self._messages.append(message)

    def extend(self, messages: list[dict[str, Any]]) -> None:
        """Append multiple messages."""
        self._messages.extend(messages)

    def get_messages(self) -> list[dict[str, Any]]:
        """Return a shallow copy of the session history."""
        return list(self._messages)

    def clear(self) -> None:
        """Reset session history."""
        self._messages.clear()

    def ensure_system_prompt(self, content: str) -> None:
        """Prepend system message if the session has no system role yet."""
        if self._messages and self._messages[0].get("role") == "system":
            return
        self._messages.insert(0, {"role": "system", "content": content})

    def pop_last(self) -> dict[str, Any] | None:
        """Remove and return the last message, if any."""
        if not self._messages:
            return None
        return self._messages.pop()
