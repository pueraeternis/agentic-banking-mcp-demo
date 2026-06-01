"""Money helpers: integer kopecks in storage, rubles/kopecks for MCP/LLM."""

from __future__ import annotations

from typing import TypedDict


class BalanceParts(TypedDict):
    """Balance decomposed for tool responses."""

    balance_cents: int
    balance_rubles: int
    balance_kopecks: int


def split_amount_cents(amount_cents: int) -> tuple[int, int]:
    """Split minor units into whole rubles and kopecks (0–99)."""
    if amount_cents < 0:
        msg = f"amount_cents must be non-negative, got {amount_cents}"
        raise ValueError(msg)
    return amount_cents // 100, amount_cents % 100


def balance_parts(amount_cents: int) -> BalanceParts:
    """Build balance fields for MCP tool JSON."""
    rubles, kopecks = split_amount_cents(amount_cents)
    return BalanceParts(
        balance_cents=amount_cents,
        balance_rubles=rubles,
        balance_kopecks=kopecks,
    )
