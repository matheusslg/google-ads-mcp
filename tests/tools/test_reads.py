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
    list_accessible_customers,
    list_ad_groups,
    list_campaigns,
    list_keywords,
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


# --- list_accessible_customers ---


def test_list_accessible_customers_parses_resource_names(
    mock_google_ads_client: MagicMock,
) -> None:
    result = MagicMock()
    result.resource_names = ["customers/1234567890", "customers/9876543210"]
    mock_google_ads_client.get_service.return_value.list_accessible_customers.return_value = result
    resp = list_accessible_customers()
    assert [c.customer_id for c in resp.customers] == ["1234567890", "9876543210"]
    assert resp.warnings == []


def test_list_accessible_customers_maps_auth_error(mock_google_ads_client: MagicMock) -> None:
    mock_google_ads_client.get_service.return_value.list_accessible_customers.side_effect = (
        _make_google_ads_exception(auth=True)
    )
    with pytest.raises(CredentialsRevoked):
        list_accessible_customers()


# --- list_campaigns ---


def _make_campaign_row(
    id: int = 1, name: str = "cmp", status: str = "ENABLED", channel: str = "SEARCH"
) -> MagicMock:
    row = MagicMock()
    row.campaign.id = id
    row.campaign.name = name
    row.campaign.status.name = status
    row.campaign.advertising_channel_type.name = channel
    return row


def test_list_campaigns_returns_envelope_with_customer_id_and_items(
    mock_google_ads_client: MagicMock,
) -> None:
    batch = MagicMock()
    batch.results = [_make_campaign_row(id=1, name="Cmp A"), _make_campaign_row(id=2, name="Cmp B")]
    mock_google_ads_client.get_service.return_value.search_stream.return_value = [batch]
    resp = list_campaigns(customer_id="1234567890")
    assert resp.customer_id == "1234567890"
    assert len(resp.campaigns) == 2
    assert resp.campaigns[0].id == "1"
    assert resp.campaigns[0].name == "Cmp A"
    assert resp.campaigns[0].status == "ENABLED"


def test_list_campaigns_status_filter_adds_where_clause(
    mock_google_ads_client: MagicMock,
) -> None:
    mock_google_ads_client.get_service.return_value.search_stream.return_value = []
    list_campaigns(customer_id="1234567890", status="PAUSED")
    call = mock_google_ads_client.get_service.return_value.search_stream.call_args
    assert "WHERE campaign.status = 'PAUSED'" in call.kwargs["query"]


def test_list_campaigns_falls_back_to_default_customer_id(
    mock_google_ads_client: MagicMock,
) -> None:
    mock_google_ads_client.get_service.return_value.search_stream.return_value = []
    resp = list_campaigns()  # no customer_id
    assert resp.customer_id == "9999999999"  # from fixture


# --- list_ad_groups ---


def _make_adgroup_row(
    id: int = 1,
    name: str = "ag",
    status: str = "ENABLED",
    campaign_rn: str = "customers/1234567890/campaigns/5555",
) -> MagicMock:
    row = MagicMock()
    row.ad_group.id = id
    row.ad_group.name = name
    row.ad_group.status.name = status
    row.ad_group.campaign = campaign_rn
    return row


def test_list_ad_groups_extracts_campaign_id_from_resource_name(
    mock_google_ads_client: MagicMock,
) -> None:
    batch = MagicMock()
    batch.results = [_make_adgroup_row(id=1, campaign_rn="customers/1234567890/campaigns/5555")]
    mock_google_ads_client.get_service.return_value.search_stream.return_value = [batch]
    resp = list_ad_groups(customer_id="1234567890")
    assert resp.ad_groups[0].campaign_id == "5555"


def test_list_ad_groups_scopes_to_campaign(mock_google_ads_client: MagicMock) -> None:
    mock_google_ads_client.get_service.return_value.search_stream.return_value = []
    list_ad_groups(customer_id="1234567890", campaign_id="5555")
    call = mock_google_ads_client.get_service.return_value.search_stream.call_args
    assert "ad_group.campaign = 'customers/1234567890/campaigns/5555'" in call.kwargs["query"]


# --- list_keywords ---


def _make_keyword_row(
    id: int = 1,
    text: str = "shoes",
    match: str = "EXACT",
    status: str = "ENABLED",
    ag_rn: str = "customers/1234567890/adGroups/7777",
) -> MagicMock:
    row = MagicMock()
    row.ad_group_criterion.criterion_id = id
    row.ad_group_criterion.keyword.text = text
    row.ad_group_criterion.keyword.match_type.name = match
    row.ad_group_criterion.status.name = status
    row.ad_group_criterion.ad_group = ag_rn
    return row


def test_list_keywords_returns_envelope(mock_google_ads_client: MagicMock) -> None:
    batch = MagicMock()
    batch.results = [_make_keyword_row()]
    mock_google_ads_client.get_service.return_value.search_stream.return_value = [batch]
    resp = list_keywords(customer_id="1234567890")
    assert len(resp.keywords) == 1
    assert resp.keywords[0].text == "shoes"
    assert resp.keywords[0].ad_group_id == "7777"


def test_list_keywords_always_filters_to_keyword_type(
    mock_google_ads_client: MagicMock,
) -> None:
    mock_google_ads_client.get_service.return_value.search_stream.return_value = []
    list_keywords(customer_id="1234567890")
    call = mock_google_ads_client.get_service.return_value.search_stream.call_args
    assert "ad_group_criterion.type = 'KEYWORD'" in call.kwargs["query"]


def test_list_keywords_scopes_to_ad_group(mock_google_ads_client: MagicMock) -> None:
    mock_google_ads_client.get_service.return_value.search_stream.return_value = []
    list_keywords(customer_id="1234567890", ad_group_id="7777")
    call = mock_google_ads_client.get_service.return_value.search_stream.call_args
    q = call.kwargs["query"]
    assert "ad_group_criterion.ad_group = 'customers/1234567890/adGroups/7777'" in q
