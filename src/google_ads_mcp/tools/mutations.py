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


def _check_guardrails(
    current_dollars: float,
    new_dollars: float,
    *,
    max_increase_percent: float | None,
    absolute_cap: float | None,
) -> tuple[bool, list[str]]:
    """Return (allowed, warnings). warnings always populated; if not allowed, includes reason(s)."""
    warnings: list[str] = []
    allowed = True

    if max_increase_percent is None and absolute_cap is None:
        max_increase_percent = 50.0
        warnings.append("default max_increase_percent=50 applied (no explicit cap supplied)")

    if absolute_cap is not None and new_dollars > absolute_cap:
        allowed = False
        warnings.append(f"new amount ${new_dollars:.2f} exceeds absolute_cap ${absolute_cap:.2f}")

    if max_increase_percent is not None and new_dollars > current_dollars:
        if current_dollars == 0:
            warnings.append("current amount is 0; max_increase_percent skipped")
        else:
            delta_pct = (new_dollars - current_dollars) / current_dollars * 100
            if delta_pct > max_increase_percent:
                allowed = False
                warnings.append(
                    f"increase +{delta_pct:.1f}% exceeds max_increase_percent "
                    f"{max_increase_percent}% "
                    f"(current ${current_dollars:.2f} → new ${new_dollars:.2f})"
                )

    return allowed, warnings


@mcp.tool
def update_campaign_budget(
    campaign_id: str,
    new_amount: float,
    customer_id: str | None = None,
    max_increase_percent: float | None = None,
    absolute_cap: float | None = None,
    dry_run: bool = False,
) -> MutationResponse:
    """Update a campaign's daily budget with mandatory guardrails.

    Args:
        campaign_id: The campaign whose budget to update (numeric ID as string).
        new_amount: New daily budget in dollars (e.g. 50.00).
        customer_id: 10-digit ID; defaults to `default_customer_id`.
        max_increase_percent: Refuse if the increase exceeds this percent of current.
        absolute_cap: Refuse if new_amount exceeds this dollar value.
        dry_run: When True, don't call the API — return the projected before/after only.

    If both max_increase_percent and absolute_cap are omitted, defaults to
    max_increase_percent=50 (per PRD § Risks mitigation). Refuses (returns
    success=False, no API call) if the new amount would exceed any active cap.
    """
    cid = _resolve_customer_id(customer_id)
    rows, _ = _search(
        cid,
        "SELECT campaign.id, campaign_budget.id, campaign_budget.amount_micros "
        f"FROM campaign WHERE campaign.id = {campaign_id}",
    )
    if not rows:
        raise ValueError(f"campaign {campaign_id} not found under customer {cid}")
    row = rows[0]
    budget_id = row.campaign_budget.id
    if not budget_id:
        raise ValueError("campaign has no budget attached")

    current_micros = row.campaign_budget.amount_micros
    current_dollars = current_micros / 1_000_000
    new_micros = round(new_amount * 1_000_000)
    before = {"amount": f"${current_dollars:.2f}", "amount_micros": str(current_micros)}
    after = {"amount": f"${new_amount:.2f}", "amount_micros": str(new_micros)}

    allowed, warnings = _check_guardrails(
        current_dollars,
        new_amount,
        max_increase_percent=max_increase_percent,
        absolute_cap=absolute_cap,
    )
    if not allowed:
        return MutationResponse(
            success=False, dry_run=dry_run, before=before, after=after, warnings=warnings
        )

    if dry_run:
        return MutationResponse(
            success=True, dry_run=True, before=before, after=after, warnings=warnings
        )

    client = reads.get_google_ads_client()
    service = client.get_service("CampaignBudgetService")
    budget = client.get_type("CampaignBudget")
    budget.resource_name = f"customers/{cid}/campaignBudgets/{budget_id}"
    budget.amount_micros = new_micros
    op = client.get_type("CampaignBudgetOperation")
    op.update = budget
    op.update_mask.paths.append("amount_micros")
    try:
        response = service.mutate_campaign_budgets(customer_id=cid, operations=[op])
    except GoogleAdsException as e:
        _raise_friendly(e)
    mutation_id: str = response.results[0].resource_name

    return MutationResponse(
        success=True,
        dry_run=False,
        mutation_id=mutation_id,
        before=before,
        after=after,
        warnings=warnings,
    )


@mcp.tool
def update_keyword_bid(
    ad_group_id: str,
    criterion_id: str,
    new_bid: float,
    customer_id: str | None = None,
    max_bid_cap: float | None = None,
    dry_run: bool = False,
) -> MutationResponse:
    """Update a keyword's max CPC bid with an absolute cap guardrail.

    Args:
        ad_group_id: Ad group containing the keyword (keyword IDs are only unique
            within an ad group).
        criterion_id: The keyword criterion to update (numeric ID as string).
        new_bid: New max CPC bid in dollars (e.g. 1.20).
        customer_id: 10-digit ID; defaults to `default_customer_id`.
        max_bid_cap: Refuse if new_bid exceeds this dollar value. If omitted,
            defaults to current_bid x 1.5 (50% ceiling).
        dry_run: When True, don't call the API — return the projected before/after only.
    """
    cid = _resolve_customer_id(customer_id)
    rows, _ = _search(
        cid,
        "SELECT ad_group_criterion.criterion_id, ad_group_criterion.cpc_bid_micros "
        "FROM ad_group_criterion "
        f"WHERE ad_group_criterion.ad_group = 'customers/{cid}/adGroups/{ad_group_id}' "
        f"AND ad_group_criterion.criterion_id = {criterion_id}",
    )
    if not rows:
        raise ValueError(
            f"criterion {criterion_id} not found in ad group {ad_group_id} under customer {cid}"
        )
    row = rows[0]
    current_micros = row.ad_group_criterion.cpc_bid_micros
    current_dollars = current_micros / 1_000_000
    new_micros = round(new_bid * 1_000_000)
    before = {"bid": f"${current_dollars:.2f}", "bid_micros": str(current_micros)}
    after = {"bid": f"${new_bid:.2f}", "bid_micros": str(new_micros)}

    warnings: list[str] = []
    if max_bid_cap is None:
        max_bid_cap = current_dollars * 1.5
        warnings.append(f"default max_bid_cap=${max_bid_cap:.2f} (current x 1.5) applied")

    if new_bid > max_bid_cap:
        warnings.append(f"new bid ${new_bid:.2f} exceeds max_bid_cap ${max_bid_cap:.2f}")
        return MutationResponse(
            success=False, dry_run=dry_run, before=before, after=after, warnings=warnings
        )

    if dry_run:
        return MutationResponse(
            success=True, dry_run=True, before=before, after=after, warnings=warnings
        )

    client = reads.get_google_ads_client()
    service = client.get_service("AdGroupCriterionService")
    criterion = client.get_type("AdGroupCriterion")
    criterion.resource_name = f"customers/{cid}/adGroupCriteria/{ad_group_id}~{criterion_id}"
    criterion.cpc_bid_micros = new_micros
    op = client.get_type("AdGroupCriterionOperation")
    op.update = criterion
    op.update_mask.paths.append("cpc_bid_micros")
    try:
        response = service.mutate_ad_group_criteria(customer_id=cid, operations=[op])
    except GoogleAdsException as e:
        _raise_friendly(e)
    mutation_id: str = response.results[0].resource_name

    return MutationResponse(
        success=True,
        dry_run=False,
        mutation_id=mutation_id,
        before=before,
        after=after,
        warnings=warnings,
    )
