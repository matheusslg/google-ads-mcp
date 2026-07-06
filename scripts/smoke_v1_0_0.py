"""Smoke test the v1.0.0 mutation + drafting surface.

Read tools are covered by scripts/smoke_v0_1_0.py — run that first.

This script:
- Reads one real campaign / ad_group / keyword from the account
- Dry-runs every mutation tool against those IDs (never commits — dry_run=True)
- Exercises the drafting tools (pure Python, no API)
- Reports per-tool status
"""

from __future__ import annotations

import sys
from typing import Any

from google_ads_mcp.tools.drafts import (
    AdGroupDraftSpec,
    CampaignDraftSpec,
    KeywordDraftSpec,
    draft_campaign_csv,
    draft_responsive_search_ad,
)
from google_ads_mcp.tools.mutations import (
    ChangeSetItem,
    add_negative_keywords,
    dry_run_changes,
    enable_campaign,
    pause_campaign,
    update_campaign_budget,
    update_keyword_bid,
)
from google_ads_mcp.tools.reads import (
    list_ad_groups,
    list_campaigns,
    list_keywords,
)


def _fetch_ids() -> dict[str, str]:
    """Grab one campaign, one ad_group, one keyword from the account."""
    campaigns = list_campaigns().campaigns
    if not campaigns:
        raise RuntimeError("no campaigns available for smoke test")
    campaign_id = campaigns[0].id

    ad_groups = list_ad_groups(campaign_id=campaign_id).ad_groups
    if not ad_groups:
        raise RuntimeError(f"campaign {campaign_id} has no ad groups")
    ad_group_id = ad_groups[0].id

    keywords = list_keywords(ad_group_id=ad_group_id).keywords
    keyword_id = keywords[0].id if keywords else ""

    return {
        "campaign_id": campaign_id,
        "campaign_status": campaigns[0].status,
        "ad_group_id": ad_group_id,
        "keyword_id": keyword_id,
    }


def _fmt_response(name: str, resp: Any) -> str:
    """Compact one-line rendering of a MutationResponse."""
    parts = [
        f"success={resp.success}",
        f"dry_run={resp.dry_run}",
        f"before={dict(resp.before)}",
        f"after={dict(resp.after)}",
    ]
    if resp.warnings:
        parts.append(f"warnings={resp.warnings[:2]}")
    return f"  {name}: " + " | ".join(parts)


def run(name: str, fn: Any) -> bool:
    print(f"\n▶ {name}")
    try:
        result = fn()
        if hasattr(result, "success"):
            print(_fmt_response("result", result))
        else:
            print(f"  ✓ {result}")
        return True
    except Exception as e:
        print(f"  ✗ FAIL — {type(e).__name__}: {e}")
        return False


def main() -> int:
    print("google-ads-mcp v1.0.0 — mutation + drafting smoke")
    print("=" * 66)

    print("\nFetching real IDs from the account...")
    ids = _fetch_ids()
    print(f"  campaign_id  : {ids['campaign_id']} (currently {ids['campaign_status']})")
    print(f"  ad_group_id  : {ids['ad_group_id']}")
    print(f"  keyword_id   : {ids['keyword_id'] or '(none in this ad group)'}")

    print("\n" + "-" * 66)
    print("MUTATIONS (all with dry_run=True — no API calls)")
    print("-" * 66)

    passed = 0
    total = 0

    # 1. pause_campaign dry-run
    total += 1
    if run(
        "pause_campaign (dry_run=True)",
        lambda: pause_campaign(campaign_id=ids["campaign_id"], dry_run=True),
    ):
        passed += 1

    # 2. enable_campaign dry-run
    total += 1
    if run(
        "enable_campaign (dry_run=True)",
        lambda: enable_campaign(campaign_id=ids["campaign_id"], dry_run=True),
    ):
        passed += 1

    # 3. update_campaign_budget — under-cap
    total += 1
    if run(
        "update_campaign_budget +10% (should pass default 50% cap)",
        lambda: update_campaign_budget(
            campaign_id=ids["campaign_id"], new_amount=1.1, dry_run=True
        ),
    ):
        passed += 1

    # 4. update_campaign_budget — over-cap (guardrail proof)
    total += 1
    if run(
        "update_campaign_budget 10x (over default cap — expect success=False)",
        lambda: update_campaign_budget(
            campaign_id=ids["campaign_id"], new_amount=10_000.0, dry_run=True
        ),
    ):
        passed += 1

    # 5. update_keyword_bid — only if we have a keyword
    if ids["keyword_id"]:
        total += 1
        if run(
            "update_keyword_bid (dry_run=True)",
            lambda: update_keyword_bid(
                ad_group_id=ids["ad_group_id"],
                criterion_id=ids["keyword_id"],
                new_bid=0.5,
                dry_run=True,
            ),
        ):
            passed += 1

    # 6. add_negative_keywords
    total += 1
    if run(
        "add_negative_keywords (dry_run=True)",
        lambda: add_negative_keywords(
            scope="ad_group",
            target_id=ids["ad_group_id"],
            keywords=["smoke test negative"],
            dry_run=True,
        ),
    ):
        passed += 1

    # 7. dry_run_changes — 2-item change set
    total += 1
    if run(
        "dry_run_changes (2-item change set)",
        lambda: dry_run_changes(
            [
                ChangeSetItem(tool="pause_campaign", args={"campaign_id": ids["campaign_id"]}),
                ChangeSetItem(
                    tool="update_campaign_budget",
                    args={"campaign_id": ids["campaign_id"], "new_amount": 2.0},
                ),
            ]
        ),
    ):
        passed += 1

    print("\n" + "-" * 66)
    print("DRAFTING (no API — pure Python)")
    print("-" * 66)

    # 8. draft_campaign_csv
    total += 1
    if run(
        "draft_campaign_csv",
        lambda: draft_campaign_csv(
            CampaignDraftSpec(
                campaign_name="Smoke Test v1",
                daily_budget=25.0,
                ad_groups=[
                    AdGroupDraftSpec(
                        name="AG-1",
                        max_cpc=1.50,
                        keywords=[
                            KeywordDraftSpec(text="handmade shoes"),
                            KeywordDraftSpec(text="leather boots", match_type="Phrase"),
                        ],
                    )
                ],
            )
        ),
    ):
        passed += 1

    # 9. draft_responsive_search_ad — English
    total += 1
    if run(
        "draft_responsive_search_ad (en)",
        lambda: draft_responsive_search_ad(
            product_description="leather boots",
            target_audience="hikers",
            language="en",
        ),
    ):
        passed += 1

    # 10. draft_responsive_search_ad — pt-br
    total += 1
    if run(
        "draft_responsive_search_ad (pt-br)",
        lambda: draft_responsive_search_ad(
            product_description="botas",
            target_audience="trilheiros",
            language="pt-br",
        ),
    ):
        passed += 1

    print("\n" + "=" * 66)
    print(f"Result: {passed}/{total} tools OK")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
