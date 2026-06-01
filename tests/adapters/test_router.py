"""Tests for semantic router structured output (no live API)."""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import MagicMock

from openai import APIError

from adapters.config import AppConfig
from adapters.memory import SessionMemory
from adapters.router import (
    ROUTER_RESPONSE_SCHEMA,
    _parse_route_from_content,
    route_user_message,
    router_response_format,
)


def test_router_response_format_schema() -> None:
    fmt = router_response_format()
    assert fmt["type"] == "json_schema"
    schema = fmt["json_schema"]["schema"]
    assert schema == ROUTER_RESPONSE_SCHEMA
    assert schema["properties"]["route"]["enum"] == ["simple", "agent"]


def test_parse_route_from_content() -> None:
    assert _parse_route_from_content('{"route": "simple"}') == "simple"
    assert _parse_route_from_content('{"route": "agent"}') == "agent"
    assert _parse_route_from_content('{"route": "unknown"}') is None


def test_route_user_message_uses_structured_output() -> None:
    memory = SessionMemory()
    memory.append({"role": "user", "content": "Привет"})

    client = MagicMock()
    client.chat.completions.create.return_value = SimpleNamespace(
        choices=[
            SimpleNamespace(message=SimpleNamespace(content=json.dumps({"route": "simple"}))),
        ],
        usage=SimpleNamespace(prompt_tokens=1, completion_tokens=2),
    )

    config = AppConfig(
        folder_id="f",
        api_key="k",
        model_router="qwen-test",
        model_agent="qwen-agent",
        database_path="data/banking.db",
        mcp_server_module="mcp_servers.banking_server",
        stream_final_response=True,
    )

    route = route_user_message(client=client, config=config, memory=memory)
    assert route == "simple"

    call_kwargs = client.chat.completions.create.call_args.kwargs
    assert call_kwargs["response_format"] == router_response_format()
    assert call_kwargs["temperature"] == 0.0


def test_route_user_message_fallback_on_api_error() -> None:
    memory = SessionMemory()
    memory.append({"role": "user", "content": "Привет"})

    err = APIError("unsupported", request=MagicMock(), body=None)  # type: ignore[arg-type]
    ok_response = SimpleNamespace(
        choices=[
            SimpleNamespace(message=SimpleNamespace(content='{"route": "agent"}')),
        ],
        usage=None,
    )
    client = MagicMock()
    client.chat.completions.create.side_effect = [err, ok_response]

    config = AppConfig(
        folder_id="f",
        api_key="k",
        model_router="qwen-test",
        model_agent="qwen-agent",
        database_path="data/banking.db",
        mcp_server_module="mcp_servers.banking_server",
        stream_final_response=False,
    )

    route = route_user_message(client=client, config=config, memory=memory)
    assert route == "agent"
    assert client.chat.completions.create.call_count == 2
    assert "response_format" not in client.chat.completions.create.call_args_list[1].kwargs


def test_route_user_message_defaults_to_agent_on_bad_json() -> None:
    memory = SessionMemory()
    memory.append({"role": "user", "content": "x"})

    client = MagicMock()
    client.chat.completions.create.return_value = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content="not json"))],
        usage=None,
    )

    config = AppConfig(
        folder_id="f",
        api_key="k",
        model_router="qwen-test",
        model_agent="qwen-agent",
        database_path="data/banking.db",
        mcp_server_module="mcp_servers.banking_server",
        stream_final_response=False,
    )

    assert route_user_message(client=client, config=config, memory=memory) == "agent"
