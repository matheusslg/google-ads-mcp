"""Shared pytest fixtures for google-ads-mcp."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest


@pytest.fixture
def tmp_credentials_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Override CREDENTIALS_PATH to a temp directory; return the file path.

    The file itself is NOT created here — individual tests decide whether to
    write valid/malformed/missing-field content before exercising load_credentials.
    """
    creds_dir = tmp_path / ".config" / "google-ads-mcp"
    creds_dir.mkdir(parents=True)
    creds_path = creds_dir / "credentials.json"
    monkeypatch.setattr("google_ads_mcp.auth.CREDENTIALS_PATH", creds_path)
    return creds_path


@pytest.fixture
def mock_google_ads_client(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """Patch get_google_ads_client + get_default_customer_id in tools.reads.

    The returned MagicMock is the SDK client — tests program
    `client.get_service("GoogleAdsService").search_stream.return_value = [...]`
    (or `.side_effect = GoogleAdsException(...)`) to control row output.
    """
    client = MagicMock()
    monkeypatch.setattr(
        "google_ads_mcp.tools.reads.get_google_ads_client",
        lambda *a, **k: client,
    )
    monkeypatch.setattr(
        "google_ads_mcp.tools.reads.get_default_customer_id",
        lambda *a, **k: "9999999999",
    )
    return client
