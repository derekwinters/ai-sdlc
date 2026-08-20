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

- **BLK-001** Reading an issue's blockers returns them from the native graph.
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

- **BLK-010** `Depends on: #N` lines in an issue body are soft dependencies.
- **BLK-011** Several numbers on one line are all read.
- **BLK-012** Several lines are all read.
- **BLK-013** The reference is case-insensitive and tolerates surrounding punctuation.
- **BLK-014** A mention of `#N` in ordinary prose is not a dependency.
- **BLK-015** A `Depends on:` inside a fenced code block is ignored.
- **BLK-016** Soft dependencies order the queue; they never gate it.

## 3. Prose blockers are drift

- **BLK-020** `Blocked by #N` written as text is found by the same reading rules.
- **BLK-021** Finding one is reported as drift, with the issue and the numbers.
- **BLK-022** A prose blocker is never treated as a real blocker. Honouring it would make the
  invisible-to-tooling form work, and it would stay.

## 4. Writing

- **BLK-030** Blocking creates a native blocked-by relationship, and nothing that reads the graph may also write it.
- **BLK-031** Creating one that already exists is a no-op, not an error.
- **BLK-032** Unblocking removes one.
- **BLK-033** Removing one that does not exist is a no-op, not an error.
- **BLK-034** An issue may not block itself; the attempt is refused.
- **BLK-036** A blocker is named to GitHub by its **database id**, never by its issue number. The
  two are different integers for the same issue, so sending one where the other is meant is
  accepted and writes an edge to whichever issue that value identifies. `block` and `unblock` take
  numbers — that is what a person says — and convert in one named place.
- **BLK-035** A cycle is refused, naming the path. Two issues each waiting for the other are both
  permanently ineligible.

## 5. Eligibility

- **BLK-040** An issue is eligible when every hard blocker is resolved.
- **BLK-041** An issue with no blockers is eligible.
- **BLK-042** One unresolved blocker is enough to make it ineligible.
- **BLK-043** An unknown blocker — one whose state could not be read — is treated as unresolved.
  Not knowing whether the thing you depend on is finished is not the same as it being finished.
- **BLK-044** The reason an issue is ineligible names the blockers responsible.

---

> **How the spec is changing (#153).** These requirements named functions — `blockers_of`,
> `depends_on`, `block`, `is_eligible` — in a module installed into consuming repositories, where
> nothing ever constructed the client every one of them took. They are behaviour now rather than
> signatures, and where the behaviour happens depends on who needs it: the **dashboard** reads the
> graph in code, because it runs in a workflow with nobody there; everything else is an agent's
> work through `github-api`, stated in the `issue-blockers` skill.
>
> The traversal was the reason to keep code, and it is also why code could not stay. A cycle check
> cannot know which issue to fetch next until it has read the last one, so it never decomposed into
> "fetch, then call a pure function" — it was always going to be the whole walk or none of it, and
> in a consumer it was none of it. `DIST-043`.

## Traceability

| Section | IDs | Tests |
|---|---|---|
| Reading | BLK-001–007 | `test_blockers_read.py` |
| Soft dependencies | BLK-010–016 | `test_blockers_rules.py` |
| Prose blockers are drift | BLK-020–022 | `test_blockers_text.py` |
| Writing | BLK-030–036 | `test_blockers_rules.py` |
| Eligibility | BLK-040–044 | `test_blockers_rules.py` |

**30 requirements, all `auto`.**

> **How the spec is changing (#155).** §4 said `block` creates a relationship and `unblock` removes
> one, and said nothing about what identifies the blocker. So the client sent an issue *number*
> where the API means a database id, GitHub accepted it, and `block(154, 153)` blocked #154 by
> **#4** — an unrelated issue — and reported success. `blockers_of` then read the edge back and
> reported #4, consistently, so a read-after-write confirmed a relationship nobody asked for.
>
> The invariant this breaks is `BLK`'s own: a prose blocker is invisible to the queue and a native
> one is a real gate. A native relationship pointing at the wrong issue is worse than either, because
> the queue honours it — the wrong issue gates the work and the right one does not.
>
> All 29 requirements were green throughout. `lib/fake_github.py` stored edges as `{"number": …}`
> with no `id` field at all, so the distinction the real API turns on did not exist in the double,
> and no test written against it could have expressed the defect. `API-056` states what the fake
> owes as a result: where a value changes meaning at the boundary, the fake must model the change,
> not the happy case.
