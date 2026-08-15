# Specification — Milestones (`MS`)

Milestone operations the GitHub MCP server does not provide. It exposes no milestone CRUD at all,
which is why milestone work in these repositories has been done by hand or skipped.

The existing implementations cover list, close and reopen. They do not cover **create** or
**edit**, despite one of them describing itself as "milestone CRUD the MCP server doesn't have".
That gap is why a milestone sometimes ends up created through the web interface without the
description the pipeline reads — a milestone that exists and is invisible to the thing meant to
consume it.

`MS` belongs to the **pipeline** capability.

Every requirement below is `auto` (covered by a named test) unless marked otherwise.

---

## Invariants

> **Invariant — a milestone is never deleted.** Deleting one detaches it from every issue that
> carried it and cannot be undone. Closing is always available and always reversible.

> **Invariant — closing refuses while open work remains, unless forced.** A milestone closed over
> open issues silently orphans them: they keep a milestone that no longer appears in any open list.

> **Invariant — the description is data, not prose.** The focus marker and the frozen marker are
> read from it, so an operation that rewrites a description preserves markers it was not asked to
> change.

---

## 1. Reading

- **MS-001** `list` returns every milestone with its number, title, state, and open and closed
  issue counts.
- **MS-002** Milestones are returned in a stable order — by number — so output is diffable.
- **MS-003** `find` resolves a milestone by exact title.
- **MS-004** `find` resolves by unique title prefix, so `v0.4` matches `v0.4 — Something`.
- **MS-005** An ambiguous prefix resolves to nothing rather than guessing.
- **MS-006** `find` searches open and closed milestones; a caller that means open only says so.
- **MS-007** `open_issue_count` reports how much work remains in a milestone.

## 2. Creating

- **MS-010** `create` makes a milestone with a title, and optionally a description and due date.
- **MS-011** Creating a milestone whose title already exists is refused, naming the existing one.
- **MS-012** An empty title is refused.
- **MS-013** A created milestone is returned with its assigned number, so a caller can use it
  immediately.
- **MS-014** `create` never sets a state other than open. A milestone created closed is a
  contradiction.

## 3. Editing

- **MS-020** `edit` changes any of title, description, due date.
- **MS-021** An omitted field is left unchanged; editing is not replacement.
- **MS-022** Editing a milestone that does not exist is refused, naming what was searched for.
- **MS-023** Renaming to a title another milestone already has is refused.
- **MS-024** Editing preserves description markers the caller did not ask to change.

## 4. Closing and reopening

- **MS-030** `close` refuses while the milestone has open issues, reporting how many.
- **MS-031** `close --force` closes anyway, and says how many issues it orphaned.
- **MS-032** Closing an already-closed milestone is a no-op, not an error.
- **MS-033** `reopen` reopens a closed milestone.
- **MS-034** Reopening an already-open milestone is a no-op, not an error.
- **MS-035** No operation deletes a milestone, and none is exposed that could.

## 5. Description markers

The description carries machine-read markers as well as prose. The focus milestone is matched live
from it, so a milestone created without the right marker is invisible to the pipeline.

- **MS-040** A description beginning `focus.` marks the focus milestone.
- **MS-041** Exactly one milestone may be the focus; `set_focus` clears the marker from any other.
- **MS-042** A description containing `frozen.` marks a milestone whose scope is settled.
- **MS-043** Markers are read case-insensitively and may appear with surrounding prose.
- **MS-044** Setting a marker preserves the prose around it.
- **MS-045** Clearing a marker preserves the prose around it.

---

## Traceability

| Section | IDs | Tests |
|---|---|---|
| Reading | MS-001–007 | `test_milestone_read.py` |
| Creating | MS-010–014 | `test_milestone_write.py` |
| Editing | MS-020–024 | `test_milestone_write.py` |
| Closing and reopening | MS-030–035 | `test_milestone_write.py` |
| Description markers | MS-040–045 | `test_milestone_markers.py` |

**27 requirements, all `auto`.**
