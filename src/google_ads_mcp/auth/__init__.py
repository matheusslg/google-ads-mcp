"""Runtime credential loading and GoogleAdsClient construction for google-ads-mcp.

The interactive setup helper lives in `google_ads_mcp.auth.setup`; this module
is what the server and tool modules import at request time.
"""

from __future__ import annotations

from pathlib import Path

CREDENTIALS_PATH: Path = Path.home() / ".config" / "google-ads-mcp" / "credentials.json"

REQUIRED_FIELDS: tuple[str, ...] = (
    "schema_version",
    "developer_token",
    "client_id",
    "client_secret",
    "refresh_token",
    "login_customer_id",
    "default_customer_id",
    "use_proto_plus",
)

_DEFAULT_API_VERSION = "v24"  # verify at scaffold time per spec § Verification


class CredentialsError(Exception):
    """Base class for credential-loading failures."""


class CredentialsNotFound(CredentialsError):
    """credentials.json does not exist."""


class CredentialsMalformed(CredentialsError):
    """credentials.json exists but is invalid JSON or missing required fields."""


class CredentialsRevoked(CredentialsError):
    """The refresh token has been revoked or expired."""
