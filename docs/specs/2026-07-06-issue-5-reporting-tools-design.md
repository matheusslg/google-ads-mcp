# Design: Performance reporting tools (Issue #5)

**Date**: 2026-07-06
**Issue**: [#5 — Performance reporting tools](https://github.com/matheusslg/google-ads-mcp/issues/5)
**Status**: Approved (autonomous — per user `/goal` directive)
**Branch**: `feat/issue-5-reporting-tools`

---

## Context

Second batch of read tools: `get_performance`, `list_search_terms`, `summarize_performance`. Adds metrics aggregation, date-range filtering, and a deterministic English narrative for the summary. All built on the `_search` helper shipped in #4.

## Decisions (ponytail defaults, autonomous)

| # | Question | Choice |
|---|---|---|
| 1 | `date_range` shape | `Literal["LAST_7_DAYS", "LAST_14_DAYS", "LAST_30_DAYS", "THIS_MONTH", "LAST_MONTH"]`. GAQL constants only; no explicit start/end dates for v0.1 (add when demanded). |
| 2 | `segment_by` shape | `Literal[None, "campaign", "device", "network", "day"]`. Single-segment, optional. |
| 3 | Metrics to expose | 6 fields: `impressions`, `clicks`, `cost` (dollars, from cost_micros/1e6), `conversions`, `ctr`, `average_cpc` (dollars). Enough for weekly reports; add more when actually needed. |
| 4 | `min_impressions` default | `100`. Below is usually noise. Pass `0` to disable. |
| 5 | `comparison_period` default for `summarize_performance` | Same duration prior period — `LAST_7_DAYS` auto-compares to the 7 days before. Explicit override optional but same enum. |
| 6 | Summary narrative language | English only per PRD Open Q3 (LLM translates for the user). |
| 7 | File layout | New `src/google_ads_mcp/tools/reports.py`. Aggregations + narrative are a distinct concern from the flat listings in `reads.py`. |
| 8 | Response envelopes | Pydantic. Same pattern as #4: `{customer_id, <resource>, warnings}`. Summary adds `narrative: str`. |
| 9 | Cost math | `cost = cost_micros / 1_000_000` (dollars, float). `ctr` from proto is already 0.0–1.0. `average_cpc = cost / clicks` if clicks > 0 else 0.0. |
| 10 | Tests | Same mock strategy as #4 — `mock_google_ads_client` fixture yields programmed rows. Deterministic narrative → unit-testable string. |

## File layout

```
src/google_ads_mcp/tools/
├── reads.py          # unchanged (#4)
└── reports.py        # NEW — 3 tools + models + narrative formatter

tests/tools/
├── test_reads.py     # unchanged
└── test_reports.py   # NEW
```

## Pydantic models

```python
from typing import Literal
from pydantic import BaseModel

_DateRange = Literal["LAST_7_DAYS", "LAST_14_DAYS", "LAST_30_DAYS", "THIS_MONTH", "LAST_MONTH"]
_Segment = Literal["campaign", "device", "network", "day"]


class Metrics(BaseModel):
    impressions: int
    clicks: int
    cost: float          # dollars
    conversions: float   # can be fractional in Google Ads (attributed conversions)
    ctr: float           # 0.0-1.0
    average_cpc: float   # dollars


class PerformanceRow(BaseModel):
    """A single row of the performance report, keyed by segment if requested."""

    segment: str | None = None          # e.g. "MOBILE", "SEARCH", "2026-06-30", or campaign name
    segment_id: str | None = None       # e.g. campaign_id when segment_by='campaign'
    metrics: Metrics


class GetPerformanceResponse(BaseModel):
    customer_id: str
    date_range: _DateRange
    segment_by: _Segment | None
    rows: list[PerformanceRow]
    warnings: list[str] = []


class SearchTerm(BaseModel):
    text: str
    match_type: str      # broader than keyword match — includes NEAR_EXACT etc.
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
    delta_pct: Metrics   # per-field percentage change (current - previous) / previous


class SummarizePerformanceResponse(BaseModel):
    customer_id: str
    date_range: _DateRange
    comparison_period: _DateRange
    narrative: str
    comparison: PeriodComparison
    warnings: list[str] = []
```

## Tool signatures

```python
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
```

## GAQL templates

Aggregate performance (no segment):
```
SELECT metrics.impressions, metrics.clicks, metrics.cost_micros,
       metrics.conversions, metrics.ctr, metrics.average_cpc
FROM customer
WHERE segments.date DURING {date_range}
```

Segmented by campaign:
```
SELECT campaign.id, campaign.name, metrics.impressions, metrics.clicks,
       metrics.cost_micros, metrics.conversions, metrics.ctr, metrics.average_cpc
FROM campaign
WHERE segments.date DURING {date_range}
```

Segmented by device / network / day: FROM the segment's compatible view, or use the segments.X approach — implementer picks correct GAQL per Google's segmentation rules at scaffold time.

Search terms:
```
SELECT search_term_view.search_term, search_term_view.status,
       metrics.impressions, metrics.clicks, metrics.cost_micros,
       metrics.conversions, metrics.ctr, metrics.average_cpc,
       search_term_view.ad_group, campaign.id
FROM search_term_view
WHERE segments.date DURING {date_range}
  AND metrics.impressions >= {min_impressions}
```

## Narrative formatter

Deterministic (no LLM call). Template:

```
"{date_range_pretty}: {clicks} clicks ({clicks_delta}) at ${avg_cpc} CPC ({cpc_delta}).
Conversions: {conversions} ({conv_delta}). Spend: ${cost} ({cost_delta}).
Impressions: {impressions} ({imp_delta}). CTR: {ctr_pct}% ({ctr_delta})."
```

Where `{X_delta}` renders `+N%` / `-N%` / `flat` based on percentage change. `+N%` colored implicitly by tone — no ANSI or markdown. Numbers rendered with thousands separators.

Helper: `_format_delta(pct: float) -> str` → `"+12%"`, `"-3%"`, `"flat"` (if abs < 0.5%).

## `comparison_period` auto-derivation

```python
_PRIOR_PERIOD = {
    "LAST_7_DAYS": "LAST_7_DAYS",       # explicit prior 7 days requires GAQL date math
    ...
}
```

Wait — GAQL only has fixed date-range constants; there's no "prior LAST_7_DAYS". Solution: run TWO GAQL queries.

- Current: `WHERE segments.date DURING LAST_7_DAYS`
- Previous: `WHERE segments.date BETWEEN '{start-14}' AND '{start-8}'` — computed in Python from today.

Python date math via `datetime.date` and `timedelta`. Deterministic. The one place we materialize explicit dates in this issue.

## Error handling

Same as #4: `_search` catches `GoogleAdsException`, calls `_raise_friendly` (imported from `tools.reads`). Non-auth exceptions propagate.

## Tests

`tests/tools/test_reports.py`:

| Test | Verifies |
|---|---|
| `test_get_performance_no_segment_returns_single_row` | Mock yields 1 aggregate row → response has 1 row, `segment=None` |
| `test_get_performance_segment_by_campaign` | Mock yields 3 campaign rows → 3 rows with segment/segment_id filled |
| `test_get_performance_cost_micros_converted_to_dollars` | Row with `cost_micros=1_500_000` → `metrics.cost == 1.5` |
| `test_get_performance_uses_default_customer_id` | Called with `customer_id=None` → uses mock default |
| `test_list_search_terms_applies_min_impressions_filter` | Query includes `metrics.impressions >= 100` (or supplied value) |
| `test_list_search_terms_returns_envelope` | Rows → `SearchTerm(...)` envelope with `min_impressions` echoed |
| `test_summarize_performance_computes_deltas` | Current: 100 clicks, previous: 80 → `delta_pct.clicks == 25.0` |
| `test_summarize_performance_narrative_contains_key_metrics` | Narrative string contains "clicks", "CPC", "conversions", "spend" (case-insensitive) |
| `test_summarize_performance_uses_two_gaql_queries` | Mock's `search_stream` called twice (once for current, once for previous) |
| `test_format_delta_positive_negative_flat` | Unit test for `_format_delta` — 25.0 → "+25%", -12.3 → "-12%", 0.2 → "flat" |
| `test_summarize_performance_prior_period_dates` | Prior period computed correctly for LAST_7_DAYS given a fixed reference date |

## Out of scope (deferred)

| Not in #5 | Owned by |
|---|---|
| Explicit start/end date arguments | Future — Literal enum covers agency weekly reports; add when demanded |
| Multi-segment (e.g. campaign × device) | Future — YAGNI |
| Additional metrics (view_through_conversions, video quartile completions, etc.) | Future — add when actual users ask |
| i18n on the narrative | PRD Q3 — English only for v0.1 |
| Currency other than USD-style dollars | Future — `cost_micros` semantics vary by account currency, but display units don't; document as "account currency" |
| Ad-level performance | Future — currently metrics up to campaign/device level; ad-level would need `ad_group_ad` FROM |

## Verification at scaffold time

1. GAQL syntax for `segments.date DURING {enum}` — validate with a real query if possible.
2. `metrics.cost_micros` type in proto — int64, safe to divide by 1_000_000 as int/float.
3. Confirm `search_term_view.search_term`, `search_term_view.status`, `search_term_view.ad_group` are the right field paths.
4. Confirm segment_by BY DEVICE / NETWORK / DAY GAQL syntax — may need `segments.device`, `segments.network`, `segments.date` in SELECT + implicit group by.

## Acceptance criteria mapping (issue #5)

| Criterion | Satisfied by |
|---|---|
| All three tools implemented with date_range + optional-arg handling | `get_performance`, `list_search_terms`, `summarize_performance` |
| `summarize_performance` returns narrative + structured deltas | `SummarizePerformanceResponse` shape |
| Language decision per PRD Q3 | English only (LLM translates); code comment where i18n would plug in |
| Unit tests + integration smoke | 11 unit tests; smoke deferred to #7 |

---

*Autonomous per `/goal`. Ponytail defaults throughout.*
