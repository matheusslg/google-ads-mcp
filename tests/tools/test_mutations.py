"""Tests for google_ads_mcp.tools.mutations (pause_campaign, enable_campaign)."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from google.ads.googleads.errors import GoogleAdsException

from google_ads_mcp.auth import CredentialsRevoked
from google_ads_mcp.tools.mutations import (
    MutationResponse,
    _check_guardrails,
    enable_campaign,
    pause_campaign,
    update_campaign_budget,
    update_keyword_bid,
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


def _stream_with_budget(amount_micros: int, budget_id: int = 8888) -> list[MagicMock]:
    row = MagicMock()
    row.campaign.id = 5555
    row.campaign_budget.id = budget_id
    row.campaign_budget.amount_micros = amount_micros
    batch = MagicMock()
    batch.results = [row]
    return [batch]


def _stream_with_bid(cpc_bid_micros: int) -> list[MagicMock]:
    row = MagicMock()
    row.ad_group_criterion.criterion_id = 42
    row.ad_group_criterion.cpc_bid_micros = cpc_bid_micros
    batch = MagicMock()
    batch.results = [row]
    return [batch]


def _program_budget_mutation_response(mock_client: MagicMock, resource_name: str) -> None:
    result = MagicMock()
    result.resource_name = resource_name
    resp = MagicMock()
    resp.results = [result]
    mock_client.get_service.return_value.mutate_campaign_budgets.return_value = resp


def _program_bid_mutation_response(mock_client: MagicMock, resource_name: str) -> None:
    result = MagicMock()
    result.resource_name = resource_name
    resp = MagicMock()
    resp.results = [result]
    mock_client.get_service.return_value.mutate_ad_group_criteria.return_value = resp


def test_check_guardrails_helper_all_paths() -> None:
    # both omitted -> default percent applied
    allowed, warnings = _check_guardrails(50.0, 60.0, max_increase_percent=None, absolute_cap=None)
    assert allowed is True
    assert any("default max_increase_percent=50" in w for w in warnings)

    # over default percent -> refused
    allowed, warnings = _check_guardrails(50.0, 80.0, max_increase_percent=None, absolute_cap=None)
    assert allowed is False
    assert any("exceeds max_increase_percent" in w for w in warnings)

    # absolute cap refusal
    allowed, warnings = _check_guardrails(
        50.0, 150.0, max_increase_percent=None, absolute_cap=100.0
    )
    assert allowed is False
    assert any("exceeds absolute_cap" in w for w in warnings)

    # decrease always allowed regardless of percent cap
    allowed, warnings = _check_guardrails(100.0, 10.0, max_increase_percent=10.0, absolute_cap=None)
    assert allowed is True

    # zero current skips percent check
    allowed, warnings = _check_guardrails(0.0, 50.0, max_increase_percent=50.0, absolute_cap=None)
    assert allowed is True
    assert any("current amount is 0" in w for w in warnings)

    # both caps set, both can independently refuse
    allowed, warnings = _check_guardrails(
        50.0, 200.0, max_increase_percent=10.0, absolute_cap=100.0
    )
    assert allowed is False
    assert len(warnings) == 2


def test_update_budget_default_cap_applied_when_both_omitted(
    mock_google_ads_client: MagicMock,
) -> None:
    mock_google_ads_client.get_service.return_value.search_stream.return_value = (
        _stream_with_budget(50_000_000)
    )
    resp = update_campaign_budget(campaign_id="5555", new_amount=55.0, dry_run=True)
    assert resp.success is True
    assert any("default max_increase_percent=50" in w for w in resp.warnings)


def test_update_budget_over_percent_refused(mock_google_ads_client: MagicMock) -> None:
    mock_google_ads_client.get_service.return_value.search_stream.return_value = (
        _stream_with_budget(50_000_000)
    )
    resp = update_campaign_budget(campaign_id="5555", new_amount=80.0)  # +60% > 50%
    assert resp.success is False
    assert any("exceeds max_increase_percent" in w for w in resp.warnings)
    mock_google_ads_client.get_service.return_value.mutate_campaign_budgets.assert_not_called()


def test_update_budget_within_percent_allowed(mock_google_ads_client: MagicMock) -> None:
    mock_google_ads_client.get_service.return_value.search_stream.return_value = (
        _stream_with_budget(50_000_000)
    )
    resp = update_campaign_budget(campaign_id="5555", new_amount=60.0, dry_run=True)  # +20%
    assert resp.success is True


def test_update_budget_absolute_cap_refused(mock_google_ads_client: MagicMock) -> None:
    mock_google_ads_client.get_service.return_value.search_stream.return_value = (
        _stream_with_budget(50_000_000)
    )
    resp = update_campaign_budget(campaign_id="5555", new_amount=150.0, absolute_cap=100.0)
    assert resp.success is False
    assert any("exceeds absolute_cap" in w for w in resp.warnings)


def test_update_budget_decrease_always_allowed(mock_google_ads_client: MagicMock) -> None:
    mock_google_ads_client.get_service.return_value.search_stream.return_value = (
        _stream_with_budget(100_000_000)
    )
    resp = update_campaign_budget(campaign_id="5555", new_amount=10.0, dry_run=True)
    assert resp.success is True


def test_update_budget_zero_current_skips_percent(mock_google_ads_client: MagicMock) -> None:
    mock_google_ads_client.get_service.return_value.search_stream.return_value = (
        _stream_with_budget(0)
    )
    resp = update_campaign_budget(campaign_id="5555", new_amount=50.0, dry_run=True)
    assert resp.success is True
    assert any("current amount is 0" in w for w in resp.warnings)


def test_update_budget_dry_run_no_mutation_call(mock_google_ads_client: MagicMock) -> None:
    mock_google_ads_client.get_service.return_value.search_stream.return_value = (
        _stream_with_budget(50_000_000)
    )
    resp = update_campaign_budget(campaign_id="5555", new_amount=55.0, dry_run=True)
    assert resp.success is True
    assert resp.dry_run is True
    mock_google_ads_client.get_service.return_value.mutate_campaign_budgets.assert_not_called()


def test_update_budget_real_mutation_uses_correct_micros(
    mock_google_ads_client: MagicMock,
) -> None:
    mock_google_ads_client.get_service.return_value.search_stream.return_value = (
        _stream_with_budget(50_000_000)
    )
    _program_budget_mutation_response(
        mock_google_ads_client, "customers/1234567890/campaignBudgets/8888"
    )
    resp = update_campaign_budget(campaign_id="5555", new_amount=55.0, customer_id="1234567890")
    assert resp.success is True
    assert resp.mutation_id == "customers/1234567890/campaignBudgets/8888"
    mutate_call = mock_google_ads_client.get_service.return_value.mutate_campaign_budgets
    mutate_call.assert_called_once()
    op = mutate_call.call_args.kwargs["operations"][0]
    assert op.update.amount_micros == round(55.0 * 1_000_000)


def test_update_bid_default_cap_applied_when_omitted(mock_google_ads_client: MagicMock) -> None:
    mock_google_ads_client.get_service.return_value.search_stream.return_value = (
        _stream_with_bid(1_000_000)  # $1.00
    )
    resp = update_keyword_bid(ad_group_id="111", criterion_id="42", new_bid=1.20, dry_run=True)
    assert resp.success is True
    assert any("current x 1.5" in w for w in resp.warnings)


def test_update_bid_over_absolute_cap_refused(mock_google_ads_client: MagicMock) -> None:
    mock_google_ads_client.get_service.return_value.search_stream.return_value = _stream_with_bid(
        1_000_000
    )
    resp = update_keyword_bid(ad_group_id="111", criterion_id="42", new_bid=2.0, max_bid_cap=1.0)
    assert resp.success is False
    assert any("exceeds max_bid_cap" in w for w in resp.warnings)
    mock_google_ads_client.get_service.return_value.mutate_ad_group_criteria.assert_not_called()


def test_update_bid_within_cap_allowed(mock_google_ads_client: MagicMock) -> None:
    mock_google_ads_client.get_service.return_value.search_stream.return_value = _stream_with_bid(
        1_000_000
    )
    resp = update_keyword_bid(
        ad_group_id="111", criterion_id="42", new_bid=1.10, max_bid_cap=2.0, dry_run=True
    )
    assert resp.success is True


def test_update_bid_dry_run_no_mutation_call(mock_google_ads_client: MagicMock) -> None:
    mock_google_ads_client.get_service.return_value.search_stream.return_value = _stream_with_bid(
        1_000_000
    )
    resp = update_keyword_bid(ad_group_id="111", criterion_id="42", new_bid=1.10, dry_run=True)
    assert resp.success is True
    assert resp.dry_run is True
    mock_google_ads_client.get_service.return_value.mutate_ad_group_criteria.assert_not_called()


def test_update_bid_real_mutation_uses_correct_micros(mock_google_ads_client: MagicMock) -> None:
    mock_google_ads_client.get_service.return_value.search_stream.return_value = _stream_with_bid(
        1_000_000
    )
    _program_bid_mutation_response(
        mock_google_ads_client, "customers/1234567890/adGroupCriteria/111~42"
    )
    resp = update_keyword_bid(
        ad_group_id="111",
        criterion_id="42",
        new_bid=1.10,
        max_bid_cap=2.0,
        customer_id="1234567890",
    )
    assert resp.success is True
    assert resp.mutation_id == "customers/1234567890/adGroupCriteria/111~42"
    mutate_call = mock_google_ads_client.get_service.return_value.mutate_ad_group_criteria
    mutate_call.assert_called_once()
    op = mutate_call.call_args.kwargs["operations"][0]
    assert op.update.cpc_bid_micros == round(1.10 * 1_000_000)


def test_update_bid_current_zero_uses_new_as_baseline(mock_google_ads_client: MagicMock) -> None:
    mock_google_ads_client.get_service.return_value.search_stream.return_value = _stream_with_bid(0)
    resp = update_keyword_bid(ad_group_id="111", criterion_id="42", new_bid=0.50)
    assert resp.success is False
    assert any("exceeds max_bid_cap" in w for w in resp.warnings)
