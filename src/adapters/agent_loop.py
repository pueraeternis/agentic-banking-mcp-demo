"""ReAct-style agent loop via OpenAI function calling (max 8 tool rounds)."""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from dataclasses import dataclass
from types import SimpleNamespace
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

Деньги: в БД и переводах — balance_cents / amount_cents (копейки). Для ответа пользователю
используй balance_rubles и balance_kopecks из get_account_balance; не пересчитывай сам.

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
    streamed_to_user: bool = False


def _stream_completion_with_tools(
    client: OpenAI,
    *,
    model: str,
    messages: list[ChatCompletionMessageParam],
    tools: list[ChatCompletionToolUnionParam],
    temperature: float,
    on_token: Callable[[str], None],
) -> tuple[Any, bool, Any]:
    """Stream one agent step with tools; on_token only until tool_call deltas appear."""
    stream = client.chat.completions.create(
        model=model,
        messages=messages,
        tools=tools,
        tool_choice="auto",
        temperature=temperature,
        stream=True,
    )
    content_parts: list[str] = []
    tool_calls_acc: dict[int, dict[str, Any]] = {}
    tool_call_started = False
    usage: Any = None

    for chunk in stream:
        if chunk.usage is not None:
            usage = chunk.usage
        if not chunk.choices:
            continue
        delta = chunk.choices[0].delta
        if delta.content:
            content_parts.append(delta.content)
            if not tool_call_started:
                on_token(delta.content)
        if delta.tool_calls:
            tool_call_started = True
            for tc in delta.tool_calls:
                idx = tc.index
                if idx not in tool_calls_acc:
                    tool_calls_acc[idx] = {
                        "id": "",
                        "type": "function",
                        "function": {"name": "", "arguments": ""},
                    }
                entry = tool_calls_acc[idx]
                if tc.id:
                    entry["id"] = tc.id
                if tc.function and tc.function.name:
                    entry["function"]["name"] += tc.function.name
                if tc.function and tc.function.arguments:
                    entry["function"]["arguments"] += tc.function.arguments

    content = "".join(content_parts)
    if not tool_calls_acc:
        message = SimpleNamespace(content=content or None, tool_calls=None)
        return message, True, usage

    assembled = [tool_calls_acc[i] for i in sorted(tool_calls_acc)]
    tool_call_objects = [
        SimpleNamespace(
            id=tc["id"],
            function=SimpleNamespace(
                name=tc["function"]["name"],
                arguments=tc["function"]["arguments"],
            ),
        )
        for tc in assembled
    ]
    message = SimpleNamespace(content=content or None, tool_calls=tool_call_objects)
    return message, False, usage


def _assistant_turn_dict(response_message: Any) -> dict[str, Any]:
    if hasattr(response_message, "model_dump"):
        return response_message.model_dump(exclude_none=True)
    tool_calls = response_message.tool_calls or []
    return {
        "role": "assistant",
        "content": response_message.content,
        "tool_calls": [
            {
                "id": tc.id,
                "type": "function",
                "function": {
                    "name": tc.function.name,
                    "arguments": tc.function.arguments,
                },
            }
            for tc in tool_calls
        ],
    }


def _agent_step_completion(
    client: OpenAI,
    *,
    config: AppConfig,
    phase: str,
    messages: list[ChatCompletionMessageParam],
    tools: list[ChatCompletionToolUnionParam],
    use_streaming: bool,
    on_token: Callable[[str], None] | None,
) -> tuple[Any, Any, bool]:
    """One LLM step (blocking or streaming with tools)."""
    if use_streaming and on_token is not None:
        logger.info("LLM stream start phase=%s model=%s", phase, config.agent_model_uri)
        message, streamed, usage = _stream_completion_with_tools(
            client,
            model=config.agent_model_uri,
            messages=messages,
            tools=tools,
            temperature=0.2,
            on_token=on_token,
        )
        return message, usage, streamed

    response = client.chat.completions.create(
        model=config.agent_model_uri,
        messages=messages,
        tools=tools,
        tool_choice="auto",
        temperature=0.2,
    )
    return response.choices[0].message, response.usage, False


