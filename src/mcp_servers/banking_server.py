"""FastMCP banking server (stdio) — delegates to operations layer."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Annotated, Any

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field

SRC_ROOT = Path(__file__).resolve().parents[1]
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from adapters.database import DatabaseSettings
from adapters.paths import resolve_data_path
from core.errors import AppError
from operations import banking

BANK_SERVICES_URI = "banking://services"

load_dotenv()

mcp = FastMCP("banking")


class ToolErrorPayload(BaseModel):
    """Stable error envelope for MCP tool responses."""

    ok: bool = False
    code: str
    message: str


class ClientOut(BaseModel):
    """Client row for tool output."""

    id: int
    full_name: str
    phone: str


class FindClientResult(BaseModel):
    """Result of find_client."""

    ok: bool = True
    clients: list[ClientOut]


class BalanceResult(BaseModel):
    """Balance lookup result."""

    ok: bool = True
    balance_cents: int
    account_id: int | None = None
    client_id: int | None = None


class TransferResult(BaseModel):
    """Transfer operation result."""

    ok: bool = True
    transfer_id: int
    from_account_id: int
    to_account_id: int
    amount_cents: int
    status: str
    created_at: str


def _configure_db() -> None:
    """Apply DATABASE_PATH from env (always absolute when spawned from REPL/tests)."""
    env_path = os.getenv("DATABASE_PATH")
    if env_path:
        DatabaseSettings.path = str(resolve_data_path(env_path))


def _error_payload(exc: Exception) -> dict[str, Any]:
    if isinstance(exc, AppError):
        return ToolErrorPayload(code=exc.code, message=exc.message).model_dump()
    return ToolErrorPayload(code="INTERNAL_ERROR", message=str(exc)).model_dump()


@mcp.resource(BANK_SERVICES_URI, mime_type="text/markdown", name="bank_services")
def bank_services_catalog() -> str:
    """Каталог услуг и продуктов демо-банка."""
    path = resolve_data_path("data/bank_services.md")
    return path.read_text(encoding="utf-8")


@mcp.tool()
def find_client(
    query: Annotated[str, Field(description="Фрагмент ФИО или номер телефона клиента")],
) -> dict[str, Any]:
    """Найти клиента по имени или телефону."""
    try:
        clients = banking.find_client(query)
        return FindClientResult(
            clients=[ClientOut(id=c.id, full_name=c.full_name, phone=c.phone) for c in clients],
        ).model_dump()
    except Exception as exc:
        return _error_payload(exc)


@mcp.tool()
def get_account_balance(
    account_id: Annotated[int | None, Field(description="ID счёта")] = None,
    client_id: Annotated[int | None, Field(description="ID клиента (первый счёт)")] = None,
) -> dict[str, Any]:
    """Получить баланс счёта в копейках (RUB)."""
    try:
        balance = banking.get_account_balance(account_id=account_id, client_id=client_id)
        return BalanceResult(
            balance_cents=balance,
            account_id=account_id,
            client_id=client_id,
        ).model_dump()
    except Exception as exc:
        return _error_payload(exc)


@mcp.tool()
def prepare_transfer(
    from_account_id: Annotated[int, Field(description="Счёт отправителя")],
    to_account_id: Annotated[int, Field(description="Счёт получателя")],
    amount_cents: Annotated[int, Field(description="Сумма перевода в копейках", gt=0)],
) -> dict[str, Any]:
    """Создать перевод в статусе pending (без списания средств)."""
    try:
        transfer = banking.prepare_transfer(
            from_account_id=from_account_id,
            to_account_id=to_account_id,
            amount_cents=amount_cents,
        )
        return TransferResult(
            transfer_id=transfer.id,
            from_account_id=transfer.from_account_id,
            to_account_id=transfer.to_account_id,
            amount_cents=transfer.amount_cents,
            status=transfer.status.value,
            created_at=transfer.created_at,
        ).model_dump()
    except Exception as exc:
        return _error_payload(exc)


@mcp.tool()
def commit_transfer(
    transfer_id: Annotated[int, Field(description="ID pending-перевода")],
) -> dict[str, Any]:
    """Подтвердить pending-перевод и списать средства."""
    try:
        transfer = banking.commit_transfer(transfer_id)
        return TransferResult(
            transfer_id=transfer.id,
            from_account_id=transfer.from_account_id,
            to_account_id=transfer.to_account_id,
            amount_cents=transfer.amount_cents,
            status=transfer.status.value,
            created_at=transfer.created_at,
        ).model_dump()
    except Exception as exc:
        return _error_payload(exc)


@mcp.tool()
def cancel_transfer(
    transfer_id: Annotated[int, Field(description="ID pending-перевода")],
) -> dict[str, Any]:
    """Отменить pending-перевод."""
    try:
        transfer = banking.cancel_transfer(transfer_id)
        return TransferResult(
            transfer_id=transfer.id,
            from_account_id=transfer.from_account_id,
            to_account_id=transfer.to_account_id,
            amount_cents=transfer.amount_cents,
            status=transfer.status.value,
            created_at=transfer.created_at,
        ).model_dump()
    except Exception as exc:
        return _error_payload(exc)


def main() -> None:
    """Run MCP server over stdio."""
    _configure_db()
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
