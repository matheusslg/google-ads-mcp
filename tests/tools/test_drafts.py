"""Tests for google_ads_mcp.tools.drafts (draft_campaign_csv, draft_responsive_search_ad).

Both tools are pure Python (no Google Ads API calls) so these tests need no mocks.
"""

from __future__ import annotations

from google_ads_mcp.tools.drafts import (
    AdGroupDraftSpec,
    CampaignDraftSpec,
    KeywordDraftSpec,
    draft_campaign_csv,
    draft_responsive_search_ad,
)

# --- draft_campaign_csv -----------------------------------------------------


def _sample_spec() -> CampaignDraftSpec:
    return CampaignDraftSpec(
        campaign_name="Summer Sale",
        daily_budget=50.0,
        status="Paused",
        ad_groups=[
            AdGroupDraftSpec(
                name="Ad Group A",
                max_cpc=1.5,
                keywords=[
                    KeywordDraftSpec(text="buy shoes", match_type="Exact"),
                    KeywordDraftSpec(text="cheap shoes", match_type="Broad"),
                ],
            ),
            AdGroupDraftSpec(name="Ad Group B", max_cpc=2.0, keywords=[]),
        ],
    )


def test_draft_campaign_csv_produces_row_per_entity() -> None:
    resp = draft_campaign_csv(_sample_spec())
    # 1 campaign + 2 ad groups + 2 keywords = 5 rows (excludes header)
    assert resp.row_count == 5
    lines = resp.csv_content.splitlines()
    assert len(lines) == 6  # header + 5 rows


def test_draft_campaign_csv_header_matches_editor_format() -> None:
    resp = draft_campaign_csv(_sample_spec())
    header = resp.csv_content.splitlines()[0]
    assert header == (
        '"Row Type","Campaign","Campaign type","Budget","Ad Group",'
        '"Max CPC","Keyword","Match type","Status"'
    )


def test_draft_campaign_csv_status_defaults_to_paused() -> None:
    spec = CampaignDraftSpec(campaign_name="X", daily_budget=10.0)
    assert spec.status == "Paused"
    resp = draft_campaign_csv(spec)
    campaign_row = resp.csv_content.splitlines()[1]
    assert '"Paused"' in campaign_row


def test_draft_campaign_csv_warns_on_zero_budget() -> None:
    spec = CampaignDraftSpec(campaign_name="X", daily_budget=0.0)
    resp = draft_campaign_csv(spec)
    assert any("daily_budget" in w for w in resp.warnings)


def test_draft_campaign_csv_quotes_names_with_commas() -> None:
    spec = CampaignDraftSpec(campaign_name="Sale, Summer", daily_budget=10.0)
    resp = draft_campaign_csv(spec)
    campaign_row = resp.csv_content.splitlines()[1]
    assert '"Sale, Summer"' in campaign_row


def test_draft_campaign_csv_preview_first_5_lines() -> None:
    resp = draft_campaign_csv(_sample_spec())
    all_lines = resp.csv_content.splitlines()
    assert resp.preview == "\n".join(all_lines[:5])
    assert len(resp.preview.splitlines()) == 5


# --- draft_responsive_search_ad ---------------------------------------------


def test_draft_rsa_returns_15_headlines_and_4_descriptions() -> None:
    resp = draft_responsive_search_ad("leather boots", "hikers")
    assert len(resp.headlines) == 15
    assert len(resp.descriptions) == 4


def test_draft_rsa_all_headlines_under_30_chars() -> None:
    resp = draft_responsive_search_ad("leather boots", "outdoor enthusiasts in the US")
    assert all(len(h) <= 30 for h in resp.headlines)


def test_draft_rsa_all_descriptions_under_90_chars() -> None:
    resp = draft_responsive_search_ad("leather boots", "outdoor enthusiasts in the US")
    assert all(len(d) <= 90 for d in resp.descriptions)


def test_draft_rsa_truncates_long_substitutions_with_warning() -> None:
    long_product = "a" * 50
    resp = draft_responsive_search_ad(long_product, "a" * 50)
    assert all(len(h) <= 30 for h in resp.headlines)
    assert all(len(d) <= 90 for d in resp.descriptions)
    assert any("truncated" in w for w in resp.warnings)


def test_draft_rsa_pt_br_uses_portuguese_templates() -> None:
    resp = draft_responsive_search_ad("botas", "trilheiros", language="pt-br")
    assert resp.language == "pt-br"
    assert any("Compre" in h or "Melhor" in h for h in resp.headlines)


def test_draft_rsa_headlines_incorporate_product_description() -> None:
    resp = draft_responsive_search_ad("boots", "hikers")
    count_with_product = sum(1 for h in resp.headlines if "boots" in h)
    assert count_with_product >= len(resp.headlines) // 2
