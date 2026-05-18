---
description: Create a GitHub Pull Request for the current feature branch
allowed-tools: Bash, Read
argument-hint: [base-branch]  # defaults to main
---

# Create Pull Request

## Context
- Current branch: !`git branch --show-current`
- Base branch (origin HEAD): !`git remote show origin 2>/dev/null | grep "HEAD branch" | cut -d: -f2 | xargs || echo "main"`
- Upstream set: !`git rev-parse --abbrev-ref --symbolic-full-name @{u} 2>/dev/null || echo "no upstream"`
- Unpushed commits: !`git log @{u}.. --oneline 2>/dev/null | head -10 || echo "branch not yet pushed"`
- Changed files: !`git diff --stat @{u}.. 2>/dev/null | tail -5 || git diff --stat main.. 2>/dev/null | tail -5`

## Task

Refuse if the current branch is `main` (or `master`). PRs must come from feature branches per `standards.md`.

1. Push the current branch (sets upstream on first push):

```bash
git push -u origin $(git branch --show-current)
```

2. Open the PR. Use `--fill` to seed title/body from commits, then let the user edit if needed:

```bash
gh pr create --base ${1:-main} --fill
```

3. After creation, surface the PR URL and CI status:

```bash
gh pr view --json url,number,state,statusCheckRollup -q '{url, number, state, checks: [.statusCheckRollup[] | {name, conclusion}]}'
```

If the PR body is auto-filled with a one-line commit message, suggest expanding it with: `## Summary`, `## Test plan`, and a link to the parent issue (`Closes #N`).
