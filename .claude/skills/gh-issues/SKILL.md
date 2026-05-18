---
description: List, view, and search GitHub issues for google-ads-mcp
allowed-tools: Bash, Read
argument-hint: [label-or-issue-number]
---

# GitHub Issues

## Context
- Repo: !`gh repo view --json nameWithOwner -q .nameWithOwner 2>/dev/null || echo "Not a GitHub repo"`
- Open count: !`gh issue list --state open --json number -q 'length' 2>/dev/null || echo "?"`
- Closed count: !`gh issue list --state closed --json number -q 'length' 2>/dev/null || echo "?"`
- Available phase labels: !`gh label list --limit 100 --json name -q '.[].name' 2>/dev/null | grep '^phase:' | tr '\n' ' '`

## Task

Pick the operation based on `$1`:

- **No arg or label** — list open issues, optionally filtered by label:
  ```bash
  gh issue list --state open ${1:+--label "$1"} --limit 30
  ```

- **Issue number (e.g. `#7` or `7`)** — show full issue details + comments:
  ```bash
  ISSUE=$(echo "$1" | tr -d '#')
  gh issue view "$ISSUE" --comments
  ```

After listing, suggest a next action:
- "Pick an issue with `/wf-core:wf-pick-issue`"
- "Break an epic down with `/wf-core:wf-breakdown #<N>`"
- "Check status with `/wf-core:wf-ticket-status #<N>`"

When listing all open issues, sort by phase label so the work order is visible (`phase:0-mvp` → `phase:1-safe-writes` → `phase:2-drafting` → `phase:3-hardening`).
