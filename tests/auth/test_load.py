"""Tests for credential loading."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from google_ads_mcp.auth import (
    REQUIRED_FIELDS,
    CredentialsMalformed,
    CredentialsNotFound,
    get_default_customer_id,
    load_credentials,
)


def _valid_credentials() -> dict[str, object]:
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


def test_load_credentials_returns_dict_with_all_fields(tmp_credentials_dir: Path) -> None:
    tmp_credentials_dir.write_text(json.dumps(_valid_credentials()))
    data = load_credentials(tmp_credentials_dir)
    for field in REQUIRED_FIELDS:
        assert field in data, f"missing {field}"


def test_load_credentials_raises_not_found_when_missing(tmp_credentials_dir: Path) -> None:
    # fixture creates the dir but no file
    with pytest.raises(CredentialsNotFound):
        load_credentials(tmp_credentials_dir)


def test_load_credentials_raises_malformed_on_bad_json(tmp_credentials_dir: Path) -> None:
    tmp_credentials_dir.write_text("{not json")
    with pytest.raises(CredentialsMalformed, match="not valid JSON"):
        load_credentials(tmp_credentials_dir)


def test_load_credentials_raises_malformed_on_missing_field(tmp_credentials_dir: Path) -> None:
    bad = _valid_credentials()
    del bad["developer_token"]
    tmp_credentials_dir.write_text(json.dumps(bad))
    with pytest.raises(CredentialsMalformed, match="developer_token"):
        load_credentials(tmp_credentials_dir)


def test_get_default_customer_id_returns_field(tmp_credentials_dir: Path) -> None:
    tmp_credentials_dir.write_text(json.dumps(_valid_credentials()))
    assert get_default_customer_id(tmp_credentials_dir) == "9876543210"
