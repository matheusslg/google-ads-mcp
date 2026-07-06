"""Tests for the helper functions in google_ads_mcp.tools.reads.

Tool function tests (list_accessible_customers, list_campaigns, etc.) land in T5-T8.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from google.ads.googleads.errors import GoogleAdsException

from google_ads_mcp.auth import CredentialsRevoked
from google_ads_mcp.tools.reads import (
    _MAX_ROWS,
    _raise_friendly,
    _resolve_customer_id,
    _search,
)


def _make_google_ads_exception(*, auth: bool = True) -> GoogleAdsException:
    """Build a GoogleAdsException whose top error is an auth error (or something else)."""
    err = MagicMock()
    err.error_code.authentication_error = 1 if auth else 0
    err.error_code.authorization_error = 0
    err.message = "invalid grant" if auth else "quota exceeded"
    failure = MagicMock()
    failure.errors = [err]
    # GoogleAdsException signature: (error, call, failure, request_id)
    exc = GoogleAdsException(None, None, failure, "req-1")
    return exc


def test_resolve_customer_id_uses_arg_when_provided(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "google_ads_mcp.tools.reads.get_default_customer_id",
        lambda *a, **k: "1111111111",
    )
    assert _resolve_customer_id("2222222222") == "2222222222"


def test_resolve_customer_id_falls_back_to_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "google_ads_mcp.tools.reads.get_default_customer_id",
        lambda *a, **k: "1111111111",
    )
    assert _resolve_customer_id(None) == "1111111111"


def test_raise_friendly_maps_authentication_error_to_credentials_revoked() -> None:
    with pytest.raises(CredentialsRevoked, match="Refresh token may be revoked"):
        _raise_friendly(_make_google_ads_exception(auth=True))


def test_raise_friendly_reraises_non_auth_error() -> None:
    exc = _make_google_ads_exception(auth=False)
    with pytest.raises(GoogleAdsException) as raised:
        _raise_friendly(exc)
    assert raised.value is exc


def test_search_yields_rows_and_no_warnings(mock_google_ads_client: MagicMock) -> None:
    batch = MagicMock()
    batch.results = [MagicMock(id=1), MagicMock(id=2), MagicMock(id=3)]
    mock_google_ads_client.get_service.return_value.search_stream.return_value = [batch]
    rows, warnings = _search("1234567890", "SELECT campaign.id FROM campaign")
    assert len(rows) == 3
    assert warnings == []


def test_search_truncates_at_max_rows(mock_google_ads_client: MagicMock) -> None:
    """Yield _MAX_ROWS + 1 rows across a batch; verify cap + warning."""
    batch = MagicMock()
    batch.results = [MagicMock(id=i) for i in range(_MAX_ROWS + 1)]
    mock_google_ads_client.get_service.return_value.search_stream.return_value = [batch]
    rows, warnings = _search("1234567890", "SELECT campaign.id FROM campaign")
    assert len(rows) == _MAX_ROWS
    assert warnings == [f"truncated at {_MAX_ROWS} rows; refine filters to see more"]


def test_search_maps_google_ads_exception_via_raise_friendly(
    mock_google_ads_client: MagicMock,
) -> None:
    mock_google_ads_client.get_service.return_value.search_stream.side_effect = (
        _make_google_ads_exception(auth=True)
    )
    with pytest.raises(CredentialsRevoked):
        _search("1234567890", "SELECT campaign.id FROM campaign")


def test_search_propagates_non_auth_google_ads_exception(
    mock_google_ads_client: MagicMock,
) -> None:
    mock_google_ads_client.get_service.return_value.search_stream.side_effect = (
        _make_google_ads_exception(auth=False)
    )
    with pytest.raises(GoogleAdsException):
        _search("1234567890", "SELECT campaign.id FROM campaign")
