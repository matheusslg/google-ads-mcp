"""Read-only Google Ads tools for google-ads-mcp.

Contains Pydantic response models, a `_search()` helper that runs GAQL with
a 10k row cap, and the `GoogleAdsException` → `CredentialsRevoked` bridge.
Tool functions land in T5-T8.
"""

from __future__ import annotations

from typing import Any, Literal, NoReturn

from google.ads.googleads.errors import GoogleAdsException
from pydantic import BaseModel

from google_ads_mcp._mcp import mcp
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


@mcp.tool
def list_accessible_customers() -> ListAccessibleCustomersResponse:
    """List Google Ads customer IDs the current developer token has access to.

    No arguments. Uses OAuth credentials configured via `google-ads-mcp setup`.
    """
    client = get_google_ads_client()
    service = client.get_service("CustomerService")
    try:
        result = service.list_accessible_customers()
    except GoogleAdsException as e:
        _raise_friendly(e)
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
    """List ad groups for a customer, optionally scoped to a single campaign.

    Args:
        customer_id: 10-digit ID. Defaults to `default_customer_id` in credentials.json.
        campaign_id: Optional — restrict to ad groups within this campaign.
    """
    cid = _resolve_customer_id(customer_id)
    where = (
        f" WHERE ad_group.campaign = 'customers/{cid}/campaigns/{campaign_id}'"
        if campaign_id
        else ""
    )
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
    """List keywords for a customer, optionally scoped to a campaign and/or ad group.

    Args:
        customer_id: 10-digit ID. Defaults to `default_customer_id` in credentials.json.
        campaign_id: Optional — restrict to keywords under this campaign.
        ad_group_id: Optional — restrict to keywords under this ad group.
    """
    cid = _resolve_customer_id(customer_id)
    filters = ["ad_group_criterion.type = 'KEYWORD'"]
    if ad_group_id:
        filters.append(f"ad_group_criterion.ad_group = 'customers/{cid}/adGroups/{ad_group_id}'")
    if campaign_id:
        filters.append(f"campaign.id = {campaign_id}")
    where = " WHERE " + " AND ".join(filters)
    query = (
        "SELECT ad_group_criterion.criterion_id, ad_group_criterion.keyword.text, "
        "ad_group_criterion.keyword.match_type, ad_group_criterion.status, "
        "ad_group_criterion.ad_group FROM ad_group_criterion" + where
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
