# Design: Campaign state mutations (Issue #8)

**Date**: 2026-07-06
**Issue**: [#8 — pause_campaign, enable_campaign](https://github.com/matheusslg/google-ads-mcp/issues/8)
**Status**: Approved (autonomous — `/goal`)
**Branch**: `feat/issue-8-campaign-state`

---

## Context

First mutation tools. Establishes the mutation-envelope pattern (PRD line 121) + the `dry_run: bool = False` contract (PRD line 120) that #9 and #10 reuse.

## Decisions

| # | Question | Choice |
|---|---|---|
| 1 | Envelope shape | Shared `MutationResponse` Pydantic base class in a new `tools/mutations.py` module. All future mutations subclass or return it. Fields: `success: bool, mutation_id: str \| None, before: dict, after: dict, warnings: list[str], dry_run: bool`. |
| 2 | `dry_run` default | `False`. Kwarg-only-friendly via ordinary keyword arg (`dry_run: bool = False`) — no decorator magic. |
| 3 | `mutation_id` on dry_run | `None`. Only present when a real API call happened. |
| 4 | `before` / `after` shape | `dict[str, str]` — thin. For state changes: `{"status": "ENABLED"}` → `{"status": "PAUSED"}`. Callers can inspect the field-level diff. |
| 5 | Empty-mutation case | If current state == target state (e.g. `pause_campaign` on an already-PAUSED campaign), return `success=True` with `before == after` and a warning `"campaign is already PAUSED; no-op"`. No API call made. |
| 6 | `reason` param on `pause_campaign` | Accept as `reason: str \| None = None`, stored in `warnings` for audit trail. Not passed to the SDK (Google Ads API doesn't take a reason on state change). |
| 7 | File layout | New `src/google_ads_mcp/tools/mutations.py` — envelope + first two tools. #9, #10 append to this file. When it grows > 300 lines, split. |
| 8 | Testing | Mock at `get_google_ads_client()` level (same fixture). Test dry_run path (no API call made), real mutation (mock returns success), no-op (current==target). |

## `MutationResponse` (shared base)

```python
from pydantic import BaseModel

class MutationResponse(BaseModel):
    success: bool
    dry_run: bool = False
    mutation_id: str | None = None      # resource name if real mutation happened
    before: dict[str, str] = {}
    after: dict[str, str] = {}
    warnings: list[str] = []
```

## Tool signatures

```python
@mcp.tool
def pause_campaign(
    campaign_id: str,
    customer_id: str | None = None,
    dry_run: bool = False,
    reason: str | None = None,
) -> MutationResponse: ...

@mcp.tool
def enable_campaign(
    campaign_id: str,
    customer_id: str | None = None,
    dry_run: bool = False,
) -> MutationResponse: ...
```

## Flow (both tools)

1. Resolve `customer_id`.
2. Fetch current status: `SELECT campaign.status FROM campaign WHERE campaign.id = {campaign_id}` (via `_search`).
3. If already at target state → return `success=True`, `before == after`, warning `"already X; no-op"`.
4. Build `before = {"status": current}`.
5. If `dry_run=True`: return `success=True, dry_run=True, before, after={"status": target}, warnings=[]` (plus reason echo if given).
6. Else: `CampaignService.mutate_campaigns` with a single UPDATE operation (`campaign.status` field, `update_mask={"status"}`). Extract `mutation_id` (resource name) from response.
7. Return `success=True, dry_run=False, mutation_id, before, after={"status": target}, warnings=[reason] if reason`.

## GAQL for status fetch

```
SELECT campaign.id, campaign.status
FROM campaign
WHERE campaign.id = {campaign_id}
```

Empty result → raise `ValueError(f"campaign {campaign_id} not found")`. Not a `GoogleAdsException`; a normal caller mistake.

## Error handling

- `CampaignService.mutate_campaigns` raises `GoogleAdsException` on failure → hits `_raise_friendly` (already exists in `.reads`); auth errors → `CredentialsRevoked`, otherwise propagate.
- Guardrail refusal: NONE for state changes — no delta/threshold applies. That's #9's world.

## Tests

`tests/tools/test_mutations.py` — ~10 tests:

| Test | Verifies |
|---|---|
| `test_pause_campaign_dry_run_makes_no_mutation_call` | `mutate_campaigns` NOT called; envelope has `dry_run=True`, `mutation_id=None`, correct before/after |
| `test_pause_campaign_real_mutation_calls_sdk` | `mutate_campaigns` called once with correct operation; envelope has `mutation_id`, `dry_run=False` |
| `test_pause_campaign_no_op_when_already_paused` | Current status = PAUSED; no `mutate_campaigns` call; warning `"already PAUSED; no-op"` |
| `test_pause_campaign_reason_appears_in_warnings` | `reason="testing"` passed; warnings contains `"reason: testing"` |
| `test_pause_campaign_raises_when_campaign_not_found` | `_search` returns empty → `ValueError` |
| `test_enable_campaign_dry_run` | Same as pause but for enable path |
| `test_enable_campaign_real_mutation` | ditto |
| `test_enable_campaign_no_op_when_already_enabled` | ditto |
| `test_mutation_response_shape_has_all_fields` | Pydantic model has success/dry_run/mutation_id/before/after/warnings |
| `test_pause_campaign_authentication_error_maps_to_credentials_revoked` | Auth error path still routes through `_raise_friendly` |

## Out of scope

- Bulk state changes (multiple campaigns in one call)
- Ad-group / ad state changes
- Campaign creation
- Confirmation prompts (that's an MCP-client concern, not a tool concern)

## Acceptance criteria

| Criterion | Met by |
|---|---|
| Both tools accept `dry_run: bool = False` | Signatures |
| Output shape matches PRD line 121 | `MutationResponse` fields |
| Confirmation pattern documented | Docstrings note: "callers should confirm before setting dry_run=False" |
| Tests cover dry-run, real, no-op | 10 tests above |

---

*Autonomous per `/goal`.*
