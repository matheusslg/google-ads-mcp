"""Drafting tools for google-ads-mcp (issues #12 + #13).

Both tools here are pure Python: no Google Ads API calls, no auth, no
network. They produce human-reviewable drafts (a CSV for Google Ads Editor
import, and RSA ad copy from deterministic templates) that the caller reviews
before using the mutation tools in `mutations.py`.
"""

from __future__ import annotations

import _csv
import csv
import io
from typing import Literal

from pydantic import BaseModel

from google_ads_mcp._mcp import mcp


class KeywordDraftSpec(BaseModel):
    text: str
    match_type: Literal["Exact", "Phrase", "Broad"] = "Exact"


class AdGroupDraftSpec(BaseModel):
    name: str
    max_cpc: float
    keywords: list[KeywordDraftSpec] = []


class CampaignDraftSpec(BaseModel):
    campaign_name: str
    daily_budget: float
    campaign_type: Literal["Search"] = "Search"
    status: Literal["Enabled", "Paused"] = "Paused"
    ad_groups: list[AdGroupDraftSpec] = []


class DraftCampaignCsvResponse(BaseModel):
    csv_content: str
    row_count: int
    preview: str
    warnings: list[str] = []


class DraftRsaResponse(BaseModel):
    headlines: list[str]
    descriptions: list[str]
    language: Literal["en", "pt-br"]
    warnings: list[str] = []


_CSV_HEADER = [
    "Row Type",
    "Campaign",
    "Campaign type",
    "Budget",
    "Ad Group",
    "Max CPC",
    "Keyword",
    "Match type",
    "Status",
]


def _write_rows(writer: _csv.Writer, spec: CampaignDraftSpec) -> int:
    """Write header + campaign + ad_groups + keywords. Return row count (excluding header)."""
    writer.writerow(_CSV_HEADER)
    row_count = 0
    writer.writerow(
        [
            "Campaign",
            spec.campaign_name,
            spec.campaign_type,
            f"{spec.daily_budget:.2f}",
            "",
            "",
            "",
            "",
            spec.status,
        ]
    )
    row_count += 1
    for ag in spec.ad_groups:
        writer.writerow(
            [
                "Ad group",
                spec.campaign_name,
                "",
                "",
                ag.name,
                f"{ag.max_cpc:.2f}",
                "",
                "",
                spec.status,
            ]
        )
        row_count += 1
        for kw in ag.keywords:
            writer.writerow(
                [
                    "Keyword",
                    spec.campaign_name,
                    "",
                    "",
                    ag.name,
                    "",
                    kw.text,
                    kw.match_type,
                    spec.status,
                ]
            )
            row_count += 1
    return row_count


@mcp.tool
def draft_campaign_csv(spec: CampaignDraftSpec) -> DraftCampaignCsvResponse:
    """Draft a Google Ads Editor-importable CSV from a campaign spec.

    Google Ads Editor accepts CSV with specific columns. This tool takes a
    structured spec and produces the CSV as a string (returned as `csv_content`);
    the user reviews it and imports via Editor (Account -> Import).

    Args:
        spec: Structured description of the campaign (see `CampaignDraftSpec` fields).

    Returns the CSV content + a preview + warnings for anything that couldn't be included.
    """
    warnings: list[str] = []
    if spec.daily_budget < 1.0:
        warnings.append(
            f"daily_budget ${spec.daily_budget:.2f} is below the typical minimum of $1.00"
        )
    if not spec.ad_groups:
        warnings.append("no ad_groups specified; CSV contains only the campaign row")

    buf = io.StringIO()
    writer = csv.writer(buf, quoting=csv.QUOTE_ALL)
    row_count = _write_rows(writer, spec)

    for ag in spec.ad_groups:
        if ag.max_cpc <= 0:
            warnings.append(
                f"ad_group '{ag.name}' has max_cpc={ag.max_cpc:.2f} (must be > 0 to serve)"
            )

    csv_content = buf.getvalue()
    preview = "\n".join(csv_content.splitlines()[:5])

    return DraftCampaignCsvResponse(
        csv_content=csv_content,
        row_count=row_count,
        preview=preview,
        warnings=warnings,
    )


