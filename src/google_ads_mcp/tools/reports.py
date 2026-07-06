"""Performance reporting tools for google-ads-mcp.

Built on the `_search` / `_resolve_customer_id` helpers from `tools.reads` —
row-cap and auth-error mapping are reused for free, nothing is reimplemented
here. Adds metrics aggregation, date-range filtering, and a deterministic
English narrative for `summarize_performance`.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Literal

from pydantic import BaseModel

from google_ads_mcp._mcp import mcp
from google_ads_mcp.tools.reads import _resolve_customer_id, _search

_DateRange = Literal["LAST_7_DAYS", "LAST_14_DAYS", "LAST_30_DAYS", "THIS_MONTH", "LAST_MONTH"]
_Segment = Literal["campaign", "device", "network", "day"]

_METRICS_SELECT = (
    "metrics.impressions, metrics.clicks, metrics.cost_micros, "
    "metrics.conversions, metrics.ctr, metrics.average_cpc"
)

# Duration (in days) of the fixed-window enums. THIS_MONTH / LAST_MONTH are
# calendar-based and handled separately in _compute_prior_period.
_DURATION_DAYS: dict[str, int] = {"LAST_7_DAYS": 7, "LAST_14_DAYS": 14, "LAST_30_DAYS": 30}


class Metrics(BaseModel):
    impressions: int
    clicks: int
    cost: float  # dollars
    conversions: float  # can be fractional in Google Ads (attributed conversions)
    ctr: float  # 0.0-1.0
    average_cpc: float  # dollars


class MetricsDelta(BaseModel):
    """Per-field percentage change. Always float — a delta is a %, not a raw
    metric, so (unlike Metrics) impressions/clicks aren't coerced to int here.
    """

    impressions: float
    clicks: float
    cost: float
    conversions: float
    ctr: float
    average_cpc: float


class PerformanceRow(BaseModel):
    """A single row of the performance report, keyed by segment if requested."""

    segment: str | None = None  # e.g. "MOBILE", "SEARCH", "2026-06-30", or campaign name
    segment_id: str | None = None  # e.g. campaign_id when segment_by='campaign'
    metrics: Metrics


class GetPerformanceResponse(BaseModel):
    customer_id: str
    date_range: _DateRange
    segment_by: _Segment | None
    rows: list[PerformanceRow]
    warnings: list[str] = []


class SearchTerm(BaseModel):
    text: str
    match_type: str  # broader than keyword match — includes NEAR_EXACT etc.
    metrics: Metrics
    campaign_id: str
    ad_group_id: str


class ListSearchTermsResponse(BaseModel):
    customer_id: str
    date_range: _DateRange
    min_impressions: int
    search_terms: list[SearchTerm]
    warnings: list[str] = []


class PeriodComparison(BaseModel):
    current: Metrics
    previous: Metrics
    delta_pct: MetricsDelta


class SummarizePerformanceResponse(BaseModel):
    customer_id: str
    date_range: _DateRange
    comparison_period: _DateRange
    narrative: str
    comparison: PeriodComparison
    warnings: list[str] = []


def _metrics_from_row(r: Any) -> Metrics:
    """Build Metrics from a GoogleAdsRow. `average_cpc` is a double field but,
    like cost_micros, its value is expressed in micros — verified against the
    installed google-ads proto (metrics.py); divide by 1e6 same as cost.
    """
    return Metrics(
        impressions=int(r.metrics.impressions),
        clicks=int(r.metrics.clicks),
        cost=r.metrics.cost_micros / 1_000_000,
        conversions=float(r.metrics.conversions),
        ctr=float(r.metrics.ctr),
        average_cpc=r.metrics.average_cpc / 1_000_000,
    )


def _aggregate_metrics(rows: list[Any]) -> Metrics:
    """Customer-level aggregate queries (no segment in SELECT) return at most
    one row. No data in range -> zeroed metrics rather than an error.
    """
    if not rows:
        return Metrics(impressions=0, clicks=0, cost=0.0, conversions=0.0, ctr=0.0, average_cpc=0.0)
    return _metrics_from_row(rows[0])


def _performance_query(date_range: _DateRange, segment_by: _Segment | None) -> str:
    extra_select = {
        None: "",
        "campaign": "campaign.id, campaign.name, ",
        "device": "segments.device, ",
        "network": "segments.ad_network_type, ",
        "day": "segments.date, ",
    }[segment_by]
    from_table = "campaign" if segment_by == "campaign" else "customer"
    return (
        f"SELECT {extra_select}{_METRICS_SELECT} FROM {from_table} "
        f"WHERE segments.date DURING {date_range}"
    )


def _row_to_performance_row(r: Any, segment_by: _Segment | None) -> PerformanceRow:
    segment: str | None = None
    segment_id: str | None = None
    if segment_by == "campaign":
        segment = r.campaign.name
        segment_id = str(r.campaign.id)
    elif segment_by == "device":
        segment = r.segments.device.name
    elif segment_by == "network":
        segment = r.segments.ad_network_type.name
    elif segment_by == "day":
        segment = r.segments.date
    return PerformanceRow(segment=segment, segment_id=segment_id, metrics=_metrics_from_row(r))


def _compute_prior_period(date_range: _DateRange, _today: date | None = None) -> tuple[date, date]:
    """Return (start, end) dates for the comparable period immediately before
    `date_range`. GAQL has no "prior LAST_7_DAYS" enum, so this is computed in
    Python and issued as an explicit `segments.date BETWEEN` query.
    """
    today = _today or date.today()
    if date_range in _DURATION_DAYS:
        days = _DURATION_DAYS[date_range]
        current_start = today - timedelta(days=days)  # DURING excludes today
        prior_end = current_start - timedelta(days=1)
        prior_start = prior_end - timedelta(days=days - 1)
        return prior_start, prior_end
    if date_range == "THIS_MONTH":
        prior_end = today.replace(day=1) - timedelta(days=1)  # last day of previous month
        return prior_end.replace(day=1), prior_end
    # LAST_MONTH -> prior period is the full calendar month before that
    last_month_start = (today.replace(day=1) - timedelta(days=1)).replace(day=1)
    prior_end = last_month_start - timedelta(days=1)
    return prior_end.replace(day=1), prior_end


def _pct_change(current: float, previous: float) -> float:
    if previous == 0:
        return 0.0 if current == 0 else 100.0
    return (current - previous) / previous * 100


def _compute_delta_pct(current: Metrics, previous: Metrics) -> MetricsDelta:
    return MetricsDelta(
        impressions=_pct_change(current.impressions, previous.impressions),
        clicks=_pct_change(current.clicks, previous.clicks),
        cost=_pct_change(current.cost, previous.cost),
        conversions=_pct_change(current.conversions, previous.conversions),
        ctr=_pct_change(current.ctr, previous.ctr),
        average_cpc=_pct_change(current.average_cpc, previous.average_cpc),
    )


def _format_delta(pct: float) -> str:
    """`+12%` / `-3%` / `flat` (if abs(pct) < 0.5)."""
    if abs(pct) < 0.5:
        return "flat"
    if pct >= 0.5:
        return f"+{round(pct)}%"
    return f"{round(pct)}%"


def _format_narrative(
    date_range: _DateRange,
    current: Metrics,
    previous: Metrics,
    delta_pct: MetricsDelta,
) -> str:
    """Deterministic English narrative, optimized for LLM consumption — the
    LLM handles translation to the user's conversational language (PRD Q3).
    """
    imp_delta = _format_delta(delta_pct.impressions)
    clicks_delta = _format_delta(delta_pct.clicks)
    cpc_delta = _format_delta(delta_pct.average_cpc)
    conv_delta = _format_delta(delta_pct.conversions)
    cost_delta = _format_delta(delta_pct.cost)
    ctr_delta = _format_delta(delta_pct.ctr)
    return (
        f"{date_range}: {current.impressions:,} impressions ({imp_delta}), "
        f"{current.clicks:,} clicks ({clicks_delta}) "
        f"at ${current.average_cpc:.2f} CPC ({cpc_delta}). "
        f"Conversions: {current.conversions:.1f} ({conv_delta}). "
        f"Spend: ${current.cost:,.2f} ({cost_delta}). "
        f"CTR: {current.ctr * 100:.2f}% ({ctr_delta})."
    )


@mcp.tool
def get_performance(
    customer_id: str | None = None,
    date_range: _DateRange = "LAST_7_DAYS",
    segment_by: _Segment | None = None,
) -> GetPerformanceResponse:
    """Get performance metrics for a customer, optionally segmented.

    Args:
        customer_id: 10-digit ID. Defaults to `default_customer_id`.
        date_range: One of LAST_7_DAYS, LAST_14_DAYS, LAST_30_DAYS, THIS_MONTH, LAST_MONTH.
        segment_by: Optional — split rows by campaign, device, network, or day.

    Returns rows with impressions, clicks, cost, conversions, ctr, average_cpc.
    """
    cid = _resolve_customer_id(customer_id)
    rows, warnings = _search(cid, _performance_query(date_range, segment_by))
    return GetPerformanceResponse(
        customer_id=cid,
        date_range=date_range,
        segment_by=segment_by,
        rows=[_row_to_performance_row(r, segment_by) for r in rows],
        warnings=warnings,
    )


@mcp.tool
def list_search_terms(
    customer_id: str | None = None,
    date_range: _DateRange = "LAST_7_DAYS",
    min_impressions: int = 100,
) -> ListSearchTermsResponse:
    """List search terms that triggered ads, optionally filtered by impression count.

    Args:
        customer_id: 10-digit ID. Defaults to `default_customer_id`.
        date_range: One of the standard ranges.
        min_impressions: Skip terms with fewer than this many impressions. Default 100.
    """
    cid = _resolve_customer_id(customer_id)
    query = (
        "SELECT search_term_view.search_term, segments.search_term_match_type, "
        f"campaign.id, search_term_view.ad_group, {_METRICS_SELECT} "
        f"FROM search_term_view WHERE segments.date DURING {date_range} "
        f"AND metrics.impressions >= {min_impressions}"
    )
    rows, warnings = _search(cid, query)
    return ListSearchTermsResponse(
        customer_id=cid,
        date_range=date_range,
        min_impressions=min_impressions,
        search_terms=[
            SearchTerm(
                text=r.search_term_view.search_term,
                match_type=r.segments.search_term_match_type.name,
                metrics=_metrics_from_row(r),
                campaign_id=str(r.campaign.id),
                ad_group_id=r.search_term_view.ad_group.split("/")[-1],
            )
            for r in rows
        ],
        warnings=warnings,
    )


@mcp.tool
def summarize_performance(
    customer_id: str | None = None,
    date_range: _DateRange = "LAST_7_DAYS",
    comparison_period: _DateRange | None = None,
) -> SummarizePerformanceResponse:
    """Narrative + structured summary comparing a period to the prior period.

    Args:
        customer_id: 10-digit ID. Defaults to `default_customer_id`.
        date_range: The primary period. Default LAST_7_DAYS.
        comparison_period: Prior period to compare against. Defaults to the same-duration
            period immediately before `date_range` (auto-derived).

    Returns a plain-English narrative plus current/previous metric aggregates and per-field
    percentage deltas. The narrative is optimized for LLM consumption; the LLM handles
    translation to the user's conversational language.
    """
    cid = _resolve_customer_id(customer_id)
    comparison = comparison_period or date_range

    current_rows, current_warnings = _search(
        cid, f"SELECT {_METRICS_SELECT} FROM customer WHERE segments.date DURING {date_range}"
    )
    current = _aggregate_metrics(current_rows)

    prior_start, prior_end = _compute_prior_period(comparison)
    prior_rows, prior_warnings = _search(
        cid,
        f"SELECT {_METRICS_SELECT} FROM customer WHERE segments.date BETWEEN "
        f"'{prior_start.isoformat()}' AND '{prior_end.isoformat()}'",
    )
    previous = _aggregate_metrics(prior_rows)

    delta_pct = _compute_delta_pct(current, previous)
    return SummarizePerformanceResponse(
        customer_id=cid,
        date_range=date_range,
        comparison_period=comparison,
        narrative=_format_narrative(date_range, current, previous, delta_pct),
        comparison=PeriodComparison(current=current, previous=previous, delta_pct=delta_pct),
        warnings=current_warnings + prior_warnings,
    )
