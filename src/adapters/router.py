"""Semantic router: simple chat vs agent with tools."""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from typing import Any

from openai import OpenAI

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

ROUTER_SYSTEM = """Ты — семантический маршрутизатор банковского ассистента.
Ответь ТОЛЬКО JSON без markdown: {"route": "simple"} или {"route": "agent"}.

route = "simple" — только общий разговор без фактов о банке: приветствие, благодарность, оффтоп.
НЕ используй simple для услуг, продуктов, тарифов или каталога НАШЕГО банка.

route = "agent" — баланс, клиенты, счета, переводы, услуги и продукты НАШЕГО банка,
любые данные из БД или официального каталога банка.

Если сомневаешься или нужны инструменты/каталог — выбирай "agent"."""

SIMPLE_SYSTEM = (
    "Ты — вежливый банковский ассистент. Отвечай по-русски на общий разговор. "
    "Не выдумывай балансы, переводы, данные клиентов и каталог услуг банка — "
    "для фактов о банке нужен другой режим."
)


def _llm_messages(system_content: str, memory: SessionMemory) -> list[dict[str, Any]]:
    """One system block at the start (Yandex prompt template requirement)."""
    return [
        {"role": "system", "content": system_content},
        *memory.get_dialog_messages(),
    ]


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
        response = client.chat.completions.create(
            model=config.router_model_uri,
            messages=messages,  # type: ignore[arg-type]
            temperature=0.0,
        )
        content = (response.choices[0].message.content or "").strip()
        log_llm_response(
            phase="router",
            model=config.router_model_uri,
            usage=response.usage,
            content_len=len(content),
        )
        data = json.loads(content)
        route = str(data.get("route", "agent")).lower()
        if route in {"simple", "agent"}:
            return route
    except (json.JSONDecodeError, KeyError, TypeError, IndexError) as exc:
        logger.warning("Router parse failed, defaulting to agent: %s", exc)
    return "agent"


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
