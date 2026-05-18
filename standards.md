# Code Standards

> Stack-specific conventions for google-ads-mcp. Authoritative companion to `PRD.md`.

## General

- Follow existing patterns in the codebase
- Write tests for new functionality
- Keep functions focused and small (KISS)
- Prefer explicit over implicit
- Document non-obvious decisions
- Never silence type errors with `cast(..., Any)` — fix the actual type

## Commits

Conventional commits: `type(scope): description`

**Types**:
- `feat` — new feature
- `fix` — bug fix
- `refactor` — code restructuring (no behavior change)
- `docs` — documentation only
- `test` — adding/updating tests
- `chore` — build, config, dependencies
- `style` — formatting, whitespace

**Examples**:
```
feat(tools): add list_campaigns MCP tool
fix(oauth): handle expired refresh token
chore(deps): bump google-ads to 25.0.0
docs(safety): document guardrail defaults
```

## Branching

- **Never commit directly to `main`** — always feature-branch + PR
- Branch naming: `feat/issue-<N>-<short-slug>`, `fix/issue-<N>-<short-slug>`, `chore/issue-<N>-<short-slug>`
- One issue per branch; one branch per PR

## Code Style (Python)

- **Python ≥ 3.11**
- **Type hints on every public function**; favor concrete types over `Any`
- **Format with `ruff format`**; lint with `ruff check`
- **Type-check with `mypy`** (strict where practical)
- **Async**: use `asyncio` + `pytest-asyncio` for async-test paths
- **No `cast(..., Any)`** to bypass mypy — fix the underlying type
- **f-strings** for formatting; avoid `%` and `.format()`
- **Dataclasses or Pydantic models** for typed data structures (Pydantic preferred for MCP I/O since FastMCP integrates with it)
- **Docstrings on every `@mcp.tool` function** — they become the MCP tool schema/description; be precise about args and return shape

## MCP Tool Design (per PRD design contracts)

- **Tool naming** (PRD line 119): `<verb>_<resource>` for primitives (`list_campaigns`), `<verb>_<workflow>` for composed ops (`audit_account_health`). Lowercase snake_case. Verbs from the fixed set: `list`, `get`, `find`, `summarize`, `audit`, `pause`, `enable`, `update`, `add`, `remove`, `draft`, `dry_run`.
- **Read tools return** JSON-serializable arrays of typed objects (NOT raw protobuf).
- **Write tools return** `{ success: bool, mutation_id?: str, before: {...}, after: {...}, warnings: [...] }`.
- **Every mutation tool accepts** `dry_run: bool = False`.
- **Every budget-touching tool accepts** at least one of `max_increase_percent` or `absolute_cap`.
- **Default guardrail** when caller omits both: `max_increase_percent: 50` (PRD line 181).

## Testing

- **Framework**: `pytest` + `pytest-asyncio`
- **Layout**: tests live in `tests/`, mirroring the source tree
- **Naming**: files `test_*.py`; functions `test_*`
- **Fixtures**: prefer pytest fixtures over setUp/tearDown; share via `conftest.py`
- **Synthetic data** for test fixtures (per PRD Open Questions, line 190 — leans synthetic for v0.1)
- **Coverage**: `pytest --cov` with terminal report; aim for high coverage on tool logic and guardrails
- **Every mutation tool MUST have**:
  - a dry-run test (asserts no API call made, preview returned)
  - a happy-path test
  - a guardrail-violation test (asserts refusal + clear error)

## Dependency Management

- Use `uv` for everything: `uv add <pkg>`, `uv sync`, `uv run pytest`, `uvx <cmd>`
- Pin the Google Ads API major version in `pyproject.toml`; document the supported version in the README
- Lock file (`uv.lock`) is committed
- Distribution target: `uvx google-ads-mcp` for end users

## File Organization

```
.
├── PRD.md                       # design contract (source of truth)
├── README.md                    # install + Claude Desktop config + first-call example
├── LICENSE                      # MIT
├── pyproject.toml               # uv-managed; project metadata, deps, ruff/mypy/pytest config
├── uv.lock                      # committed
├── src/
│   └── google_ads_mcp/
│       ├── __init__.py
│       ├── server.py            # FastMCP entry point
│       ├── auth.py              # OAuth2 flow + credentials.json handling
│       ├── tools/               # one module per logical tool group
│       │   ├── list_tools.py
│       │   ├── performance.py
│       │   ├── audit.py
│       │   └── mutations.py
│       └── clients/             # Google Ads SDK wrappers / GAQL helpers
├── tests/                       # mirrors src/ structure
│   ├── conftest.py              # shared fixtures (synthetic data)
│   ├── tools/
│   └── clients/
├── docs/
│   └── developer-token.md       # end-user setup notes
└── .github/
    └── workflows/               # CI: lint + type-check + test matrix (Phase 3)
```

(This layout is a starting point — adjust as the codebase grows. Document any deviations here.)

## Safety Model (Mutations)

Every mutation tool MUST:
1. Accept `dry_run: bool = False`
2. On `dry_run=True`, never call the Google Ads API — return the predicted `before`/`after` only
3. Validate caller-supplied guardrails BEFORE building the mutation operation
4. Apply the default cap (`max_increase_percent: 50`) when both guardrails are omitted
5. Return a clear, non-cryptic error when a guardrail blocks the operation

The PRD's Risks section (line 181) and Success Metrics section (line 130) make safety the most-scrutinized property of this codebase. Reviewers treat safety regressions as Critical.
