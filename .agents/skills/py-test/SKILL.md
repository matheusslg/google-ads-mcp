---
description: Run pytest with coverage for google-ads-mcp
allowed-tools: Bash, Read
argument-hint: [test-path-or-pattern]
---

# Python Tests

## Context
- Python: !`python3 --version 2>/dev/null || echo "Python not in PATH"`
- uv: !`uv --version 2>/dev/null || echo "uv not installed"`
- pyproject.toml: !`ls pyproject.toml 2>/dev/null || echo "not present yet (Phase 0 / issue #1)"`
- Test files: !`find . -path ./.venv -prune -o -path ./node_modules -prune -o \( -name "test_*.py" -o -name "*_test.py" \) -print 2>/dev/null | grep -c '\.py$' | tr -d ' '` test files

## Task

Run pytest with coverage:

```bash
uv run pytest -v --cov --cov-report=term-missing ${1:-}
```

If `uv` isn't available yet (early Phase 0 before issue #1 lands), fall back to:

```bash
pytest -v --cov --cov-report=term-missing ${1:-}
```

Analyze failures and suggest fixes. For every mutation-tool test that fails on the guardrail-violation path, treat it as Critical — the safety model is the project's most scrutinized property.
