"""Tests for setup wizard helpers (non-OAuth)."""

from __future__ import annotations

import pytest

from google_ads_mcp.auth.setup import validate_customer_id


def test_validate_customer_id_accepts_10_digits() -> None:
    assert validate_customer_id("1234567890") == "1234567890"


def test_validate_customer_id_strips_dashes() -> None:
    assert validate_customer_id("123-456-7890") == "1234567890"


def test_validate_customer_id_rejects_letters() -> None:
    with pytest.raises(ValueError, match="digits"):
        validate_customer_id("abc1234567")


def test_validate_customer_id_rejects_wrong_length() -> None:
    with pytest.raises(ValueError, match="10 digits"):
        validate_customer_id("12345")
