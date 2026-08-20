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

- **MS-001** A listing returns every milestone with its number, title, state, and open and closed
  issue counts.
- **MS-002** Milestones are returned in a stable order — by number — so output is diffable.
- **MS-003** A milestone is resolved by exact title.
- **MS-004** A unique title prefix resolves, so `v0.4` matches `v0.4 — Something`.
- **MS-005** An ambiguous prefix resolves to nothing rather than guessing.
- **MS-006** Open and closed milestones are both searched; meaning open only is said out loud.
- **MS-007** How much work remains in a milestone is readable.

## 2. Creating

- **MS-010** Creating makes a milestone with a title, and optionally a description and due date.
- **MS-011** Creating a milestone whose title already exists is refused, naming the existing one.
- **MS-012** An empty title is refused.
- **MS-013** A created milestone is returned with its assigned number, so a caller can use it
  immediately.
- **MS-014** Nothing is created in a state other than open. A milestone created closed is a
  contradiction.

## 3. Editing

- **MS-020** Editing changes any of title, description, due date.
- **MS-021** An omitted field is left unchanged; editing is not replacement.
- **MS-022** Editing a milestone that does not exist is refused, naming what was searched for.
- **MS-023** Renaming to a title another milestone already has is refused.
- **MS-024** Editing preserves description markers the caller did not ask to change.

## 4. Closing and reopening

- **MS-030** Closing refuses while the milestone has open issues, reporting how many.
- **MS-031** Closing anyway is available deliberately, and says how many issues it orphaned.
- **MS-032** Closing an already-closed milestone is a no-op, not an error.
- **MS-033** Reopening a closed milestone is always available.
- **MS-034** Reopening an already-open milestone is a no-op, not an error.
- **MS-035** No operation deletes a milestone, and none is exposed that could.

## 5. Description markers

The description carries machine-read markers as well as prose. The focus milestone is matched live
from it, so a milestone created without the right marker is invisible to the pipeline.

- **MS-040** A description beginning `focus.` marks the focus milestone.
- **MS-041** Exactly one milestone is the focus; marking one clears the marker from every other, in the same operation.
- **MS-042** A description containing `frozen.` marks a milestone whose scope is settled.
- **MS-043** Markers are read case-insensitively and may appear with surrounding prose.
- **MS-044** Setting a marker preserves the prose around it.
- **MS-045** Clearing a marker preserves the prose around it.

---

> **How the spec is changing (#153).** These requirements named methods on a `Milestones(api)`
> class that was installed into consuming repositories, where nothing constructed the client it
> took. They are behaviour now, applied by an agent through `github-api`. Unlike blockers, no
> script manages milestones — the dashboard resolves its focus from a marker in its own body — so
> nothing here stayed as code. `DIST-043`.

## Traceability

| Section | IDs | Tests |
|---|---|---|
| Reading | MS-001–007 | `test_milestone_rules.py` |
| Creating | MS-010–014 | `test_milestone_rules.py` |
| Editing | MS-020–024 | `test_milestone_rules.py` |
| Closing and reopening | MS-030–035 | `test_milestone_rules.py` |
| Description markers | MS-040–045 | `test_milestone_rules.py` |

**27 requirements, all `auto`.**
