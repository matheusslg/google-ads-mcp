"""google-ads-mcp — MCP server for Google Ads workflows."""

from importlib.metadata import version

from google_ads_mcp.server import main

__version__ = version("google-ads-mcp")

__all__ = ["main", "__version__"]
