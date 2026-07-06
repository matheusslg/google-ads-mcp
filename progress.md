# Project Progress

> This file tracks progress across sessions. Update before ending each session.
> **Keep this file under 400 lines** - archive old sessions to `.claude/session-archive/`

## Current Status
**Phase**: Phase 1 — Safe Writes **COMPLETE** (v0.2.0 tagged). Phase 0 done. Phase 2 (drafting tools) next.
**Last Updated**: 2026-07-06

---

### Session 11 (2026-07-06)
**Focus**: Issue #7 — v0.1.0 release prep (autonomous under `/goal`)
**Completed**:
- README polished: Status → v0.1.0, "Available tools (v0.1.0)" section replaces the "Real tools land in #4–#6" placeholder, "First-call example" is now a real Claude Desktop walkthrough, Safety model note explains v0.1.0 is read-only and mutations land in Phase 1
- `pyproject.toml` version 0.0.1 → 0.1.0
- All 65 tests still pass; ruff/mypy clean
- v0.1.0 tag will be cut on `main` after PR merge; draft GitHub Release will be created but NOT published (awaits user's manual smoke against a real Test Account)
**MVP status**: **all 4 acceptance issues complete** (#4, #5, #6, #7). Phase 0 done.
**Branch**: `chore/release-v0.1.0`
**Next**: User smokes against real Test Account → publishes the draft Release. Then #8 (Phase 1 mutations) is unblocked with Basic Access already approved.

### Session 10 (2026-07-06)
**Focus**: Issue #6 — analytical / audit tools (autonomous)
**Completed**:
- `src/google_ads_mcp/tools/audits.py` — `find_negative_keyword_candidates` (ranked by cost desc, English reasoning per candidate) + `audit_account_health` (5 checks: disapproved ads, low quality scores, budget pacing, missing conversion tracking, paused-but-still-spending; overall status derived from worst)
- Promoted `_DURATION_DAYS` → public `PERIOD_DAYS` in `reports.py` (needed by pacing check); added THIS_MONTH/LAST_MONTH as nominal 30-day approximations
- 18 new tests → 65 total; ruff/mypy strict clean; 2 commits
**Judgment calls**: check helpers drop `_search` truncation warnings (return type has no room; 10k cap unlikely to matter for audit scans); pacing aggregates cost per-campaign in Python defensively
**Branch**: `feat/issue-6-audit-tools`
**Next (autonomous)**: #7 v0.1.0 release — README polish + tag + draft GitHub Release. Manual smoke against real Test Account left for user.

### Session 9 (2026-07-06)
**Focus**: Issue #5 — performance reporting tools (autonomous under `/goal`)
**Completed**:
- `src/google_ads_mcp/tools/reports.py` — `get_performance` (with `segment_by` for campaign/device/network/day), `list_search_terms` (with `min_impressions` filter, default 100), `summarize_performance` (narrative + `PeriodComparison` deltas)
- `_format_delta`, `_format_narrative` (deterministic English, no LLM), `_compute_prior_period` (Python `datetime` math for the comparison period since GAQL has no "prior LAST_7_DAYS")
- Reused `_search` / `_resolve_customer_id` / `_raise_friendly` from `.reads`; no conftest changes needed
- 11 new tests → 47 total; ruff/mypy strict clean
**Surprises resolved**: `metrics.average_cpc` returns micro-value despite lacking `_micros` suffix (Google API quirk); search-term match type lives at `segments.search_term_match_type` (not `search_term_view.status`); `PeriodComparison.delta_pct` uses a `MetricsDelta` model with float fields to avoid Pydantic rejecting fractional percentages assigned to int fields.
**Branch**: `feat/issue-5-reporting-tools`
**Next (autonomous)**: #6 (audit + negative keyword tools) → #7 v0.1.0 release.

### Session 8 (2026-07-06)
**Focus**: Issue #4 — read-only listing tools (autonomous execution under user `/goal` directive to wrap up MVP)
**Completed**:
- Basic Access approved by Google 2026-07-06; recorded in `docs/developer-token.md` (PR #22 merged)
- `src/google_ads_mcp/_mcp.py` — shared FastMCP instance to break circular import between `server.py` and `tools/reads.py`
- `src/google_ads_mcp/tools/reads.py` — 4 read tools (`list_accessible_customers`, `list_campaigns`, `list_ad_groups`, `list_keywords`) with Pydantic response envelopes, 10k row cap + truncation warning, `_search` GAQL helper, `_raise_friendly` bridge mapping `GoogleAdsException` auth codes to `CredentialsRevoked` (closes the deferral from #3's spec)
- `src/google_ads_mcp/server.py` — imports `mcp` from `_mcp`; registers tools via `from google_ads_mcp.tools import reads` at bottom
- `tests/conftest.py` — `mock_google_ads_client` fixture (patches `get_google_ads_client` + `get_default_customer_id` in `tools.reads`)
- `tests/tools/test_reads.py` — 18 tests: 8 for helpers (`_resolve_customer_id`, `_raise_friendly`, `_search` truncation + error mapping) + 10 for the 4 tools (envelope shape, WHERE-clause filters, `default_customer_id` fallback, resource-name parsing)
- All gates clean: 36 tests, ruff, mypy strict
- Spec at `docs/specs/2026-07-06-issue-4-read-tools-design.md`; plan at `docs/plans/2026-07-06-issue-4-read-tools-plan.md`
**Branch**: `feat/issue-4-read-tools`
**Next (autonomous)**: brainstorm + implement #5 (performance reporting), then #6 (audit tools), then #7 (v0.1.0 release prep).

### Session 7 (2026-06-03)
**Focus**: Issue #3 — implement OAuth2 setup helper + credential management
**Completed**:
- Added 3 runtime deps (`google-ads`, `google-auth`, `google-auth-oauthlib`)
- `src/google_ads_mcp/auth/__init__.py` — `CREDENTIALS_PATH`, error classes, `load_credentials`, `get_default_customer_id`, `get_google_ads_client`
- `src/google_ads_mcp/auth/setup.py` — `validate_customer_id`, `load_client_secrets_json`, `write_credentials_file`, `_run_oauth_flow`, `run_setup(argv)` wizard
- `src/google_ads_mcp/server.py` — argv dispatch: `setup` → wizard, else → server
- `tests/conftest.py` — first shared fixture (`tmp_credentials_dir`)
- 14 new tests across `tests/auth/test_load.py`, `tests/auth/test_setup_helpers.py`, and `tests/test_server.py`
- README "Setup (first-time only)" section + Claude Desktop config note revision
- `docs/developer-token.md` "After approval" → points at `uvx google-ads-mcp setup`
- All quality gates clean (pytest, ruff check, ruff format, mypy strict)
**Branch**: `feat/issue-3-oauth-setup`
**Next**: PR review/merge → close #3 → start #4 (Read-only listing tools, against Test Account).

### Session 6 (2026-05-21 → 2026-06-03)
**Focus**: Brainstorm issue #3 (OAuth2 setup helper & credential management); produce design spec
**Completed**:
- Pulled the official Google Ads Python SDK credential shape via Context7 (`GoogleAdsClient.load_from_dict()` keys + the OAuth Flow snippet from Google's own docs)
- Resolved 4 design decisions: (Q1) single-account flat `credentials.json` with `schema_version: 1`; (Q2) `google-ads-mcp setup` subcommand via argv dispatch in `main()`; (Q3) stdlib `argparse` + `getpass`; (Q4) path-to-`client_secrets.json` for OAuth + pre-flight Cloud Console banner
- Wrote `docs/specs/2026-05-28-issue-3-oauth-setup-design.md` (413 lines) — covers file layout (`auth/` sub-package), credentials.json schema, 5-step wizard flow, runtime auth module (with code), `server.py` argv dispatch, 3-class `CredentialsError` hierarchy, error matrix, test list, out-of-scope, verification-at-scaffold-time
- Spec approved 2026-06-03
**Branch**: `feat/issue-3-oauth-setup` (spec is commit 1; plan + implementation will land on top)
**Next**: Invoke `superpowers:writing-plans` to produce a bite-sized TDD implementation plan from the spec.

### Session 5 (2026-05-19)
**Focus**: Resolve the four PRD Open Questions before #3 design work
**Completed**:
- **Q1 — MCC hierarchy in v1**: Confirmed listing-only; create/link/unlink stays out per existing Non-Goals
- **Q2 — `customer_id` selection**: Default in config (`~/.config/google-ads-mcp/credentials.json` or env var) + per-call override. Every tool response includes the `customer_id` it operated on; mutation responses include it in `warnings` for safety. Affects #3 and every downstream tool.
- **Q3 — `summarize_performance` language**: English only for v0.1. Narrative output is consumed by the LLM, which translates to the user's conversational language for free. No i18n infrastructure now.
- **Q4 — Test fixtures**: All-synthetic unit fixtures + integration smoke against Google Test Accounts. Reactive escape hatch only if a real-world quirk forces anonymized real data.
- All 4 resolutions written into `PRD.md` `## Open Questions` section as `**Resolved 2026-05-19**:` annotations
**Branch**: `chore/resolve-prd-open-questions`
**Next**: Brainstorm #3 (OAuth2 setup helper) — design will now reference the `default_customer_id` config slot decided in Q2.

### Session 4 (2026-05-19)
**Focus**: Issue #2 — Apply for Google Ads API Basic Access + write `docs/developer-token.md`
**Completed**:
- Filed Basic Access application via https://ads.google.com/aw/apicenter
  - Applicant: Cavallini Imóveis (`https://cavalliniimoveis.com.br/`)
  - API contact email: `cavallini.matheus34@gmail.com`
  - Design doc uploaded: PRD.md → PDF (via GitHub renderer print-to-PDF)
  - Field 8 (access): Both internal and external users
  - Field 11 (campaign types): Search, Display
  - Field 12 (capabilities): Campaign Management + Reporting
- Wrote `docs/developer-token.md` — full end-user setup guide: prerequisites (MCC), four access tiers, all 12 form fields with example answers, Test Account fallback, common rejection patterns, BYO-token model notes
- Corrected outdated risk note in `PRD.md` line 180: Basic Access SLA is ~3 business days (per Google's confirmation screen), not "1–4 weeks" — re-wrote the risk + mitigation accordingly
**Discovered**:
- Google's confirmation screen states the SLA is "~3 business days" (some applications may take longer); old PRD claim of 1–4 weeks was inaccurate
- Test Account tier suffices for all Phase 0 development (issues #3–#7) — Basic Access is only strictly needed for Phase 1+ mutations against real production accounts and for our own Cavallini Imóveis ad operations
**Branch**: `chore/issue-2-developer-token`
**Next**: Await Google compliance team response (case ID arrives by email at `cavallini.matheus34@gmail.com`). Meanwhile, brainstorm + implement #3 (OAuth setup) against a Test Account.

### Session 3 (2026-05-18)
**Focus**: Issue #1 — Bootstrap project skeleton (executed via `superpowers:subagent-driven-development`)
**Completed**:
- `uv init --package` scaffold (commit `6b38213`), then replaced generated `pyproject.toml` with the spec'd content (PEP 621 + PEP 735 + PEP 639) in `98d6ed2`
- Placeholder `README.md` marked with TODO comment to signal future agents it would be overwritten (`5c9a7f1`)
- `.python-version` (3.11) + `.gitignore` with Python/uv/secrets ignores (`b832274`)
- `src/google_ads_mcp/__init__.py` (version from `importlib.metadata`) + `src/google_ads_mcp/server.py` (FastMCP instance + `ping` no-op tool + `main()`) + `tests/__init__.py` + `tests/test_server.py` — TDD red→green cycle, single commit (`d958f56`)
- Ruff `RUF022` fix sorting `__all__` (`c1e1b12`)
- Full README skeleton with Install / Claude Desktop config / First call / Safety placeholder / Development / License sections (`cf66043`)
- `uv.lock` committed; ruff + ruff-format + mypy + pytest gates all clean
**Discovered**: FastMCP 3.3.1 is current stable (spec's `>=2.0` floor accommodated; API surface — `from fastmcp import FastMCP` and `@mcp.tool` decorator — verified working)
**Branch**: `feat/issue-1-bootstrap` (built atop spec commit `2ccb67d` and plan commit `0cfdae2`)
**Result**: PR #17 merged into `main`.

### Session 2 (2026-05-18)
**Focus**: `/wf-core:wf-generate` — scaffold agents and skills for the Python/MCP stack
**Completed**:
- Created 2 agents under `.claude/agents/`:
  - `google-ads-mcp-backend` (Python/MCP-customized — diverges from the generic web-flavored template to match the actual stack: FastMCP, google-ads SDK, OAuth2, uv, pytest, ruff, mypy. Encodes the PRD safety model.)
  - `google-ads-mcp-reviewer` (read-only, with PRD-specific review checklist)
- Created 6 skills under `.claude/skills/`: `py-test`, `py-lint`, `uv-deps`, `gh-pr`, `gh-issues`, `gh-pr-status`
- Updated `.claude/workflow.json`: `scopes: ["backend"]`, `agents` map, `init_script: "uv sync"`
- Rewrote `standards.md` with Python/uv conventions, MCP tool-design contracts, mutation safety checklist, file-layout starting point
- Branch: `chore/wf-generate` (per the never-commit-to-main rule)
**Skipped intentionally — no stack fit**: `ui-developer`, `fullstack-developer`, `generic-developer`, docker-*, db-*, visual-verify, agent-browser, nest-*, next-*
**Result**: PR #16 merged into `main` (after rebase to resolve `progress.md` conflict with Session 3 entry).

### Session 1 (2026-05-17)
**Focus**: Project initialization + PRD parsing
**Completed**:
- Initialized git repository (`main`)
- Created public GitHub repo: `matheusslg/google-ads-mcp`
- Created workflow scaffolding: `.claude/workflow.json`, `progress.md`, `standards.md` (generic placeholder)
- Pushed `main` to origin; switched origin from SSH to HTTPS (gh-token-backed) because no local SSH key was wired
- Added MIT LICENSE (`Copyright (c) 2026 Matheus Nascimento Cavallini`)
- Created 15 parent issues (#1–#15) from PRD via `/wf-core:wf-parse-prd`, covering Phases 0–3
- Created labels: `phase:0-mvp`, `phase:1-safe-writes`, `phase:2-drafting`, `phase:3-hardening`, `type:epic`, `priority:p0`, `priority:p1`, `admin`
**Notable choice**: Moved "Apply for Google Ads API Basic Access" from Phase 1 (where the PRD listed it) to Phase 0 (#2), because approval takes 1–4 weeks and would otherwise block Phase 1 testing.

---

## Session Archive

> When this file exceeds 500 lines, move older sessions to `.claude/session-archive/sessions-{N}-{M}.md`
> Keep only the last 5 sessions in this file for AI readability.

## In Progress
- `chore/release-v0.1.0` branch — release prep; PR pending
- User's Test-Account smoke + draft-release publish is the last MVP step

## Next Session Should
- [ ] Merge #4 PR when open
- [ ] #5 (performance reporting: `get_performance`, `list_search_terms`, `summarize_performance`)
- [ ] #6 (audit tools: `find_negative_keyword_candidates`, `audit_account_health`)
- [ ] #7 (v0.1.0 release — smoke against real Test Account, tag, GitHub Release — user's hands for the smoke step)

## Decisions Made
- **Ticketing platform**: GitHub Issues (matches MIT/OSS distribution model)
- **Repository visibility**: Public (MIT license, per PRD)
- **Distribution model**: `uvx` (per PRD — same playbook as `google-search-console-mcp`; reference repo is TypeScript/Node, so it informs project shape only, not language stack)
- **Backend agent**: customized for Python/MCP rather than using the web-flavored template verbatim, to avoid agent prompts that reference non-existent HTTP/DB concepts
- **Skill set**: minimal MCP-appropriate (6 skills) rather than the full menu — no UI, no DB, no Docker in this project
- **Day-1 server scaffold**: src-layout, `uv init --package`, single-file `server.py` (modular split deferred until first real tool lands in #4)
- **`init_script`**: `uv sync` (set in `workflow.json` during Session 2; functional once Session 3's `pyproject.toml` landed)
- **Author email on PyPI metadata**: `nascimentocavallini@hotmail.com` for v0.0.1; revisit before v0.1.0 (#7) if a noreply form is preferred

## Notes
- PRD.md is in the repo root and is the source of truth for scope, non-goals, and tool surface
- Reference implementation playbook: https://github.com/matheusslg/google-search-console-mcp
- Spec for issue #1: `docs/specs/2026-05-18-issue-1-bootstrap-design.md`; plan: `docs/plans/2026-05-18-issue-1-bootstrap-plan.md`
- FastMCP version pulled by uv at scaffold time: 3.3.1 (constraint `>=2.0`); decorator form `@mcp.tool` without parens confirmed working
- PRD line references in issue bodies are pinned to the committed PRD.md — if the PRD is edited, those references may drift
