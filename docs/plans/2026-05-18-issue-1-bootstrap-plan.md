# Issue #1 — Bootstrap Project Skeleton — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Land a runnable `uvx google-ads-mcp` MCP server skeleton that exposes a single `ping` no-op tool, with `pyproject.toml`, MIT LICENSE, README skeleton, tests, and clean ruff/mypy/pytest gates.

**Architecture:** Single-file FastMCP server (`src/google_ads_mcp/server.py`) decorating one no-op `ping()` function as an `@mcp.tool`, with `main()` calling `mcp.run()` over stdio. `[project.scripts]` entry point makes `uvx google-ads-mcp` work. Distributed via uv + hatchling.

**Tech Stack:** Python 3.11+, FastMCP, uv (deps + build via uvx), hatchling (build backend), pytest + pytest-asyncio (tests), ruff (lint/format), mypy (strict).

**Spec:** `docs/specs/2026-05-18-issue-1-bootstrap-design.md` (commit `2ccb67d`, branch `feat/issue-1-bootstrap`).

**Issue:** [#1 Bootstrap project skeleton](https://github.com/matheusslg/google-ads-mcp/issues/1)

---

## File Structure (created/modified by this plan)

| File | Action | Responsibility |
|---|---|---|
| `pyproject.toml` | Create | Project metadata, deps, build, scripts, ruff/mypy/pytest config |
| `.python-version` | Create | `3.11` — pins dev Python |
| `.gitignore` | Create | Python + uv + venv + defensive secrets ignores |
| `src/google_ads_mcp/__init__.py` | Create | `__version__` from `importlib.metadata`, re-exports `main` |
| `src/google_ads_mcp/server.py` | Create | FastMCP instance, `ping` tool, `main()` |
| `tests/__init__.py` | Create | Empty — makes tests a package |
| `tests/test_server.py` | Create | Asserts `ping() == {"ok": True}` |
| `README.md` | Create | Skeleton — Install, Claude Desktop config, First call, Safety placeholder, Development, License |
| `uv.lock` | Generated | First `uv sync` produces this; committed |
| `progress.md` | Modify | Add Session 3 entry |

**Pre-existing files NOT touched** by this plan: `LICENSE`, `PRD.md`, `standards.md`, `.claude/**`, `docs/specs/2026-05-18-issue-1-bootstrap-design.md` (this plan's spec).

---

## Task 1: Scaffold the uv project

**Files:**
- Create: `pyproject.toml`, `src/google_ads_mcp/__init__.py`, possibly `.python-version` and example boilerplate (depending on uv version)

- [ ] **Step 1.1: Confirm starting state**

Run:
```bash
git status && git branch --show-current
```
Expected output: clean working tree, branch `feat/issue-1-bootstrap`. If branch is wrong, run `git checkout feat/issue-1-bootstrap` first.

- [ ] **Step 1.2: Confirm `uv` is installed**

Run:
```bash
uv --version
```
Expected: a version string (e.g. `uv 0.4.x`). If not installed, install via `curl -LsSf https://astral.sh/uv/install.sh | sh` and retry.

- [ ] **Step 1.3: Run `uv init --package` with no README override**

Run:
```bash
uv init --package --name google-ads-mcp --no-readme
```
Expected: creates `pyproject.toml`, `src/google_ads_mcp/__init__.py`, possibly `.python-version` and an example file like `src/google_ads_mcp/__main__.py` or a hello example. **Does not create `README.md`** (we have our own coming in Task 6).

If `uv init` complains about a non-empty directory: read the warning, ensure nothing was overwritten that shouldn't have been, then proceed. The existing files in this repo (`LICENSE`, `PRD.md`, `progress.md`, `standards.md`, `.claude/`) should not conflict with `uv init` output.

- [ ] **Step 1.4: Inspect what was created**

Run:
```bash
git status
ls -la src/google_ads_mcp/
cat pyproject.toml
```
Expected: see what uv generated. We will overwrite `pyproject.toml` in Task 2 and replace `__init__.py` in Task 4 — but first record what came out of the box so we know what to delete.

- [ ] **Step 1.5: Delete any uv-generated example/boilerplate files**

If `uv init` created any of: `hello.py`, `src/google_ads_mcp/__main__.py`, sample test stubs, etc. that aren't in the spec's file list, delete them:
```bash
# Example — adjust paths to what uv actually generated:
rm -f src/google_ads_mcp/__main__.py hello.py 2>/dev/null || true
```
Expected: only `src/google_ads_mcp/__init__.py` remains under `src/google_ads_mcp/`.

- [ ] **Step 1.6: Commit the raw scaffold (no overrides yet)**

```bash
git add -A
git status      # review what's being staged
git commit -m "chore: scaffold uv package via uv init"
```
Expected: one commit added on top of the spec commit. (Commit message intentionally narrow; the next task replaces the generated `pyproject.toml`.)

---

## Task 2: Replace `pyproject.toml` with the spec'd content

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 2.1: Overwrite `pyproject.toml` with the spec block**

Replace the entire file contents with this (verbatim from spec Section 2):

```toml
[project]
name = "google-ads-mcp"
version = "0.0.1"
description = "Workflow-shaped MCP server exposing the Google Ads API to AI agents with built-in safety rails for mutations."
readme = "README.md"
requires-python = ">=3.11"
license = "MIT"
license-files = ["LICENSE"]
authors = [
    { name = "Matheus Nascimento Cavallini", email = "nascimentocavallini@hotmail.com" }
]
keywords = ["mcp", "google-ads", "ai", "claude", "fastmcp"]
classifiers = [
    "Development Status :: 3 - Alpha",
    "Intended Audience :: Developers",
    "License :: OSI Approved :: MIT License",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
    "Topic :: Internet :: WWW/HTTP",
    "Topic :: Software Development :: Libraries",
]
dependencies = [
    "fastmcp>=2.0",
]

[project.urls]
Homepage   = "https://github.com/matheusslg/google-ads-mcp"
Repository = "https://github.com/matheusslg/google-ads-mcp"
Issues     = "https://github.com/matheusslg/google-ads-mcp/issues"

[project.scripts]
google-ads-mcp = "google_ads_mcp.server:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[dependency-groups]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
    "pytest-cov>=5.0",
    "ruff>=0.6",
    "mypy>=1.10",
]

[tool.hatch.build.targets.wheel]
packages = ["src/google_ads_mcp"]

[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
addopts = "-v"

[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "I", "B", "UP", "RUF"]

[tool.mypy]
python_version = "3.11"
strict = true
warn_return_any = true
warn_unused_configs = true
```

- [ ] **Step 2.2: Run `uv sync` to install runtime + dev deps and generate the lockfile**

```bash
uv sync
```
Expected:
- Creates `.venv/` (already gitignored after Task 3, but won't matter for this step)
- Generates `uv.lock` (committed)
- Installs `fastmcp`, `pytest`, `pytest-asyncio`, `pytest-cov`, `ruff`, `mypy`

If `uv sync` fails on the `license = "MIT" + license-files = ["LICENSE"]` PEP 639 form, the hatchling version is too old. Fix: bump hatchling explicitly by adding `hatchling >= 1.21` to `[build-system].requires`, OR fall back to the legacy `license = { text = "MIT" }` form. Prefer the bump.

- [ ] **Step 2.3: Verify FastMCP installed and import works**

Run:
```bash
uv run python -c "from fastmcp import FastMCP; print(FastMCP.__module__, FastMCP.__name__)"
```
Expected: prints `fastmcp FastMCP` (or similar — confirms import path is `fastmcp`, not `mcp.server.fastmcp`).

If the import fails with `ModuleNotFoundError`, try:
```bash
uv run python -c "from mcp.server.fastmcp import FastMCP; print('legacy path')"
```
If the legacy path works, the FastMCP major version pulled by `uv add` was older than expected. Bump the constraint: change `fastmcp>=2.0` in pyproject.toml to `fastmcp>=2.0,<3` (or whatever current major works). Re-run `uv sync`.

- [ ] **Step 2.4: Verify the `@mcp.tool` decorator form**

Run:
```bash
uv run python -c "from fastmcp import FastMCP; m = FastMCP('test'); print('no parens' if callable(m.tool) and not hasattr(m.tool, '__call__') == False else 'check'); help(m.tool)" 2>&1 | head -20
```
Goal: determine whether the current FastMCP exposes `@mcp.tool` (no parens) or `@mcp.tool()` (with parens). The spec assumed no-parens; if reality differs, adjust the server.py snippet in Task 4 accordingly.

A simpler smoke-check:
```bash
uv run python -c "
from fastmcp import FastMCP
m = FastMCP('x')
try:
    @m.tool
    def f(): return 1
    print('no-parens form works')
except Exception as e:
    print(f'no-parens failed: {e}')
"
```
Expected: prints `no-parens form works`. If it prints `no-parens failed`, the codebase needs `@m.tool()` in Task 4 instead.

- [ ] **Step 2.5: Commit `pyproject.toml` and `uv.lock`**

```bash
git add pyproject.toml uv.lock
git commit -m "chore: replace generated pyproject.toml with spec'd content"
```

---

## Task 3: Add housekeeping files

**Files:**
- Create or overwrite: `.python-version`, `.gitignore`

- [ ] **Step 3.1: Write `.python-version`**

```bash
echo "3.11" > .python-version
```

- [ ] **Step 3.2: Write `.gitignore`**

Create `.gitignore` with this content (verbatim from spec):

```
# Python
__pycache__/
*.py[cod]
*.egg-info/
*.egg
build/
dist/

# Tool caches
.pytest_cache/
.mypy_cache/
.ruff_cache/
.coverage
coverage.xml
htmlcov/

# Virtual environments
.venv/
venv/

# Editor / OS
.DS_Store
.vscode/
.idea/

# Secrets (defensive — covers OAuth credentials added in #3)
.env
.env.*
!.env.example
credentials.json
```

If `uv init` already created a `.gitignore`, overwrite it (the spec content is intentional).

- [ ] **Step 3.3: Verify `.venv/` is ignored**

```bash
git check-ignore .venv/lib 2>&1 || git status --short | head -20
```
Expected: `git check-ignore` exits 0 (printed nothing or printed `.venv/lib`), or `git status` does not list `.venv/` as untracked.

- [ ] **Step 3.4: Commit**

```bash
git add .python-version .gitignore
git commit -m "chore: add .python-version pin and .gitignore"
```

---

## Task 4: Write the failing ping test (TDD red)

**Files:**
- Create: `tests/__init__.py`, `tests/test_server.py`

- [ ] **Step 4.1: Create empty `tests/__init__.py`**

```bash
mkdir -p tests
touch tests/__init__.py
```

- [ ] **Step 4.2: Write `tests/test_server.py`**

Create the file with:

```python
"""Smoke tests for the MCP server skeleton."""

from google_ads_mcp.server import ping


def test_ping_returns_ok() -> None:
    assert ping() == {"ok": True}
```

- [ ] **Step 4.3: Run pytest to confirm the test fails (red phase)**

```bash
uv run pytest -v
```
Expected: collection error or test failure citing `ImportError` (or `ModuleNotFoundError`) on the `from google_ads_mcp.server import ping` line. `server.py` doesn't exist yet, or the `ping` symbol isn't there.

If the test unexpectedly passes (which would happen if `uv init` left a hello-world function in server.py and you missed deleting it in Step 1.5), revisit Step 1.5 and delete the offending file before continuing.

- [ ] **Step 4.4: Do NOT commit yet** — red test stays uncommitted until the green implementation lands in Task 5. (Optional: if you prefer separate "test added" and "impl added" commits, you can commit the failing test now with a `wip:` prefix and amend later. Recommended: keep it uncommitted until Task 5.)

---

## Task 5: Implement the server (TDD green)

**Files:**
- Overwrite: `src/google_ads_mcp/__init__.py`
- Create: `src/google_ads_mcp/server.py`

- [ ] **Step 5.1: Replace `src/google_ads_mcp/__init__.py`**

Overwrite with:

```python
"""google-ads-mcp — MCP server for Google Ads workflows."""

from importlib.metadata import version

from google_ads_mcp.server import main

__version__ = version("google-ads-mcp")

__all__ = ["main", "__version__"]
```

- [ ] **Step 5.2: Create `src/google_ads_mcp/server.py`**

```python
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
```

**If Step 2.4 revealed the decorator form is `@mcp.tool()` (with parens) instead of `@mcp.tool`**, change line 7 to `@mcp.tool()` accordingly.

- [ ] **Step 5.3: Run pytest to confirm it passes (green phase)**

```bash
uv run pytest -v
```
Expected: `tests/test_server.py::test_ping_returns_ok PASSED` and the suite reports 1 passed, 0 failed.

- [ ] **Step 5.4: Verify the package is importable + script entry point is registered**

```bash
uv run python -c "import google_ads_mcp; print(google_ads_mcp.__version__)"
```
Expected: prints `0.0.1`.

```bash
uv run python -c "
import importlib.metadata
eps = [ep for ep in importlib.metadata.entry_points(group='console_scripts') if ep.name == 'google-ads-mcp']
print(eps[0] if eps else 'NOT REGISTERED')
"
```
Expected: prints an EntryPoint pointing at `google_ads_mcp.server:main`.

- [ ] **Step 5.5: Commit**

```bash
git add tests/__init__.py tests/test_server.py src/google_ads_mcp/__init__.py src/google_ads_mcp/server.py
git commit -m "feat(server): add FastMCP skeleton with ping tool"
```

---

## Task 6: Quality gates — ruff (lint + format) and mypy

**Files:** none new; runs against everything written so far.

- [ ] **Step 6.1: Run ruff format check**

```bash
uv run ruff format --check .
```
If it reports diffs, run:
```bash
uv run ruff format .
```
Then re-run `uv run ruff format --check .` and confirm clean.

- [ ] **Step 6.2: Run ruff lint**

```bash
uv run ruff check .
```
Expected: `All checks passed!`

If issues are reported and ruff offers `--fix`, apply them: `uv run ruff check --fix .`. If something requires manual attention, fix the code (do not blanket-`# noqa`).

- [ ] **Step 6.3: Run mypy (strict)**

```bash
uv run mypy src tests
```
Expected: `Success: no issues found in 4 source files` (or similar).

If type errors appear, fix them by adjusting types properly. **Never** add `cast(..., Any)` or `# type: ignore` blanket suppressions to silence mypy — per `standards.md`. The only acceptable `# type: ignore[<specific>]` is when a third-party (e.g. `fastmcp`) lacks stubs and there's no upstream fix; in that case, document why in a one-line comment.

- [ ] **Step 6.4: Commit any quality-gate fixes**

If Step 6.1 / 6.2 / 6.3 produced changes:
```bash
git add -A
git commit -m "style: apply ruff format and fix lint/type findings"
```
If nothing changed, skip this step.

---

## Task 7: Write the README skeleton

**Files:**
- Create: `README.md`

- [ ] **Step 7.1: Write `README.md`**

Create with this content (verbatim from spec Section 4):

````markdown
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

Every mutation tool will ship with `dry_run: bool = False` and at least one guardrail (`max_increase_percent` or `absolute_cap`). Default cap is `max_increase_percent: 50` when both guardrails are omitted. Full documentation in #11. Contract details in `PRD.md` (Design System) and `standards.md`.

## Development

```bash
git clone https://github.com/matheusslg/google-ads-mcp
cd google-ads-mcp
uv sync
uv run pytest
```

## License

MIT — see `LICENSE`.
````

(File contents are the markdown between the four-backtick fences — strip the outer four-backtick markers when saving.)

- [ ] **Step 7.2: Sanity-render**

```bash
head -20 README.md
```
Expected: see the markdown header and Status line. (No automated render verification; trust that the content matches the fenced block above.)

- [ ] **Step 7.3: Commit**

```bash
git add README.md
git commit -m "docs: add README skeleton with install + Claude Desktop config"
```

---

## Task 8: Final verification + progress.md update

**Files:**
- Modify: `progress.md`

- [ ] **Step 8.1: Run the full gate one more time**

```bash
uv sync && uv run pytest -v && uv run ruff check . && uv run ruff format --check . && uv run mypy src tests
```
Expected: all four commands exit 0. If any fail, stop and fix before proceeding to the PR.

- [ ] **Step 8.2: Read `progress.md` to see current state**

```bash
head -40 progress.md
```

- [ ] **Step 8.3: Add a Session 3 entry at the top (under `## Current Status`)**

Edit `progress.md` and insert after the `---` that follows `## Current Status`:

```markdown
### Session 3 (2026-05-18)
**Focus**: Issue #1 — Bootstrap project skeleton
**Completed**:
- `uv init --package` scaffold, then replaced generated `pyproject.toml` with the spec'd content (PEP 621 + PEP 735 + PEP 639)
- `.python-version` pinned to 3.11; `.gitignore` covers Python build artefacts, tool caches, venvs, OS noise, and defensive secrets ignores
- `src/google_ads_mcp/__init__.py` (version from `importlib.metadata`) + `src/google_ads_mcp/server.py` (FastMCP instance + `ping` no-op tool + `main()`)
- `tests/test_server.py` with one assertion (`ping() == {"ok": True}`)
- README skeleton with Install / Claude Desktop config / First call / Safety placeholder / Development / License sections
- `uv.lock` committed; ruff + mypy + pytest gates all clean
**Branch**: `feat/issue-1-bootstrap` (spec is commit 1; bootstrap implementation in subsequent commits)
**Next**: PR review/merge → close #1 → start #2 (Basic Access application, parallel admin track) and #3 (OAuth setup).
```

Also update the `## Current Status` header line:
- Change `**Last Updated**: 2026-05-17` → `**Last Updated**: 2026-05-18`
- Change `**Phase**: Setup` → `**Phase**: Phase 0 — MVP Read-Only (in progress)`

And update `## In Progress`:
```markdown
## In Progress
- `feat/issue-1-bootstrap` branch — implementation complete; PR open awaiting review
```

And update `## Next Session Should`:
```markdown
## Next Session Should
- [ ] Merge PR for #1
- [ ] File the Basic Access application (#2) — external SLA is 1–4 weeks
- [ ] Start #3 (OAuth2 setup helper) — unblocks all read tools (#4, #5, #6)
- [ ] Resolve PRD Open Questions (default customer_id, summary language, fixture strategy) before #3/#5 breakdown
```

- [ ] **Step 8.4: Commit `progress.md`**

```bash
git add progress.md
git commit -m "chore(progress): log session 3 — issue #1 bootstrap complete"
```

---

## Task 9: Push branch and open PR

**Files:** none.

- [ ] **Step 9.1: Review the commit log on the branch**

```bash
git log --oneline main..HEAD
```
Expected: somewhere between 6–8 commits — spec, scaffold, pyproject, housekeeping, server+test, (optional) lint fixes, README, progress.

- [ ] **Step 9.2: Push the branch (sets upstream)**

```bash
git push -u origin feat/issue-1-bootstrap
```

- [ ] **Step 9.3: Open the PR**

```bash
gh pr create --base main --title "feat(#1): bootstrap project skeleton" --body "$(cat <<'EOF'
## Summary

Closes #1.

Bootstrap of the google-ads-mcp Python/FastMCP server. Adds the runnable `uvx google-ads-mcp` skeleton with one `ping` no-op tool, MIT-licensed `pyproject.toml`, README skeleton, and clean ruff/mypy/pytest gates.

- `uv init --package` scaffold reconciled against the design spec at `docs/specs/2026-05-18-issue-1-bootstrap-design.md`
- `pyproject.toml` with PEP 621 + PEP 735 (`[dependency-groups]`) + PEP 639 license expression
- `src/google_ads_mcp/server.py` — FastMCP instance + `@mcp.tool ping()` + `main()` calling `mcp.run()` over stdio
- `tests/test_server.py` — single smoke assertion against `ping()`
- `README.md` skeleton — full polish lands in #7 (v0.1.0 release)
- `uv.lock` committed for reproducible dev/CI builds

Explicit out-of-scope (covered by other issues): auth (#3), real Google Ads tools (#4–#6), CI matrix (#15), polished README (#7).

## Test plan

- [ ] `uv sync` clean
- [ ] `uv run pytest -v` reports 1 passed
- [ ] `uv run ruff check . && uv run ruff format --check .` clean
- [ ] `uv run mypy src tests` reports `Success: no issues found`
- [ ] `uv run python -c "from google_ads_mcp import main; print(main)"` prints a function reference
- [ ] `console_scripts` entry point `google-ads-mcp` is registered (verified in Task 5 Step 5.4 of the plan)
EOF
)"
```

- [ ] **Step 9.4: Post the PR URL back to issue #1 as a comment**

```bash
PR_URL=$(gh pr view --json url -q .url)
gh issue comment 1 --body "PR opened: $PR_URL"
```

- [ ] **Step 9.5: Confirm PR state**

```bash
gh pr view --json url,state,statusCheckRollup -q '{url, state, checks: .statusCheckRollup}'
```
Expected: state `OPEN`, no checks yet (CI lands in #15).

---

## Self-Review

**1. Spec coverage**

| Spec section | Implemented by |
|---|---|
| File Layout | Tasks 1, 3, 4, 5, 7 (every file in the layout is created or modified by a numbered step) |
| pyproject.toml (Section 2) | Task 2 Step 2.1 (verbatim block) |
| `src/google_ads_mcp/__init__.py` (Section 3) | Task 5 Step 5.1 |
| `src/google_ads_mcp/server.py` (Section 3) | Task 5 Step 5.2 |
| `tests/test_server.py` (Section 3) | Task 4 Step 4.2 |
| `tests/__init__.py` (Section 3) | Task 4 Step 4.1 |
| README.md (Section 4) | Task 7 Step 7.1 |
| `.python-version` (Section 4) | Task 3 Step 3.1 |
| `.gitignore` (Section 4) | Task 3 Step 3.2 |
| `uv.lock` (Section 4) | Task 2 Step 2.5 (committed) |
| Verification: FastMCP API / decorator form | Task 2 Steps 2.3 + 2.4 (with fix-forward branch into Task 5 Step 5.2) |
| Verification: PEP 639 hatchling | Task 2 Step 2.2 (with fallback documented) |
| Verification: pytest-asyncio | Implicitly verified when `uv run pytest -v` passes in Task 5 Step 5.3 |
| Acceptance criteria 1–4 (issue #1) | Task 1 + 2 + 5 + 7 collectively |
| Out-of-Scope list | Not actioned (deferred to other issues, as designed) |

**2. Placeholder scan**: no "TBD", "TODO", "later", or "implement appropriately" tokens — every code step has actual code; every command step has the actual command + expected output.

**3. Type / name consistency**:
- Package import name `google_ads_mcp` is used consistently in all tasks (`from google_ads_mcp.server import ping`, `[tool.hatch.build.targets.wheel] packages = ["src/google_ads_mcp"]`, `google-ads-mcp = "google_ads_mcp.server:main"`)
- PyPI dist name `google-ads-mcp` is used consistently
- Function name `ping` matches across spec, test, and impl
- `main()` signature matches between `__init__.py` re-export and `server.py` definition

**4. Branch consistency**: every commit and the final push targets `feat/issue-1-bootstrap` — same as the spec commit.

---

## Risks Specific to Execution

| Risk | Manifests as | Recovery |
|---|---|---|
| `uv init --package` flag set or behavior differs from expectation | Step 1.3 errors or creates unexpected files | Read the error / output; the plan's Step 1.5 sweep handles extras; if it refuses to run in a non-empty dir, hand-write `pyproject.toml` directly and skip `uv init` |
| FastMCP `@mcp.tool` (no parens) was correct at training time but the current major changed it | Step 2.4 reports `no-parens failed` | Use `@mcp.tool()` with parens in Step 5.2 |
| Latest FastMCP requires Python > 3.11 | `uv sync` fails at Step 2.2 with a version-constraint error | Either bump `requires-python` in `pyproject.toml` (and `.python-version`), or pin `fastmcp` to a version that supports 3.11 |
| mypy strict mode complains about FastMCP missing stubs | Step 6.3 errors on `from fastmcp import FastMCP` | Add `[[tool.mypy.overrides]] module = "fastmcp.*" ignore_missing_imports = true` to `pyproject.toml`. Document in a comment. |
| PR #16 merges concurrently and causes a rebase requirement before this PR can merge | PR shows out-of-date | `git fetch && git rebase origin/main`, push with `--force-with-lease` |

---

## Execution Handoff

Plan complete and saved to `docs/plans/2026-05-18-issue-1-bootstrap-plan.md`. Two execution options:

1. **Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration. Best for keeping the main context clean.
2. **Inline Execution** — I execute tasks in this session using `superpowers:executing-plans`, batching with checkpoints for review. Faster turn-around but uses more main-context tokens.

Which approach?
