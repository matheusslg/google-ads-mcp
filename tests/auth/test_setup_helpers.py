"""Tests for setup wizard helpers (non-OAuth)."""

from __future__ import annotations

import json
import stat
from pathlib import Path

import pytest

from google_ads_mcp.auth.setup import validate_customer_id, write_credentials_file


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


def _valid_creds() -> dict[str, object]:
    return {
        "schema_version": 1,
        "developer_token": "dev-token-abc",
        "client_id": "client-id.apps.googleusercontent.com",
        "client_secret": "client-secret-xyz",
        "refresh_token": "1//refresh-token-foo",
        "login_customer_id": "1234567890",
        "default_customer_id": "9876543210",
        "use_proto_plus": True,
    }


def test_write_credentials_file_creates_with_0600_mode(tmp_path: Path) -> None:
    path = tmp_path / ".config" / "google-ads-mcp" / "credentials.json"
    write_credentials_file(path, _valid_creds())
    mode = stat.S_IMODE(path.stat().st_mode)
    assert mode == 0o600, f"expected 0o600, got {oct(mode)}"


def test_write_credentials_file_creates_parent_dir_with_0700(tmp_path: Path) -> None:
    path = tmp_path / ".config" / "google-ads-mcp" / "credentials.json"
    write_credentials_file(path, _valid_creds())
    parent_mode = stat.S_IMODE(path.parent.stat().st_mode)
    assert parent_mode == 0o700, f"expected 0o700, got {oct(parent_mode)}"


def test_write_credentials_file_roundtrips_json(tmp_path: Path) -> None:
    path = tmp_path / ".config" / "google-ads-mcp" / "credentials.json"
    creds = _valid_creds()
    write_credentials_file(path, creds)
    assert json.loads(path.read_text()) == creds
