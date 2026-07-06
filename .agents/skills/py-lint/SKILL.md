---
description: Run ruff and mypy on the google-ads-mcp Python codebase
allowed-tools: Bash, Read
---

# Python Lint & Type Check

## Context
- ruff: !`ruff --version 2>/dev/null || uv run ruff --version 2>/dev/null || echo "ruff not available"`
- mypy: !`mypy --version 2>/dev/null || uv run mypy --version 2>/dev/null || echo "mypy not available"`
- Lint config in pyproject.toml: !`grep -A 1 '\[tool.ruff' pyproject.toml 2>/dev/null | head -3 || echo "no ruff config yet"`
- mypy config: !`grep -A 1 '\[tool.mypy' pyproject.toml 2>/dev/null | head -3 || echo "no mypy config yet"`

## Task

Run linting:

```bash
uv run ruff check .
uv run ruff format --check .
```

Run type checking:

```bash
uv run mypy src tests
```

If `uv` isn't available yet (early Phase 0), substitute `ruff`, `mypy` directly.

Fix issues or explain how to fix them. **Never suggest `cast(..., Any)` to silence a type error** — fix the underlying type per `standards.md`.
