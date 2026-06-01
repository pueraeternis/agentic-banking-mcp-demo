"""Fixtures for MCP stdio integration tests."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from adapters.database import DatabaseSettings
from adapters.mcp_client import BankingMcpClient

BANKING_SCHEMA = """
CREATE TABLE clients (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    full_name TEXT NOT NULL,
    phone TEXT NOT NULL UNIQUE
);
CREATE TABLE accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id INTEGER NOT NULL,
    currency TEXT NOT NULL DEFAULT 'RUB',
    balance_cents INTEGER NOT NULL
);
CREATE TABLE transfers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    from_account_id INTEGER NOT NULL,
    to_account_id INTEGER NOT NULL,
    amount_cents INTEGER NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""

EXPECTED_TOOL_NAMES = frozenset(
    {
        "find_client",
        "get_account_balance",
        "prepare_transfer",
        "commit_transfer",
        "cancel_transfer",
    },
)


def seed_test_database(path: Path) -> None:
    """Create schema and two clients with accounts for MCP tests."""
    conn = sqlite3.connect(path)
    try:
        conn.executescript(BANKING_SCHEMA)
        conn.execute("INSERT INTO clients (full_name, phone) VALUES ('Иванов', '+79001')")
        conn.execute("INSERT INTO clients (full_name, phone) VALUES ('Петров', '+79002')")
        conn.execute(
            "INSERT INTO accounts (client_id, currency, balance_cents) VALUES (1, 'RUB', 100000)",
        )
        conn.execute(
            "INSERT INTO accounts (client_id, currency, balance_cents) VALUES (2, 'RUB', 50000)",
        )
        conn.commit()
    finally:
        conn.close()


@dataclass(frozen=True)
class McpIntegrationConfig:
    """Minimal config for BankingMcpClient in tests (no Yandex credentials)."""

    database_path: str
    mcp_server_module: str = "mcp_servers.banking_server"


@pytest.fixture
def seeded_db(tmp_path: Path) -> Path:
    """Temporary SQLite database shared by MCP server subprocess."""
    path = tmp_path / "mcp_integration.db"
    seed_test_database(path)
    DatabaseSettings.path = str(path)
    return path


@pytest.fixture
def mcp_client(seeded_db: Path) -> Iterator[BankingMcpClient]:
    """Connected MCP client over stdio to banking_server."""
    config = McpIntegrationConfig(database_path=str(seeded_db))
    client = BankingMcpClient(config)  # type: ignore[arg-type]
    client.connect()
    yield client
    client.close()


def parse_tool_json(raw: str) -> dict[str, Any]:
    """Parse JSON returned by BankingMcpClient.call_tool."""
    return json.loads(raw)
