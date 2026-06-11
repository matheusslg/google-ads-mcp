"""Smoke tests for the MCP server skeleton."""

import sys
from unittest.mock import patch

import pytest

from google_ads_mcp.server import main, ping


def test_ping_returns_ok() -> None:
    assert ping() == {"ok": True}


def test_main_dispatches_to_setup_when_argv_setup(monkeypatch: pytest.MonkeyPatch) -> None:
    """`google-ads-mcp setup ...` should call run_setup and sys.exit with its code."""
    monkeypatch.setattr(sys, "argv", ["google-ads-mcp", "setup", "--force"])
    with patch("google_ads_mcp.auth.setup.run_setup", return_value=0) as mock_setup:
        with pytest.raises(SystemExit) as exc:
            main()
    mock_setup.assert_called_once_with(["--force"])
    assert exc.value.code == 0


def test_main_runs_server_when_no_argv(monkeypatch: pytest.MonkeyPatch) -> None:
    """`google-ads-mcp` with no extra argv should call mcp.run()."""
    monkeypatch.setattr(sys, "argv", ["google-ads-mcp"])
    with patch("google_ads_mcp.server.mcp.run") as mock_run:
        main()
    mock_run.assert_called_once()
