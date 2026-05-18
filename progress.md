# Project Progress

> This file tracks progress across sessions. Update before ending each session.
> **Keep this file under 400 lines** - archive old sessions to `.claude/session-archive/`

## Current Status
**Phase**: Phase 0 — MVP Read-Only (in progress)
**Last Updated**: 2026-05-18

---

### Session 3 (2026-05-18)
**Focus**: Issue #1 — Bootstrap project skeleton (executed via `superpowers:subagent-driven-development`)
**Completed**:
- `uv init --package` scaffold (commit `6b38213`), then replaced generated `pyproject.toml` with the spec'd content (PEP 621 + PEP 735 + PEP 639) in `98d6ed2`
- Placeholder `README.md` marked with TODO comment to signal future agents it would be overwritten (`5c9a7f1`)
- `.python-version` (3.11) + `.gitignore` with Python/uv/secrets ignores (`b832274`)
- `src/google_ads_mcp/__init__.py` (version from `importlib.metadata`) + `src/google_ads_mcp/server.py` (FastMCP instance + `ping` no-op tool + `main()`) + `tests/__init__.py` + `tests/test_server.py` — TDD red→green cycle, single commit (`d958f56`)
- Ruff `RUF022` fix sorting `__all__` (`c1e1b12`)
- Full README skeleton with Install / Claude Desktop config / First call / Safety placeholder / Development / License sections (`cf66043`)
- `uv.lock` committed; ruff + ruff-format + mypy + pytest gates all clean
**Discovered**: FastMCP 3.3.1 is current stable (spec's `>=2.0` floor accommodated; API surface — `from fastmcp import FastMCP` and `@mcp.tool` decorator — verified working)
**Branch**: `feat/issue-1-bootstrap` (built atop spec commit `2ccb67d` and plan commit `0cfdae2`)
**Result**: PR #17 merged into `main`.

### Session 2 (2026-05-18)
**Focus**: `/wf-core:wf-generate` — scaffold agents and skills for the Python/MCP stack
**Completed**:
- Created 2 agents under `.claude/agents/`:
  - `google-ads-mcp-backend` (Python/MCP-customized — diverges from the generic web-flavored template to match the actual stack: FastMCP, google-ads SDK, OAuth2, uv, pytest, ruff, mypy. Encodes the PRD safety model.)
  - `google-ads-mcp-reviewer` (read-only, with PRD-specific review checklist)
- Created 6 skills under `.claude/skills/`: `py-test`, `py-lint`, `uv-deps`, `gh-pr`, `gh-issues`, `gh-pr-status`
- Updated `.claude/workflow.json`: `scopes: ["backend"]`, `agents` map, `init_script: "uv sync"`
- Rewrote `standards.md` with Python/uv conventions, MCP tool-design contracts, mutation safety checklist, file-layout starting point
- Branch: `chore/wf-generate` (per the never-commit-to-main rule)
**Skipped intentionally — no stack fit**: `ui-developer`, `fullstack-developer`, `generic-developer`, docker-*, db-*, visual-verify, agent-browser, nest-*, next-*
**Result**: PR #16 merged into `main` (after rebase to resolve `progress.md` conflict with Session 3 entry).

### Session 1 (2026-05-17)
**Focus**: Project initialization + PRD parsing
**Completed**:
- Initialized git repository (`main`)
- Created public GitHub repo: `matheusslg/google-ads-mcp`
- Created workflow scaffolding: `.claude/workflow.json`, `progress.md`, `standards.md` (generic placeholder)
- Pushed `main` to origin; switched origin from SSH to HTTPS (gh-token-backed) because no local SSH key was wired
- Added MIT LICENSE (`Copyright (c) 2026 Matheus Nascimento Cavallini`)
- Created 15 parent issues (#1–#15) from PRD via `/wf-core:wf-parse-prd`, covering Phases 0–3
- Created labels: `phase:0-mvp`, `phase:1-safe-writes`, `phase:2-drafting`, `phase:3-hardening`, `type:epic`, `priority:p0`, `priority:p1`, `admin`
**Notable choice**: Moved "Apply for Google Ads API Basic Access" from Phase 1 (where the PRD listed it) to Phase 0 (#2), because approval takes 1–4 weeks and would otherwise block Phase 1 testing.

---

## Session Archive

> When this file exceeds 500 lines, move older sessions to `.claude/session-archive/sessions-{N}-{M}.md`
> Keep only the last 5 sessions in this file for AI readability.

## In Progress
- None — both bootstrap PRs (#16 wf-generate, #17 issue #1) merged. Phase 0 development can begin.

## Next Session Should
- [ ] File the Basic Access application (#2) — external SLA is 1–4 weeks; start day-1 to avoid blocking Phase 1
- [ ] Start #3 (OAuth2 setup helper) — unblocks all read tools (#4, #5, #6)
- [ ] Resolve PRD Open Questions before breaking down #3 and #5:
  - default `customer_id` config? (affects #3)
  - language for `summarize_performance`? (affects #5)
  - test fixtures: synthetic vs anonymized real? (affects every Phase 0 test)

## Decisions Made
- **Ticketing platform**: GitHub Issues (matches MIT/OSS distribution model)
- **Repository visibility**: Public (MIT license, per PRD)
- **Distribution model**: `uvx` (per PRD — same playbook as `google-search-console-mcp`; reference repo is TypeScript/Node, so it informs project shape only, not language stack)
- **Backend agent**: customized for Python/MCP rather than using the web-flavored template verbatim, to avoid agent prompts that reference non-existent HTTP/DB concepts
- **Skill set**: minimal MCP-appropriate (6 skills) rather than the full menu — no UI, no DB, no Docker in this project
- **Day-1 server scaffold**: src-layout, `uv init --package`, single-file `server.py` (modular split deferred until first real tool lands in #4)
- **`init_script`**: `uv sync` (set in `workflow.json` during Session 2; functional once Session 3's `pyproject.toml` landed)
- **Author email on PyPI metadata**: `nascimentocavallini@hotmail.com` for v0.0.1; revisit before v0.1.0 (#7) if a noreply form is preferred

## Notes
- PRD.md is in the repo root and is the source of truth for scope, non-goals, and tool surface
- Reference implementation playbook: https://github.com/matheusslg/google-search-console-mcp
- Spec for issue #1: `docs/specs/2026-05-18-issue-1-bootstrap-design.md`; plan: `docs/plans/2026-05-18-issue-1-bootstrap-plan.md`
- FastMCP version pulled by uv at scaffold time: 3.3.1 (constraint `>=2.0`); decorator form `@mcp.tool` without parens confirmed working
- PRD line references in issue bodies are pinned to the committed PRD.md — if the PRD is edited, those references may drift
