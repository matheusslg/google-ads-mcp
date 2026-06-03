"""Interactive setup wizard for google-ads-mcp: captures credentials and writes
them to ~/.config/google-ads-mcp/credentials.json.

This module never imports GoogleAdsClient or makes live API calls — keeps the
wizard fast to start and the runtime module independent of OAuth machinery.
"""

from __future__ import annotations

import argparse
import getpass
import json
import sys
from pathlib import Path
from typing import Any, Callable, TypeVar

from google_ads_mcp.auth import CREDENTIALS_PATH

T = TypeVar("T")

_BANNER = """\
google-ads-mcp setup
─────────────────────

Before continuing, you need:

  1. A Google Ads developer token (Test or Basic Access).
     Get one at: https://ads.google.com/aw/apicenter

  2. An OAuth 2.0 Client of type "Desktop application" from
     Google Cloud Console. To create one:

       a) Go to https://console.cloud.google.com
       b) Create or select a project
       c) APIs & Services → enable the "Google Ads API"
       d) Credentials → "Create credentials" → OAuth client ID
            → Application type: Desktop app
       e) Download the JSON (`client_secret_*.json`)

  3. Your Manager Account (MCC) ID and the ID of the Google Ads
     account you want tools to operate on by default.

Full walkthrough: docs/developer-token.md
"""


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


def _prompt_yes_no(prompt: str) -> bool:
    answer = input(prompt).strip().lower()
    return answer in ("y", "yes")


def _prompt_with_retry(
    prompt: str,
    validator: Callable[[str], T],
    *,
    secret: bool = False,
    max_attempts: int = 3,
) -> T:
    """Prompt up to ``max_attempts`` times; return validator's normalized output.

    Raises ValueError after max_attempts with a clear message.
    """
    read = getpass.getpass if secret else input
    for attempt in range(1, max_attempts + 1):
        raw = read(prompt)
        try:
            return validator(raw)
        except ValueError as e:
            remaining = max_attempts - attempt
            print(f"  Invalid: {e}", file=sys.stderr)
            if remaining > 0:
                print(
                    f"  ({remaining} attempt{'s' if remaining > 1 else ''} left)",
                    file=sys.stderr,
                )
    raise ValueError(f"Too many invalid attempts for {prompt!r}.")


def _validate_non_empty(raw: str) -> str:
    if not raw.strip():
        raise ValueError("must not be empty")
    return raw.strip()


def _validate_client_secrets_path(raw: str) -> Path:
    path = Path(raw.strip()).expanduser()
    # load_client_secrets_json raises FileNotFoundError or ValueError
    load_client_secrets_json(path)
    return path


def _run_oauth_flow(client_secrets_path: Path) -> str:
    """Run the installed-app OAuth2 flow, return the refresh_token.

    Implemented in Task 10.
    """
    raise NotImplementedError("OAuth flow lands in Task 10")


def run_setup(argv: list[str]) -> int:
    """Entry point for `google-ads-mcp setup`. Returns exit code."""
    parser = argparse.ArgumentParser(
        prog="google-ads-mcp setup",
        description="Capture Google Ads credentials and write credentials.json.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite ~/.config/google-ads-mcp/credentials.json without asking.",
    )
    args = parser.parse_args(argv)

    # Step 1 — pre-flight banner
    print(_BANNER)
    if not _prompt_yes_no("Have you completed the above? [y/N]: "):
        print("Re-run `google-ads-mcp setup` once you have the items above.")
        return 1

    # Existing-file confirmation
    if CREDENTIALS_PATH.exists() and not args.force:
        prompt = f"\nA credentials file already exists at {CREDENTIALS_PATH}\nOverwrite it? [y/N]: "
        if not _prompt_yes_no(prompt):
            return 0

    # Step 2 — prompts
    try:
        developer_token = _prompt_with_retry(
            "\nDeveloper token (input hidden): ",
            _validate_non_empty,
            secret=True,
        )
        client_secrets_path = _prompt_with_retry(
            "Path to client_secrets.json: ",
            _validate_client_secrets_path,
        )
        login_customer_id = _prompt_with_retry(
            "Manager (MCC) account ID [digits only, no dashes]: ",
            validate_customer_id,
        )
        default_customer_id = _prompt_with_retry(
            "Default Google Ads account ID [digits only, no dashes]: ",
            validate_customer_id,
        )
    except ValueError as e:
        print(f"\n{e}", file=sys.stderr)
        return 1

    # Step 3 — OAuth flow (Task 10)
    refresh_token = _run_oauth_flow(client_secrets_path)

    # Step 4 — assemble and write
    client_secrets = load_client_secrets_json(client_secrets_path)
    credentials = {
        "schema_version": 1,
        "developer_token": developer_token,
        "client_id": client_secrets["client_id"],
        "client_secret": client_secrets["client_secret"],
        "refresh_token": refresh_token,
        "login_customer_id": login_customer_id,
        "default_customer_id": default_customer_id,
        "use_proto_plus": True,
    }
    write_credentials_file(CREDENTIALS_PATH, credentials)

    # Step 5 — success
    print(f"\n✓ Credentials saved to {CREDENTIALS_PATH} (mode 0600)\n")
    print("You can now:")
    print("  • Run the server directly:           uvx google-ads-mcp")
    print('  • Or wire Claude Desktop / Cursor:   see README "Claude Desktop config" section')
    return 0
