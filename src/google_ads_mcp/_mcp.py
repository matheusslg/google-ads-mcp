"""Shared FastMCP instance.

Kept in its own module (separate from `server.py`) to avoid a circular
import: `tools/*.py` needs `mcp` to register `@mcp.tool` decorators, and
`server.py` needs to import `tools/*.py` to trigger that registration.
"""

from __future__ import annotations

from fastmcp import FastMCP

mcp: FastMCP = FastMCP("google-ads-mcp")
