# Smoke-Test Playbook

Run before every release tag. Validates that the shipped tools actually work against a real Google Ads account.

## Prerequisites

- Basic Access developer token (or Test Account tier — sufficient for read tools)
- A Google Cloud OAuth 2.0 Desktop client (`client_secret_*.json`)
- Setup wizard already run: `~/.config/google-ads-mcp/credentials.json` exists at mode 0600
- Local checkout at the tag being tested

## Step 1 — Read surface

```bash
uv run python scripts/smoke_v0_1_0.py
```

Expected: 9/9 tools OK. Non-zero counts across `list_campaigns`, `list_ad_groups`, `list_keywords`. `audit_account_health` returns a specific overall status.

If failures:

| Symptom | Likely cause | Fix |
|---|---|---|
| `CredentialsNotFound` | No setup run | `uv run google-ads-mcp setup` |
| `CredentialsRevoked: authentication_error` | Refresh token invalid | Re-run setup; Google may have expired the grant |
| `GoogleAdsException: user doesn't have permission` | `login_customer_id` doesn't route to the target | Edit `credentials.json` to set `login_customer_id = default_customer_id` if the account isn't under an MCC hierarchy |
| `ModuleNotFoundError: v24` / `v17` | google-ads library too old | Check `pyproject.toml` pin; API versions v24/v23/v22/v21 are supported by google-ads 31.x |

## Step 2 — Mutation dry-runs (safe: never touches the API)

From a Python REPL or a small script:

```python
from google_ads_mcp.tools.mutations import (
    pause_campaign, enable_campaign, update_campaign_budget,
    update_keyword_bid, add_negative_keywords, dry_run_changes, ChangeSetItem,
)
from google_ads_mcp.tools.reads import list_campaigns

# Pick a real campaign
cid = list_campaigns().campaigns[0].id

# Each of these must NOT hit mutate_* on the real API
print(pause_campaign(campaign_id=cid, dry_run=True))
print(enable_campaign(campaign_id=cid, dry_run=True))
print(update_campaign_budget(campaign_id=cid, new_amount=1.00, dry_run=True))
```

Expected: every response has `dry_run=True, mutation_id=None, success=True`. `before` shows current state; `after` shows projected state.

## Step 3 — Multi-step preview

```python
change_set = [
    ChangeSetItem(tool="pause_campaign", args={"campaign_id": cid}),
    ChangeSetItem(tool="update_campaign_budget", args={"campaign_id": cid, "new_amount": 5.00}),
]
resp = dry_run_changes(change_set)
assert resp.total_items == 2
assert resp.any_refused is False
```

## Step 4 — Guardrail refusal (safety proof)

```python
# Try an over-cap budget: should refuse without calling the API
resp = update_campaign_budget(campaign_id=cid, new_amount=10_000.00, dry_run=True)
assert resp.success is False
assert "exceeds" in " ".join(resp.warnings)
```

## Step 5 — Drafting tools (no API)

```python
from google_ads_mcp.tools.drafts import (
    draft_campaign_csv, draft_responsive_search_ad,
    CampaignDraftSpec, AdGroupDraftSpec, KeywordDraftSpec,
)

spec = CampaignDraftSpec(
    campaign_name="Smoke Test",
    daily_budget=10.0,
    ad_groups=[AdGroupDraftSpec(name="AG1", max_cpc=1.0, keywords=[KeywordDraftSpec(text="test")])],
)
csv = draft_campaign_csv(spec)
assert csv.row_count == 3  # campaign + ad group + keyword
assert "Row Type" in csv.csv_content

rsa = draft_responsive_search_ad(product_description="handmade boots", target_audience="hikers")
assert len(rsa.headlines) == 15
assert all(len(h) <= 30 for h in rsa.headlines)
assert len(rsa.descriptions) == 4
assert all(len(d) <= 90 for d in rsa.descriptions)
```

## Step 6 — Gate check

```bash
uv sync
uv run pytest -v
uv run ruff check .
uv run ruff format --check .
uv run mypy src tests
```

All must exit 0. If any fail, do NOT tag the release.

## Sign-off checklist

- [ ] Step 1: 9/9 read tools OK
- [ ] Step 2: mutation dry-runs succeed without API calls
- [ ] Step 3: `dry_run_changes` aggregates correctly
- [ ] Step 4: guardrail refusal proves the safety story
- [ ] Step 5: drafting tools produce valid output within char limits
- [ ] Step 6: all local gates green

When all six ✅, tag and publish the release.
