"""Interactive setup wizard for google-ads-mcp: captures credentials and writes
them to ~/.config/google-ads-mcp/credentials.json.

This module never imports GoogleAdsClient or makes live API calls — keeps the
wizard fast to start and the runtime module independent of OAuth machinery.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


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


def write_credentials_file(path: Path, credentials: dict[str, Any]) -> None:
    """Write the credentials dict to ``path`` with mode 0600.

    Creates the parent directory (mode 0700) if it does not exist. The chmod
    is applied explicitly after write_text because umask can mask the mode
    argument on macOS / some Linux configs.
    """
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    # mkdir's mode is masked by umask on some platforms; force the mode:
    path.parent.chmod(0o700)

    path.write_text(json.dumps(credentials, indent=2) + "\n")
    path.chmod(0o600)


def load_client_secrets_json(path: Path) -> dict[str, str]:
    """Parse a Google Cloud Console client_secrets.json file.

    Returns a dict with ``client_id`` and ``client_secret`` keys, extracted
    from either the ``installed`` (Desktop application) or ``web`` block.

    Raises:
        FileNotFoundError: if the path doesn't exist.
        ValueError: if neither ``installed`` nor ``web`` block is present, or
            the block is missing client_id / client_secret.
    """
    if not path.exists():
        raise FileNotFoundError(f"client_secrets.json not found at {path}")

    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError as e:
        raise ValueError(f"{path} is not valid JSON: {e.msg}") from e

    block = data.get("installed") or data.get("web")
    if block is None:
        raise ValueError(
            f"{path} has no 'installed' or 'web' block — is this a "
            "Desktop application OAuth client? Re-download from Google Cloud Console."
        )

    if "client_id" not in block or "client_secret" not in block:
        raise ValueError(f"{path} is missing client_id or client_secret in the OAuth block.")

    return {
        "client_id": block["client_id"],
        "client_secret": block["client_secret"],
    }
