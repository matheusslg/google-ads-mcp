"""Tests for google_ads_mcp.tools.audits."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from google_ads_mcp.tools.audits import (
    HealthCheck,
    _check_budget_pacing,
    _check_conversion_tracking,
    _check_disapproved_ads,
    _check_low_quality_scores,
    _check_paused_but_spending,
    _overall,
    audit_account_health,
    find_negative_keyword_candidates,
)


def _make_search_term_row(
    *,
    text: str = "free stuff",
    campaign_id: int = 111,
    ad_group_rn: str = "customers/1234567890/adGroups/222",
    impressions: int = 200,
    clicks: int = 10,
    cost_micros: int = 5_000_000,
    conversions: float = 0.0,
) -> MagicMock:
    row = MagicMock()
    row.search_term_view.search_term = text
    row.search_term_view.ad_group = ad_group_rn
    row.campaign.id = campaign_id
    row.metrics.impressions = impressions
    row.metrics.clicks = clicks
    row.metrics.cost_micros = cost_micros
    row.metrics.conversions = conversions
    return row


def _make_disapproved_ad_row(ad_id: int) -> MagicMock:
    row = MagicMock()
    row.ad_group_ad.ad.id = ad_id
    return row


def _make_quality_score_row(criterion_id: int) -> MagicMock:
    row = MagicMock()
    row.ad_group_criterion.criterion_id = criterion_id
    return row


def _make_campaign_budget_row(
    *,
    campaign_id: int = 1,
    campaign_name: str = "Cmp A",
    amount_micros: int = 10_000_000,
    cost_micros: int = 10_000_000,
) -> MagicMock:
    row = MagicMock()
    row.campaign.id = campaign_id
    row.campaign.name = campaign_name
    row.campaign_budget.amount_micros = amount_micros
    row.metrics.cost_micros = cost_micros
    return row


def _make_paused_campaign_row(
    *, campaign_id: int, campaign_name: str, cost_micros: int
) -> MagicMock:
    row = MagicMock()
    row.campaign.id = campaign_id
    row.campaign.name = campaign_name
    row.metrics.cost_micros = cost_micros
    return row


def _stream(mock_client: MagicMock, rows: list[MagicMock]) -> None:
    batch = MagicMock()
    batch.results = rows
    mock_client.get_service.return_value.search_stream.return_value = [batch]


# --- find_negative_keyword_candidates ---


def test_find_negative_keyword_candidates_ranks_by_cost_desc(
    mock_google_ads_client: MagicMock,
) -> None:
    _stream(
        mock_google_ads_client,
        [
            _make_search_term_row(text="cheap", cost_micros=1_000_000),
            _make_search_term_row(text="expensive", cost_micros=9_000_000),
            _make_search_term_row(text="mid", cost_micros=5_000_000),
        ],
    )
    resp = find_negative_keyword_candidates(customer_id="1234567890")
    assert [c.search_term for c in resp.candidates] == ["expensive", "mid", "cheap"]


def test_find_negative_keyword_candidates_reasoning_string(
    mock_google_ads_client: MagicMock,
) -> None:
    _stream(
        mock_google_ads_client,
        [_make_search_term_row(cost_micros=5_420_000, impressions=234, conversions=0.0)],
    )
    resp = find_negative_keyword_candidates(customer_id="1234567890")
    reasoning = resp.candidates[0].reasoning
    assert "$5.42" in reasoning
    assert "234" in reasoning
    assert "0.0" in reasoning


def test_find_negative_keyword_candidates_falls_back_to_default_customer_id(
    mock_google_ads_client: MagicMock,
) -> None:
    _stream(mock_google_ads_client, [])
    resp = find_negative_keyword_candidates()
    assert resp.customer_id == "9999999999"


def test_find_negative_keyword_candidates_zero_conversions_flag_toggles_where_clause(
    mock_google_ads_client: MagicMock,
) -> None:
    _stream(mock_google_ads_client, [])
    find_negative_keyword_candidates(customer_id="1234567890", require_zero_conversions=False)
    call = mock_google_ads_client.get_service.return_value.search_stream.call_args
    assert "metrics.conversions = 0" not in call.kwargs["query"]

    find_negative_keyword_candidates(customer_id="1234567890", require_zero_conversions=True)
    call = mock_google_ads_client.get_service.return_value.search_stream.call_args
    assert "metrics.conversions = 0" in call.kwargs["query"]


# --- _check_disapproved_ads ---


def test_check_disapproved_ads_ok_when_no_rows(mock_google_ads_client: MagicMock) -> None:
    _stream(mock_google_ads_client, [])
    check = _check_disapproved_ads("1234567890", "LAST_7_DAYS")
    assert check.status == "OK"


def test_check_disapproved_ads_warning_1_to_5(mock_google_ads_client: MagicMock) -> None:
    _stream(mock_google_ads_client, [_make_disapproved_ad_row(i) for i in range(3)])
    check = _check_disapproved_ads("1234567890", "LAST_7_DAYS")
    assert check.status == "WARNING"
    assert len(check.details) == 3


def test_check_disapproved_ads_critical_above_5(mock_google_ads_client: MagicMock) -> None:
    _stream(mock_google_ads_client, [_make_disapproved_ad_row(i) for i in range(6)])
    check = _check_disapproved_ads("1234567890", "LAST_7_DAYS")
    assert check.status == "CRITICAL"


# --- _check_low_quality_scores ---


@pytest.mark.parametrize(
    ("row_count", "expected_status"),
    [(0, "OK"), (5, "WARNING"), (11, "CRITICAL")],
)
def test_check_low_quality_scores_thresholds(
    mock_google_ads_client: MagicMock, row_count: int, expected_status: str
) -> None:
    _stream(mock_google_ads_client, [_make_quality_score_row(i) for i in range(row_count)])
    check = _check_low_quality_scores("1234567890", "LAST_7_DAYS")
    assert check.status == expected_status


# --- _check_budget_pacing ---


def test_check_budget_pacing_ok_at_100_percent(mock_google_ads_client: MagicMock) -> None:
    # $10/day budget over 7 days -> expected $70; actual $70 -> 100%, OK.
    _stream(
        mock_google_ads_client,
        [_make_campaign_budget_row(amount_micros=10_000_000, cost_micros=70_000_000)],
    )
    check = _check_budget_pacing("1234567890", "LAST_7_DAYS")
    assert check.status == "OK"
    assert check.details == []


def test_check_budget_pacing_critical_above_200_percent(mock_google_ads_client: MagicMock) -> None:
    # expected $70; actual $150 -> ~214% -> CRITICAL.
    _stream(
        mock_google_ads_client,
        [_make_campaign_budget_row(amount_micros=10_000_000, cost_micros=150_000_000)],
    )
    check = _check_budget_pacing("1234567890", "LAST_7_DAYS")
    assert check.status == "CRITICAL"
    assert len(check.details) == 1


def test_check_budget_pacing_warning_underspend(mock_google_ads_client: MagicMock) -> None:
    # expected $70; actual $10 -> ~14% -> WARNING (< 30%).
    _stream(
        mock_google_ads_client,
        [_make_campaign_budget_row(amount_micros=10_000_000, cost_micros=10_000_000)],
    )
    check = _check_budget_pacing("1234567890", "LAST_7_DAYS")
    assert check.status == "WARNING"


# --- _check_conversion_tracking ---


def test_check_conversion_tracking_critical_when_empty(mock_google_ads_client: MagicMock) -> None:
    _stream(mock_google_ads_client, [])
    check = _check_conversion_tracking("1234567890", "LAST_7_DAYS")
    assert check.status == "CRITICAL"


def test_check_conversion_tracking_ok_when_any_enabled(mock_google_ads_client: MagicMock) -> None:
    row = MagicMock()
    row.conversion_action.id = 1
    _stream(mock_google_ads_client, [row])
    check = _check_conversion_tracking("1234567890", "LAST_7_DAYS")
    assert check.status == "OK"


# --- _check_paused_but_spending ---


def test_check_paused_but_spending_flags_cost_gt_zero(mock_google_ads_client: MagicMock) -> None:
    _stream(
        mock_google_ads_client,
        [
            _make_paused_campaign_row(campaign_id=1, campaign_name="Cmp A", cost_micros=5_000_000),
            _make_paused_campaign_row(campaign_id=2, campaign_name="Cmp B", cost_micros=0),
        ],
    )
    check = _check_paused_but_spending("1234567890", "LAST_7_DAYS")
    assert check.status == "WARNING"
    assert len(check.details) == 1


# --- overall status ---


def test_audit_overall_computed_from_worst_check() -> None:
    def _check(status: str) -> HealthCheck:
        return HealthCheck(name="x", status=status, summary="s")  # type: ignore[arg-type]

    assert _overall([_check("OK"), _check("WARNING"), _check("CRITICAL")]) == "CRITICAL"
    assert _overall([_check("OK"), _check("OK")]) == "OK"


def test_audit_account_health_runs_all_checks_and_falls_back_to_default_customer_id(
    mock_google_ads_client: MagicMock,
) -> None:
    _stream(mock_google_ads_client, [])
    resp = audit_account_health()
    assert resp.customer_id == "9999999999"
    assert resp.overall == "CRITICAL"  # conversion_tracking check is CRITICAL with 0 rows
    assert {c.name for c in resp.checks} == {
        "disapproved_ads",
        "low_quality_scores",
        "budget_pacing",
        "conversion_tracking",
        "paused_but_spending",
    }
