---
name: closing-keyword
description: Require a closing keyword on a pull request, so the issue its work resolves actually closes on merge. Use when setting up or debugging the closing-keyword required check, or when a pull request deliberately closes no issue and needs the escape hatch.
allowed-tools: Bash, Read
---

# Closing keyword

An issue whose work has merged should close. When it does not, it sits in a working state and the
board misreports what is in flight. This check requires `Closes #N` (or `Fixes`/`Resolves`) in the
pull request body, so the condition never arises rather than being repaired afterwards.

## Running it

```bash
echo "$PR_BODY" | PR_LABELS="$PR_LABELS" \
  python3 .claude/skills/closing-keyword/check_closing_keyword.py
```

Exits `0` when satisfied, `1` when not. Always prints its reasoning: a required check that says
nothing on success gives a reviewer no way to tell "passed" from "never ran".

## When a pull request deliberately closes nothing

Apply the **`no-closing-keyword`** label. The check then passes and says why.

**It passes; it does not skip.** A required check skipped by a workflow condition stays pending
forever and blocks the merge it was meant to permit. If you are wiring this into a workflow, do not
add an `if:` that skips the job — let it run and let the label decide the outcome.

## What counts

| Accepted | Not accepted |
| --- | --- |
| `Closes #12`, `Fixes #12`, `Resolves #12` | `Refs #12`, `See #12`, a bare `#12` |
| Any tense: `close`, `closed`, `fixes`, `resolved` | A keyword with no issue number |
| `Closes owner/repo#12` | A keyword inside a fenced code block |

The fence rule is not pedantry: GitHub does not close an issue from inside a code fence either, so
accepting one would pass a pull request that then fails to close its issue.

Specification: `docs/spec/hygiene.md` (`SYS`).
