# Specification — Blockers (`BLK`)

Dependency relationships between issues: which must finish before which may start.

GitHub's issue-dependency API has no MCP tool, so without this there is no way to create or read a
native relationship from an agent — which is why dependencies in these repositories have been
written as prose in issue bodies, where the pipeline cannot see them.

`BLK` belongs to the **pipeline** capability.

Every requirement below is `auto` (covered by a named test) unless marked otherwise.

---

## Invariants

> **Invariant — a hard blocker is a native relationship, never prose.** Prose is invisible to the
> queue, so an issue "blocked by #42" in its body is one the builder will start anyway.

> **Invariant — blockedness is derived, never stored.** There is no blocked label. An issue's
> eligibility is computed from the graph at selection time, which is what makes the state correct
> without anything having to maintain it.

> **Invariant — an unreadable dependency is reported, not assumed resolved.** Failing to read the
> graph must not silently make work eligible.

---

## 1. Reading

- **BLK-001** `blockers_of(issue)` returns the issues blocking it, from the native graph.
- **BLK-002** Each carries its number, state and milestone, so a caller can judge without a second
  read.
- **BLK-003** A closed blocker is marked resolved.
- **BLK-004** A merged blocker is marked resolved.
- **BLK-005** An open blocker is not resolved.
- **BLK-006** An issue with no blockers returns an empty list, not an error.
- **BLK-007** A failing read raises rather than returning empty. Empty means "nothing blocks
  this", and a failed read must never be mistaken for it.

## 2. Soft dependencies

An ordering hint rather than a gate. GitHub has no native form, so these stay structured text.

- **BLK-010** `depends_on(body)` reads `Depends on: #N` lines from an issue body.
- **BLK-011** Several numbers on one line are all read.
- **BLK-012** Several lines are all read.
- **BLK-013** The reference is case-insensitive and tolerates surrounding punctuation.
- **BLK-014** A mention of `#N` in ordinary prose is not a dependency.
- **BLK-015** A `Depends on:` inside a fenced code block is ignored.
- **BLK-016** Soft dependencies order the queue; they never gate it.

## 3. Prose blockers are drift

- **BLK-020** `prose_blockers(body)` finds `Blocked by #N` written as text.
- **BLK-021** Finding one is reported as drift, with the issue and the numbers.
- **BLK-022** A prose blocker is never treated as a real blocker. Honouring it would make the
  invisible-to-tooling form work, and it would stay.

## 4. Writing

- **BLK-030** `block(issue, by)` creates a native blocked-by relationship.
- **BLK-031** Creating one that already exists is a no-op, not an error.
- **BLK-032** `unblock(issue, by)` removes one.
- **BLK-033** Removing one that does not exist is a no-op, not an error.
- **BLK-034** An issue may not block itself; the attempt is refused.
- **BLK-035** A cycle is refused, naming the path. Two issues each waiting for the other are both
  permanently ineligible.

## 5. Eligibility

- **BLK-040** `is_eligible(issue, blockers)` is true when every hard blocker is resolved.
- **BLK-041** An issue with no blockers is eligible.
- **BLK-042** One unresolved blocker is enough to make it ineligible.
- **BLK-043** An unknown blocker — one whose state could not be read — is treated as unresolved.
  Not knowing whether the thing you depend on is finished is not the same as it being finished.
- **BLK-044** The reason an issue is ineligible names the blockers responsible.

---

## Traceability

| Section | IDs | Tests |
|---|---|---|
| Reading | BLK-001–007 | `test_blockers_read.py` |
| Soft dependencies | BLK-010–016 | `test_blockers_text.py` |
| Prose blockers are drift | BLK-020–022 | `test_blockers_text.py` |
| Writing | BLK-030–035 | `test_blockers_write.py` |
| Eligibility | BLK-040–044 | `test_blockers_read.py` |

**29 requirements, all `auto`.**