def _execute_tool_calls(
    *,
    tool_calls: list[Any],
    response_message: Any,
    memory: SessionMemory,
    messages: list[ChatCompletionMessageParam],
    mcp: BankingMcpClient,
    on_action: Callable[[str, dict[str, Any]], None] | None,
    on_observation: Callable[[str], None] | None,
) -> dict[str, Any] | None:
    """Run MCP tools for one assistant turn; return HITL payload after prepare_transfer."""
    assistant_turn = _assistant_turn_dict(response_message)
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

        if function_name != "prepare_transfer":
            continue
        try:
            payload = json.loads(observation)
        except json.JSONDecodeError:
            payload = {}
        if payload.get("ok") is True:
            return payload
    return None


def run_agent_loop(
    *,
    client: OpenAI,
    config: AppConfig,
    memory: SessionMemory,
    mcp: BankingMcpClient,
    openai_tools: list[dict[str, Any]],
    on_action: Callable[[str, dict[str, Any]], None] | None = None,
    on_observation: Callable[[str], None] | None = None,
    on_token: Callable[[str], None] | None = None,
) -> AgentLoopResult:
    """Run tool-calling loop until final text or HITL after prepare_transfer."""
    memory.ensure_system_prompt(AGENT_SYSTEM)

    hitl_prepare: dict[str, Any] | None = None
    messages = cast("list[ChatCompletionMessageParam]", memory.get_messages())
    tools = cast("list[ChatCompletionToolUnionParam]", openai_tools)
    use_streaming = config.stream_final_response and on_token is not None

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

        response_message, usage, streamed_to_user = _agent_step_completion(
            client,
            config=config,
            phase=phase,
            messages=messages,
            tools=tools,
            use_streaming=use_streaming,
            on_token=on_token,
        )
        tool_calls = response_message.tool_calls

        if not tool_calls:
            text = response_message.content or ""
            log_llm_response(
                phase=phase,
                model=config.agent_model_uri,
                usage=usage,
                content_len=len(text),
            )
            if use_streaming:
                logger.info(
                    "LLM stream end phase=%s model=%s content_len=%s",
                    phase,
                    config.agent_model_uri,
                    len(text),
                )
            logger.info("Agent step %s finished with text len=%s", step, len(text))
            memory.append({"role": "assistant", "content": text})
            messages.append({"role": "assistant", "content": text})
            return AgentLoopResult(
                assistant_message=text,
                hitl_prepare=hitl_prepare,
                streamed_to_user=streamed_to_user,
            )

        tool_names = [
            tc.function.name  # pyright: ignore[reportAttributeAccessIssue]
            for tc in tool_calls
        ]
        log_llm_response(
            phase=phase,
            model=config.agent_model_uri,
            usage=usage,
            content_len=len(response_message.content or ""),
        )
        if use_streaming:
            logger.info(
                "LLM stream end phase=%s model=%s tool_calls=%s",
                phase,
                config.agent_model_uri,
                tool_names,
            )
        logger.info("Agent step %s tool_calls=%s", step, tool_names)

        prepare_payload = _execute_tool_calls(
            tool_calls=tool_calls,
            response_message=response_message,
            memory=memory,
            messages=messages,
            mcp=mcp,
            on_action=on_action,
            on_observation=on_observation,
        )
        if prepare_payload is not None:
            hitl_prepare = prepare_payload
            return AgentLoopResult(
                assistant_message=None,
                hitl_prepare=hitl_prepare,
                streamed_to_user=False,
            )

    logger.warning("Agent loop reached max steps (%s)", MAX_AGENT_STEPS)
    fallback = "Достигнут лимит шагов агента. Уточните запрос или повторите."
    memory.append({"role": "assistant", "content": fallback})
    messages.append({"role": "assistant", "content": fallback})
    return AgentLoopResult(
        assistant_message=fallback,
        hitl_prepare=hitl_prepare,
        streamed_to_user=False,
    )
