"""Read-only Google Ads tools for google-ads-mcp.

Contains Pydantic response models, a `_search()` helper that runs GAQL with
a 10k row cap, and the `GoogleAdsException` → `CredentialsRevoked` bridge.
Tool functions land in T5-T8.
"""

from __future__ import annotations

from typing import Any, Literal, NoReturn

from google.ads.googleads.errors import GoogleAdsException
from pydantic import BaseModel

from google_ads_mcp.auth import (
    CredentialsRevoked,
    get_default_customer_id,
    get_google_ads_client,
)

_MAX_ROWS = 10_000
_TRUNCATED_WARNING = f"truncated at {_MAX_ROWS} rows; refine filters to see more"

_Status = Literal["ENABLED", "PAUSED", "REMOVED"]


class Customer(BaseModel):
    customer_id: str


class Campaign(BaseModel):
    id: str
    name: str
    status: _Status
    advertising_channel_type: str


class AdGroup(BaseModel):
    id: str
    name: str
    status: _Status
    campaign_id: str


class Keyword(BaseModel):
    id: str
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


def _resolve_customer_id(customer_id: str | None) -> str:
    """Return caller-supplied ID or fall back to config default."""
    return customer_id or get_default_customer_id()


def _raise_friendly(e: GoogleAdsException) -> NoReturn:
    """Map GoogleAdsException auth codes to CredentialsRevoked; otherwise re-raise."""
    for err in e.failure.errors:
        if err.error_code.authentication_error or err.error_code.authorization_error:
            raise CredentialsRevoked(
                f"Authentication failed: {err.message}. "
                "Refresh token may be revoked. Re-run `google-ads-mcp setup`."
            ) from e
    raise e


def _search(customer_id: str, query: str) -> tuple[list[Any], list[str]]:
    """Run GAQL against `customer_id`, cap at `_MAX_ROWS`.

    Returns (rows, warnings). `warnings` non-empty iff the cap was hit.
    Raises `CredentialsRevoked` on auth failure; other `GoogleAdsException`s propagate.
    """
    client = get_google_ads_client()
    service = client.get_service("GoogleAdsService")
    rows: list[Any] = []
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
