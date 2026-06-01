"""Semantic router: simple chat vs agent with tools."""

from __future__ import annotations

import json
import logging
from typing import Any

from openai import OpenAI

from adapters.config import AppConfig
from adapters.memory import SessionMemory

logger = logging.getLogger(__name__)

ROUTER_SYSTEM = """Ты — семантический маршрутизатор банковского ассистента.
Ответь ТОЛЬКО JSON без markdown: {"route": "simple"} или {"route": "agent"}.

route = "simple" — общие вопросы о банке без фактов из базы (услуги, часы работы, FAQ).
route = "agent" — баланс, клиенты, счета, переводы, любые данные из БД.

Если сомневаешься или нужны инструменты — выбирай "agent"."""


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
    try:
        response = client.chat.completions.create(
            model=config.router_model_uri,
            messages=messages,  # type: ignore[arg-type]
            temperature=0.0,
        )
        content = (response.choices[0].message.content or "").strip()
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
                "Ты — вежливый банковский ассистент. Отвечай по-русски на общие вопросы. "
                "Не выдумывай балансы, переводы и данные клиентов — для этого нужен другой режим."
            ),
        },
        *memory.get_messages(),
    ]
    response = client.chat.completions.create(
        model=config.router_model_uri,
        messages=messages,  # type: ignore[arg-type]
        temperature=0.3,
    )
    return response.choices[0].message.content or ""
