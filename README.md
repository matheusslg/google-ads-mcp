# google-ads-mcp

> Workflow-shaped MCP server exposing the Google Ads API to AI agents
> with built-in safety rails for mutations.

**Status**: Pre-release (v0.0.1) — bootstrap skeleton only. See [open issues](https://github.com/matheusslg/google-ads-mcp/issues) for the roadmap.

## Install

```bash
uvx google-ads-mcp
```

(Full install + Google Ads OAuth setup walkthrough lands in #3 and is documented in `docs/developer-token.md` once #2 ships.)

## Claude Desktop config

Add to `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) or the equivalent path:

```json
{
  "mcpServers": {
    "google-ads-mcp": {
      "command": "uvx",
      "args": ["google-ads-mcp"]
    }
  }
}
```

Environment variables for the Google Ads developer token / OAuth refresh token are added once #3 wires the auth flow.

## First call example

While only the `ping` connectivity probe exists:

> **You**: Call the `ping` tool on `google-ads-mcp`.
> **Claude**: `→ ping() → {"ok": true}`

Real tools land in #4–#6.

## Safety model

Every mutation tool will ship with `dry_run: bool = False` and at least one guardrail (`max_increase_percent` or `absolute_cap`). Default cap is `max_increase_percent: 50` when both guardrails are omitted. Full documentation in #11. Contract details in [`PRD.md`](PRD.md) (Design System) and [`standards.md`](standards.md).

## Development

```bash
git clone https://github.com/matheusslg/google-ads-mcp
cd google-ads-mcp
uv sync
uv run pytest
```

## License

MIT — see [`LICENSE`](LICENSE).
