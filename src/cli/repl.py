"""Interactive banking REPL with router, agent, MCP tools, and HITL."""

from __future__ import annotations

import json
import logging
import sys
from typing import Any

from openai import APIError, OpenAIError
from rich.console import Console
from rich.panel import Panel

from adapters.agent_loop import run_agent_loop
from adapters.config import AppConfig
from adapters.database import DatabaseSettings
from adapters.llm_client import create_llm_client
from adapters.llm_logging import log_llm_error, truncate_for_log
from adapters.logging_setup import get_session_log_path, setup_logging
from adapters.mcp_client import BankingMcpClient
from adapters.memory import SessionMemory
from adapters.paths import resolve_data_path
from adapters.router import route_user_message, run_simple_chat
from adapters.tool_schema import mcp_tools_to_openai

logger = logging.getLogger(__name__)
console = Console()

LLM_ERROR_MESSAGE = "Не удалось обратиться к модели Yandex. Проверьте ключ и квоту."

BANK_SERVICES_URI = "banking://services"

_SERVICE_KEYWORDS = (
    "услуг",
    "продукт",
    "продукты",
    "карт",
    "вклад",
    "кредит",
    "тариф",
    "пакет",
    "обслуживан",
    "что предлагает",
    "что умеет",
    "каталог",
)


def _truncate(text: str, limit: int = 500) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def _log_action(name: str, args: dict[str, Any]) -> None:
    console.print(f"[bold cyan]Action[/bold cyan] {name}({json.dumps(args, ensure_ascii=False)})")


def _log_observation(text: str) -> None:
    console.print(f"[bold green]Observation[/bold green] {_truncate(text)}")


def _log_resource(uri: str) -> None:
    console.print(f"[bold blue]Resource[/bold blue] {uri}")


def _is_bank_services_intent(text: str) -> bool:
    lower = text.lower()
    return any(keyword in lower for keyword in _SERVICE_KEYWORDS)


def _inject_bank_services_context(*, mcp: BankingMcpClient, memory: SessionMemory) -> None:
    services_text = mcp.read_resource(BANK_SERVICES_URI)
    _log_resource(BANK_SERVICES_URI)
    logger.info(
        "Resource inject uri=%s chars=%s preview=%s",
        BANK_SERVICES_URI,
        len(services_text),
        truncate_for_log(services_text, 120),
    )
    memory.append(
        {
            "role": "user",
            "content": (
                "Контекст: официальный каталог услуг и продуктов нашего банка "
                f"(MCP resource {BANK_SERVICES_URI}):\n\n"
                f"{services_text}\n\n"
                "Ответь на последний вопрос пользователя, опираясь только на этот каталог."
            ),
        },
    )


def _show_hitl_panel(prepare_payload: dict[str, Any]) -> None:
    amount = prepare_payload.get("amount_cents", "?")
    transfer_id = prepare_payload.get("transfer_id", "?")
    from_acc = prepare_payload.get("from_account_id", "?")
    to_acc = prepare_payload.get("to_account_id", "?")
    body = f"Перевод #{transfer_id}\nСо счёта: {from_acc} → на счёт: {to_acc}\nСумма: {amount} коп.\n\nПодтвердить перевод? (да / нет)"
    console.print(Panel(body, title="Подтверждение перевода", border_style="yellow"))


def _read_user_line() -> str | None:
    try:
        return console.input("[bold]Вы[/bold]: ").strip()
    except (EOFError, KeyboardInterrupt):
        return None


