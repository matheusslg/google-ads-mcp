---
description: Manage uv-based Python dependencies (add, sync, lock, upgrade) for google-ads-mcp
allowed-tools: Bash, Read, AskUserQuestion
argument-hint: <subcommand> [args]  # add | sync | lock | upgrade | tree | outdated
---

# uv Dependency Management

## Context
- uv: !`uv --version 2>/dev/null || echo "uv not installed (install via: curl -LsSf https://astral.sh/uv/install.sh | sh)"`
- pyproject.toml: !`ls pyproject.toml 2>/dev/null || echo "not present yet (Phase 0 / issue #1)"`
- uv.lock: !`ls uv.lock 2>/dev/null || echo "no lockfile yet"`
- Python pin: !`grep -E '^python' .python-version 2>/dev/null || grep 'requires-python' pyproject.toml 2>/dev/null | head -1 || echo "no Python pin found"`

## Task

Pick the right subcommand based on `$1`:

| Subcommand | Action |
|---|---|
| `add` | `uv add <pkg> [<pkg>...]` — add a runtime dependency |
| `add --dev` | `uv add --dev <pkg>` — add a dev-only dependency (ruff, mypy, pytest, etc.) |
| `sync` | `uv sync` — install everything from `pyproject.toml` + `uv.lock` |
| `lock` | `uv lock` — recompute the lockfile without installing |
| `upgrade` | `uv lock --upgrade` then `uv sync` — bump deps within constraints |
| `tree` | `uv tree` — show dependency tree |
| `outdated` | `uv tree --outdated` — show outdated packages |

**Confirm with the user before running `upgrade`** — it changes the lockfile and may pull breaking versions of `google-ads`.

### Special: pinning Google Ads API version

Per the PRD risks section (line 179), the `google-ads` SDK should be pinned to a single major API version per release. When adding or upgrading it, ask the user which API major version they intend to target and document it in the README.

```bash
uv ${1:?subcommand required: add|sync|lock|upgrade|tree|outdated} ${@:2}
```

After the command runs, show:
```bash
uv tree --depth 1 2>/dev/null | head -30
```
