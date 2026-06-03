"""Interactive setup wizard for google-ads-mcp: captures credentials and writes
them to ~/.config/google-ads-mcp/credentials.json.

This module never imports GoogleAdsClient or makes live API calls — keeps the
wizard fast to start and the runtime module independent of OAuth machinery.
"""

from __future__ import annotations


def validate_customer_id(raw: str) -> str:
    """Normalize and validate a Google Ads customer ID.

    Accepts the dashed form (``123-456-7890``) or plain digits (``1234567890``).
    Returns the normalized 10-digit string, or raises ValueError.
    """
    normalized = raw.replace("-", "").strip()
    if not normalized.isdigit():
        raise ValueError(f"Customer ID must contain only digits (got: {raw!r}).")
    if len(normalized) != 10:
        raise ValueError(f"Customer ID must be 10 digits (got {len(normalized)}: {raw!r}).")
    return normalized
