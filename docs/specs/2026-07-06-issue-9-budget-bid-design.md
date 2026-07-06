# Design: Budget & bid mutations with guardrails (Issue #9)

**Date**: 2026-07-06
**Issue**: [#9 — update_campaign_budget, update_keyword_bid](https://github.com/matheusslg/google-ads-mcp/issues/9)
**Branch**: `feat/issue-9-budget-bid-guardrails`

---

## Context

Highest-stakes mutations in Phase 1. Real money moves on approval. Guardrails are the safety story.

## Decisions

| # | Question | Choice |
|---|---|---|
| 1 | Amount units in the API | **Dollars (float)** for caller; converted to micros (`× 1_000_000`) internally. Callers never see `_micros` fields. |
| 2 | Guardrail semantics | `max_increase_percent`: refuse if `(new-current)/current × 100 > cap`. Only applies to **increases**. `absolute_cap`: refuse if `new > cap`. Independent — both can be set; either can refuse. |
| 3 | Default guardrail (both omitted) | `max_increase_percent = 50` (PRD line 181). |
| 4 | Refusal behavior | Return `MutationResponse(success=False, warnings=["<reason>"])`. No API call. Not an exception. |
| 5 | Zero-current-amount edge case | If current amount == 0 (rare — placeholder budgets), skip the `max_increase_percent` check (division by zero); apply `absolute_cap` normally. Add warning: `"current amount is 0; max_increase_percent skipped"`. |
| 6 | Decrease behavior | Always allowed. `max_increase_percent` doesn't apply. `absolute_cap` still applies (defensive: what if user sets an odd cap). |
| 7 | Bid tool signature | `update_keyword_bid(customer_id?, ad_group_id, criterion_id, new_bid, max_bid_cap?, dry_run=False)`. Both `ad_group_id` + `criterion_id` required — keyword IDs are only unique within an ad group. |
| 8 | Bid default cap | Same as budget: `max_bid_cap` unset AND `max_increase_percent` unset → default `max_increase_percent=50` applied. Actually — bids don't have a `max_increase_percent` parameter per the PRD (line 74). Just `max_bid_cap`. **When omitted, we default `max_bid_cap` to `current_bid × 1.5` (50% increase ceiling)** — same safety story, different mechanic. |
| 9 | File | Append to existing `src/google_ads_mcp/tools/mutations.py`. |

## Tool signatures

```python
@mcp.tool
def update_campaign_budget(
    campaign_id: str,
    new_amount: float,                        # dollars
    customer_id: str | None = None,
    max_increase_percent: float | None = None,
    absolute_cap: float | None = None,        # dollars
    dry_run: bool = False,
) -> MutationResponse:
    """Update a campaign's daily budget with mandatory guardrails.

    If both max_increase_percent and absolute_cap are omitted, defaults to
    max_increase_percent=50 (per PRD § Risks mitigation). Refuses (returns
    success=False, no API call) if the new amount would exceed any active cap.
    """

@mcp.tool
def update_keyword_bid(
    ad_group_id: str,
    criterion_id: str,
    new_bid: float,                           # dollars
    customer_id: str | None = None,
    max_bid_cap: float | None = None,         # dollars
    dry_run: bool = False,
) -> MutationResponse:
    """Update a keyword's max CPC bid with an absolute cap guardrail.

    If max_bid_cap is omitted, defaults to current_bid × 1.5 (50% ceiling).
    """
```

## Guardrail logic (shared helper)

```python
def _check_guardrails(
    current_dollars: float,
    new_dollars: float,
    *,
    max_increase_percent: float | None,
    absolute_cap: float | None,
) -> tuple[bool, list[str]]:
    """Return (allowed, warnings). warnings always populated; if not allowed, includes reason(s)."""
    warnings = []
    allowed = True

    # Default cap
    if max_increase_percent is None and absolute_cap is None:
        max_increase_percent = 50.0
        warnings.append("default max_increase_percent=50 applied (no explicit cap supplied)")

    # Absolute cap
    if absolute_cap is not None and new_dollars > absolute_cap:
        allowed = False
        warnings.append(f"new amount ${new_dollars:.2f} exceeds absolute_cap ${absolute_cap:.2f}")

    # Percent cap — only on increases, guard against zero current
    if max_increase_percent is not None and new_dollars > current_dollars:
        if current_dollars == 0:
            warnings.append("current amount is 0; max_increase_percent skipped")
        else:
            delta_pct = (new_dollars - current_dollars) / current_dollars * 100
            if delta_pct > max_increase_percent:
                allowed = False
                warnings.append(
                    f"increase +{delta_pct:.1f}% exceeds max_increase_percent {max_increase_percent}% "
                    f"(current ${current_dollars:.2f} → new ${new_dollars:.2f})"
                )

    return allowed, warnings
```

## Flow — `update_campaign_budget`

1. Resolve `customer_id`.
2. Fetch current budget resource + amount:
   ```
   SELECT campaign.id, campaign_budget.id, campaign_budget.amount_micros
   FROM campaign WHERE campaign.id = {campaign_id}
   ```
   Not-found → `ValueError`. Empty budget row → `ValueError("campaign has no budget attached")`.
3. `current_dollars = amount_micros / 1_000_000`.
4. `allowed, warnings = _check_guardrails(current_dollars, new_amount, max_increase_percent=..., absolute_cap=...)`.
5. If not allowed: return `MutationResponse(success=False, dry_run=dry_run, before={"amount": f"${current_dollars:.2f}"}, after={"amount": f"${new_amount:.2f}"}, warnings=warnings)`.
6. `before = {"amount_micros": str(current_micros), "amount": f"${current_dollars:.2f}"}`.
7. If `dry_run=True`: return with `success=True, dry_run=True, before, after, warnings`.
8. Real mutation: `CampaignBudgetService.mutate_campaign_budgets` — UPDATE operation on `campaign_budget.amount_micros = int(new_amount * 1_000_000)`; `update_mask.paths.append("amount_micros")`.
9. Return `success=True, dry_run=False, mutation_id=<budget resource name>, before, after, warnings`.

## Flow — `update_keyword_bid`

1. Resolve `customer_id`.
2. Fetch current bid:
   ```
   SELECT ad_group_criterion.criterion_id, ad_group_criterion.cpc_bid_micros
   FROM ad_group_criterion
   WHERE ad_group_criterion.ad_group = 'customers/{cid}/adGroups/{ad_group_id}'
     AND ad_group_criterion.criterion_id = {criterion_id}
   ```
   Not-found → `ValueError`.
3. `current_dollars = cpc_bid_micros / 1_000_000`. If `cpc_bid_micros == 0` or unset → treat as 0 (still allow via zero-current path).
4. Compute effective cap: `effective_cap = max_bid_cap if max_bid_cap is not None else current_dollars * 1.5`.
   Warning if defaulted: `"default max_bid_cap=${effective_cap:.2f} (current × 1.5) applied"`.
5. If `new_bid > effective_cap`: refuse with warning naming the cap.
6. Same dry_run + mutate flow: `AdGroupCriterionService.mutate_ad_group_criteria` with `cpc_bid_micros` update.

## `MutationResponse.before` / `.after` shape

For both tools: `{"amount": "$50.00", "amount_micros": "50000000"}` (or `{"bid": "$1.20", "bid_micros": "1200000"}`). Two keys so callers can pick the format they prefer.

## Tests

`tests/tools/test_mutations.py` — append ~14 tests:

**Budget (8):**
- `test_update_budget_default_cap_applied_when_both_omitted` — warnings contains "default max_increase_percent=50"
- `test_update_budget_over_percent_refused` — current $50, new $80 (+60%), default cap → success=False, no mutate call
- `test_update_budget_within_percent_allowed` — current $50, new $60 (+20%), default → success=True
- `test_update_budget_absolute_cap_refused` — absolute_cap=$100, new=$150 → refuse
- `test_update_budget_decrease_always_allowed` — current $100, new $10 → success (default percent doesn't apply)
- `test_update_budget_zero_current_skips_percent` — current $0, new $50 → success + warning about zero
- `test_update_budget_dry_run_no_mutation_call` — mutate_campaign_budgets NOT called
- `test_update_budget_real_mutation_uses_correct_micros` — mutate called with amount_micros=int(50*1e6)

**Bid (6):**
- `test_update_bid_default_cap_applied_when_omitted` — warnings mentions "current × 1.5"
- `test_update_bid_over_absolute_cap_refused` — max_bid_cap=$1.00, new=$2.00 → refuse
- `test_update_bid_within_cap_allowed` — under cap → success
- `test_update_bid_dry_run_no_mutation_call` → mutate_ad_group_criteria not called
- `test_update_bid_real_mutation_uses_correct_micros` — cpc_bid_micros=int(new * 1e6)
- `test_update_bid_current_zero_uses_new_as_baseline` — current 0, cap unset → default cap = 0 × 1.5 = 0; refuse with clear warning

Plus a shared:
- `test_check_guardrails_helper_all_paths` — pure unit test on the helper

## Out of scope

- Bid strategy switches (PRD non-goal line 47)
- Portfolio bid strategies
- Bulk budget updates (single-target for v0.1)
- Currency conversion (assume account currency)

## Acceptance criteria

| Criterion | Met by |
|---|---|
| Both tools refuse over-cap | Guardrail helper + refusal path |
| Default max_increase_percent=50 | Applied when both omitted; warning surfaces it |
| dry_run=True returns preview without commit | Explicit branch in each tool |
| Tests cover under/over-cap/dry_run/default | 14+ tests above |
| README safety section | Deferred to #11 (per PRD; #11 wraps Phase 1 with safety docs) |

---

*Autonomous per `/goal`.*
