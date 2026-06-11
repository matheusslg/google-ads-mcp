# google-ads-mcp

> Workflow-shaped MCP server exposing the Google Ads API to AI agents
> with built-in safety rails for mutations.

**Status**: Pre-release (v0.0.1) — bootstrap skeleton only. See [open issues](https://github.com/matheusslg/google-ads-mcp/issues) for the roadmap.

## Install

```bash
uvx google-ads-mcp
```

## Setup (first-time only)

Before Claude Desktop can connect, run the setup wizard once:

```bash
uvx google-ads-mcp setup
```

The wizard:
1. Prints the Google Cloud Console steps to create an OAuth 2.0 client (Desktop application type)
2. Prompts for your developer token (from <https://ads.google.com/aw/apicenter>)
3. Prompts for the path to your downloaded `client_secrets.json`
4. Prompts for your Manager (MCC) ID and the default Google Ads account ID
5. Opens a browser tab for OAuth consent
6. Saves credentials to `~/.config/google-ads-mcp/credentials.json` (mode 0600)

See [`docs/developer-token.md`](docs/developer-token.md) for the full Google Cloud Console walkthrough.

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

Once the setup wizard above has run, the server reads credentials from `~/.config/google-ads-mcp/credentials.json` automatically. No additional environment variables are required.

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
