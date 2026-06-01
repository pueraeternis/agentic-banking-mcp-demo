"""SQLite connection helper for infrastructure and operations."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass


@dataclass
class DatabaseSettings:
    """Mutable holder for the active database path (tests may override)."""

    path: str = "data/banking.db"


def get_connection() -> sqlite3.Connection:
    """Open a connection with row dict-like access."""
    conn = sqlite3.connect(DatabaseSettings.path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn
