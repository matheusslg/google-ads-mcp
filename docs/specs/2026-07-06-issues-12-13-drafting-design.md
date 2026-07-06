# Design: Drafting tools (Issues #12 + #13)

**Date**: 2026-07-06
**Issues**: [#12 draft_campaign_csv](https://github.com/matheusslg/google-ads-mcp/issues/12), [#13 draft_responsive_search_ad](https://github.com/matheusslg/google-ads-mcp/issues/13)
**Branch**: `feat/phase-2-drafting`

Both are pure Python — no Google API calls. Both go in one new file: `src/google_ads_mcp/tools/drafts.py`.

---

## Issue #12: `draft_campaign_csv`

### Signature

```python
@mcp.tool
def draft_campaign_csv(spec: CampaignDraftSpec) -> DraftCampaignCsvResponse:
    """Draft a Google Ads Editor-importable CSV from a campaign spec.

    Google Ads Editor accepts CSV with specific columns. This tool takes a
    structured spec and produces the CSV as a string (returned as `csv_content`);
    the user reviews it and imports via Editor (Account → Import).

    Args:
        spec: Structured description of the campaign (see `CampaignDraftSpec` fields).

    Returns the CSV content + a preview + warnings for anything that couldn't be included.
    """
```

### Pydantic input model

```python
class CampaignDraftSpec(BaseModel):
    campaign_name: str
    daily_budget: float                 # dollars
    campaign_type: Literal["Search"] = "Search"   # only Search for v0.3
    status: Literal["Enabled", "Paused"] = "Paused"  # Draft = paused by default (safety)
    ad_groups: list[AdGroupDraftSpec] = []

class AdGroupDraftSpec(BaseModel):
    name: str
    max_cpc: float                      # dollars
    keywords: list[KeywordDraftSpec] = []

class KeywordDraftSpec(BaseModel):
    text: str
    match_type: Literal["Exact", "Phrase", "Broad"] = "Exact"

class DraftCampaignCsvResponse(BaseModel):
    csv_content: str
    row_count: int
    preview: str  # first 5 lines
    warnings: list[str] = []
```

### CSV format

Google Ads Editor v2 CSV — one row per entity, with a `Row Type` first column:

```
Row Type,Campaign,Campaign type,Budget,Ad Group,Max CPC,Keyword,Match type,Status
Campaign,"Summer Sale","Search",50.00,,,,,"Paused"
Ad group,"Summer Sale",,,"Ad Group A",1.50,,,"Paused"
Keyword,"Summer Sale",,,"Ad Group A",,"buy shoes","Exact","Paused"
Keyword,"Summer Sale",,,"Ad Group A",,"cheap shoes","Broad","Paused"
```

Use `csv.writer` from stdlib. Quote all fields. `Status` field always echoes the spec's status.

Warnings for: no ad_groups (empty keywords section), max_cpc = 0, budget < $1 (Google's minimum for many locales).

### Tests (`tests/tools/test_drafts.py`)

- `test_draft_campaign_csv_produces_row_per_entity` — 1 campaign + 2 ad groups + 3 keywords → 6 rows + header
- `test_draft_campaign_csv_header_matches_editor_format` — first line contains "Row Type,Campaign,..." fields
- `test_draft_campaign_csv_status_defaults_to_paused` — safety default
- `test_draft_campaign_csv_warns_on_zero_budget` — budget=0 → warnings
- `test_draft_campaign_csv_quotes_names_with_commas` — campaign name "Sale, Summer" → quoted in CSV
- `test_draft_campaign_csv_preview_first_5_lines` — preview is exactly first 5 lines

---

## Issue #13: `draft_responsive_search_ad`

### Signature

```python
@mcp.tool
def draft_responsive_search_ad(
    product_description: str,
    target_audience: str,
    language: Literal["en", "pt-br"] = "en",
) -> DraftRsaResponse:
    """Draft 15 RSA headlines (≤30 chars) + 4 descriptions (≤90 chars).

    Uses deterministic templates — the LLM caller (Claude) reviews the output
    and can refine, replace, or regenerate via editing the response. For truly
    creative copy, the caller should iterate.

    Args:
        product_description: What's being sold. e.g. "handmade leather boots".
        target_audience: Who it's for. e.g. "outdoor enthusiasts in the US".
        language: Output language. English or Brazilian Portuguese.

    Returns 15 headlines + 4 descriptions, each within RSA character limits.
    Warnings if any template overflows and gets truncated.
    """
```

### Model

```python
class DraftRsaResponse(BaseModel):
    headlines: list[str]        # exactly 15, each len <= 30
    descriptions: list[str]     # exactly 4, each len <= 90
    language: Literal["en", "pt-br"]
    warnings: list[str] = []
```

### Templates

Two template sets (en + pt-br). Each set has:
- 15 headline templates (mix of product-focus, audience-focus, call-to-action)
- 4 description templates

Example English headline templates:
1. `"Buy {product} Today"` — CTA
2. `"Best {product} Online"` — superlative
3. `"{product} - {audience}"` — direct
4. `"Shop {product} Now"` — CTA
...

Descriptions (~30-80 chars each), same substitution pattern.

**Char limit enforcement**: after substitution, if a headline > 30 chars, **truncate** at 27 chars + "..." AND add a warning `"headline #N truncated (was M chars)"`. Same for descriptions (>90 → truncate at 87 + "...").

Extract into helper `_render(templates: list[str], substitutions: dict[str, str], max_len: int, kind: str) -> tuple[list[str], list[str]]` returning (rendered, warnings).

### Tests

- `test_draft_rsa_returns_15_headlines_and_4_descriptions` — exact counts
- `test_draft_rsa_all_headlines_under_30_chars` — enforced even after substitution
- `test_draft_rsa_all_descriptions_under_90_chars` — same
- `test_draft_rsa_truncates_long_substitutions_with_warning` — very long product_description → warning + truncation
- `test_draft_rsa_pt_br_uses_portuguese_templates` — output contains Portuguese-language words
- `test_draft_rsa_headlines_incorporate_product_description` — at least half contain the product word

---

## Out of scope (both)

- Multiple campaign types (only Search for v0.3)
- Ad extensions (sitelinks, callouts, etc.)
- Image assets for RSAs
- Localization beyond en + pt-br

---

*Autonomous per `/goal`. Both tools land in one PR.*
