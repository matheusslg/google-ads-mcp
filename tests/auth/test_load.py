"""Tests for credential loading."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from google_ads_mcp.auth import (
    REQUIRED_FIELDS,
    CredentialsMalformed,
    CredentialsNotFound,
    get_default_customer_id,
    get_google_ads_client,
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


def test_get_google_ads_client_passes_sdk_fields_only(tmp_credentials_dir: Path) -> None:
    """get_google_ads_client must strip our extra fields before load_from_dict."""
    tmp_credentials_dir.write_text(json.dumps(_valid_credentials()))
    with patch("google_ads_mcp.auth.GoogleAdsClient") as mock_client:
        get_google_ads_client(tmp_credentials_dir)
        # called with (sdk_config_dict, version="v24")
        assert mock_client.load_from_dict.call_count == 1
        sdk_config = mock_client.load_from_dict.call_args.args[0]
        # our extra fields stripped:
        assert "schema_version" not in sdk_config
        assert "default_customer_id" not in sdk_config
        # required SDK fields present:
        for field in (
            "developer_token",
            "client_id",
            "client_secret",
            "refresh_token",
            "login_customer_id",
            "use_proto_plus",
        ):
            assert field in sdk_config
