---
name: docs-gate
description: Require a pull request that changes code to change documentation too, or to say deliberately that it needs none. Use when setting up the docs reconciliation gate, or when a pull request genuinely needs no documentation change.
allowed-tools: Bash, Read
---

# Documentation gate

A pull request that changes code should change documentation too.

Not because every change needs a paragraph — but because deciding it *doesn't* should be a
decision somebody made, rather than one nobody thought about. The `skip-docs` label is that
decision, recorded where a reviewer can see it.

## Running it

```bash
git diff --name-only "$BASE" "$HEAD" | \
  PR_LABELS="$PR_LABELS" python3 .claude/skills/docs-gate/check_docs_changed.py
```

Exits `0` when satisfied, `1` when not, and always prints which files it judged code and which
documentation — so a surprising verdict is explainable rather than mysterious.

## The escape hatch passes; it does not skip

Apply **`skip-docs`** and the check passes, saying why. As everywhere else here, an escape hatch
makes a check *pass* — never absent. A skipped required check stays pending forever and blocks the
merge it was meant to permit.

## What counts

| | |
| --- | --- |
| Documentation | anything under `docs/`, and any `*.md` or `*.rst` |
| Ignored entirely | `.gitignore`, `LICENSE`, lockfiles — neither code nor docs |
| Code | everything else |

The patterns are configurable when a repository keeps its documentation somewhere else.

A pull request that changes only documentation passes. One that changes neither passes too —
there is nothing to reconcile.

Specification: `docs/spec/profiles.md` (`PROF`), 15 requirements.
