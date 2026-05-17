# PRD: google-ads-mcp

## Vision

A Model Context Protocol (MCP) server that exposes the Google Ads API to AI agents through **workflow-shaped tools** — verbs that match how marketers actually think (`audit_account_health`, `triage_search_terms`, `draft_campaign_csv`) rather than raw API endpoints. Mutations carry built-in safety rails so AI assistance can speed up Google Ads operations without burning real ad spend on a typo. Open-source under MIT, distributed via `uvx`, same playbook as [google-search-console-mcp](https://github.com/matheusslg/google-search-console-mcp).

## Problem Statement

Existing Google Ads MCP servers (including the one currently published by Google) expose only the raw API surface — basically GAQL search + resource metadata. Every non-trivial workflow becomes a multi-step orchestration the user has to assemble:

- **"How did last week go?"** — multiple GAQL queries against `customer`, `campaign`, `metrics.*`, then aggregation in the agent's head.
- **"Find waste"** — pull `search_term_view`, filter by `metrics.cost_micros > X AND metrics.conversions = 0`, decide thresholds yourself, then build the mutation manually.
- **"Pause underperformers"** — read campaigns, compute CPL per campaign, filter, then issue mutations one by one with no atomicity.
- **"Create a new campaign"** — requires constructing 5+ nested operations (CampaignBudget → Campaign → AdGroup → AdGroupAd → Keywords) with the right protobuf shapes.

The result: developers building AI agents over Google Ads write the same glue code over and over. Marketers using AI assistants get raw API responses and have to interpret them. Mutation tools, where they exist, have no guardrails — one typo on a budget mutation burns a month of ad spend in a night.

## Target Users

- **Indie developers** building AI agents over their own (or a single client's) Google Ads account.
- **Agencies** managing multi-client portfolios, wanting AI-assisted weekly audits across accounts.
- **In-house marketing teams** using Claude / Cursor / similar AI tools for daily Google Ads operations.
- **Open-source community** — anyone who'd rather depend on a maintained MCP than rewrite the SDK glue.

## Personas

### Indie Dev Iara
- **Role**: Solo SaaS founder, runs ~3 Google Ads campaigns for her own product.
- **Goals**: Ask Claude "how did last week go?" in natural language and get a coherent narrative. Bulk-create campaigns when launching a new product line without clicking through the UI for 4 hours.
- **Pain Points**: The official Google Ads MCP returns raw GAQL JSON; she ends up writing prompts that re-encode the entire API. Doesn't want to maintain SDK glue code in her agent project.

### Agency Operator Tiago
- **Role**: Manages 12 client accounts at a small Brazilian performance agency.
- **Goals**: Run AI-assisted health audits across all 12 accounts every Monday morning, get a single triaged report. Catch wasted spend (irrelevant search terms, paused conversion actions, disapproved ads) without manually clicking through each dashboard.
- **Pain Points**: 12 dashboards × 30 min/account = 6 hours every Monday. Easy to miss issues. Wants AI to do the first pass; he handles the judgment calls.

## Goals

- Reduce time-to-task for common Google Ads workflows (weekly report, account audit, search-terms triage) from tens of minutes to single-digit minutes.
- Provide a write surface that is **safe by construction** — every mutation tool ships with at least one guardrail (cap, dry-run, or human-confirmation step).
- Become the canonical MCP layer for AI-assisted Google Ads operations in the OSS ecosystem.
- Ship a reference implementation (this repo) that real users can `uvx install` and wire into Claude Desktop / Cursor today.

## Non-Goals

- **Direct API campaign creation.** Campaign creation always routes through `draft_campaign_csv` → human review → manual import in Google Ads Editor. Too high-stakes for direct AI commits.
- **Bid strategy switches.** Switching from Manual CPC to Maximize Conversions (or vice-versa) is a multi-week experiment, not a tool call.
- **Audience targeting changes.** Privacy-sensitive and requires human review of every change.
- **Real-time bidding optimization.** Google's own ML (Smart Bidding, Performance Max) owns this layer; competing with it is wasted effort.
- **Bypassing developer-token requirements.** Users must bring their own token. No shared-token model.
- **Replacing the Google Ads UI for creative review.** Humans review final ads before they go live.
- **Manager-account hierarchy management.** Listing sub-accounts is in scope; creating/linking/unlinking them is not (v1).

## Features

### MVP (Phase 0) — Read-Only

- `list_accessible_customers` — returns customer IDs the auth has access to.
- `list_campaigns(customer_id, status?)` — wraps the common "show me my campaigns" query.
- `list_ad_groups(customer_id, campaign_id?)`
- `list_keywords(customer_id, campaign_id?, ad_group_id?)`
- `get_performance(customer_id, date_range, segment_by?)` — performance reports with optional segmentation by campaign, device, network, day.
- `list_search_terms(customer_id, date_range, min_impressions?)` — surfaces the search-terms report.
- `find_negative_keyword_candidates(customer_id, criteria)` — analytical helper, returns ranked candidates with reasoning.
- `audit_account_health(customer_id)` — comprehensive snapshot: disapproved ads, low quality scores, budget pacing anomalies, missing conversion tracking, paused-but-still-spending edge cases.
- `summarize_performance(customer_id, date_range, comparison_period?)` — narrative summary suitable for weekly reports, with computed deltas.

### Phase 1 — Safe Writes (Guardrailed)

- `pause_campaign(customer_id, campaign_id, reason?)`
- `enable_campaign(customer_id, campaign_id)`
- `update_campaign_budget(customer_id, campaign_id, new_amount, max_increase_percent?, absolute_cap?)` — refuses if delta exceeds guardrail.
- `add_negative_keywords(customer_id, scope: campaign | ad_group, target_id, keywords[], match_type?)`
- `update_keyword_bid(customer_id, keyword_id, new_bid, max_bid_cap?)`
- Every mutation supports `dry_run: true` returning the impact preview without committing.

### Phase 2 — Drafting (No Direct API Commits)

- `draft_campaign_csv(spec)` → Google Ads Editor-importable CSV for human review and manual upload.
- `draft_responsive_search_ad(product_description, target_audience, language?)` → 15 headlines + 4 descriptions JSON, RSA-compliant character limits enforced.
- `dry_run_changes(change_set)` → simulate the impact of a multi-step change set before any commits.

### Future (Post-v1)

- Manager-account hierarchy ops (link/unlink sub-accounts).
- Performance Max campaign support.
- Asset library management (image/video uploads).
- Conversion tracking management (create/edit conversion actions).
- Batch / bulk-mutation patterns for high-volume operations.
- CLI front-end for non-AI users (current focus is MCP-only).

## Tech Stack

### Backend (only layer)
- **Language**: Python 3.11+
- **MCP framework**: [FastMCP](https://github.com/jlowin/fastmcp) (same as google-search-console-mcp)
- **Google Ads SDK**: [`google-ads`](https://pypi.org/project/google-ads/) (official Python client)
- **Auth**: OAuth2 via `google-auth` + `google-auth-oauthlib`
- **Dependency management**: [`uv`](https://github.com/astral-sh/uv)
- **Distribution**: `uvx` (single-command install for end users)
- **Testing**: `pytest` + `pytest-asyncio`
- **Linting / formatting**: `ruff`, `mypy`
- **License**: MIT

### Infrastructure
- **None.** Local-first; runs in the user's Claude Desktop / Cursor / shell process. No hosted backend.
- **CI**: GitHub Actions (lint, type-check, test on Python 3.11/3.12).

### External Dependencies
- Google Ads API (v17 at time of writing — pin and ship migration script with each major bump).
- User-supplied: Google Cloud OAuth2 client credentials, Google Ads developer token, refresh token.

## Design

### Design Resources
- N/A — this is a server-side tool with no UI. Tool naming, input schema, and output shape are the only design surfaces.

### Design System
- **Tool-naming convention**: `<verb>_<resource>` for primitive ops (`list_campaigns`), `<verb>_<workflow>` for composed ops (`audit_account_health`). Always lowercase snake_case. Verbs from a fixed set: `list`, `get`, `find`, `summarize`, `audit`, `pause`, `enable`, `update`, `add`, `remove`, `draft`, `dry_run`.
- **Input shape**: every mutation tool MUST accept `dry_run: bool = False`. Every budget-touching tool MUST accept either `max_increase_percent` or `absolute_cap`.
- **Output shape**: read tools return structured JSON suitable for AI consumption (arrays of typed objects, not nested protobuf). Write tools return `{ success: bool, mutation_id?: str, before: {...}, after: {...}, warnings: [] }`.

### Brand/Style Guide
- Repo identity matches the GSC MCP pattern: minimal README focused on install + Claude Desktop config + 3-step "first call" example. No marketing fluff.

## Success Metrics

- **Adoption**: 50+ GitHub stars within 6 months; 5+ public users referencing setup in their own repos / blog posts.
- **Coverage**: ≥ 80% of a published "common marketing workflow" checklist achievable with single-tool calls.
- **Safety**: zero reported incidents of mutation tools causing budget overruns or unintended account-state changes.
- **Time-to-task**: weekly performance report generation drops from ~30 min manual → < 5 min via MCP for representative agency users.
- **Maintenance**: < 1 week to ship a release after each Google Ads API major version bump.

## Roadmap

### Phase 0: MVP — Read-Only (Test-Token-Only)
- [ ] Bootstrap project: `uv init`, FastMCP server skeleton, `pyproject.toml`, MIT LICENSE, README outline.
- [ ] OAuth2 setup helper: walks user through generating client credentials + refresh token, writes to `~/.config/google-ads-mcp/credentials.json`.
- [ ] Implement `list_accessible_customers`, `list_campaigns`, `list_ad_groups`, `list_keywords`.
- [ ] Implement `get_performance` with date_range + segment_by.
- [ ] Implement `list_search_terms`.
- [ ] Implement `find_negative_keyword_candidates`.
- [ ] Implement `audit_account_health`.
- [ ] Implement `summarize_performance` (narrative output).
- [ ] Test against Google Ads test accounts (Test tier — no Basic Access needed).
- [ ] Claude Desktop config snippet in README.
- [ ] Tag v0.1.0, publish to GitHub.

### Phase 1: Safe Writes — Requires Basic Access Approval
- [ ] Apply for Google Ads API Basic Access tier (parallel to Phase 0 dev work — approval takes 1–4 weeks).
- [ ] Implement `pause_campaign` / `enable_campaign` with confirmation pattern.
- [ ] Implement `update_campaign_budget` with `max_increase_percent` + `absolute_cap` guardrails.
- [ ] Implement `add_negative_keywords`.
- [ ] Implement `update_keyword_bid` with `max_bid_cap`.
- [ ] Add `dry_run: bool` to every mutation tool.
- [ ] Document safety model in README.
- [ ] Tag v0.2.0.

### Phase 2: Drafting Tools
- [ ] Implement `draft_campaign_csv` → Google Ads Editor format.
- [ ] Implement `draft_responsive_search_ad` with RSA character-limit validation.
- [ ] Implement `dry_run_changes` for multi-step previews.
- [ ] Tag v0.3.0.

### Phase 3: Hardening + Polish
- [ ] Comprehensive error handling (quota exceeded, auth refresh, partial failures in batch ops).
- [ ] CI: lint + type-check + test matrix on Python 3.11 / 3.12.
- [ ] Smoke-test playbook for a real account.
- [ ] Tag v1.0.0, announce on relevant channels.

### Future
- [ ] Manager-account hierarchy ops.
- [ ] Performance Max support.
- [ ] Asset library management.
- [ ] CLI front-end.

## Risks

- **Google Ads API version churn.** The API ships a major version yearly, deprecates the prior version on a known schedule. Mitigation: pin to one major version per release, ship a migration script with each bump, run a CI smoke test against the new version 1 month before deprecation.
- **Developer-token approval delays for end users.** Basic Access approval takes 1–4 weeks and isn't guaranteed. End users may install the MCP and hit a wall when trying to use it against real accounts. Mitigation: ship a detailed `docs/developer-token.md` walking through the application form, common rejection reasons, and the Test-Account fallback for getting started immediately.
- **Mutation safety despite guardrails.** A user could still set `max_increase_percent: 500` and run a mutation that 5x's their budget. Guardrails reduce risk; they don't eliminate it. Mitigation: ship sensible defaults (`max_increase_percent: 50` if unspecified), require explicit opt-in for aggressive changes, document the safety model loudly in README.
- **Competing MCPs.** Google may ship a more capable official MCP. Other OSS authors may ship competing servers. Differentiation = **workflow-shaped tools, not raw-API**. Stay focused on that; don't try to be a kitchen sink.
- **Single-maintainer bus factor.** Initially one author. Mitigation: aggressive testing, clear contributing guide, accept early PRs to grow contributor base.

## Open Questions

- **MCC hierarchy support in v1, or punt?** Listing sub-accounts is in MVP; creating/linking/unlinking is out. Decide based on early user feedback.
- **How to expose customer_id selection?** Every tool requires `customer_id`. Should we support a default-customer config so users don't have to pass it on every call, or always require explicit passing?
- **Output language for `summarize_performance`?** Hardcoded English, locale-aware, or user-configurable? Author's home market is pt-BR; first contributors may prefer i18n.
- **Test fixtures: real anonymized data, or all-synthetic?** Real data is more realistic but harder to share publicly. Lean synthetic for v0.1.

---
*Generated with /wf-core:wf-create-prd*
