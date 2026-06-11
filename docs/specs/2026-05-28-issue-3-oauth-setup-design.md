# Design: OAuth2 setup helper & credential management (Issue #3)

**Date**: 2026-05-28
**Issue**: [#3 — OAuth2 setup helper & credential management](https://github.com/matheusslg/google-ads-mcp/issues/3)
**Status**: Approved (input to the implementation plan)
**Branch**: `feat/issue-3-oauth-setup`
**Author**: Matheus Nascimento Cavallini (with Claude Code, brainstorming-skill flow)

---

## Context

`google-ads-mcp` needs credentials before any Google Ads tool can call the API. Issue #3 delivers the one-time `google-ads-mcp setup` wizard that captures those credentials (developer token, OAuth client, refresh token, account IDs) and writes them to `~/.config/google-ads-mcp/credentials.json`, plus the runtime module the server uses to load them and build a `GoogleAdsClient`.

This is the gate between the bootstrap skeleton (#1, shipped) and the first real read tools (#4–#6). No tool can hit the API until this lands. The wizard runs against any developer-token tier — including the **Test Account** tier, which means #3 can be fully developed and used before Basic Access approval arrives.

## Reference: Google Ads Python SDK credential shape

Confirmed via the official `google-ads-python` docs (Context7). `GoogleAdsClient.load_from_dict()` accepts:

```python
{
    "developer_token": "...",
    "client_id": "...",
    "client_secret": "...",
    "refresh_token": "...",
    "login_customer_id": "1234567890",   # MCC ID, digits only
    "use_proto_plus": True,
}
client = GoogleAdsClient.load_from_dict(config, version="v24")
```

OAuth refresh tokens are generated via `google_auth_oauthlib.flow.Flow.from_client_secrets_file()` with scope `https://www.googleapis.com/auth/adwords` and a localhost loopback redirect (`http://127.0.0.1:8080`).

## Decisions

Resolved during brainstorming (2026-05-21 → 2026-05-28):

| # | Question | Choice | Rationale |
|---|---|---|---|
| 1 | `credentials.json` schema | **Single-account flat object with `schema_version: 1`** | Matches Cavallini Imóveis (single account). Forward-compat: a future schema 2 wraps in `{"accounts": {...}}` and migrates on read. Mirrors `load_from_dict()` + adds `default_customer_id`. |
| 2 | Setup helper invocation | **Subcommand: `google-ads-mcp setup`** | `main()` becomes argv-aware. Single `[project.scripts]` entry stays. Familiar pattern (git/gh/uv). Claude Desktop config unchanged. |
| 3 | CLI framework | **stdlib `argparse` + `input()` + `getpass.getpass()`** | Zero new dependency for the CLI surface. Sufficient for a 4-prompt wizard. `getpass` masks the developer token. |
| 4 | Client-secret input | **Path to `client_secrets.json`** | SDK-blessed `Flow.from_client_secrets_file()`. User pastes/drags the path. No copy-paste of long secrets. |
| 4b | Pre-flight | **Print Cloud Console steps + confirm before proceeding** | Prevents the most common confused-user failure mode. ~15 lines of banner. |

### Sensible defaults (not separately questioned)

| Aspect | Choice |
|---|---|
| Auth module shape | `auth/` sub-package: `__init__.py` (runtime) + `setup.py` (wizard) |
| Redirect URI | Hardcoded `http://127.0.0.1:8080` (Google installed-app pattern) |
| OAuth scope | `https://www.googleapis.com/auth/adwords` |
| `use_proto_plus` | `True` (Google recommendation) |
| `default_customer_id` | Required in the wizard (no skip) |
| Credential loading at runtime | Lazy — per tool call, not at server startup |
| File permissions | `credentials.json` mode `0600`; parent dir mode `0700` |
| End-of-setup verification call | Out of scope (no live API call in the setup path) |
| Validation re-prompt cap | 3 attempts per field, then exit 1 |

## File Layout

```
src/google_ads_mcp/
├── __init__.py              # unchanged
├── server.py                # MODIFIED — argv dispatch: `setup` → wizard, else → mcp.run()
└── auth/                    # NEW sub-package
    ├── __init__.py          # runtime: CREDENTIALS_PATH, error classes, load_credentials(),
    │                        # get_google_ads_client(), get_default_customer_id()
    └── setup.py             # wizard: run_setup(argv), banner, prompts, validators,
                             # OAuth flow, write_credentials_file()

tests/
├── __init__.py              # unchanged
├── conftest.py              # NEW — tmp_credentials_dir fixture
├── test_server.py           # MODIFIED — add dispatch tests; keep ping test
└── auth/
    ├── __init__.py          # NEW empty
    ├── test_load.py         # NEW — load_credentials() + error classes
    └── test_setup_helpers.py # NEW — validators + write_credentials_file()
```

`auth/setup.py` never imports `GoogleAdsClient`; `auth/__init__.py` never imports OAuth machinery. The only cross-import is `setup.py` → `__init__.py` for `CREDENTIALS_PATH`.

## `credentials.json` schema

Stored at `~/.config/google-ads-mcp/credentials.json`, mode `0600`.

```json
{
  "schema_version": 1,
  "developer_token": "abc123XYZ...",
  "client_id": "1234567890-abc...apps.googleusercontent.com",
  "client_secret": "GOCSPX-...",
  "refresh_token": "1//0g...",
  "login_customer_id": "1234567890",
  "default_customer_id": "9876543210",
  "use_proto_plus": true
}
```

| Field | Source | Notes |
|---|---|---|
| `schema_version` | constant `1` | Forward-compat marker |
| `developer_token` | API Center | Captured via `getpass` (masked) |
| `client_id`, `client_secret` | `client_secrets.json` | Extracted after OAuth flow |
| `refresh_token` | OAuth flow | `flow.credentials.refresh_token` |
| `login_customer_id` | user input | MCC ID, digits only (dashes stripped) |
| `default_customer_id` | user input | Q2 default; digits only |
| `use_proto_plus` | constant `true` | Google recommendation |

Runtime mapping drops `schema_version` and `default_customer_id` before `load_from_dict()`:

```python
sdk_config = {k: v for k, v in credentials.items()
              if k not in ("schema_version", "default_customer_id")}
client = GoogleAdsClient.load_from_dict(sdk_config, version="v24")
```

## Setup wizard flow (`google-ads-mcp setup`)

### Step 0 — Argument parsing
`argparse` consumes flags. Only `--force` in v0.1 (overwrite existing credentials without prompting).

### Step 1 — Pre-flight banner
Prints what the user needs (developer token, OAuth Desktop client + steps to create one, MCC ID, default account ID), links `docs/developer-token.md`, then `Have you completed the above? [y/N]:`. `n`/empty → exit 1. If `credentials.json` exists and not `--force` → confirm overwrite; `n` → exit 0.

### Step 2 — Prompts

| # | Prompt | Input fn | Validation |
|---|---|---|---|
| 2.1 | `Developer token (input hidden): ` | `getpass.getpass()` | non-empty |
| 2.2 | `Path to client_secrets.json: ` | `input()` | file exists, readable, valid JSON, has `installed` or `web` key |
| 2.3 | `Manager (MCC) account ID [digits only, no dashes]: ` | `input()` | strip dashes; assert 10 digits |
| 2.4 | `Default Google Ads account ID [digits only, no dashes]: ` | `input()` | strip dashes; assert 10 digits |

Validation failure → "Invalid: <reason>. Try again." and re-prompt. 3 failures on one field → exit 1.

### Step 3 — OAuth flow

```python
SCOPE = "https://www.googleapis.com/auth/adwords"
REDIRECT_URI = "http://127.0.0.1:8080"

flow = Flow.from_client_secrets_file(client_secrets_path, scopes=[SCOPE])
flow.redirect_uri = REDIRECT_URI
state = hashlib.sha256(os.urandom(1024)).hexdigest()
auth_url, _ = flow.authorization_url(
    access_type="offline", state=state, prompt="consent",
    include_granted_scopes="true",
)
print(f"\nOpen this URL in your browser to authorize:\n  {auth_url}\n")
# bind 127.0.0.1:8080, accept callback, verify state, capture code
flow.fetch_token(code=code)
refresh_token = flow.credentials.refresh_token
```

`client_id` / `client_secret` are read from the `installed` (or `web`) block of `client_secrets.json`.

OAuth failure modes handled inline (each → clear message + exit 1):
- Port 8080 in use (`OSError` on bind)
- Browser closed / no callback within 5 min (timeout)
- `state` mismatch (possible CSRF)
- `refresh_token is None` (guidance: revoke prior grant at myaccount.google.com/permissions, re-run)

### Step 4 — Write credentials.json

```python
creds_dir = Path.home() / ".config" / "google-ads-mcp"
creds_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
creds_path = creds_dir / "credentials.json"
creds_path.write_text(json.dumps(credentials, indent=2) + "\n")
creds_path.chmod(0o600)   # explicit — write_text honors umask
```

### Step 5 — Success message
Confirms path + mode, points to `uvx google-ads-mcp` / README Claude Desktop config. Exit 0.

## Runtime auth module (`src/google_ads_mcp/auth/__init__.py`)

```python
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

_DEFAULT_API_VERSION = "v24"


class CredentialsError(Exception):
    """Base class for credential-loading failures."""


class CredentialsNotFound(CredentialsError):
    """credentials.json does not exist."""


class CredentialsMalformed(CredentialsError):
    """credentials.json exists but is invalid JSON or missing required fields."""


class CredentialsRevoked(CredentialsError):
    """The refresh token has been revoked or expired."""


def load_credentials(path: Path = CREDENTIALS_PATH) -> dict[str, Any]:
    if not path.exists():
        raise CredentialsNotFound(
            f"Credentials not found at {path}. "
            "Run `google-ads-mcp setup` to create them."
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
            f"Credentials file at {path} is missing required fields: {missing}. "
            "Re-run `google-ads-mcp setup` to recreate it."
        )
    return data


def get_default_customer_id(path: Path = CREDENTIALS_PATH) -> str:
    value: str = load_credentials(path)["default_customer_id"]
    return value


def get_google_ads_client(
    path: Path = CREDENTIALS_PATH,
    api_version: str = _DEFAULT_API_VERSION,
) -> GoogleAdsClient:
    config = load_credentials(path)
    sdk_config = {
        k: v for k, v in config.items()
        if k not in ("schema_version", "default_customer_id")
    }
    return GoogleAdsClient.load_from_dict(sdk_config, version=api_version)
```

### Lazy loading at the MCP layer

`server.py` does NOT load credentials at import time. Each tool that needs the API calls `get_google_ads_client()` itself. Rationale: `ping` must work without credentials (post-install connectivity test); broken credentials should fail individual tools with helpful messages, not crash the process.

Pattern future tools (#4+) follow:

```python
@mcp.tool
def list_campaigns(customer_id: str | None = None) -> dict[str, Any]:
    from google_ads_mcp.auth import get_google_ads_client, get_default_customer_id

    client = get_google_ads_client()
    target = customer_id or get_default_customer_id()
    # ... use client ...
    return {"customer_id": target, "campaigns": [...]}
```

The `customer_id: str | None = None` + `default_customer_id` fallback is the Q2 PRD decision in action.

## `server.py` change

```python
import sys
# ... existing FastMCP + ping ...

def main() -> None:
    """Entry point — dispatches between the setup wizard and the MCP server."""
    if len(sys.argv) > 1 and sys.argv[1] == "setup":
        from google_ads_mcp.auth.setup import run_setup

        sys.exit(run_setup(sys.argv[2:]))
    mcp.run()
```

`run_setup` returns an int exit code. Import is inside the branch to keep server startup free of OAuth-module imports. All existing invocations (`uvx google-ads-mcp`, the `ping` test) are unaffected.

## `pyproject.toml` dependency additions

```toml
dependencies = [
    "fastmcp>=2.0",
    "google-ads>=24,<25",            # pin to one major API version (PRD line 110)
    "google-auth>=2.0",
    "google-auth-oauthlib>=1.0",
]
```

## README + docs updates

- **README**: new "Setup (first-time only)" section between Install and Claude Desktop config (documents `uvx google-ads-mcp setup` + the 6 wizard steps). Replace the placeholder line in Claude Desktop config ("Environment variables ... added once #3 wires the auth flow") with "the server reads credentials from `~/.config/google-ads-mcp/credentials.json` automatically."
- **docs/developer-token.md**: update the "After approval" section to point to `uvx google-ads-mcp setup` instead of setting an env var manually.

## Error matrix

| Failure | Detection | Exception | User-facing message |
|---|---|---|---|
| No credentials file | `Path.exists()` False | `CredentialsNotFound` | "Credentials not found at `<path>`. Run `google-ads-mcp setup` to create them." |
| Malformed JSON / missing field | parse error or field check | `CredentialsMalformed` | "Credentials file at `<path>` is [not valid JSON / missing fields: …]. Re-run `google-ads-mcp setup`." |
| Refresh token revoked | `RefreshError` on first SDK call | `CredentialsRevoked` (re-raised in tool) | "Refresh token revoked. Re-run `google-ads-mcp setup` to re-authorize." |
| Developer token wrong/unapproved | `GoogleAdsException` auth code | re-raised, annotated | "Developer token not approved / missing / incorrect. See `docs/developer-token.md`." |

First two are synchronous (load time) → owned by #3. Last two manifest only on a live SDK call → bridge code lands in #4.

## Tests

`tests/conftest.py` — first shared fixture:

```python
@pytest.fixture
def tmp_credentials_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    creds_dir = tmp_path / ".config" / "google-ads-mcp"
    creds_dir.mkdir(parents=True)
    creds_path = creds_dir / "credentials.json"
    monkeypatch.setattr("google_ads_mcp.auth.CREDENTIALS_PATH", creds_path)
    return creds_path
```

`tests/auth/test_load.py`:
- `test_load_credentials_returns_dict_with_all_fields`
- `test_load_credentials_raises_not_found_when_missing`
- `test_load_credentials_raises_malformed_on_bad_json`
- `test_load_credentials_raises_malformed_on_missing_field`
- `test_get_default_customer_id_returns_field`

`tests/auth/test_setup_helpers.py`:
- `test_validate_customer_id_accepts_10_digits`
- `test_validate_customer_id_strips_dashes`
- `test_validate_customer_id_rejects_letters`
- `test_validate_customer_id_rejects_wrong_length`
- `test_write_credentials_file_creates_with_0600_mode`
- `test_write_credentials_file_creates_parent_dir_with_0700`
- `test_write_credentials_file_roundtrips_json`

`tests/test_server.py` (additions):
- `test_main_dispatches_to_setup_when_argv_setup` (monkeypatch `run_setup`, set `sys.argv`, assert called + `SystemExit`)
- `test_main_runs_server_when_no_argv` (monkeypatch `mcp.run`, assert called)

OAuth-flow tests (mocking `Flow`, `fetch_token`, the socket dance) are **deferred** — mock-heavy and brittle; real coverage comes from the #7 smoke test against a Google Test Account.

## Out of Scope (deferred)

| Not in #3 | Owned by |
|---|---|
| Real Google Ads tool implementation using `get_google_ads_client()` | #4, #5, #6 |
| `CredentialsRevoked` / `GoogleAdsException` → friendly-error bridge | #4 (first live SDK call) |
| Mocked OAuth-flow tests | Deferred; #7 smoke test covers real flow |
| Multi-account map (Q1 alternate) | Post-v1 if demand emerges |
| Env-var override for credential location/contents | Future; KISS for v0.1 |
| `--non-interactive` flag for CI | Future |
| Encryption of `credentials.json` | Out of scope — mode 0600 + filesystem ACL is the v0.1 trust boundary; refresh_token is revocable |
| `setup --verify` (sample API call at end of setup) | Future; not in #3 acceptance criteria |

## Verification Required at Scaffold Time

1. **`google-ads` SDK current major** — design assumes v24. After `uv add 'google-ads>=24,<25'`, verify with `uv run python -c "import google.ads.googleads; print(google.ads.googleads.VERSION)"`. If Google shipped v25, bump the constraint + `_DEFAULT_API_VERSION`. Prefer reality over this document.
2. **`Flow.from_client_secrets_file` signature** — confirm `scopes=[...]` is the right kwarg name via `uv run python -c "from google_auth_oauthlib.flow import Flow; help(Flow.from_client_secrets_file)"`.
3. **`Path.mkdir(mode=0o700)` on macOS** — umask may mask the mode. `test_write_credentials_file_creates_parent_dir_with_0700` catches it; if it fails, add an explicit `chmod(0o700)` after `mkdir`.
4. **Import path for `GoogleAdsClient`** — design uses `from google.ads.googleads.client import GoogleAdsClient`. Confirm this is correct for the installed `google-ads` version (the package has used both `google.ads.google_ads` and `google.ads.googleads` historically). Verify post-install.

## Risks

| Risk | Likelihood | Mitigation |
|---|---|---|
| `google-ads` import path differs from `google.ads.googleads.client` | Medium | Verification step 4; quick fix |
| `google-ads` requires Python > 3.11 | Low | `uv sync` fails fast; pin a compatible version |
| mypy strict complains about untyped `google-ads` SDK | Medium | Add scoped `[[tool.mypy.overrides]] module = "google.ads.*" ignore_missing_imports = true` if the SDK ships no stubs; document the override |
| Wizard is large for one PR (~150–200 lines in setup.py) | Medium | Plan splits it into small tasks; if it balloons, split #3 into runtime-module PR + wizard PR |
| Port 8080 conflicts on user machine | Low | Clear error message; `--port` flag deferred to future |

## Acceptance Criteria Mapping (issue #3)

| Criterion | Satisfied by |
|---|---|
| Setup helper runs OAuth consent flow + captures refresh token | `auth/setup.py` Steps 2–3 |
| Credentials persisted to `~/.config/google-ads-mcp/credentials.json` with `0600` | `auth/setup.py` Step 4 (explicit `chmod(0o600)`) |
| Server loads credentials on startup + refreshes access token transparently | `auth/__init__.py` `get_google_ads_client()` (SDK auto-refresh). "On startup" is intentionally lazy — first API-touching tool call triggers load; PRD doesn't require eager loading. |
| Helpful errors when credentials missing/malformed/revoked | `CredentialsError` hierarchy + messages (revoked path lands in #4) |
| README documents the setup flow + credentials location | README "Setup" section + docs/developer-token.md update |

## Next Steps

Per the brainstorming flow, the next step is `writing-plans` to produce a bite-sized implementation plan. After plan approval, implementation lands on this branch (`feat/issue-3-oauth-setup`); spec + plan + impl ship as one PR closing #3.

---

*Generated via `superpowers:brainstorming` skill, 2026-05-21 → 2026-05-28.*
