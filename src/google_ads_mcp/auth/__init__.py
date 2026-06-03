"""Runtime credential loading and GoogleAdsClient construction for google-ads-mcp.

The interactive setup helper lives in `google_ads_mcp.auth.setup`; this module
is what the server and tool modules import at request time.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from google.ads.googleads.client import GoogleAdsClient

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


def load_credentials(path: Path = CREDENTIALS_PATH) -> dict[str, Any]:
    """Read and validate the credentials file.

    Raises:
        CredentialsNotFound: if the file does not exist.
        CredentialsMalformed: if the file is not valid JSON or is missing required fields.
    """
    if not path.exists():
        raise CredentialsNotFound(
            f"Credentials not found at {path}. Run `google-ads-mcp setup` to create them."
        )
    try:
        data: dict[str, Any] = json.loads(path.read_text())
    except json.JSONDecodeError as e:
        raise CredentialsMalformed(
            f"Credentials file at {path} is not valid JSON: {e.msg}. "
            "Re-run `google-ads-mcp setup` to recreate it."
        ) from e
    missing = [f for f in REQUIRED_FIELDS if f not in data]
    if missing:
        raise CredentialsMalformed(
            f"Credentials file at {path} is missing required fields: "
            f"{', '.join(missing)}. Re-run `google-ads-mcp setup` to recreate it."
        )
    return data


def get_default_customer_id(path: Path = CREDENTIALS_PATH) -> str:
    """Return the `default_customer_id` from credentials.json."""
    value = load_credentials(path)["default_customer_id"]
    if not isinstance(value, str):
        raise CredentialsMalformed(
            f"default_customer_id must be a string, got {type(value).__name__}."
        )
    return value


def get_google_ads_client(
    path: Path = CREDENTIALS_PATH,
    api_version: str = _DEFAULT_API_VERSION,
) -> GoogleAdsClient:
    """Build a GoogleAdsClient from credentials.json.

    The SDK handles access-token refresh transparently using the refresh_token.
    If the refresh token has been revoked, the first API call raises
    `google.auth.exceptions.RefreshError`; tool code should catch it and
    re-raise as CredentialsRevoked with re-auth guidance.
    """
    config = load_credentials(path)
    sdk_config = {
        k: v for k, v in config.items() if k not in ("schema_version", "default_customer_id")
    }
    return GoogleAdsClient.load_from_dict(sdk_config, version=api_version)
