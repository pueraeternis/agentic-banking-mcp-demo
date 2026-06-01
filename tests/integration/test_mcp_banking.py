"""Integration tests: MCP stdio server + temp SQLite (no LLM)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from tests.integration.conftest import EXPECTED_TOOL_NAMES, parse_tool_json

if TYPE_CHECKING:
    from adapters.mcp_client import BankingMcpClient

pytestmark = pytest.mark.integration

BANK_SERVICES_URI = "banking://services"


def test_list_resources_includes_bank_services(mcp_client: BankingMcpClient) -> None:
    """MCP resources/list exposes the bank services catalog."""
    uris = {str(resource.uri) for resource in mcp_client.list_resources()}
    assert BANK_SERVICES_URI in uris


def test_read_bank_services_resource_returns_markdown(mcp_client: BankingMcpClient) -> None:
    """read_resource returns non-empty markdown from data/bank_services.md."""
    text = mcp_client.read_resource(BANK_SERVICES_URI)
    assert "Услуги демо-банка" in text
    assert "Вклады" in text
    assert len(text.strip()) > 100


def test_list_tools_exposes_five_banking_tools(mcp_client: BankingMcpClient) -> None:
    """MCP tools/list matches the v1 banking tool set."""
    names = {tool.name for tool in mcp_client.list_tools()}
    assert names == EXPECTED_TOOL_NAMES


def test_find_client_via_mcp(mcp_client: BankingMcpClient) -> None:
    """find_client returns structured ok payload over stdio."""
    raw = mcp_client.call_tool("find_client", {"query": "иванов"})
    payload = parse_tool_json(raw)
    assert payload["ok"] is True
    assert len(payload["clients"]) == 1
    assert payload["clients"][0]["full_name"] == "Иванов"


def test_get_account_balance_via_mcp(mcp_client: BankingMcpClient) -> None:
    """get_account_balance reads from the seeded database."""
    raw = mcp_client.call_tool("get_account_balance", {"account_id": 1})
    payload = parse_tool_json(raw)
    assert payload["ok"] is True
    assert payload["balance_cents"] == 100_000
    assert payload["balance_rubles"] == 1_000
    assert payload["balance_kopecks"] == 0


def test_prepare_and_commit_transfer_via_mcp(mcp_client: BankingMcpClient) -> None:
    """Full transfer flow through MCP tools updates balances."""
    prepare_raw = mcp_client.call_tool(
        "prepare_transfer",
        {"from_account_id": 1, "to_account_id": 2, "amount_cents": 25_000},
    )
    prepare = parse_tool_json(prepare_raw)
    assert prepare["ok"] is True
    assert prepare["status"] == "pending"
    transfer_id = prepare["transfer_id"]

    commit_raw = mcp_client.call_tool("commit_transfer", {"transfer_id": transfer_id})
    commit = parse_tool_json(commit_raw)
    assert commit["ok"] is True
    assert commit["status"] == "completed"

    balance_from = parse_tool_json(
        mcp_client.call_tool("get_account_balance", {"account_id": 1}),
    )
    balance_to = parse_tool_json(
        mcp_client.call_tool("get_account_balance", {"account_id": 2}),
    )
    assert balance_from["balance_cents"] == 75_000
    assert balance_to["balance_cents"] == 75_000


def test_prepare_insufficient_funds_error_payload(mcp_client: BankingMcpClient) -> None:
    """Domain error is mapped to stable MCP error JSON."""
    raw = mcp_client.call_tool(
        "prepare_transfer",
        {"from_account_id": 1, "to_account_id": 2, "amount_cents": 500_000},
    )
    payload = parse_tool_json(raw)
    assert payload["ok"] is False
    assert payload["code"] == "INSUFFICIENT_FUNDS"


def test_cancel_transfer_via_mcp(mcp_client: BankingMcpClient) -> None:
    """cancel_transfer cancels pending without moving funds."""
    prepare = parse_tool_json(
        mcp_client.call_tool(
            "prepare_transfer",
            {"from_account_id": 1, "to_account_id": 2, "amount_cents": 10_000},
        ),
    )
    transfer_id = prepare["transfer_id"]

    cancel = parse_tool_json(
        mcp_client.call_tool("cancel_transfer", {"transfer_id": transfer_id}),
    )
    assert cancel["ok"] is True
    assert cancel["status"] == "cancelled"

    balance = parse_tool_json(
        mcp_client.call_tool("get_account_balance", {"account_id": 1}),
    )
    assert balance["balance_cents"] == 100_000
