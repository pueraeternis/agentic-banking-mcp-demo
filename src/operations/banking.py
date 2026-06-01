"""Banking use cases backed by SQLite."""

from __future__ import annotations

import sqlite3
from typing import Any

from adapters.database import get_connection
from core.constants import TransferStatus
from core.errors import (
    AccountNotFound,
    InsufficientFunds,
    InvalidTransferState,
    TransferNotFound,
)
from core.models import Account, Client, Transfer


def find_client(query: str) -> list[Client]:
    """Search clients by full name (case-insensitive) or exact phone."""
    needle = query.strip()
    if not needle:
        return []

    needle_lower = needle.casefold()
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT id, full_name, phone FROM clients ORDER BY full_name",
        ).fetchall()

    results: list[Client] = []
    for row in rows:
        name_match = needle_lower in str(row["full_name"]).casefold()
        phone_match = str(row["phone"]) == needle
        if name_match or phone_match:
            results.append(
                Client(id=row["id"], full_name=row["full_name"], phone=row["phone"]),
            )
    return results


def get_account_balance(*, account_id: int | None = None, client_id: int | None = None) -> int:
    """Return balance in kopecks for an account or a client's primary account."""
    if account_id is None and client_id is None:
        msg = "Either account_id or client_id must be provided"
        raise ValueError(msg)

    with get_connection() as conn:
        if account_id is not None:
            row = conn.execute(
                "SELECT balance_cents FROM accounts WHERE id = ?",
                (account_id,),
            ).fetchone()
            if row is None:
                raise AccountNotFound(f"Account {account_id} not found")
            return int(row["balance_cents"])

        row = conn.execute(
            """
            SELECT balance_cents
            FROM accounts
            WHERE client_id = ?
            ORDER BY id
            LIMIT 1
            """,
            (client_id,),
        ).fetchone()
        if row is None:
            raise AccountNotFound(f"No account for client {client_id}")
        return int(row["balance_cents"])


def _load_account(conn: sqlite3.Connection, account_id: int) -> sqlite3.Row:
    row = conn.execute(
        "SELECT id, client_id, currency, balance_cents FROM accounts WHERE id = ?",
        (account_id,),
    ).fetchone()
    if row is None:
        raise AccountNotFound(f"Account {account_id} not found")
    return row


def prepare_transfer(
    *,
    from_account_id: int,
    to_account_id: int,
    amount_cents: int,
) -> Transfer:
    """Create a pending transfer after validating accounts and funds."""
    if amount_cents <= 0:
        msg = "amount_cents must be positive"
        raise ValueError(msg)
    if from_account_id == to_account_id:
        msg = "from_account_id and to_account_id must differ"
        raise ValueError(msg)

    with get_connection() as conn:
        from_row = _load_account(conn, from_account_id)
        _load_account(conn, to_account_id)

        balance = int(from_row["balance_cents"])
        if balance < amount_cents:
            raise InsufficientFunds(
                f"Account {from_account_id} has {balance} kopecks, need {amount_cents}",
            )

        cursor = conn.execute(
            """
            INSERT INTO transfers (from_account_id, to_account_id, amount_cents, status)
            VALUES (?, ?, ?, ?)
            """,
            (from_account_id, to_account_id, amount_cents, TransferStatus.PENDING.value),
        )
        row_id = cursor.lastrowid
        if row_id is None:
            msg = "INSERT INTO transfers did not return lastrowid"
            raise RuntimeError(msg)
        transfer_id = row_id
        row = conn.execute(
            """
            SELECT id, from_account_id, to_account_id, amount_cents, status, created_at
            FROM transfers
            WHERE id = ?
            """,
            (transfer_id,),
        ).fetchone()
        conn.commit()

    assert row is not None
    return _row_to_transfer(row)


def commit_transfer(transfer_id: int) -> Transfer:
    """Complete a pending transfer and move funds between accounts."""
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT id, from_account_id, to_account_id, amount_cents, status, created_at
            FROM transfers
            WHERE id = ?
            """,
            (transfer_id,),
        ).fetchone()
        if row is None:
            raise TransferNotFound(f"Transfer {transfer_id} not found")
        if row["status"] != TransferStatus.PENDING.value:
            raise InvalidTransferState(
                f"Transfer {transfer_id} is {row['status']}, expected pending",
            )

        from_row = _load_account(conn, int(row["from_account_id"]))
        amount = int(row["amount_cents"])
        if int(from_row["balance_cents"]) < amount:
            raise InsufficientFunds(
                f"Account {row['from_account_id']} has insufficient funds for commit",
            )

        conn.execute(
            "UPDATE accounts SET balance_cents = balance_cents - ? WHERE id = ?",
            (amount, row["from_account_id"]),
        )
        conn.execute(
            "UPDATE accounts SET balance_cents = balance_cents + ? WHERE id = ?",
            (amount, row["to_account_id"]),
        )
        conn.execute(
            "UPDATE transfers SET status = ? WHERE id = ?",
            (TransferStatus.COMPLETED.value, transfer_id),
        )
        updated = conn.execute(
            """
            SELECT id, from_account_id, to_account_id, amount_cents, status, created_at
            FROM transfers
            WHERE id = ?
            """,
            (transfer_id,),
        ).fetchone()
        conn.commit()

    assert updated is not None
    return _row_to_transfer(updated)


def cancel_transfer(transfer_id: int) -> Transfer:
    """Cancel a pending transfer without moving funds."""
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT id, from_account_id, to_account_id, amount_cents, status, created_at
            FROM transfers
            WHERE id = ?
            """,
            (transfer_id,),
        ).fetchone()
        if row is None:
            raise TransferNotFound(f"Transfer {transfer_id} not found")
        if row["status"] != TransferStatus.PENDING.value:
            raise InvalidTransferState(
                f"Transfer {transfer_id} is {row['status']}, expected pending",
            )

        conn.execute(
            "UPDATE transfers SET status = ? WHERE id = ?",
            (TransferStatus.CANCELLED.value, transfer_id),
        )
        updated = conn.execute(
            """
            SELECT id, from_account_id, to_account_id, amount_cents, status, created_at
            FROM transfers
            WHERE id = ?
            """,
            (transfer_id,),
        ).fetchone()
        conn.commit()

    assert updated is not None
    return _row_to_transfer(updated)


def get_account(account_id: int) -> Account:
    """Load a single account by id."""
    with get_connection() as conn:
        row = _load_account(conn, account_id)
    return Account(
        id=int(row["id"]),
        client_id=int(row["client_id"]),
        currency=str(row["currency"]),
        balance_cents=int(row["balance_cents"]),
    )


def _row_to_transfer(row: sqlite3.Row | dict[str, Any]) -> Transfer:
    return Transfer(
        id=int(row["id"]),
        from_account_id=int(row["from_account_id"]),
        to_account_id=int(row["to_account_id"]),
        amount_cents=int(row["amount_cents"]),
        status=TransferStatus(str(row["status"])),
        created_at=str(row["created_at"]),
    )
