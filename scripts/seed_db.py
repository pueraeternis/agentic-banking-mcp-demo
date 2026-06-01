#!/usr/bin/env python3
"""Create SQLite schema and seed demo clients (Ivanov, Petrov, Sidorov)."""

from __future__ import annotations

import argparse
import os
import sqlite3
import sys
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SEED_CURRENCY = "RUB"

SCHEMA = """
CREATE TABLE IF NOT EXISTS clients (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    full_name TEXT NOT NULL,
    phone TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id INTEGER NOT NULL REFERENCES clients(id),
    currency TEXT NOT NULL DEFAULT 'RUB',
    balance_cents INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS transfers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    from_account_id INTEGER NOT NULL REFERENCES accounts(id),
    to_account_id INTEGER NOT NULL REFERENCES accounts(id),
    amount_cents INTEGER NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""

# balance_cents: Ivanov 1_000.00 RUB, Petrov 500.00 RUB, Sidorov 250.00 RUB
SEED_CLIENTS = [
    ("Иванов Иван Иванович", "+79001111111", 100_000),
    ("Петров Пётр Петрович", "+79002222222", 50_000),
    ("Сидоров Сидор Сидорович", "+79003333333", 25_000),
]


def seed_database(db_path: Path) -> None:
    """Apply schema and insert demo rows."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(SCHEMA)
        conn.execute("DELETE FROM transfers")
        conn.execute("DELETE FROM accounts")
        conn.execute("DELETE FROM clients")

        for full_name, phone, balance_cents in SEED_CLIENTS:
            cursor = conn.execute(
                "INSERT INTO clients (full_name, phone) VALUES (?, ?)",
                (full_name, phone),
            )
            row_id = cursor.lastrowid
            if row_id is None:
                msg = "INSERT INTO clients did not return lastrowid"
                raise RuntimeError(msg)
            conn.execute(
                """
                INSERT INTO accounts (client_id, currency, balance_cents)
                VALUES (?, ?, ?)
                """,
                (row_id, SEED_CURRENCY, balance_cents),
            )
        conn.commit()
    finally:
        conn.close()


def main() -> None:
    """CLI entry for database seeding."""
    sys.path.insert(0, str(PROJECT_ROOT / "src"))
    from adapters.database import DatabaseSettings

    load_dotenv(PROJECT_ROOT / ".env")
    default_db = os.getenv("DATABASE_PATH", DatabaseSettings.path)
    parser = argparse.ArgumentParser(description="Seed banking SQLite database")
    parser.add_argument(
        "--database",
        default=default_db,
        help="Path to SQLite file (default: DATABASE_PATH or data/banking.db)",
    )
    args = parser.parse_args()
    db_path = Path(args.database)
    DatabaseSettings.path = str(db_path)
    seed_database(db_path)
    print(f"Seeded database at {db_path}")


if __name__ == "__main__":
    main()
