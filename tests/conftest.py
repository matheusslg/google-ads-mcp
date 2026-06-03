"""Shared pytest fixtures for google-ads-mcp."""

from __future__ import annotations

from pathlib import Path

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
