# Design: Read-only listing tools (Issue #4)

**Date**: 2026-07-06
**Issue**: [#4 — Read-only listing tools](https://github.com/matheusslg/google-ads-mcp/issues/4)
**Status**: Approved (autonomous — per user `/goal` directive to wrap up MVP)
**Branch**: `feat/issue-4-read-tools`

---

## Context

First real Google Ads tools. Adds `list_accessible_customers`, `list_campaigns`, `list_ad_groups`, `list_keywords` as FastMCP tools. Uses the auth module shipped in #3 (`get_google_ads_client()`, `get_default_customer_id()`) and completes the `CredentialsRevoked` bridge #3 deferred.

## Decisions

| # | Question | Choice |
|---|---|---|
| 1 | Response object type | Pydantic BaseModel (item + envelope models) — FastMCP auto-generates rich JSON schemas |
| 2 | Pagination | Hard cap 10,000 rows/call; add `warnings: ["truncated at 10000 rows"]` if hit |
| 3 | File layout | Single `src/google_ads_mcp/tools/reads.py` for all 4 tools + models + `_search` helper |
| 4 | Status filter shape | `Literal["ENABLED", "PAUSED", "REMOVED"] \| None` |
| 5 | GAQL strategy | Inline strings per tool + tiny `_search()` helper (SDK boilerplate + row cap + error mapping) |
| 6 | Field selection per resource | Minimal (4-5 fields per model); expand when real usage demands |
| 7 | `id` type | `str` — Google returns int64; string is safer across JSON/TS and consistent with `customer_id: str` elsewhere |
| 8 | Response envelope | `{customer_id, <resource>, warnings}` — Q2-decision echo + Q4-decision warnings surface |
| 9 | Testing | Mock at `get_google_ads_client()` level; conftest `mock_google_ads_client` fixture with hand-crafted rows |
| 10 | GoogleAdsException bridge | `_raise_friendly()` maps `authentication_error` / `authorization_error` codes to `CredentialsRevoked`; else re-raise |

## File Layout

```
src/google_ads_mcp/
├── auth/                         # unchanged
├── server.py                     # MODIFIED — 1 line: import tools.reads to register @mcp.tool
└── tools/                        # NEW
    ├── __init__.py               # empty
    └── reads.py                  # models + 4 tools + _search + _raise_friendly + _resolve_customer_id

tests/
├── conftest.py                   # MODIFIED — add mock_google_ads_client fixture
└── tools/
    ├── __init__.py               # empty
    └── test_reads.py             # unit tests for all 4 tools + error mapping + truncation
```

**Notable absence**: no `clients/` subdirectory. GAQL boilerplate stays inside `reads.py` until #5 duplicates the pattern.

## Pydantic models

```python
from typing import Literal
from pydantic import BaseModel

_Status = Literal["ENABLED", "PAUSED", "REMOVED"]


class Customer(BaseModel):
    customer_id: str


class Campaign(BaseModel):
    id: str
    name: str
    status: _Status
    advertising_channel_type: str  # SEARCH, DISPLAY, VIDEO, SHOPPING, etc.


class AdGroup(BaseModel):
    id: str
    name: str
    status: _Status
    campaign_id: str


class Keyword(BaseModel):
    id: str  # criterion_id
    text: str
    match_type: Literal["EXACT", "PHRASE", "BROAD"]
    status: _Status
    ad_group_id: str


class ListAccessibleCustomersResponse(BaseModel):
    customers: list[Customer]
    warnings: list[str] = []


class ListCampaignsResponse(BaseModel):
    customer_id: str
    campaigns: list[Campaign]
    warnings: list[str] = []


class ListAdGroupsResponse(BaseModel):
    customer_id: str
    ad_groups: list[AdGroup]
    warnings: list[str] = []


class ListKeywordsResponse(BaseModel):
    customer_id: str
    keywords: list[Keyword]
    warnings: list[str] = []
```

## Helper functions

```python
_MAX_ROWS = 10_000
_TRUNCATED_WARNING = f"truncated at {_MAX_ROWS} rows; refine filters to see more"


def _resolve_customer_id(customer_id: str | None) -> str:
    """Return caller-supplied ID or fall back to config default."""
    return customer_id or get_default_customer_id()


def _search(customer_id: str, query: str) -> tuple[list, list[str]]:
    """Run GAQL against customer_id, cap at _MAX_ROWS.

    Returns (rows, warnings). warnings non-empty iff the cap was hit.
    Raises CredentialsRevoked on auth failure; other GoogleAdsExceptions propagate.
    """
    client = get_google_ads_client()
    service = client.get_service("GoogleAdsService")
    rows: list = []
    warnings: list[str] = []
    try:
        stream = service.search_stream(customer_id=customer_id, query=query)
        for batch in stream:
            for row in batch.results:
                if len(rows) >= _MAX_ROWS:
                    warnings.append(_TRUNCATED_WARNING)
                    return rows, warnings
                rows.append(row)
    except GoogleAdsException as e:
        _raise_friendly(e)
    return rows, warnings


def _raise_friendly(e: GoogleAdsException) -> None:
    """Map GoogleAdsException auth codes to CredentialsRevoked; otherwise re-raise."""
    for err in e.failure.errors:
        if err.error_code.authentication_error or err.error_code.authorization_error:
            raise CredentialsRevoked(
                f"Authentication failed: {err.message}. "
                "Refresh token may be revoked. Re-run `google-ads-mcp setup`."
            ) from e
    raise e
```

## Tool implementations

```python
@mcp.tool
def list_accessible_customers() -> ListAccessibleCustomersResponse:
    """List Google Ads customer IDs the current developer token has access to.

    No arguments. Uses the OAuth credentials configured via `google-ads-mcp setup`.
    """
    client = get_google_ads_client()
    service = client.get_service("CustomerService")
    try:
        result = service.list_accessible_customers()
    except GoogleAdsException as e:
        _raise_friendly(e)
        raise  # unreachable but appeases mypy
    # result.resource_names is like ["customers/1234567890", ...]
    return ListAccessibleCustomersResponse(
        customers=[Customer(customer_id=rn.split("/")[-1]) for rn in result.resource_names],
    )


@mcp.tool
def list_campaigns(
    customer_id: str | None = None,
    status: _Status | None = None,
) -> ListCampaignsResponse:
    """List campaigns for a Google Ads customer, optionally filtered by status.

    Args:
        customer_id: 10-digit ID (no dashes). Defaults to `default_customer_id` in credentials.json.
        status: Optional — filter to ENABLED, PAUSED, or REMOVED campaigns.
    """
    cid = _resolve_customer_id(customer_id)
    where = f" WHERE campaign.status = '{status}'" if status else ""
    query = (
        "SELECT campaign.id, campaign.name, campaign.status, "
        "campaign.advertising_channel_type FROM campaign" + where
    )
    rows, warnings = _search(cid, query)
    return ListCampaignsResponse(
        customer_id=cid,
        campaigns=[
            Campaign(
                id=str(r.campaign.id),
                name=r.campaign.name,
                status=r.campaign.status.name,
                advertising_channel_type=r.campaign.advertising_channel_type.name,
            )
            for r in rows
        ],
        warnings=warnings,
    )


@mcp.tool
def list_ad_groups(
    customer_id: str | None = None,
    campaign_id: str | None = None,
) -> ListAdGroupsResponse:
    """List ad groups for a customer, optionally scoped to a single campaign."""
    cid = _resolve_customer_id(customer_id)
    where = f" WHERE ad_group.campaign = 'customers/{cid}/campaigns/{campaign_id}'" if campaign_id else ""
    query = (
        "SELECT ad_group.id, ad_group.name, ad_group.status, "
        "ad_group.campaign FROM ad_group" + where
    )
    rows, warnings = _search(cid, query)
    return ListAdGroupsResponse(
        customer_id=cid,
        ad_groups=[
            AdGroup(
                id=str(r.ad_group.id),
                name=r.ad_group.name,
                status=r.ad_group.status.name,
                campaign_id=r.ad_group.campaign.split("/")[-1],
            )
            for r in rows
        ],
        warnings=warnings,
    )


@mcp.tool
def list_keywords(
    customer_id: str | None = None,
    campaign_id: str | None = None,
    ad_group_id: str | None = None,
) -> ListKeywordsResponse:
    """List keywords for a customer, optionally scoped to a campaign and/or ad group."""
    cid = _resolve_customer_id(customer_id)
    filters = []
    if ad_group_id:
        filters.append(f"ad_group_criterion.ad_group = 'customers/{cid}/adGroups/{ad_group_id}'")
    if campaign_id:
        filters.append(f"campaign.id = {campaign_id}")
    where = f" WHERE {' AND '.join(filters)}" if filters else ""
    query = (
        "SELECT ad_group_criterion.criterion_id, ad_group_criterion.keyword.text, "
        "ad_group_criterion.keyword.match_type, ad_group_criterion.status, "
        "ad_group_criterion.ad_group FROM ad_group_criterion "
        "WHERE ad_group_criterion.type = 'KEYWORD'" + (f" AND {' AND '.join(filters)}" if filters else "")
    )
    rows, warnings = _search(cid, query)
    return ListKeywordsResponse(
        customer_id=cid,
        keywords=[
            Keyword(
                id=str(r.ad_group_criterion.criterion_id),
                text=r.ad_group_criterion.keyword.text,
                match_type=r.ad_group_criterion.keyword.match_type.name,
                status=r.ad_group_criterion.status.name,
                ad_group_id=r.ad_group_criterion.ad_group.split("/")[-1],
            )
            for r in rows
        ],
        warnings=warnings,
    )
```

## `server.py` change

Add at the bottom:

```python
from google_ads_mcp.tools import reads  # noqa: F401 — registers @mcp.tool functions
```

## Tests

`tests/conftest.py` gains a fixture that hands out a mocked SDK client:

```python
@pytest.fixture
def mock_google_ads_client(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """Patch `get_google_ads_client` and return the MagicMock for row programming."""
    client = MagicMock()
    monkeypatch.setattr(
        "google_ads_mcp.tools.reads.get_google_ads_client",
        lambda *a, **k: client,
    )
    # Also patch the default_customer_id fallback so tests don't touch real credentials.
    monkeypatch.setattr(
        "google_ads_mcp.tools.reads.get_default_customer_id",
        lambda *a, **k: "9999999999",
    )
    return client
```

`tests/tools/test_reads.py` covers:

| Test | Verifies |
|---|---|
| `test_list_accessible_customers_returns_customer_ids` | `CustomerService.list_accessible_customers()` result → list of `Customer(customer_id=...)`, IDs parsed from `customers/N` resource names |
| `test_list_campaigns_returns_envelope_and_items` | GAQL query issued; each row → `Campaign(...)`; envelope has `customer_id` echo |
| `test_list_campaigns_status_filter_adds_where_clause` | When `status="PAUSED"` passed, GAQL includes `WHERE campaign.status = 'PAUSED'` |
| `test_list_campaigns_falls_back_to_default_customer_id` | Called with `customer_id=None` → uses `get_default_customer_id()` return; envelope echoes the default |
| `test_list_ad_groups_scopes_to_campaign` | When `campaign_id` passed, GAQL WHERE narrows to that campaign |
| `test_list_keywords_scopes_to_ad_group` | When `ad_group_id` passed, GAQL WHERE narrows correctly |
| `test_search_truncates_at_10000_rows` | Mock yields 10001 rows → response has 10000 items + truncation warning |
| `test_search_maps_auth_error_to_credentials_revoked` | Mock raises `GoogleAdsException` with `authentication_error` code → `CredentialsRevoked` raised |
| `test_search_re_raises_non_auth_google_ads_exception` | Mock raises `GoogleAdsException` with non-auth code → original exception propagates |

Integration smoke (manual, deferred to #7): `uvx google-ads-mcp` + Claude Desktop, call `list_accessible_customers` — should return the actual customer IDs.

## Out of scope (deferred)

| Not in #4 | Owned by |
|---|---|
| Pagination tokens / cursor-based paging | Future — 10k cap works for v0.1 |
| Extra Campaign fields (start_date, budget, bidding_strategy) | Future — add when real usage demands |
| MCC hierarchy operations | PRD Non-Goals (line 52) — post-v1 if ever |
| Aggregations / metrics-per-campaign | #5 (`get_performance`, `summarize_performance`) |
| Retries on transient SDK errors | Future — defer until real usage shows the problem |
| Real-account integration test in CI | #15 (Phase 3 hardening) |

## Verification Required at Scaffold Time

1. **`GoogleAdsException.failure.errors[*].error_code.authentication_error`** — confirm the exact protobuf field names. The SDK docs show `error_code` with a oneof; `authentication_error` and `authorization_error` are two of the fields. May need adjustment.
2. **`CustomerService.list_accessible_customers()` return shape** — `.resource_names` field name confirmed via the SDK; verify at implementation time.
3. **Enum field `.name` access** — for `campaign.status.name`, `.advertising_channel_type.name`, etc. The proto-plus setting makes these string-valued at access. Confirm with a smoke.

## Acceptance Criteria Mapping (issue #4)

| Criterion | Satisfied by |
|---|---|
| All four tools as FastMCP tool definitions | `@mcp.tool` decorators on all 4 functions in `tools/reads.py` |
| Output: JSON-serializable arrays of typed objects, not raw protobuf | Pydantic response envelopes; each row extracted into Pydantic item models |
| Docstrings/schemas describe args + shape clearly | Pydantic BaseModel → JSON schema; explicit docstrings on all 4 tools |
| Unit tests with synthetic fixtures | `mock_google_ads_client` fixture; 9 unit tests listed above |
| Integration smoke against Test Account | Deferred to #7 v0.1.0 release (manual step) |

---

*Auto-generated under user `/goal` directive; ponytail defaults throughout.*