def _handle_hitl(
    *,
    prepare_payload: dict[str, Any],
    mcp: BankingMcpClient,
    memory: SessionMemory,
    config: AppConfig,
    openai_tools: list[dict[str, Any]],
) -> None:
    _show_hitl_panel(prepare_payload)
    answer = _read_user_line()
    if answer is None:
        return

    transfer_id = int(prepare_payload["transfer_id"])
    if answer.lower() in {"нет", "no", "n"}:
        result = mcp.call_tool("cancel_transfer", {"transfer_id": transfer_id})
        _log_action("cancel_transfer", {"transfer_id": transfer_id})
        _log_observation(result)
        memory.append(
            {
                "role": "user",
                "content": f"Пользователь отклонил перевод {transfer_id}. Перевод отменён.",
            },
        )
        console.print("[dim]Перевод отменён.[/dim]")
        return

    if answer.lower() not in {"да", "yes", "y", "подтверждаю"}:
        console.print("[yellow]Ответ не распознан. Перевод остаётся pending.[/yellow]")
        return

    memory.append(
        {
            "role": "user",
            "content": (f"Пользователь подтвердил перевод {transfer_id}. Выполни commit_transfer для этого transfer_id."),
        },
    )
    llm = create_llm_client(config)
    agent_result = run_agent_loop(
        client=llm,
        config=config,
        memory=memory,
        mcp=mcp,
        openai_tools=openai_tools,
        on_action=_log_action,
        on_observation=_log_observation,
    )
    if agent_result.assistant_message:
        console.print(f"[bold magenta]Ассистент[/bold magenta]: {agent_result.assistant_message}")


def run_repl() -> None:
    """Main REPL loop."""
    log_path = setup_logging()
    config = AppConfig.from_env()
    db_path = resolve_data_path(config.database_path)
    DatabaseSettings.path = str(db_path)
    if not db_path.is_file():
        console.print(
            f"[red]База {db_path} не найдена.[/red] Выполните: [bold]uv run python scripts/seed_db.py[/bold]",
        )
        sys.exit(1)

    llm = create_llm_client(config)
    memory = SessionMemory()
    mcp = BankingMcpClient(config)

    logger.info(
        "Session start db=%s router_model=%s agent_model=%s log_file=%s",
        db_path,
        config.router_model_uri,
        config.agent_model_uri,
        log_path,
    )

    console.print(
        Panel(
            "Банковский агент (MCP + router + HITL). Введите вопрос или 'exit' / 'quit' для выхода.",
            title="agentic-banking-mcp-demo",
        ),
    )

    try:
        mcp.connect()
        openai_tools = mcp_tools_to_openai(mcp.list_tools())

        while True:
            user_text = _read_user_line()
            if user_text is None:
                break
            if not user_text:
                continue
            if user_text.lower() in {"exit", "quit", "выход"}:
                break

            llm_phase = "router"
            llm_model = config.router_model_uri
            try:
                logger.info("User turn: %s", truncate_for_log(user_text, 300))
                memory.append({"role": "user", "content": user_text})
                route = route_user_message(client=llm, config=config, memory=memory)
                console.print(f"[dim]route={route}[/dim]")
                logger.info("route=%s", route)

                if route == "simple":
                    llm_phase = "simple"
                    reply = run_simple_chat(client=llm, config=config, memory=memory)
                    memory.append({"role": "assistant", "content": reply})
                    console.print(f"[bold magenta]Ассистент[/bold magenta]: {reply}")
                    continue

                llm_phase = "agent"
                llm_model = config.agent_model_uri
                if _is_bank_services_intent(user_text):
                    _inject_bank_services_context(mcp=mcp, memory=memory)

                agent_result = run_agent_loop(
                    client=llm,
                    config=config,
                    memory=memory,
                    mcp=mcp,
                    openai_tools=openai_tools,
                    on_action=_log_action,
                    on_observation=_log_observation,
                )

                if agent_result.hitl_prepare:
                    _handle_hitl(
                        prepare_payload=agent_result.hitl_prepare,
                        mcp=mcp,
                        memory=memory,
                        config=config,
                        openai_tools=openai_tools,
                    )
                elif agent_result.assistant_message:
                    console.print(
                        f"[bold magenta]Ассистент[/bold magenta]: {agent_result.assistant_message}",
                    )
            except (OpenAIError, APIError) as exc:
                log_llm_error(exc, phase=llm_phase, model=llm_model)
                console.print(f"[red]{LLM_ERROR_MESSAGE}[/red]")
                session_log = get_session_log_path()
                if session_log is not None:
                    console.print(f"[dim]Подробности: {session_log}[/dim]")
                last = memory.pop_last()
                if last and last.get("role") != "user":
                    memory.append(last)

    except Exception as exc:
        logger.exception("REPL failed")
        console.print(f"[red]Ошибка:[/red] {exc}")
    finally:
        mcp.close()
        console.print("[dim]До свидания.[/dim]")
