# Issue #4 — Read-Only Listing Tools — Implementation Plan

**Goal**: land 4 FastMCP read tools (`list_accessible_customers`, `list_campaigns`, `list_ad_groups`, `list_keywords`) + shared `_search` GAQL helper + `GoogleAdsException → CredentialsRevoked` bridge.

**Spec**: `docs/specs/2026-07-06-issue-4-read-tools-design.md`

**Branch**: `feat/issue-4-read-tools`

---

## Tasks

### T1 — Scaffold `tools/` subpackage + models

**Files**: `src/google_ads_mcp/tools/__init__.py` (empty), `src/google_ads_mcp/tools/reads.py`

- Create `tools/` dir + empty `__init__.py`
- `reads.py` contents at this point: module docstring, imports, `_Status` alias, `_MAX_ROWS` + `_TRUNCATED_WARNING`, all 4 item models + 4 envelope models per spec. No functions yet.
- Verify import: `uv run python -c "from google_ads_mcp.tools.reads import Campaign, ListCampaignsResponse; print('ok')"`
- Gates clean.
- Commit: `feat(tools): scaffold read-tool models and constants`

### T2 — Server registration

**Files**: `src/google_ads_mcp/server.py`

- Append (after `main()`, before `if __name__`): `from google_ads_mcp.tools import reads  # noqa: F401`
- Not strictly needed yet (no @mcp.tool functions), but wires the import path for later tasks. Alternative: defer to T5. Doing now for symmetry.
- Actually — defer to T5. FastMCP will bind decorators at import time; importing an empty tools module now does nothing. Skip this task; roll into T5.

**T2 collapsed into T5.**

### T3 — `_resolve_customer_id` + `_raise_friendly` (TDD)

**Files**: `src/google_ads_mcp/tools/reads.py`, `tests/tools/__init__.py`, `tests/tools/test_reads.py`

Tests first (all fail on import):
- `test_resolve_customer_id_uses_arg_when_provided`
- `test_resolve_customer_id_falls_back_to_default`
- `test_raise_friendly_maps_authentication_error_to_credentials_revoked`
- `test_raise_friendly_maps_authorization_error_to_credentials_revoked`
- `test_raise_friendly_reraises_non_auth_error`

Then implement per spec. Gates clean.

Commit: `feat(tools): add customer_id fallback and CredentialsRevoked bridge`

### T4 — `mock_google_ads_client` fixture + `_search` helper (TDD)

**Files**: `tests/conftest.py`, `src/google_ads_mcp/tools/reads.py`

- Add `mock_google_ads_client` fixture to conftest (per spec)
- Tests: `test_search_yields_rows_and_no_warnings`, `test_search_truncates_at_10000_rows`, `test_search_maps_google_ads_exception`
- Implement `_search` per spec

Commit: `feat(tools): add _search helper with 10k row cap`

### T5 — `list_accessible_customers` (TDD)

**Files**: `src/google_ads_mcp/tools/reads.py`, `src/google_ads_mcp/server.py`, `tests/tools/test_reads.py`

- Test: `test_list_accessible_customers_parses_resource_names`
- Implement per spec
- Add `from google_ads_mcp.tools import reads` to `server.py`

Commit: `feat(tools): add list_accessible_customers`

### T6 — `list_campaigns` (TDD)

- Tests: envelope, status filter WHERE clause, default_customer_id fallback
- Implement

Commit: `feat(tools): add list_campaigns with status filter`

### T7 — `list_ad_groups` (TDD)

- Tests: envelope, `campaign_id` scoping in WHERE
- Implement

Commit: `feat(tools): add list_ad_groups with campaign scoping`

### T8 — `list_keywords` (TDD)

- Tests: envelope, `campaign_id` + `ad_group_id` scoping
- Implement (also handles the `WHERE ad_group_criterion.type = 'KEYWORD'` clause carefully — spec draft had it appearing twice; consolidate)

Commit: `feat(tools): add list_keywords with campaign+ad_group scoping`

### T9 — Full gates + progress.md Session 8

**Files**: `progress.md`

- `uv sync && uv run pytest -v && uv run ruff check . && uv run ruff format --check . && uv run mypy src tests` — all pass
- Bump `Last Updated`, add Session 8 entry, refresh `In Progress` / `Next Session Should`

Commit: `chore(progress): log session 8 — issue #4 read tools complete`

### T10 — Push + PR + auto-merge

- `git push -u origin feat/issue-4-read-tools`
- Open PR with body referencing spec + plan + acceptance criteria + closes #4
- Squash-merge (autonomous per /goal)
- Delete branch local + remote

---

## Verification-at-implementation-time hazards (from spec)

1. `GoogleAdsException.failure.errors[*].error_code.{authentication_error, authorization_error}` field access — verify with a quick smoke; fall back to enum inspection if field access differs.
2. `CustomerService.list_accessible_customers().resource_names` — confirm.
3. Enum `.name` string access for `status`, `advertising_channel_type`, `match_type` — proto-plus default; verify.
