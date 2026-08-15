# Specification — Adoption (`ADOPT`)

Joining a repository to ai-sdlc, and moving it between versions afterwards.

Adoption is per-repository and run in place. There is no fleet operation: `adopt` reads and writes
only the repository it runs in. A single command that changed eleven repositories would be exactly
the "how many changes did that just make" problem this project exists to avoid.

`ADOPT` belongs to the **substrate** capability.

Every requirement below is `auto` (covered by a named test) unless marked otherwise.

---

## Invariants

> **Invariant — `plan` writes nothing.** It is the read-only half, and it must stay safe to run on
> a repository you have not decided about.

> **Invariant — `apply` never replaces content it did not create.** Provenance decides. Anything
> else is a conflict for the owner to resolve, not a file to overwrite.

> **Invariant — `apply` refuses while an unacknowledged workflow listens on an event it claims.**
> Two handlers on one event is worse than none: they race, and both write.

> **Invariant — `apply` works on a branch, never the default branch.** Every adoption and every
> upgrade is a reviewable pull request.

---

## 1. Detecting

- **ADOPT-001** The repository's stack is detected from marker files.
- **ADOPT-002** Detection proposes profiles; it never enables them silently.
- **ADOPT-003** An undetectable stack is reported rather than guessed at.
- **ADOPT-004** Detection is reported so the owner can correct it.
- **ADOPT-005** An existing `repo-config.yml` takes precedence over detection.

## 2. Planning

- **ADOPT-010** `plan` reports every file it would create, update or leave.
- **ADOPT-011** `plan` makes no write of any kind.
- **ADOPT-012** `plan` reports the manual tasks the owner must do.
- **ADOPT-013** `plan` reports conflicts separately from ordinary changes.
- **ADOPT-014** `plan` reports trigger collisions separately again, because they are the dangerous
  ones.
- **ADOPT-015** `plan` on an already-adopted repository at the same version reports no changes.

## 3. Classification

Every path adoption owns falls into exactly one class.

- **ADOPT-020** **Absent** — nothing there; it will be created.
- **ADOPT-021** **Managed and current** — provenance matches the pin; left alone.
- **ADOPT-022** **Managed and stale** — provenance from an earlier pin; updated.
- **ADOPT-023** **Conflict** — present with no provenance, or content differing from what the pin
  says it should be; reported, never written.
- **ADOPT-024** Provenance is the frontmatter written at install: source repository, ref and
  content hash.
- **ADOPT-025** A file whose content hash matches its recorded provenance is unmodified; a
  differing hash means the consumer edited it, which is a conflict rather than a stale file.

## 4. Trigger collisions

- **ADOPT-030** An existing workflow listening on an event the adoption claims is a collision.
- **ADOPT-031** Collisions are detected from workflow triggers, not from file names. A collision
  between differently-named files is the one a file comparison misses.
- **ADOPT-032** `apply` refuses while a collision is unacknowledged.
- **ADOPT-033** A collision may be acknowledged, which records the decision in configuration
  rather than merely silencing it.
- **ADOPT-034** The events checked are those where the pipeline is the **sole writer**:
  `issue_comment` and `issues`. `pull_request` is deliberately excluded — almost every repository
  has a test or lint workflow on it, they coexist happily, and flagging them all would train the
  owner to acknowledge collisions without reading them, which defeats the mechanism entirely.
- **ADOPT-035** Collisions are only checked for events the adoption actually installs a handler
  for. A repository taking only the hygiene capability installs no issue handler, so another
  repository's issue workflow is not its concern.

## 5. Applying

- **ADOPT-040** `apply` writes to a branch.
- **ADOPT-041** `apply` is idempotent: a second run with no version change writes nothing.
- **ADOPT-042** `apply` never renames an existing label.
- **ADOPT-043** `apply` never rewrites `CLAUDE.md`; it inserts an import line or reports that one
  is needed.
- **ADOPT-044** `apply` reuses an existing dashboard issue rather than creating a second.
- **ADOPT-045** `apply` records the version it installed, so the next run can compare.
- **ADOPT-046** Upgrading is the same operation: `apply` at a higher version updates managed files
  and leaves conflicts alone.

## 6. Verifying

- **ADOPT-050** `verify` reports whether the repository matches its recorded version.
- **ADOPT-051** `verify` fails when an installed capability's dependencies are absent.
- **ADOPT-052** `verify` fails when a managed file has been edited locally.
- **ADOPT-053** `verify` reports recorded exceptions rather than hiding them, so a repository
  keeping its own version of something is visibly non-standard.
- **ADOPT-054** `verify` writes nothing.

---

## Traceability

| Section | IDs | Tests |
|---|---|---|
| Detecting | ADOPT-001–005 | `test_adopt_detect.py` |
| Planning | ADOPT-010–015 | `test_adopt_plan.py` |
| Classification | ADOPT-020–025 | `test_adopt_classify.py` |
| Trigger collisions | ADOPT-030–035 | `test_adopt_collision.py` |
| Applying | ADOPT-040–046 | `test_adopt_apply.py` |
| Verifying | ADOPT-050–054 | `test_adopt_verify.py` |

**35 requirements, all `auto`.**
