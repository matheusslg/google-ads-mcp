"""Analytical / audit tools for google-ads-mcp.

Workflow-shaped, read-only tools: `find_negative_keyword_candidates` surfaces
search terms burning budget without converting; `audit_account_health` runs a
fixed battery of 5 health checks and rolls them up into one status. Built on
`_search` / `_resolve_customer_id` from `.reads` and `_DateRange` / `PERIOD_DAYS`
from `.reports` — nothing here reimplements row-fetching or auth handling.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel

from google_ads_mcp._mcp import mcp
from google_ads_mcp.tools.reads import _resolve_customer_id, _search
from google_ads_mcp.tools.reports import PERIOD_DAYS, _DateRange

_CheckStatus = Literal["OK", "WARNING", "CRITICAL"]


class NegativeKeywordCandidate(BaseModel):
    search_term: str
    impressions: int
    clicks: int
    cost: float
    conversions: float
    campaign_id: str
    ad_group_id: str
    reasoning: str


class FindNegativeKeywordCandidatesResponse(BaseModel):
    customer_id: str
    date_range: _DateRange
    candidates: list[NegativeKeywordCandidate]
    warnings: list[str] = []


class HealthCheck(BaseModel):
    name: str
    status: _CheckStatus
    summary: str
    details: list[str] = []


class AuditAccountHealthResponse(BaseModel):
    customer_id: str
    date_range: _DateRange
    overall: _CheckStatus
    checks: list[HealthCheck]
    warnings: list[str] = []


def _overall(checks: list[HealthCheck]) -> _CheckStatus:
    if any(c.status == "CRITICAL" for c in checks):
        return "CRITICAL"
    if any(c.status == "WARNING" for c in checks):
        return "WARNING"
    return "OK"


def _check_disapproved_ads(customer_id: str, date_range: _DateRange) -> HealthCheck:
    """OK if 0 disapproved ads, WARNING if 1-5, CRITICAL if > 5."""
    query = (
        "SELECT ad_group_ad.ad.id, ad_group_ad.status, "
        "ad_group_ad.policy_summary.approval_status "
        "FROM ad_group_ad "
        "WHERE ad_group_ad.policy_summary.approval_status = 'DISAPPROVED'"
    )
    rows, _ = _search(customer_id, query)
    ids = [str(r.ad_group_ad.ad.id) for r in rows]
    n = len(ids)
    status: _CheckStatus = "OK" if n == 0 else ("WARNING" if n <= 5 else "CRITICAL")
    summary = f"{n} disapproved ad(s)" if n else "No disapproved ads"
    return HealthCheck(name="disapproved_ads", status=status, summary=summary, details=ids)


def _check_low_quality_scores(customer_id: str, date_range: _DateRange) -> HealthCheck:
    """OK if 0 keywords with quality_score < 5, WARNING if 1-10, CRITICAL if > 10."""
    query = (
        "SELECT ad_group_criterion.criterion_id, ad_group_criterion.quality_info.quality_score "
        "FROM keyword_view "
        "WHERE ad_group_criterion.quality_info.quality_score < 5 "
        "AND ad_group_criterion.status = 'ENABLED'"
    )
    rows, _ = _search(customer_id, query)
    ids = [str(r.ad_group_criterion.criterion_id) for r in rows]
    n = len(ids)
    status: _CheckStatus = "OK" if n == 0 else ("WARNING" if n <= 10 else "CRITICAL")
    summary = f"{n} keyword(s) with quality score below 5" if n else "No low quality score keywords"
    return HealthCheck(name="low_quality_scores", status=status, summary=summary, details=ids)


def _check_budget_pacing(customer_id: str, date_range: _DateRange) -> HealthCheck:
    """Compare actual spend to expected spend (daily budget x days in range) per campaign.

    WARNING if any campaign is > 120% or < 30% of expected; CRITICAL if any campaign
    is > 200% of expected.
    """
    query = (
        "SELECT campaign.id, campaign.name, campaign.status, "
        "campaign_budget.amount_micros, metrics.cost_micros "
        "FROM campaign "
        f"WHERE campaign.status = 'ENABLED' AND segments.date DURING {date_range}"
    )
    rows, _ = _search(customer_id, query)
    days = PERIOD_DAYS[date_range]

    # rows are per-segment (e.g. per day); aggregate cost per campaign first.
    campaigns: dict[str, list[Any]] = {}
    for r in rows:
        cid = str(r.campaign.id)
        entry = campaigns.setdefault(cid, [r.campaign.name, r.campaign_budget.amount_micros, 0])
        entry[2] += r.metrics.cost_micros

    details: list[str] = []
    statuses: list[_CheckStatus] = []
    for cid, (name, amount_micros, cost_micros) in campaigns.items():
        expected = (amount_micros / 1_000_000) * days
        if expected == 0:
            continue  # no daily budget configured; nothing to compare against
        actual = cost_micros / 1_000_000
        ratio = actual / expected
        if ratio > 2.0:
            status: _CheckStatus = "CRITICAL"
        elif ratio > 1.2 or ratio < 0.3:
            status = "WARNING"
        else:
            status = "OK"
        if status != "OK":
            statuses.append(status)
            details.append(
                f"{name} (id={cid}): ${actual:.2f} actual vs ${expected:.2f} expected "
                f"({ratio * 100:.0f}%)"
            )

    overall_status: _CheckStatus = (
        "CRITICAL" if "CRITICAL" in statuses else ("WARNING" if statuses else "OK")
    )
    summary = (
        f"{len(details)} campaign(s) pacing anomalously"
        if details
        else "No budget pacing anomalies detected"
    )
    return HealthCheck(
        name="budget_pacing", status=overall_status, summary=summary, details=details
    )


def _check_conversion_tracking(customer_id: str, date_range: _DateRange) -> HealthCheck:
    """OK if >= 1 enabled conversion action exists, CRITICAL if 0."""
    query = (
        "SELECT conversion_action.id, conversion_action.name, conversion_action.status "
        "FROM conversion_action "
        "WHERE conversion_action.status = 'ENABLED'"
    )
    rows, _ = _search(customer_id, query)
    n = len(rows)
    status: _CheckStatus = "OK" if n >= 1 else "CRITICAL"
    summary = f"{n} enabled conversion action(s)" if n else "No enabled conversion actions found"
    return HealthCheck(
        name="conversion_tracking",
        status=status,
        summary=summary,
        details=[str(r.conversion_action.id) for r in rows],
    )


def _check_paused_but_spending(customer_id: str, date_range: _DateRange) -> HealthCheck:
    """OK if no paused campaign has cost > 0 in date_range, else WARNING."""
    query = (
        "SELECT campaign.id, campaign.name, campaign.status, metrics.cost_micros "
        "FROM campaign "
        f"WHERE campaign.status = 'PAUSED' AND segments.date DURING {date_range}"
    )
    rows, _ = _search(customer_id, query)

    campaigns: dict[str, list[Any]] = {}
    for r in rows:
        cid = str(r.campaign.id)
        entry = campaigns.setdefault(cid, [r.campaign.name, 0])
        entry[1] += r.metrics.cost_micros

    details = [
        f"{name} (id={cid}): ${cost_micros / 1_000_000:.2f} spent while paused"
        for cid, (name, cost_micros) in campaigns.items()
        if cost_micros > 0
    ]
    status: _CheckStatus = "WARNING" if details else "OK"
    summary = (
        f"{len(details)} paused campaign(s) still accruing spend"
        if details
        else "No paused campaigns are still spending"
    )
    return HealthCheck(name="paused_but_spending", status=status, summary=summary, details=details)


@mcp.tool
def find_negative_keyword_candidates(
    customer_id: str | None = None,
    date_range: _DateRange = "LAST_30_DAYS",
    min_impressions: int = 50,
    min_cost: float = 1.0,
    require_zero_conversions: bool = True,
) -> FindNegativeKeywordCandidatesResponse:
    """Find search terms that spent money but didn't convert — negative-keyword candidates.

    Args:
        customer_id: 10-digit ID; defaults to `default_customer_id`.
        date_range: Look-back window. Default LAST_30_DAYS.
        min_impressions: Skip terms with fewer impressions.
        min_cost: Skip terms with less than this many dollars spent.
        require_zero_conversions: When True, only include terms with 0 conversions.

    Returns candidates ranked by cost descending. Each includes a plain-English `reasoning`
    string suitable for showing the user why it was flagged.
    """
    cid = _resolve_customer_id(customer_id)
    conversions_filter = " AND metrics.conversions = 0" if require_zero_conversions else ""
    query = (
        "SELECT search_term_view.search_term, metrics.impressions, metrics.clicks, "
        "metrics.cost_micros, metrics.conversions, search_term_view.ad_group, campaign.id "
        "FROM search_term_view "
        f"WHERE segments.date DURING {date_range} "
        f"AND metrics.impressions >= {min_impressions} "
        f"AND metrics.cost_micros >= {int(min_cost * 1_000_000)}"
        f"{conversions_filter} "
        "ORDER BY metrics.cost_micros DESC"
    )
    rows, warnings = _search(cid, query)
    candidates = [
        NegativeKeywordCandidate(
            search_term=r.search_term_view.search_term,
            impressions=int(r.metrics.impressions),
            clicks=int(r.metrics.clicks),
            cost=r.metrics.cost_micros / 1_000_000,
            conversions=float(r.metrics.conversions),
            campaign_id=str(r.campaign.id),
            ad_group_id=r.search_term_view.ad_group.split("/")[-1],
            reasoning=(
                f"${r.metrics.cost_micros / 1_000_000:.2f} spent across "
                f"{int(r.metrics.impressions):,} impressions, "
                f"{float(r.metrics.conversions):.1f} conversions"
            ),
        )
        for r in rows
    ]
    # GAQL already orders by cost desc; re-sort defensively so callers (and mocked
    # tests) can't be tripped up by row order the API/mock happens to hand back.
    candidates.sort(key=lambda c: c.cost, reverse=True)
    return FindNegativeKeywordCandidatesResponse(
        customer_id=cid,
        date_range=date_range,
        candidates=candidates,
        warnings=warnings,
    )


@mcp.tool
def audit_account_health(
    customer_id: str | None = None,
    date_range: _DateRange = "LAST_7_DAYS",
) -> AuditAccountHealthResponse:
    """Comprehensive health snapshot of a Google Ads account.

    Runs 5 checks:
    - Disapproved ads (any status DISAPPROVED)
    - Low quality scores (any keyword with quality_score < 5)
    - Budget pacing anomalies (spend > 120% or < 30% of expected)
    - Missing conversion tracking (no conversion actions configured)
    - Paused-but-still-spending (PAUSED campaigns with cost > 0 in date_range)

    Args:
        customer_id: 10-digit ID; defaults to `default_customer_id`.
        date_range: Look-back window for pacing + paused-spending checks. Default LAST_7_DAYS.

    Returns per-check status + an overall status.
    """
    cid = _resolve_customer_id(customer_id)
    checks = [
        _check_disapproved_ads(cid, date_range),
        _check_low_quality_scores(cid, date_range),
        _check_budget_pacing(cid, date_range),
        _check_conversion_tracking(cid, date_range),
        _check_paused_but_spending(cid, date_range),
    ]
    return AuditAccountHealthResponse(
        customer_id=cid,
        date_range=date_range,
        overall=_overall(checks),
        checks=checks,
    )
