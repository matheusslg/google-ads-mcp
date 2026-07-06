# google-ads-mcp

> Workflow-shaped MCP server exposing the Google Ads API to AI agents
> with built-in safety rails for mutations.

**Status**: v0.3.0 — Read + Safe Writes + Drafting. Nine read tools, five guardrailed mutation tools with universal `dry_run` support, plus three drafting tools (`draft_campaign_csv`, `draft_responsive_search_ad`, `dry_run_changes` multi-step preview). See [open issues](https://github.com/matheusslg/google-ads-mcp/issues) for the roadmap (Phase 3 v1.0.0 hardening next).

## Install

```bash
uvx google-ads-mcp
```

## Setup (first-time only)

Before Claude Desktop can connect, run the setup wizard once:

```bash
uvx google-ads-mcp setup
```

The wizard:
1. Prints the Google Cloud Console steps to create an OAuth 2.0 client (Desktop application type)
2. Prompts for your developer token (from <https://ads.google.com/aw/apicenter>)
3. Prompts for the path to your downloaded `client_secrets.json`
4. Prompts for your Manager (MCC) ID and the default Google Ads account ID
5. Opens a browser tab for OAuth consent
6. Saves credentials to `~/.config/google-ads-mcp/credentials.json` (mode 0600)

See [`docs/developer-token.md`](docs/developer-token.md) for the full Google Cloud Console walkthrough.

## Claude Desktop config

Add to `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) or the equivalent path:

```json
{
  "mcpServers": {
    "google-ads-mcp": {
      "command": "uvx",
      "args": ["google-ads-mcp"]
    }
  }
}
```

Once the setup wizard above has run, the server reads credentials from `~/.config/google-ads-mcp/credentials.json` automatically. No additional environment variables are required.

## Available tools (v0.1.0)

Read-only. Every tool that operates on a customer accepts `customer_id?: str` (10 digits, no dashes) — omit to use the `default_customer_id` from `credentials.json`.

**Discovery**
- `ping()` — connectivity probe; returns `{"ok": true}`.
- `list_accessible_customers()` — customer IDs the developer token can access.

**Listings** — `list_campaigns(customer_id?, status?)`, `list_ad_groups(customer_id?, campaign_id?)`, `list_keywords(customer_id?, campaign_id?, ad_group_id?)`. Return Pydantic envelopes with typed rows + a `warnings` list.

**Reporting** — `get_performance(customer_id?, date_range="LAST_7_DAYS", segment_by?)`, `list_search_terms(customer_id?, date_range="LAST_7_DAYS", min_impressions=100)`, `summarize_performance(customer_id?, date_range="LAST_7_DAYS", comparison_period?)` — the last one returns a plain-English narrative + `PeriodComparison` deltas.

**Analytical / audit** — `find_negative_keyword_candidates(customer_id?, date_range="LAST_30_DAYS", min_impressions=50, min_cost=1.0, require_zero_conversions=True)`, `audit_account_health(customer_id?, date_range="LAST_7_DAYS")` — 5-check snapshot (disapproved ads, low quality scores, budget pacing, missing conversion tracking, paused-but-still-spending).

Response payloads are capped at 10,000 rows per call; a `warnings: ["truncated at 10000 rows; refine filters to see more"]` entry is returned if the cap is hit.

**Mutations (v0.2.0+)** — see the Safety model section below. All accept `dry_run: bool = False` and return a `MutationResponse` envelope. Budget/bid updates enforce numeric guardrails and refuse over-cap requests without calling the API.

## First-call example

Once setup has run and Claude Desktop is configured:

1. Restart Claude Desktop so it picks up the MCP server.
2. Ask Claude: *"What Google Ads customer IDs do I have access to?"*
3. Claude will call `list_accessible_customers` and return your customer IDs.

Then ask *"Summarize last week's performance"* → Claude calls `summarize_performance` with `date_range="LAST_7_DAYS"` and reads the narrative back in whatever language you were chatting in.

## Safety model

Every mutation tool ships with `dry_run: bool = False` and returns a `MutationResponse` envelope: `{success, dry_run, mutation_id?, before, after, warnings}`. `dry_run=True` **never** calls the Google Ads API — it returns the projected `after` state only, giving callers (and AI agents) a preview before committing real changes.

**Mutation tools (v0.2.0)** — all read-only surface plus:

- `pause_campaign` / `enable_campaign` — no-op detection: if the campaign is already at the target state, no API call is made and a warning surfaces
- `update_campaign_budget(campaign_id, new_amount, max_increase_percent?, absolute_cap?)` — refuses (returns `success=False`, no API call) if the new amount would exceed either cap. **When both guardrails are omitted, defaults to `max_increase_percent=50`** (per PRD § Risks mitigation).
- `update_keyword_bid(ad_group_id, criterion_id, new_bid, max_bid_cap?)` — when `max_bid_cap` is omitted, defaults to `current × 1.5` (equivalent 50% ceiling). Refuses if the new bid exceeds the cap.
- `add_negative_keywords(scope, target_id, keywords, match_type?)` — pre-checks existing negatives at the target; duplicates are skipped as warnings, not errors. Batched into a single mutate call.

Refusal is signalled by `success=False` in the envelope; the `warnings` list explains why. No exceptions are raised on caller mistakes (bad IDs raise `ValueError`; auth issues raise `CredentialsRevoked`).

Universal `dry_run` contract is pinned by an automated test that fails if any future mutation tool omits the kwarg or changes the return envelope.

Contract details in [`PRD.md`](PRD.md) (Design System) and [`standards.md`](standards.md).

## Development

```bash
git clone https://github.com/matheusslg/google-ads-mcp
cd google-ads-mcp
uv sync
uv run pytest
```

## License

MIT — see [`LICENSE`](LICENSE).
