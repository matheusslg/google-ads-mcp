"""Tests for google_ads_mcp.tools.mutations (pause_campaign, enable_campaign)."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from google.ads.googleads.errors import GoogleAdsException

from google_ads_mcp.auth import CredentialsRevoked
from google_ads_mcp.tools.mutations import (
    MutationResponse,
    enable_campaign,
    pause_campaign,
)


def _make_google_ads_exception(*, auth: bool = True) -> GoogleAdsException:
    err = MagicMock()
    err.error_code.authentication_error = 1 if auth else 0
    err.error_code.authorization_error = 0
    err.message = "invalid grant" if auth else "quota exceeded"
    failure = MagicMock()
    failure.errors = [err]
    return GoogleAdsException(None, None, failure, "req-1")


def _stream_with_status(status: str) -> list[MagicMock]:
    row = MagicMock()
    row.campaign.id = 5555
    row.campaign.status.name = status
    batch = MagicMock()
    batch.results = [row]
    return [batch]


def _program_mutation_response(mock_client: MagicMock, resource_name: str) -> None:
    result = MagicMock()
    result.resource_name = resource_name
    resp = MagicMock()
    resp.results = [result]
    mock_client.get_service.return_value.mutate_campaigns.return_value = resp


def test_mutation_response_shape_has_all_fields() -> None:
    resp = MutationResponse(success=True)
    assert resp.success is True
    assert resp.dry_run is False
    assert resp.mutation_id is None
    assert resp.before == {}
    assert resp.after == {}
    assert resp.warnings == []


def test_pause_campaign_dry_run_makes_no_mutation_call(mock_google_ads_client: MagicMock) -> None:
    mock_google_ads_client.get_service.return_value.search_stream.return_value = (
        _stream_with_status("ENABLED")
    )
    resp = pause_campaign(campaign_id="5555", customer_id="1234567890", dry_run=True)
    assert mock_google_ads_client.get_service.return_value.mutate_campaigns.call_count == 0
    assert resp.dry_run is True
    assert resp.mutation_id is None
    assert resp.before == {"status": "ENABLED"}
    assert resp.after == {"status": "PAUSED"}
    assert resp.success is True


def test_pause_campaign_real_mutation_calls_sdk(mock_google_ads_client: MagicMock) -> None:
    mock_google_ads_client.get_service.return_value.search_stream.return_value = (
        _stream_with_status("ENABLED")
    )
    _program_mutation_response(mock_google_ads_client, "customers/1234567890/campaigns/5555")
    resp = pause_campaign(campaign_id="5555", customer_id="1234567890", dry_run=False)
    assert mock_google_ads_client.get_service.return_value.mutate_campaigns.call_count == 1
    assert resp.mutation_id == "customers/1234567890/campaigns/5555"
    assert resp.dry_run is False
    assert resp.before == {"status": "ENABLED"}
    assert resp.after == {"status": "PAUSED"}


def test_pause_campaign_no_op_when_already_paused(mock_google_ads_client: MagicMock) -> None:
    mock_google_ads_client.get_service.return_value.search_stream.return_value = (
        _stream_with_status("PAUSED")
    )
    resp = pause_campaign(campaign_id="5555", customer_id="1234567890")
    assert mock_google_ads_client.get_service.return_value.mutate_campaigns.call_count == 0
    assert resp.success is True
    assert resp.before == resp.after == {"status": "PAUSED"}
    assert any("already PAUSED; no-op" in w for w in resp.warnings)


def test_pause_campaign_reason_appears_in_warnings(mock_google_ads_client: MagicMock) -> None:
    mock_google_ads_client.get_service.return_value.search_stream.return_value = (
        _stream_with_status("ENABLED")
    )
    resp = pause_campaign(
        campaign_id="5555", customer_id="1234567890", dry_run=True, reason="testing"
    )
    assert "reason: testing" in resp.warnings


def test_pause_campaign_raises_when_campaign_not_found(mock_google_ads_client: MagicMock) -> None:
    mock_google_ads_client.get_service.return_value.search_stream.return_value = []
    with pytest.raises(ValueError, match="campaign 5555 not found"):
        pause_campaign(campaign_id="5555", customer_id="1234567890")


def test_enable_campaign_dry_run(mock_google_ads_client: MagicMock) -> None:
    mock_google_ads_client.get_service.return_value.search_stream.return_value = (
        _stream_with_status("PAUSED")
    )
    resp = enable_campaign(campaign_id="5555", customer_id="1234567890", dry_run=True)
    assert mock_google_ads_client.get_service.return_value.mutate_campaigns.call_count == 0
    assert resp.dry_run is True
    assert resp.mutation_id is None
    assert resp.before == {"status": "PAUSED"}
    assert resp.after == {"status": "ENABLED"}


def test_enable_campaign_real_mutation(mock_google_ads_client: MagicMock) -> None:
    mock_google_ads_client.get_service.return_value.search_stream.return_value = (
        _stream_with_status("PAUSED")
    )
    _program_mutation_response(mock_google_ads_client, "customers/1234567890/campaigns/5555")
    resp = enable_campaign(campaign_id="5555", customer_id="1234567890", dry_run=False)
    assert mock_google_ads_client.get_service.return_value.mutate_campaigns.call_count == 1
    assert resp.mutation_id == "customers/1234567890/campaigns/5555"
    assert resp.after == {"status": "ENABLED"}


def test_enable_campaign_no_op_when_already_enabled(mock_google_ads_client: MagicMock) -> None:
    mock_google_ads_client.get_service.return_value.search_stream.return_value = (
        _stream_with_status("ENABLED")
    )
    resp = enable_campaign(campaign_id="5555", customer_id="1234567890")
    assert mock_google_ads_client.get_service.return_value.mutate_campaigns.call_count == 0
    assert resp.success is True
    assert resp.before == resp.after == {"status": "ENABLED"}
    assert any("already ENABLED; no-op" in w for w in resp.warnings)


def test_pause_campaign_authentication_error_maps_to_credentials_revoked(
    mock_google_ads_client: MagicMock,
) -> None:
    mock_google_ads_client.get_service.return_value.search_stream.side_effect = (
        _make_google_ads_exception(auth=True)
    )
    with pytest.raises(CredentialsRevoked):
        pause_campaign(campaign_id="5555", customer_id="1234567890")
