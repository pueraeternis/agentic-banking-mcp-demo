"""Semantic router: simple chat vs agent with tools."""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from typing import Any

from openai import APIError, OpenAI

from adapters.config import AppConfig
from adapters.llm_logging import (
    log_llm_request,
    log_llm_response,
    log_messages_debug,
    messages_context_chars,
)
from adapters.llm_streaming import stream_chat_text
from adapters.memory import SessionMemory

logger = logging.getLogger(__name__)

# JSON Schema for OpenAI-compatible response_format (verified on Yandex MODEL_ROUTER).
ROUTER_RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "route": {
            "type": "string",
            "enum": ["simple", "agent"],
            "description": "simple — chitchat only; agent — bank facts, tools, catalog",
        },
    },
    "required": ["route"],
    "additionalProperties": False,
}

ROUTER_SYSTEM = """Ты — семантический маршрутизатор банковского ассистента.
Верни поле route: "simple" или "agent".

route = "simple" — только общий разговор без фактов о банке: приветствие, благодарность, оффтоп.
НЕ используй simple для услуг, продуктов, тарифов или каталога НАШЕГО банка.

route = "agent" — баланс, клиенты, счета, переводы, услуги и продукты НАШЕГО банка,
любые данные из БД или официального каталога банка.

Если сомневаешься или нужны инструменты/каталог — выбирай "agent"."""

ROUTER_SYSTEM_JSON_FALLBACK_SUFFIX = (
    '\nОтветь ТОЛЬКО JSON без markdown: {"route": "simple"} или {"route": "agent"}.'
)

SIMPLE_SYSTEM = (
    "Ты — вежливый банковский ассистент. Отвечай по-русски на общий разговор. "
    "Не выдумывай балансы, переводы, данные клиентов и каталог услуг банка — "
    "для фактов о банке нужен другой режим."
)


def router_response_format() -> dict[str, Any]:
    """OpenAI-compatible structured output for route_user_message."""
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "router_route",
            "strict": True,
            "schema": ROUTER_RESPONSE_SCHEMA,
        },
    }


def _llm_messages(system_content: str, memory: SessionMemory) -> list[dict[str, Any]]:
    """One system block at the start (Yandex prompt template requirement)."""
    return [
        {"role": "system", "content": system_content},
        *memory.get_dialog_messages(),
    ]


def _parse_route_from_content(content: str) -> str | None:
    """Extract route from assistant content; None if invalid."""
    data = json.loads(content.strip())
    route = str(data.get("route", "")).lower()
    if route in {"simple", "agent"}:
        return route
    return None


def route_user_message(
    *,
    client: OpenAI,
    config: AppConfig,
    memory: SessionMemory,
) -> str:
    """Return 'simple' or 'agent'; default to agent on parse errors."""
    messages = _llm_messages(ROUTER_SYSTEM, memory)
    log_messages_debug("router", messages)
    log_llm_request(
        phase="router",
        model=config.router_model_uri,
        message_count=len(messages),
        context_chars=messages_context_chars(messages),
    )
    try:
        content, usage = _router_completion_content(
            client,
            config=config,
            messages=messages,
            use_structured_output=True,
        )
        log_llm_response(
            phase="router",
            model=config.router_model_uri,
            usage=usage,
            content_len=len(content),
        )
        route = _parse_route_from_content(content)
        if route is not None:
            return route
        logger.warning("Router invalid route in JSON, defaulting to agent: %r", content[:200])
    except APIError as exc:
        logger.warning(
            "Router structured output failed (%s), retrying without response_format: %s",
            getattr(exc, "status_code", None),
            exc,
        )
        try:
            fallback_messages = _llm_messages(
                ROUTER_SYSTEM + ROUTER_SYSTEM_JSON_FALLBACK_SUFFIX,
                memory,
            )
            content, usage = _router_completion_content(
                client,
                config=config,
                messages=fallback_messages,
                use_structured_output=False,
            )
            log_llm_response(
                phase="router",
                model=config.router_model_uri,
                usage=usage,
                content_len=len(content),
            )
            route = _parse_route_from_content(content)
            if route is not None:
                return route
        except (APIError, json.JSONDecodeError, KeyError, TypeError, IndexError) as retry_exc:
            logger.warning("Router fallback failed, defaulting to agent: %s", retry_exc)
    except (json.JSONDecodeError, KeyError, TypeError, IndexError) as exc:
        logger.warning("Router parse failed, defaulting to agent: %s", exc)
    return "agent"


def _router_completion_content(
    client: OpenAI,
    *,
    config: AppConfig,
    messages: list[dict[str, Any]],
    use_structured_output: bool,
) -> tuple[str, Any]:
    """Blocking router completion; returns (assistant content, usage)."""
    kwargs: dict[str, Any] = {
        "model": config.router_model_uri,
        "messages": messages,
        "temperature": 0.0,
    }
    if use_structured_output:
        kwargs["response_format"] = router_response_format()
    response = client.chat.completions.create(**kwargs)  # type: ignore[arg-type,call-overload]
    content = (response.choices[0].message.content or "").strip()
    return content, response.usage


def run_simple_chat(
    *,
    client: OpenAI,
    config: AppConfig,
    memory: SessionMemory,
    on_token: Callable[[str], None] | None = None,
) -> tuple[str, bool]:
    """One completion on the router model without tools. Returns (text, streamed_to_user)."""
    messages = _llm_messages(SIMPLE_SYSTEM, memory)
    log_messages_debug("simple", messages)
    log_llm_request(
        phase="simple",
        model=config.router_model_uri,
        message_count=len(messages),
        context_chars=messages_context_chars(messages),
    )
    if config.stream_final_response and on_token is not None:
        logger.info(
            "LLM stream start phase=simple model=%s",
            config.router_model_uri,
        )
        content, usage = stream_chat_text(
            client,
            model=config.router_model_uri,
            messages=messages,
            temperature=0.3,
            on_token=on_token,
        )
        log_llm_response(
            phase="simple",
            model=config.router_model_uri,
            usage=usage,
            content_len=len(content),
        )
        logger.info(
            "LLM stream end phase=simple model=%s content_len=%s",
            config.router_model_uri,
            len(content),
        )
        return content, True

    response = client.chat.completions.create(
        model=config.router_model_uri,
        messages=messages,  # type: ignore[arg-type]
        temperature=0.3,
    )
    content = response.choices[0].message.content or ""
    log_llm_response(
        phase="simple",
        model=config.router_model_uri,
        usage=response.usage,
        content_len=len(content),
    )
    return content, False
