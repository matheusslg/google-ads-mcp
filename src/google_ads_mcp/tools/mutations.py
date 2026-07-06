"""Campaign state mutation tools for google-ads-mcp.

First mutation tools (issue #8). Establishes the `MutationResponse` envelope
and `dry_run: bool = False` contract that later mutation issues reuse.
"""

from __future__ import annotations

from typing import Literal

from google.ads.googleads.errors import GoogleAdsException
from pydantic import BaseModel

from google_ads_mcp._mcp import mcp
from google_ads_mcp.tools import reads
from google_ads_mcp.tools.reads import _raise_friendly, _resolve_customer_id, _search

_TargetStatus = Literal["ENABLED", "PAUSED"]


class MutationResponse(BaseModel):
    success: bool
    dry_run: bool = False
    mutation_id: str | None = None  # resource name from SDK response
    before: dict[str, str] = {}
    after: dict[str, str] = {}
    warnings: list[str] = []


def _get_campaign_status(customer_id: str, campaign_id: str) -> str:
    """Fetch the current status of a single campaign, or raise ValueError."""
    rows, _ = _search(
        customer_id,
        f"SELECT campaign.id, campaign.status FROM campaign WHERE campaign.id = {campaign_id}",
    )
    if not rows:
        raise ValueError(f"campaign {campaign_id} not found under customer {customer_id}")
    status: str = rows[0].campaign.status.name
    return status


def _mutate_campaign_status(customer_id: str, campaign_id: str, target: _TargetStatus) -> str:
    """Send the CampaignService update mutation; return the resulting resource name."""
    client = reads.get_google_ads_client()
    service = client.get_service("CampaignService")
    campaign = client.get_type("Campaign")
    campaign.resource_name = f"customers/{customer_id}/campaigns/{campaign_id}"
    campaign.status = getattr(client.enums.CampaignStatusEnum, target)
    op = client.get_type("CampaignOperation")
    op.update = campaign
    op.update_mask.paths.append("status")
    try:
        response = service.mutate_campaigns(customer_id=customer_id, operations=[op])
    except GoogleAdsException as e:
        _raise_friendly(e)
    mutation_id: str = response.results[0].resource_name
    return mutation_id


def _set_campaign_status(
    campaign_id: str,
    customer_id: str | None,
    dry_run: bool,
    target: _TargetStatus,
    reason: str | None = None,
) -> MutationResponse:
    cid = _resolve_customer_id(customer_id)
    current = _get_campaign_status(cid, campaign_id)
    warnings = [f"reason: {reason}"] if reason else []

    if current == target:
        return MutationResponse(
            success=True,
            dry_run=dry_run,
            before={"status": current},
            after={"status": current},
            warnings=[*warnings, f"campaign {campaign_id} is already {target}; no-op"],
        )

    before: dict[str, str] = {"status": current}
    after: dict[str, str] = {"status": target}

    if dry_run:
        return MutationResponse(
            success=True, dry_run=True, before=before, after=after, warnings=warnings
        )

    mutation_id = _mutate_campaign_status(cid, campaign_id, target)
    return MutationResponse(
        success=True,
        dry_run=False,
        mutation_id=mutation_id,
        before=before,
        after=after,
        warnings=warnings,
    )


@mcp.tool
def pause_campaign(
    campaign_id: str,
    customer_id: str | None = None,
    dry_run: bool = False,
    reason: str | None = None,
) -> MutationResponse:
    """Pause a Google Ads campaign.

    Args:
        campaign_id: The campaign to pause (numeric ID as string).
        customer_id: 10-digit ID; defaults to `default_customer_id`.
        dry_run: When True, don't call the API — return the projected `after` state only.
        reason: Optional free-text reason (echoed in `warnings` for audit).

    Returns MutationResponse with before/after status and (on real mutations) a mutation_id.
    Callers should generally confirm with the human before setting dry_run=False.
    """
    return _set_campaign_status(campaign_id, customer_id, dry_run, "PAUSED", reason)


@mcp.tool
def enable_campaign(
    campaign_id: str,
    customer_id: str | None = None,
    dry_run: bool = False,
) -> MutationResponse:
    """Enable a paused Google Ads campaign. Same envelope + dry_run pattern as pause_campaign."""
    return _set_campaign_status(campaign_id, customer_id, dry_run, "ENABLED")
