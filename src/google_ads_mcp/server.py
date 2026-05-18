"""FastMCP server entry point for google-ads-mcp."""

from fastmcp import FastMCP

mcp: FastMCP = FastMCP("google-ads-mcp")


@mcp.tool
def ping() -> dict[str, bool]:
    """Health check. Returns `{"ok": True}` if the MCP server is reachable.

    Real Google Ads tools land in later issues; this is the bootstrap connectivity probe.
    """
    return {"ok": True}


def main() -> None:
    """Run the MCP server over stdio. Used as the `google-ads-mcp` console script."""
    mcp.run()


if __name__ == "__main__":
    main()
