# Design: Negative keyword management (Issue #10)

**Date**: 2026-07-06
**Issue**: [#10 — add_negative_keywords](https://github.com/matheusslg/google-ads-mcp/issues/10)
**Branch**: `feat/issue-10-negative-keywords`

---

## Decisions (ponytail)

| # | Choice |
|---|---|
| 1 | Scope shape | `scope: Literal["campaign", "ad_group"]` + `target_id: str` (dispatches to different SDK service) |
| 2 | Keywords batching | Accept `keywords: list[str]` — send as N operations in one mutate call; SDK batches |
| 3 | Match type | `match_type: Literal["EXACT", "PHRASE", "BROAD"] = "EXACT"` — one type per call; if a caller needs mixed types, they call twice |
| 4 | Duplicate handling | Pre-check via GAQL: fetch existing negative keywords at that scope; skip duplicates and add them as warnings. Not an error. |
| 5 | `dry_run` | Same envelope pattern as #8/#9 — no API call on dry_run; `after` shows what would be added |
| 6 | Response `after` | `{"added_count": str(N), "skipped_count": str(M), "keywords_added": "kw1, kw2, ..."}` |
| 7 | Bulk failure | If SDK partial-fails, still return `success=True` with mutation_id + warnings for the failures. If SDK totally fails, propagate via `_raise_friendly` |

## Signature

```python
@mcp.tool
def add_negative_keywords(
    scope: Literal["campaign", "ad_group"],
    target_id: str,
    keywords: list[str],
    customer_id: str | None = None,
    match_type: Literal["EXACT", "PHRASE", "BROAD"] = "EXACT",
    dry_run: bool = False,
) -> MutationResponse:
    """Add negative keywords at a campaign or ad_group scope.

    Args:
        scope: Where the negatives live. "campaign" applies globally to the campaign;
               "ad_group" applies only within that ad group.
        target_id: campaign_id or ad_group_id depending on scope.
        keywords: List of keyword texts (case-insensitive; Google normalizes).
        match_type: EXACT, PHRASE, or BROAD. Applied to all keywords in this call.
        dry_run: When True, preview what would be added without calling the API.

    Returns MutationResponse with counts + list of added/skipped keywords in `after`.
    Existing negatives at that scope are skipped (surfaced as warnings, not errors).
    """
```

## Flow

1. Resolve `customer_id`. Validate `scope` value.
2. Fetch existing negatives at the target:
   - **campaign scope**:
     ```
     SELECT campaign_criterion.keyword.text, campaign_criterion.keyword.match_type
     FROM campaign_criterion
     WHERE campaign.id = {target_id} AND campaign_criterion.negative = TRUE
       AND campaign_criterion.type = 'KEYWORD'
     ```
   - **ad_group scope**: `FROM ad_group_criterion WHERE ad_group_criterion.ad_group = 'customers/{cid}/adGroups/{target_id}' AND ad_group_criterion.negative = TRUE AND ad_group_criterion.type = 'KEYWORD'`
3. Build set of existing `(text, match_type)` tuples.
4. Filter input keywords: dedupe within the input; classify each as "will_add" or "already_exists" (compared against fetched set + match_type).
5. If `dry_run`: return `success=True, dry_run=True, before={"existing_count": ...}, after={"would_add": ..., "would_skip": ...}, warnings=[per-skip messages]`.
6. Real path: build N `CampaignCriterion` or `AdGroupCriterion` UPDATE-with-create ops (`op.create = criterion`).
7. Call `mutate_campaign_criteria` or `mutate_ad_group_criteria`. Extract resource names from results.
8. Return `success=True, mutation_id=<first-resource-name-or-comma-list>, before, after, warnings`.

## SDK snippets

**Campaign scope create op:**
```python
crit = client.get_type("CampaignCriterion")
crit.campaign = f"customers/{cid}/campaigns/{target_id}"
crit.negative = True
crit.keyword.text = kw_text
crit.keyword.match_type = client.enums.KeywordMatchTypeEnum[match_type]
op = client.get_type("CampaignCriterionOperation")
op.create = crit
```

**Ad group scope create op:**
```python
crit = client.get_type("AdGroupCriterion")
crit.ad_group = f"customers/{cid}/adGroups/{target_id}"
crit.negative = True
crit.keyword.text = kw_text
crit.keyword.match_type = client.enums.KeywordMatchTypeEnum[match_type]
op = client.get_type("AdGroupCriterionOperation")
op.create = crit
```

Then `service.mutate_campaign_criteria(customer_id=cid, operations=[op1, op2, ...])` (or `mutate_ad_group_criteria`).

`mutation_id` in the response: join the resource names as a comma-separated string, since we may have created N. Alternative: return `after["mutation_ids"] = "rn1, rn2, ..."` and keep the top-level `mutation_id` as the first one. Choose the latter — top-level `mutation_id` stays a single ID (first resource); full list in `after`.

## Tests (`test_mutations.py` append)

10 tests:
- `test_add_negative_keywords_ad_group_scope_dry_run` — mutate NOT called; `after.would_add` count matches
- `test_add_negative_keywords_campaign_scope_dry_run` — same for campaign scope
- `test_add_negative_keywords_real_mutation_ad_group` — mutate_ad_group_criteria called with N ops
- `test_add_negative_keywords_real_mutation_campaign` — mutate_campaign_criteria called
- `test_add_negative_keywords_skips_duplicates` — existing has "shoes/EXACT"; input includes "shoes"; warnings mention skip
- `test_add_negative_keywords_dedupes_input` — input has "shoes, shoes, boots" → only 2 unique
- `test_add_negative_keywords_match_type_broad` — GAQL/op uses BROAD enum
- `test_add_negative_keywords_invalid_scope_raises` — `scope="invalid"` → ValueError
- `test_add_negative_keywords_empty_input_returns_success_no_op` — empty list → success + no mutate call
- `test_add_negative_keywords_authentication_error_bubbles` — auth error from _search → CredentialsRevoked

## Out of scope

- Match-type mixing in one call (deferred — caller can invoke twice)
- Removing negatives (not in acceptance criteria)
- Copying negative lists between accounts

---

*Autonomous per `/goal`.*
