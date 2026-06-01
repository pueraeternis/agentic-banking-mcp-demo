"""Unit tests for money helpers."""

from __future__ import annotations

import pytest

from core.money import balance_parts, split_amount_cents


def test_split_amount_cents_whole_rubles() -> None:
    assert split_amount_cents(100_000) == (1_000, 0)


def test_split_amount_cents_with_kopecks() -> None:
    assert split_amount_cents(100_050) == (1_000, 50)


def test_balance_parts() -> None:
    parts = balance_parts(50_025)
    assert parts == {
        "balance_cents": 50_025,
        "balance_rubles": 500,
        "balance_kopecks": 25,
    }


def test_split_rejects_negative() -> None:
    with pytest.raises(ValueError, match="non-negative"):
        split_amount_cents(-1)
