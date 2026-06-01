"""Unit tests for banking operations (no LLM, no MCP)."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from adapters.database import DatabaseSettings, get_connection
from core.constants import TransferStatus
from core.errors import InsufficientFunds, InvalidTransferState
from operations import banking

SCHEMA = """
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


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    """Fresh SQLite file for each test."""
    path = tmp_path / "test.db"
    DatabaseSettings.path = str(path)
    conn = sqlite3.connect(path)
    conn.executescript(SCHEMA)
    conn.execute(
        "INSERT INTO clients (full_name, phone) VALUES ('Иванов', '+79001')",
    )
    conn.execute(
        "INSERT INTO clients (full_name, phone) VALUES ('Петров', '+79002')",
    )
    conn.execute(
        "INSERT INTO accounts (client_id, currency, balance_cents) VALUES (1, 'RUB', 100000)",
    )
    conn.execute(
        "INSERT INTO accounts (client_id, currency, balance_cents) VALUES (2, 'RUB', 50000)",
    )
    conn.commit()
    conn.close()
    return path


def test_transfer_happy_path(db_path: Path) -> None:
    """Prepare, commit, and verify balances."""
    del db_path
    transfer = banking.prepare_transfer(from_account_id=1, to_account_id=2, amount_cents=30000)
    assert transfer.status == TransferStatus.PENDING

    completed = banking.commit_transfer(transfer.id)
    assert completed.status == TransferStatus.COMPLETED

    assert banking.get_account_balance(account_id=1) == 70000
    assert banking.get_account_balance(account_id=2) == 80000


def test_prepare_insufficient_funds(db_path: Path) -> None:
    """Reject prepare when balance is too low."""
    del db_path
    with pytest.raises(InsufficientFunds):
        banking.prepare_transfer(from_account_id=1, to_account_id=2, amount_cents=200000)


def test_cancel_transfer(db_path: Path) -> None:
    """Cancel pending transfer leaves balances unchanged."""
    del db_path
    transfer = banking.prepare_transfer(from_account_id=1, to_account_id=2, amount_cents=10000)
    cancelled = banking.cancel_transfer(transfer.id)
    assert cancelled.status == TransferStatus.CANCELLED
    assert banking.get_account_balance(account_id=1) == 100000
    assert banking.get_account_balance(account_id=2) == 50000


def test_double_commit_invalid(db_path: Path) -> None:
    """Second commit on the same transfer raises invalid state."""
    del db_path
    transfer = banking.prepare_transfer(from_account_id=1, to_account_id=2, amount_cents=5000)
    banking.commit_transfer(transfer.id)
    with pytest.raises(InvalidTransferState):
        banking.commit_transfer(transfer.id)


def test_find_client_by_name(db_path: Path) -> None:
    """Case-insensitive name search returns matches."""
    del db_path
    clients = banking.find_client("иванов")
    assert len(clients) == 1
    assert clients[0].full_name == "Иванов"


def test_get_connection_uses_configured_path(db_path: Path) -> None:
    """DatabaseSettings.path drives connections in tests."""
    with get_connection() as conn:
        count = conn.execute("SELECT COUNT(*) FROM clients").fetchone()[0]
    assert count == 2
