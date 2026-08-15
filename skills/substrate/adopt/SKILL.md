---
name: adopt
description: Join a repository to ai-sdlc, or move it to a newer version — plan the change read-only, apply it on a branch, and verify a repository still matches its pin. Use when adopting ai-sdlc, upgrading it, or checking whether a repository has drifted.
allowed-tools: Bash, Read, Write, Edit
---

# adopt

Joins one repository to ai-sdlc, run in place, when that repository is ready.

**There is no fleet operation.** `adopt` reads and writes only the repository it runs in. A single
command that changed eleven repositories at once would be exactly the "how many changes did that
just make" problem this project exists to avoid.

## The three commands

```bash
python3 .claude/skills/adopt/main.py plan   v0.4.0   # read-only
python3 .claude/skills/adopt/main.py apply  v0.4.0   # writes, on a branch
python3 .claude/skills/adopt/main.py verify v0.4.0   # read-only
```

`plan` is safe to run on a repository you have not decided about. It writes nothing at all and
tells you every file it would touch, every conflict, every trigger collision, and the manual tasks
only you can do.

**`apply` is also the upgrade path.** Running it at a higher pin updates managed files and leaves
everything else alone. Install and upgrade are one mechanism, so the upgrade path cannot rot
separately from the install path.

## It never overwrites what it did not write

Files `adopt` writes carry a provenance header — source, ref, content hash. That is how it tells
"we may update this" from "somebody else's file", and how it tells a locally-edited managed file
from a merely outdated one.

| State | What happens |
| --- | --- |
| absent | created |
| managed, at this pin | left alone |
| managed, older pin | updated |
| **no provenance, or edited since** | **reported as a conflict; never written** |

An edit is a conflict, not a stale file. Overwriting it would discard your change silently.

## Trigger collisions refuse the run

Two workflows handling one event race, and both write. `apply` **refuses** while an existing
workflow handles `issue_comment` or `issues` — the events where the pipeline is the sole writer.
Disable it in the same change, or acknowledge it deliberately.

`pull_request` is deliberately not checked. Almost every repository has a test workflow on it, they
coexist fine, and flagging them all would train you to acknowledge collisions without reading them.

Collisions are found by **trigger, not by file name** — a collision between differently-named
workflows is the one a file comparison misses.

## What it never touches

- **Labels are never renamed.** Renaming rewrites the label on every issue that carried it.
- **`CLAUDE.md` is never rewritten.** One import line is appended, once. Your rules are yours.
- **An existing dashboard issue is reused**, never duplicated.

Specification: `docs/spec/adopt.md` (`ADOPT`), 35 requirements.
