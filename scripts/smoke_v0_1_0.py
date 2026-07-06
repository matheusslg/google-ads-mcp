"""Smoke test the v0.1.0 read-only tool surface against a real Google Ads account.

Run: `uv run python scripts/smoke_v0_1_0.py`

Requires: `~/.config/google-ads-mcp/credentials.json` (via `google-ads-mcp setup`).
Prints per-tool status + one-line data summary. Exits 1 if any tool errors.
"""

from __future__ import annotations

import json
import sys
import traceback
from typing import Any, Callable

from google_ads_mcp.tools.audits import (
    audit_account_health,
    find_negative_keyword_candidates,
)
from google_ads_mcp.tools.reads import (
    list_accessible_customers,
    list_ad_groups,
    list_campaigns,
    list_keywords,
)
from google_ads_mcp.tools.reports import (
    get_performance,
    list_search_terms,
    summarize_performance,
)


def _summarize(name: str, payload: dict[str, Any]) -> str:
    if "customers" in payload:
        return f"{len(payload['customers'])} accessible customer(s)"
    if "campaigns" in payload:
        return f"{len(payload['campaigns'])} campaign(s)"
    if "ad_groups" in payload:
        return f"{len(payload['ad_groups'])} ad group(s)"
    if "keywords" in payload:
        return f"{len(payload['keywords'])} keyword(s)"
    if "rows" in payload:
        return f"{len(payload['rows'])} performance row(s)"
    if "search_terms" in payload:
        return f"{len(payload['search_terms'])} search term(s)"
    if "narrative" in payload:
        return payload["narrative"][:100] + ("..." if len(payload["narrative"]) > 100 else "")
    if "candidates" in payload:
        return f"{len(payload['candidates'])} candidate(s)"
    if "checks" in payload:
        return f"overall={payload['overall']}; {len(payload['checks'])} check(s)"
    return json.dumps(payload)[:100]


def run(name: str, fn: Callable[[], Any]) -> bool:
    print(f"\n▶ {name}")
    try:
        result = fn()
        payload = result.model_dump() if hasattr(result, "model_dump") else result
        print(f"  ✓ OK — {_summarize(name, payload)}")
        if payload.get("warnings"):
            print(f"  ⚠  warnings: {payload['warnings']}")
        return True
    except Exception as e:
        # Extract useful message for GoogleAdsException; str(e) is gRPC gibberish.
        from google.ads.googleads.errors import GoogleAdsException as _GAE

        if isinstance(e, _GAE) and e.failure and e.failure.errors:
            msg = "; ".join(err.message for err in e.failure.errors)
            print(f"  ✗ FAIL — {type(e).__name__}: {msg}")
        else:
            print(f"  ✗ FAIL — {type(e).__name__}: {e}")
        return False


def main() -> int:
    print("google-ads-mcp v0.1.0 — smoke test")
    print("=" * 60)

    tests: list[tuple[str, Callable[[], Any]]] = [
        ("list_accessible_customers()", list_accessible_customers),
        ("list_campaigns()", list_campaigns),
        ("list_ad_groups()", list_ad_groups),
        ("list_keywords()", list_keywords),
        ("get_performance()", get_performance),
        ("list_search_terms()", list_search_terms),
        ("summarize_performance()", summarize_performance),
        ("find_negative_keyword_candidates()", find_negative_keyword_candidates),
        ("audit_account_health()", audit_account_health),
    ]

    passed = sum(run(name, fn) for name, fn in tests)
    total = len(tests)

    print(f"\n{'=' * 60}")
    print(f"Result: {passed}/{total} tools OK")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