_HEADLINES_EN = [
    "Buy {product} Today",
    "Best {product} Online",
    "{product} for {audience}",
    "Shop {product} Now",
    "Top-Rated {product}",
    "Discover {product}",
    "Premium {product}",
    "Get {product} Fast",
    "{product} You'll Love",
    "Try {product} Today",
    "{product} Sale",
    "Save on {product}",
    "New {product}",
    "Order {product} Now",
    "{product} Made Simple",
]

# pt-br templates use gender/number-neutral phrasing on purpose (issue #34):
# imperative verbs, invariant adjectives ("premium"), and noun phrases with
# prepositions — no bare adjectives that must agree with the {product} noun.
_HEADLINES_PT_BR = [
    "Compre {product}",
    "Melhor {product}",
    "{product} para {audience}",
    "Compre {product} agora",
    "{product} online",
    "Descubra {product}",
    "{product} premium",
    "Peça {product} já",
    "{product} de qualidade",
    "Experimente {product}",
    "Promoção {product}",
    "Economize em {product}",
    "Confira {product}",
    "Entrega de {product}",
    "Só aqui: {product}",
]

_DESCRIPTIONS_EN = [
    "Discover {product} designed for {audience}. Order now with fast shipping.",
    "Premium {product} at the best price. Perfect for {audience}. Shop today.",
    "Trusted by {audience} everywhere. Get {product} with our satisfaction guarantee.",
    "Shop {product} online. Great selection for {audience}, delivered fast.",
]

# Descriptions also use gender/number-neutral phrasing — no adjectives that
# must agree with {product} (e.g. "feito" was dropped since it agrees with the
# noun's gender/number).
_DESCRIPTIONS_PT_BR = [
    "Descubra {product} para {audience}. Peça agora com entrega rápida.",
    "{product} premium ao melhor preço. Ideal para {audience}. Compre hoje.",
    "A confiança de {audience}. Peça {product} com garantia de satisfação.",
    "Compre {product} online. Ótima seleção para {audience}, entrega rápida.",
]


def _render(
    templates: list[str],
    substitutions: dict[str, str],
    max_len: int,
    kind: str,
) -> tuple[list[str], list[str]]:
    """Format each template with substitutions; truncate any that exceed max_len."""
    rendered = []
    warnings = []
    for i, tmpl in enumerate(templates):
        s = tmpl.format(**substitutions)
        if len(s) > max_len:
            warnings.append(f"{kind} #{i + 1} truncated from {len(s)} to {max_len} chars")
            s = s[: max_len - 3] + "..."
        rendered.append(s)
    return rendered, warnings


@mcp.tool
def draft_responsive_search_ad(
    product_description: str,
    target_audience: str,
    language: Literal["en", "pt-br"] = "en",
) -> DraftRsaResponse:
    """Draft 15 RSA headlines (<=30 chars) + 4 descriptions (<=90 chars).

    Uses deterministic templates - the LLM caller (Claude) reviews the output
    and can refine, replace, or regenerate via editing the response. For truly
    creative copy, the caller should iterate.

    Args:
        product_description: What's being sold. e.g. "handmade leather boots".
        target_audience: Who it's for. e.g. "outdoor enthusiasts in the US".
        language: Output language. English or Brazilian Portuguese.

    Returns 15 headlines + 4 descriptions, each within RSA character limits.
    Warnings if any template overflows and gets truncated.
    """
    if language == "pt-br":
        headline_templates = _HEADLINES_PT_BR
        description_templates = _DESCRIPTIONS_PT_BR
    else:
        headline_templates = _HEADLINES_EN
        description_templates = _DESCRIPTIONS_EN

    subs = {"product": product_description, "audience": target_audience}
    headlines, h_warnings = _render(headline_templates, subs, max_len=30, kind="headline")
    descriptions, d_warnings = _render(description_templates, subs, max_len=90, kind="description")

    return DraftRsaResponse(
        headlines=headlines,
        descriptions=descriptions,
        language=language,
        warnings=h_warnings + d_warnings,
    )
