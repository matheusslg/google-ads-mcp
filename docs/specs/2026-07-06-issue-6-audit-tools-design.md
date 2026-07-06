# Design: Analytical / audit tools (Issue #6)

**Date**: 2026-07-06
**Issue**: [#6 — Analytical / audit tools](https://github.com/matheusslg/google-ads-mcp/issues/6)
**Status**: Approved (autonomous — per user `/goal`)
**Branch**: `feat/issue-6-audit-tools`

---

## Context

Last read-only tools before the v0.1.0 release cut. These are workflow-shaped (not raw API wrappers) and represent the core differentiator vs Google's official MCP:

- `find_negative_keyword_candidates(customer_id, criteria)` — ranked candidates with reasoning
- `audit_account_health(customer_id)` — comprehensive snapshot: disapproved ads, low quality scores, budget-pacing anomalies, missing conversion tracking, paused-but-still-spending

Both are read-only. Both use `_search` from `tools/reads.py`. Both return Pydantic envelopes.

## Decisions (ponytail defaults)

| # | Question | Choice |
|---|---|---|
| 1 | `criteria` shape for negative keywords | Individual keyword args (`min_impressions`, `max_cost`, `min_cost`, `date_range`) — not a nested Pydantic input model. Fewer names, flatter tool schema. |
| 2 | Ranking for negative keyword candidates | Descending by `cost` (dollars wasted). Simple, defensible. |
| 3 | `audit_account_health` argument surface | Just `customer_id` + `date_range` (for the pacing + paused-spending checks). No configurable thresholds in v0.1. |
| 4 | Overall health status | `Literal["OK", "WARNING", "CRITICAL"]`. WARNING if any check ≥ WARNING; CRITICAL if any check CRITICAL. |
| 5 | File layout | New `src/google_ads_mcp/tools/audits.py`. |
| 6 | Test strategy | Same mock pattern as #4/#5. Each check function unit-testable. |
| 7 | Date range for audit | Optional; default `LAST_7_DAYS`. |
| 8 | Thresholds (hardcoded for v0.1) | Low quality score: `< 5` (out of 10). Pacing anomaly: `> 120%` or `< 30%` of expected daily budget × days elapsed. Paused-but-spending: `cost > 0` in `LAST_7_DAYS` while `status == PAUSED`. |
| 9 | `find_negative_keyword_candidates` defaults | `date_range="LAST_30_DAYS"` (need meaningful data), `min_impressions=50`, `min_cost=1.0` (dollars), `require_zero_conversions=True`. Configurable per call. |

## Pydantic models

```python
from typing import Literal
from pydantic import BaseModel

_DateRange = Literal["LAST_7_DAYS", "LAST_14_DAYS", "LAST_30_DAYS", "THIS_MONTH", "LAST_MONTH"]
_CheckStatus = Literal["OK", "WARNING", "CRITICAL"]


class NegativeKeywordCandidate(BaseModel):
    search_term: str
    impressions: int
    clicks: int
    cost: float
    conversions: float
    campaign_id: str
    ad_group_id: str
    reasoning: str  # e.g. "$5.42 spent across 234 impressions, 0 conversions"


class FindNegativeKeywordCandidatesResponse(BaseModel):
    customer_id: str
    date_range: _DateRange
    candidates: list[NegativeKeywordCandidate]  # ranked by cost desc
    warnings: list[str] = []


class HealthCheck(BaseModel):
    name: str                     # e.g. "disapproved_ads"
    status: _CheckStatus
    summary: str                  # one-line description
    details: list[str] = []       # supporting items (e.g. list of disapproved ad IDs)


class AuditAccountHealthResponse(BaseModel):
    customer_id: str
    date_range: _DateRange
    overall: _CheckStatus
    checks: list[HealthCheck]
    warnings: list[str] = []
```

## Tool signatures

```python
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
```

## Check implementations (audit)

Each check is a helper `_check_<name>(customer_id: str, date_range: _DateRange) -> HealthCheck`.

### `_check_disapproved_ads`

```
SELECT ad_group_ad.ad.id, ad_group_ad.status, ad_group_ad.policy_summary.approval_status
FROM ad_group_ad
WHERE ad_group_ad.policy_summary.approval_status = 'DISAPPROVED'
```

Status: OK if 0 rows, WARNING if 1-5, CRITICAL if > 5.

### `_check_low_quality_scores`

```
SELECT ad_group_criterion.criterion_id, ad_group_criterion.quality_info.quality_score
FROM keyword_view
WHERE ad_group_criterion.quality_info.quality_score < 5
  AND ad_group_criterion.status = 'ENABLED'
```

Status: OK if 0, WARNING if 1-10, CRITICAL if > 10.

### `_check_budget_pacing`

```
SELECT campaign_budget.amount_micros, campaign_budget.total_amount_micros,
       metrics.cost_micros, campaign.id, campaign.name
FROM campaign
WHERE campaign.status = 'ENABLED' AND segments.date DURING {date_range}
```

Aggregate per campaign; compare actual cost to expected (daily_budget × days_in_range).

- WARNING if any campaign > 120% or < 30% of expected
- CRITICAL if any campaign > 200%

`days_in_range`: 7 for LAST_7_DAYS, 14 for LAST_14_DAYS, 30 for LAST_30_DAYS, etc. Same mapping as `_compute_prior_period` (share the helper from reports.py or duplicate the map).

### `_check_conversion_tracking`

```
SELECT conversion_action.id, conversion_action.name, conversion_action.status
FROM conversion_action
WHERE conversion_action.status = 'ENABLED'
```

Status: OK if ≥ 1 enabled, CRITICAL if 0.

### `_check_paused_but_spending`

```
SELECT campaign.id, campaign.name, campaign.status, metrics.cost_micros
FROM campaign
WHERE campaign.status = 'PAUSED' AND segments.date DURING {date_range}
```

Filter in Python for cost > 0 (GAQL can filter but pattern is same). Status: OK if 0, WARNING if any.

### Overall status computation

```python
def _overall(checks: list[HealthCheck]) -> _CheckStatus:
    if any(c.status == "CRITICAL" for c in checks):
        return "CRITICAL"
    if any(c.status == "WARNING" for c in checks):
        return "WARNING"
    return "OK"
```

## `find_negative_keyword_candidates` implementation

GAQL:
```
SELECT search_term_view.search_term,
       metrics.impressions, metrics.clicks, metrics.cost_micros, metrics.conversions,
       search_term_view.ad_group, campaign.id
FROM search_term_view
WHERE segments.date DURING {date_range}
  AND metrics.impressions >= {min_impressions}
  AND metrics.cost_micros >= {min_cost * 1_000_000}
  AND metrics.conversions = 0   -- only if require_zero_conversions
```

Order by `metrics.cost_micros DESC` in GAQL.

Extract campaign_id + ad_group_id from resource names. Build `reasoning` string:
`f"${cost:.2f} spent across {impressions:,} impressions, {conversions:.1f} conversions"`

## Reuse notes

- Import `_search`, `_resolve_customer_id`, `_raise_friendly` from `.reads`.
- Import `Metrics` conversion helpers if needed; more likely just do the cost_micros/1e6 inline (it's one line per site).
- Import `_DateRange` and `_PERIOD_DAYS` from `.reports` if the pacing helper needs the day-count map. Otherwise duplicate the 5-entry dict — ponytail says fewer files, but not fewer lines.

Preference: import `_DateRange` and add a public `PERIOD_DAYS: dict[_DateRange, int]` to `reports.py` if not already there — a shared constant, not an abstraction.

## Tests (`tests/tools/test_audits.py`)

10-12 tests covering:

| Test | Verifies |
|---|---|
| `test_find_negative_keyword_candidates_ranks_by_cost_desc` | Mock yields 3 rows with mixed costs; result is descending |
| `test_find_negative_keyword_candidates_reasoning_string` | Reasoning includes cost, impressions, conversions |
| `test_find_negative_keyword_candidates_falls_back_to_default_customer_id` | No customer_id → uses default |
| `test_find_negative_keyword_candidates_zero_conversions_flag_toggles_where_clause` | When False, WHERE has no conversions=0 predicate |
| `test_check_disapproved_ads_ok_when_no_rows` | Mock: 0 rows → OK |
| `test_check_disapproved_ads_warning_1_to_5` | Mock: 3 rows → WARNING; details lists 3 IDs |
| `test_check_disapproved_ads_critical_above_5` | Mock: 6 rows → CRITICAL |
| `test_check_low_quality_scores_thresholds` | Mock: 0, 5, 11 rows across 3 test runs → OK, WARNING, CRITICAL |
| `test_check_conversion_tracking_critical_when_empty` | Mock: 0 rows → CRITICAL |
| `test_check_conversion_tracking_ok_when_any_enabled` | Mock: 1 row → OK |
| `test_check_paused_but_spending_flags_cost_gt_zero` | Mock: 2 paused campaigns, one with cost 5.0, one with 0 → WARNING with 1 detail |
| `test_audit_overall_computed_from_worst_check` | Handcrafted list: [OK, WARNING, CRITICAL] → CRITICAL; [OK, OK] → OK |

## Out of scope

| Deferred | Owned by |
|---|---|
| Configurable thresholds on audit | Future |
| Additional health checks (e.g. mobile bid modifier gaps, broken URLs) | Future |
| Automatic action (add negative keyword, pause campaign) | Phase 1 (#8-#11) |
| Historical health trends | Future |
| Weighted / composite ranking for negative candidates | Future |

## Verification at scaffold

1. `ad_group_ad.policy_summary.approval_status` — verify enum name in installed google-ads v17 proto.
2. `ad_group_criterion.quality_info.quality_score` — confirm field path.
3. `conversion_action.status` enum values (`ENABLED` / `REMOVED` / `HIDDEN`).
4. `campaign_budget.amount_micros` — for daily budget on non-lifetime campaigns.

## Acceptance criteria mapping (issue #6)

| Criterion | Satisfied by |
|---|---|
| `find_negative_keyword_candidates` returns ranked candidates with reasoning | Tool sorts by cost desc, embeds English reasoning string per row |
| `audit_account_health` covers 5 PRD checks | 5 `_check_*` functions per PRD line 65 |
| Thresholds documented and tunable | Hardcoded thresholds are documented in the docstring and this spec; tunability deferred (documented in Out of Scope) |
| Unit tests with synthetic edge-case fixtures | 12 tests above, edge cases exercised via row count thresholds |
| Smoke test | Deferred to #7 |

---

*Autonomous per `/goal`.*
