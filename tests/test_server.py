"""Smoke tests for the MCP server skeleton."""

from google_ads_mcp.server import ping


def test_ping_returns_ok() -> None:
    assert ping() == {"ok": True}
