# google-ads-mcp

> Workflow-shaped MCP server exposing the Google Ads API to AI agents
> with built-in safety rails for mutations.

**Status**: v1.0.0 — stable. **18 tools** across read, mutation (guardrailed), and drafting surfaces. All mutations honor a universal `dry_run: bool = False` contract enforced by an automated audit test.

---

## What it does

Point Claude Desktop (or any MCP client) at your Google Ads account and get workflow-shaped operations instead of raw API glue:

- *"How did last week go?"* → narrative summary with period-over-period deltas
- *"Audit my account health"* → 5-check snapshot (disapproved ads, low quality scores, budget pacing, missing conversion tracking, paused-but-spending)
- *"Preview pausing campaign X"* → dry-run response with `before`/`after` state, no API call
- *"Draft a new campaign for Winter Boots"* → Google Ads Editor-importable CSV; you import through Editor (never direct API commit)

Full tool catalog in [Available tools](#available-tools-v100).

---

## Prerequisites

Before setup:

- **Python ≥ 3.11**
- **[`uv`](https://docs.astral.sh/uv/)** installed (`curl -LsSf https://astral.sh/uv/install.sh | sh`)
- **A Google Ads Manager account (MCC)** — not a regular advertiser account. Free to create at [`ads.google.com`](https://ads.google.com/) → *Tools → Account Access → Create manager account*.
- **A Google Ads developer token** — Test Account tier is enough to start. See [`docs/developer-token.md`](docs/developer-token.md) for the walkthrough (application form, Basic Access upgrade).
- **A Google Cloud OAuth 2.0 client** of type **Desktop application** — [`console.cloud.google.com`](https://console.cloud.google.com) → APIs & Services → *Enable Google Ads API* → *Create credentials → OAuth client ID → Desktop app* → download the JSON.
- **(Recommended) A Google Ads Test Account** — a sandbox with synthetic data, no real ad spend. Create under your MCC: *Accounts → `+` → Create test account*. Use it for smoke testing before pointing anything at real campaigns.

---

## Install

### Option A — PyPI (once published)

```bash
uvx google-ads-mcp
```

> **Note**: not yet on PyPI. Track [PyPI publish](https://github.com/matheusslg/google-ads-mcp/issues) for status.

### Option B — from source (current path)

```bash
git clone https://github.com/matheusslg/google-ads-mcp
cd google-ads-mcp
uv sync
```

To make `google-ads-mcp` available system-wide from the local checkout:

```bash
uv tool install --from . google-ads-mcp
```

Now `google-ads-mcp` works from any directory. To upgrade after a `git pull`: `uv tool install --from . --force google-ads-mcp`.

---

## First-time setup

Run the setup wizard **once** to capture your credentials:

```bash
google-ads-mcp setup             # if globally installed (Option B tool install)
# or
uv run google-ads-mcp setup      # from a local clone
```

The wizard:

1. Prints the Google Cloud Console steps to create the OAuth 2.0 client
2. Prompts for your developer token (from <https://ads.google.com/aw/apicenter>)
3. Prompts for the path to your `client_secrets.json` (drag-drop the file into the terminal to autopaste)
4. Prompts for your Manager (MCC) ID and default Google Ads account ID (10 digits each, no dashes)
5. Opens a browser tab for OAuth consent
6. Writes `~/.config/google-ads-mcp/credentials.json` at mode `0600` (owner read-only)

Full Google Cloud Console walkthrough: [`docs/developer-token.md`](docs/developer-token.md).

---

## Claude Desktop config

Edit your Claude Desktop config file:

| OS | Path |
|---|---|
| macOS | `~/Library/Application Support/Claude/claude_desktop_config.json` |
| Windows | `%APPDATA%\Claude\claude_desktop_config.json` |
| Linux | `~/.config/Claude/claude_desktop_config.json` |

### If installed via PyPI (Option A)

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

### If running from a local clone (Option B)

```json
{
  "mcpServers": {
    "google-ads-mcp": {
      "command": "uv",
      "args": [
        "run",
        "--directory",
        "/absolute/path/to/google-ads-mcp",
        "google-ads-mcp"
      ]
    }
  }
}
```

**Then fully quit Claude Desktop** — on macOS use **Cmd+Q**, not the window close button. Claude only reads this config at process start.

Once relaunched, the server reads credentials from `~/.config/google-ads-mcp/credentials.json` automatically. No environment variables needed.

---

## First-call example

Open a new Claude chat and try:

> *"Can you ping the google-ads-mcp server?"*

Claude calls `ping()` → `{"ok": true}` if the wiring is right.

Then:

> *"What Google Ads customer IDs do I have access to?"*
> *"Summarize last week's performance."*
> *"Audit my Google Ads account health."*
> *"Preview pausing campaign 8751615979 — dry run."*

You can talk about your ads in natural language; the tool names and args are what Claude sees.

---

## Available tools (v1.0.0)

Every tool that operates on a customer accepts `customer_id?: str` (10 digits, no dashes) — omit to use the `default_customer_id` from `credentials.json`. Every response includes the `customer_id` it operated on.

### Discovery (2 tools)

- `ping()` — connectivity probe → `{"ok": true}`
- `list_accessible_customers()` — customer IDs the developer token can access

### Listings (3 tools)

- `list_campaigns(customer_id?, status?)`
- `list_ad_groups(customer_id?, campaign_id?)`
- `list_keywords(customer_id?, campaign_id?, ad_group_id?)`

All return Pydantic envelopes with typed rows + a `warnings` list. Payloads capped at 10,000 rows; a `warnings: ["truncated at 10000 rows"]` entry surfaces if hit.

### Reporting (3 tools)

- `get_performance(customer_id?, date_range="LAST_7_DAYS", segment_by?)` — aggregate or segmented by campaign/device/network/day
- `list_search_terms(customer_id?, date_range="LAST_7_DAYS", min_impressions=100)`
- `summarize_performance(customer_id?, date_range="LAST_7_DAYS", comparison_period?)` — English narrative + `PeriodComparison` deltas; two GAQL queries under the hood (current + prior period)

`date_range` values: `LAST_7_DAYS`, `LAST_14_DAYS`, `LAST_30_DAYS`, `THIS_MONTH`, `LAST_MONTH`.

### Analytical / audit (2 tools)

- `find_negative_keyword_candidates(customer_id?, date_range="LAST_30_DAYS", min_impressions=50, min_cost=1.0, require_zero_conversions=True)` — ranked by cost descending, with per-candidate reasoning
- `audit_account_health(customer_id?, date_range="LAST_7_DAYS")` — 5-check snapshot: disapproved ads, low quality scores, budget pacing anomalies, missing conversion tracking, paused-but-still-spending. Overall status = worst individual check.

### Mutations (5 tools, all guardrailed — see [Safety model](#safety-model))

- `pause_campaign(campaign_id, customer_id?, dry_run=False, reason?)`
- `enable_campaign(campaign_id, customer_id?, dry_run=False)`
- `update_campaign_budget(campaign_id, new_amount, customer_id?, max_increase_percent?, absolute_cap?, dry_run=False)` — defaults to `max_increase_percent=50` if both guardrails omitted
- `update_keyword_bid(ad_group_id, criterion_id, new_bid, customer_id?, max_bid_cap?, dry_run=False)` — defaults `max_bid_cap = current × 1.5`
- `add_negative_keywords(scope, target_id, keywords, customer_id?, match_type?, dry_run=False)` — `scope: "campaign" | "ad_group"`

### Drafting (3 tools + 1 validator, no API calls)

Campaign creation stops at the human-review boundary — you draft, review, import via Google Ads Editor. AI never spawns live campaigns directly.

- `draft_campaign_csv(spec)` — Google Ads Editor v2 CSV from a `CampaignDraftSpec`. Import via *Editor → Account → Import*.
- `draft_responsive_search_ad(product_description, target_audience, language="en")` — 15 headlines (≤30 chars) + 4 descriptions (≤90 chars), en + pt-br templates
- `validate_rsa_ad(headlines, descriptions)` — validate LLM-generated RSA content against Google's count + char rules; returns per-item errors so the LLM can regenerate just the offenders
- `dry_run_changes(change_set)` — multi-step preview across the 5 mutation tools; forces `dry_run=True` on every item

---

## Safety model

Every mutation tool ships with `dry_run: bool = False` and returns a `MutationResponse` envelope:

```python
{
  "success": bool,
  "dry_run": bool,
  "mutation_id": "customers/.../campaigns/...",  # None on dry_run or refusal
  "before": {...},
  "after": {...},
  "warnings": [...]
}
```

- `dry_run=True` **never** calls the Google Ads API — returns the projected `after` state only
- Refusal (guardrail exceeded) → `success=False`, no API call, `warnings` explain why
- Default cap when both budget guardrails omitted: `max_increase_percent=50` (per PRD § Risks mitigation)
- Bid tool default cap: `current × 1.5` (equivalent 50% ceiling)
- No-op detection: `pause_campaign` on an already-PAUSED campaign returns `success=True` with `before == after` and a warning; no API call

The `dry_run` contract is pinned by an automated audit test that fails if any future mutation tool omits the kwarg or changes the return envelope.

Contract details in [`PRD.md`](PRD.md) (Design System) and [`standards.md`](standards.md).

---

## Known gotchas

Surfaced during real-account testing. Worth reading before your first serious use:

- **`login_customer_id` in `credentials.json`** — the setup wizard writes your MCC ID here. If the target account (`default_customer_id`) isn't hierarchically linked under that MCC, API calls fail with `User doesn't have permission to access customer`. Fix: edit `credentials.json` and set `login_customer_id = default_customer_id` (self-managed pattern).
- **Portfolio-managed keywords** — `update_keyword_bid` will refuse (correctly) when the target keyword's current bid is `$0` because it's under a portfolio bidding strategy. Default cap becomes 0 × 1.5 = 0 and any new bid exceeds it. You can't override portfolio bidding via this tool; change the bid strategy in the Google Ads UI first.
- **`login_customer_id` and `default_customer_id` must be 10 digits, no dashes** — the setup wizard strips dashes automatically, but if you edit `credentials.json` by hand, do not include them.
- **First smoke returned zero rows?** — normal on a fresh Test Account (no impression data yet), or on a real account whose campaigns aren't currently serving. Not a bug.
- **Rate limits** — the Basic Access tier gives you 15,000 operations/day. The 10k-row cap per read tool exists partly to protect against a single query burning your daily budget. See [`docs/developer-token.md`](docs/developer-token.md) for tier details.

---

## Testing

- **Automated**: 124 tests, ruff + mypy strict clean, CI matrix on Python 3.11 + 3.12
  ```bash
  uv sync && uv run pytest
  ```
- **Manual smoke against a real account** (recommended before each release):
  - Read surface: `uv run python scripts/smoke_v0_1_0.py` — hits all 9 read tools
  - Mutations + drafting: `uv run python scripts/smoke_v1_0_0.py` — dry-runs all mutations + exercises drafting
  - Full pre-release checklist: [`docs/smoke-test-playbook.md`](docs/smoke-test-playbook.md)

---

## Development

```bash
git clone https://github.com/matheusslg/google-ads-mcp
cd google-ads-mcp
uv sync
uv run pytest -v
uv run ruff check .
uv run mypy src tests
```

Standards + architectural decisions:

- [`PRD.md`](PRD.md) — product requirements + safety model design
- [`standards.md`](standards.md) — Python conventions + MCP tool-design contracts
- [`docs/specs/`](docs/specs/) — per-issue design docs
- [`docs/plans/`](docs/plans/) — implementation plans

Issue tracker: [GitHub Issues](https://github.com/matheusslg/google-ads-mcp/issues).

---

## License

MIT — see [`LICENSE`](LICENSE).
