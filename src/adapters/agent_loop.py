"""ReAct-style agent loop via OpenAI function calling (max 8 tool rounds)."""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, cast

from openai import OpenAI

from adapters.config import AppConfig
from adapters.llm_logging import (
    log_llm_request,
    log_llm_response,
    log_messages_debug,
    messages_context_chars,
)
from adapters.mcp_client import BankingMcpClient
from adapters.memory import SessionMemory

if TYPE_CHECKING:
    from openai.types.chat import ChatCompletionMessageParam, ChatCompletionToolUnionParam

logger = logging.getLogger(__name__)

MAX_AGENT_STEPS = 8

AGENT_SYSTEM = """Ты — банковский ассистент с доступом к инструментам MCP.
Отвечай по-русски. Все факты о клиентах, балансах и переводах — только через инструменты.

Правила переводов:
1. Найди счета отправителя и получателя (find_client, get_account_balance).
2. Вызови prepare_transfer и остановись — не вызывай commit_transfer в этом же ответе.
3. commit_transfer — только после явного подтверждения пользователя в отдельном сообщении.
4. cancel_transfer — если пользователь отказался от pending-перевода."""


@dataclass
class AgentLoopResult:
    """Outcome of one agent invocation."""

    assistant_message: str | None
    hitl_prepare: dict[str, Any] | None = None


def run_agent_loop(
    *,
    client: OpenAI,
    config: AppConfig,
    memory: SessionMemory,
    mcp: BankingMcpClient,
    openai_tools: list[dict[str, Any]],
    on_action: Callable[[str, dict[str, Any]], None] | None = None,
    on_observation: Callable[[str], None] | None = None,
) -> AgentLoopResult:
    """Run tool-calling loop until final text or HITL after prepare_transfer."""
    memory.ensure_system_prompt(AGENT_SYSTEM)

    hitl_prepare: dict[str, Any] | None = None
    messages = cast("list[ChatCompletionMessageParam]", memory.get_messages())
    tools = cast("list[ChatCompletionToolUnionParam]", openai_tools)

    for step in range(1, MAX_AGENT_STEPS + 1):
        phase = f"agent step {step}"
        msg_list = cast("list[dict[str, Any]]", messages)
        log_messages_debug(phase, msg_list)
        log_llm_request(
            phase=phase,
            model=config.agent_model_uri,
            message_count=len(messages),
            context_chars=messages_context_chars(msg_list),
        )
        response = client.chat.completions.create(
            model=config.agent_model_uri,
            messages=messages,
            tools=tools,
            tool_choice="auto",
            temperature=0.2,
        )
        response_message = response.choices[0].message
        tool_calls = response_message.tool_calls

        if not tool_calls:
            text = response_message.content or ""
            log_llm_response(
                phase=phase,
                model=config.agent_model_uri,
                usage=response.usage,
                content_len=len(text),
            )
            logger.info("Agent step %s finished with text len=%s", step, len(text))
            memory.append({"role": "assistant", "content": text})
            messages.append({"role": "assistant", "content": text})
            return AgentLoopResult(assistant_message=text, hitl_prepare=hitl_prepare)

        tool_names = [
            tc.function.name  # pyright: ignore[reportAttributeAccessIssue]
            for tc in tool_calls
        ]
        log_llm_response(
            phase=phase,
            model=config.agent_model_uri,
            usage=response.usage,
            content_len=len(response_message.content or ""),
        )
        logger.info("Agent step %s tool_calls=%s", step, tool_names)

        assistant_turn = response_message.model_dump(exclude_none=True)
        memory.append(assistant_turn)  # pyright: ignore[reportArgumentType]
        messages.append(cast("ChatCompletionMessageParam", assistant_turn))

        for tool_call in tool_calls:
            function_name = tool_call.function.name  # pyright: ignore[reportAttributeAccessIssue]
            function_args = json.loads(
                tool_call.function.arguments or "{}",  # pyright: ignore[reportAttributeAccessIssue]
            )
            if on_action:
                on_action(function_name, function_args)

            observation = mcp.call_tool(function_name, function_args)
            if on_observation:
                on_observation(observation)

            tool_message: dict[str, Any] = {
                "role": "tool",
                "tool_call_id": tool_call.id,
                "name": function_name,
                "content": observation,
            }
            memory.append(tool_message)
            messages.append(cast("ChatCompletionMessageParam", tool_message))

            if function_name == "prepare_transfer":
                try:
                    payload = json.loads(observation)
                except json.JSONDecodeError:
                    payload = {}
                if payload.get("ok") is True:
                    hitl_prepare = payload
                    return AgentLoopResult(assistant_message=None, hitl_prepare=hitl_prepare)

    logger.warning("Agent loop reached max steps (%s)", MAX_AGENT_STEPS)
    fallback = "Достигнут лимит шагов агента. Уточните запрос или повторите."
    memory.append({"role": "assistant", "content": fallback})
    messages.append({"role": "assistant", "content": fallback})
    return AgentLoopResult(assistant_message=fallback, hitl_prepare=hitl_prepare)
