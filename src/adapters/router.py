"""Semantic router: simple chat vs agent with tools."""

from __future__ import annotations

import json
import logging
from typing import Any

from openai import OpenAI

from adapters.config import AppConfig
from adapters.llm_logging import (
    log_llm_request,
    log_llm_response,
    log_messages_debug,
    messages_context_chars,
)
from adapters.memory import SessionMemory

logger = logging.getLogger(__name__)

ROUTER_SYSTEM = """Ты — семантический маршрутизатор банковского ассистента.
Ответь ТОЛЬКО JSON без markdown: {"route": "simple"} или {"route": "agent"}.

route = "simple" — только общий разговор без фактов о банке: приветствие, благодарность, оффтоп.
НЕ используй simple для услуг, продуктов, тарифов или каталога НАШЕГО банка.

route = "agent" — баланс, клиенты, счета, переводы, услуги и продукты НАШЕГО банка,
любые данные из БД или официального каталога банка.

Если сомневаешься или нужны инструменты/каталог — выбирай "agent"."""


def route_user_message(
    *,
    client: OpenAI,
    config: AppConfig,
    memory: SessionMemory,
) -> str:
    """Return 'simple' or 'agent'; default to agent on parse errors."""
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": ROUTER_SYSTEM},
        *memory.get_messages(),
    ]
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
) -> str:
    """One completion on the router model without tools."""
    messages: list[dict[str, Any]] = [
        {
            "role": "system",
            "content": (
                "Ты — вежливый банковский ассистент. Отвечай по-русски на общий разговор. "
                "Не выдумывай балансы, переводы, данные клиентов и каталог услуг банка — "
                "для фактов о банке нужен другой режим."
            ),
        },
        *memory.get_messages(),
    ]
    log_messages_debug("simple", messages)
    log_llm_request(
        phase="simple",
        model=config.router_model_uri,
        message_count=len(messages),
        context_chars=messages_context_chars(messages),
    )
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
    return content
