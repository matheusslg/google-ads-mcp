"""FastMCP server entry point for google-ads-mcp."""

import sys

from google_ads_mcp._mcp import mcp


@mcp.tool
def ping() -> dict[str, bool]:
    """Health check. Returns `{"ok": True}` if the MCP server is reachable.

    Real Google Ads tools land in later issues; this is the bootstrap connectivity probe.
    """
    return {"ok": True}


def main() -> None:
    """Entry point — dispatches between the setup wizard and the MCP server."""
    if len(sys.argv) > 1 and sys.argv[1] == "setup":
        from google_ads_mcp.auth.setup import run_setup

        sys.exit(run_setup(sys.argv[2:]))
    mcp.run()


if __name__ == "__main__":
    main()

# Register tools by importing modules that use @mcp.tool decorators.
from google_ads_mcp.tools import audits, reads, reports  # noqa: F401, E402
