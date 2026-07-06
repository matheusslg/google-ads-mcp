---
description: Check PR status, reviews, and CI checks for google-ads-mcp
allowed-tools: Bash, Read
argument-hint: [pr-number]  # defaults to PR for current branch
---

# PR Status

## Context
- Current branch: !`git branch --show-current`
- PR for current branch: !`gh pr list --head "$(git branch --show-current)" --json number,state,title -q '.[] | "#\(.number) [\(.state)] \(.title)"' 2>/dev/null || echo "no PR for this branch"`
- Open PRs in repo: !`gh pr list --state open --json number -q 'length' 2>/dev/null || echo "?"` open PR(s)

## Task

Resolve the PR to inspect:
- If `$1` is supplied, use it (strip leading `#`)
- Else use the PR for the current branch

```bash
PR=${1:-$(git branch --show-current)}
PR=$(echo "$PR" | tr -d '#')
```

Show the PR overview, comments, and CI rollup:

```bash
gh pr view "$PR" --comments
echo "---"
gh pr checks "$PR"
```

Interpret the result for the user:
- **All checks passing + at least one approval** → ready to merge
- **Failing checks** → list which jobs failed and which logs to read (`gh run view <run-id> --log-failed`)
- **CHANGES_REQUESTED reviews** → summarize what the reviewer asked for
- **No reviews yet** → suggest `gh pr ready` (if draft) or pinging a reviewer

Never run `gh pr merge` from this skill — merging is a separate, user-confirmed action.
