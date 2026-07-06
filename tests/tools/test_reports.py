"""Tests for google_ads_mcp.tools.reports."""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock

from google_ads_mcp.tools.reports import (
    _compute_prior_period,
    _format_delta,
    get_performance,
    list_search_terms,
    summarize_performance,
)


def _make_perf_row(
    *,
    impressions: int = 1000,
    clicks: int = 50,
    cost_micros: int = 25_000_000,
    conversions: float = 5.0,
    ctr: float = 0.05,
    average_cpc: int = 500_000,
    campaign_id: int | None = None,
    campaign_name: str | None = None,
) -> MagicMock:
    row = MagicMock()
    row.metrics.impressions = impressions
    row.metrics.clicks = clicks
    row.metrics.cost_micros = cost_micros
    row.metrics.conversions = conversions
    row.metrics.ctr = ctr
    row.metrics.average_cpc = average_cpc
    if campaign_id is not None:
        row.campaign.id = campaign_id
    if campaign_name is not None:
        row.campaign.name = campaign_name
    return row


def _make_search_term_row(
    *,
    text: str = "running shoes",
    match_type: str = "NEAR_EXACT",
    campaign_id: int = 111,
    ad_group_rn: str = "customers/1234567890/adGroups/222",
    impressions: int = 500,
    clicks: int = 20,
    cost_micros: int = 10_000_000,
    conversions: float = 1.0,
    ctr: float = 0.04,
    average_cpc: int = 500_000,
) -> MagicMock:
    row = MagicMock()
    row.search_term_view.search_term = text
    row.search_term_view.ad_group = ad_group_rn
    row.segments.search_term_match_type.name = match_type
    row.campaign.id = campaign_id
    row.metrics.impressions = impressions
    row.metrics.clicks = clicks
    row.metrics.cost_micros = cost_micros
    row.metrics.conversions = conversions
    row.metrics.ctr = ctr
    row.metrics.average_cpc = average_cpc
    return row


# --- get_performance ---


def test_get_performance_no_segment_returns_single_row(mock_google_ads_client: MagicMock) -> None:
    batch = MagicMock()
    batch.results = [_make_perf_row()]
    mock_google_ads_client.get_service.return_value.search_stream.return_value = [batch]
    resp = get_performance(customer_id="1234567890")
    assert len(resp.rows) == 1
    assert resp.rows[0].segment is None
    assert resp.rows[0].segment_id is None


def test_get_performance_segment_by_campaign(mock_google_ads_client: MagicMock) -> None:
    batch = MagicMock()
    batch.results = [
        _make_perf_row(campaign_id=1, campaign_name="Cmp A"),
        _make_perf_row(campaign_id=2, campaign_name="Cmp B"),
        _make_perf_row(campaign_id=3, campaign_name="Cmp C"),
    ]
    mock_google_ads_client.get_service.return_value.search_stream.return_value = [batch]
    resp = get_performance(customer_id="1234567890", segment_by="campaign")
    assert len(resp.rows) == 3
    assert resp.rows[0].segment == "Cmp A"
    assert resp.rows[0].segment_id == "1"
    assert resp.rows[2].segment == "Cmp C"
    assert resp.rows[2].segment_id == "3"


def test_get_performance_cost_micros_converted_to_dollars(
    mock_google_ads_client: MagicMock,
) -> None:
    batch = MagicMock()
    batch.results = [_make_perf_row(cost_micros=1_500_000)]
    mock_google_ads_client.get_service.return_value.search_stream.return_value = [batch]
    resp = get_performance(customer_id="1234567890")
    assert resp.rows[0].metrics.cost == 1.5


def test_get_performance_uses_default_customer_id(mock_google_ads_client: MagicMock) -> None:
    mock_google_ads_client.get_service.return_value.search_stream.return_value = []
    resp = get_performance()  # no customer_id
    assert resp.customer_id == "9999999999"  # from fixture


# --- list_search_terms ---


def test_list_search_terms_applies_min_impressions_filter(
    mock_google_ads_client: MagicMock,
) -> None:
    mock_google_ads_client.get_service.return_value.search_stream.return_value = []
    list_search_terms(customer_id="1234567890", min_impressions=50)
    call = mock_google_ads_client.get_service.return_value.search_stream.call_args
    assert "metrics.impressions >= 50" in call.kwargs["query"]


def test_list_search_terms_returns_envelope(mock_google_ads_client: MagicMock) -> None:
    batch = MagicMock()
    batch.results = [_make_search_term_row()]
    mock_google_ads_client.get_service.return_value.search_stream.return_value = [batch]
    resp = list_search_terms(customer_id="1234567890", min_impressions=100)
    assert resp.min_impressions == 100
    assert len(resp.search_terms) == 1
    term = resp.search_terms[0]
    assert term.text == "running shoes"
    assert term.match_type == "NEAR_EXACT"
    assert term.campaign_id == "111"
    assert term.ad_group_id == "222"


# --- summarize_performance ---


def test_summarize_performance_computes_deltas(mock_google_ads_client: MagicMock) -> None:
    current_batch = MagicMock()
    current_batch.results = [_make_perf_row(clicks=100)]
    previous_batch = MagicMock()
    previous_batch.results = [_make_perf_row(clicks=80)]
    mock_google_ads_client.get_service.return_value.search_stream.side_effect = [
        [current_batch],
        [previous_batch],
    ]
    resp = summarize_performance(customer_id="1234567890")
    assert resp.comparison.current.clicks == 100
    assert resp.comparison.previous.clicks == 80
    assert resp.comparison.delta_pct.clicks == 25.0


def test_summarize_performance_narrative_contains_key_metrics(
    mock_google_ads_client: MagicMock,
) -> None:
    batch = MagicMock()
    batch.results = [_make_perf_row()]
    mock_google_ads_client.get_service.return_value.search_stream.side_effect = [
        [batch],
        [batch],
    ]
    resp = summarize_performance(customer_id="1234567890")
    narrative = resp.narrative.lower()
    for keyword in ("clicks", "cpc", "conversions", "spend"):
        assert keyword in narrative


def test_summarize_performance_uses_two_gaql_queries(mock_google_ads_client: MagicMock) -> None:
    mock_google_ads_client.get_service.return_value.search_stream.return_value = []
    summarize_performance(customer_id="1234567890")
    stream = mock_google_ads_client.get_service.return_value.search_stream
    assert stream.call_count == 2
    first_query = stream.call_args_list[0].kwargs["query"]
    second_query = stream.call_args_list[1].kwargs["query"]
    assert "DURING LAST_7_DAYS" in first_query
    assert "BETWEEN" in second_query


# --- pure helpers ---


def test_format_delta_positive_negative_flat() -> None:
    assert _format_delta(25.0) == "+25%"
    assert _format_delta(-12.3) == "-12%"
    assert _format_delta(0.2) == "flat"


def test_summarize_performance_prior_period_dates() -> None:
    start, end = _compute_prior_period("LAST_7_DAYS", _today=date(2026, 7, 6))
    assert start == date(2026, 6, 22)
    assert end == date(2026, 6, 28)
