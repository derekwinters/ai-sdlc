# Specification — Release flow (`REL`)

Driving release-please's release pull request to a tagged release.

Two things make this worth specifying rather than doing by hand. Releases are rare enough that
nobody remembers the gotchas, and the gotchas are the kind that produce a silently wrong version
rather than an error.

`REL` belongs to the **release** capability and depends on the substrate and hygiene.

Every requirement below is `auto` (covered by a named test) unless marked otherwise.

---

## Invariants

> **Invariant — the release pull request's state is never toggled to influence CI.** Closing and
> reopening a pull request to restart parked checks looks harmless and loses the review, the
> approval, and sometimes the pull request's association with its release. If checks need
> attention, the flow halts and says so.

> **Invariant — the squash title is the release commit.** It is the one commit release-please
> parses for the next version, so it is composed here rather than taken from whatever the pull
> request happens to be called.

> **Invariant — a release is verified after the fact.** Tag, release and version are checked to
> exist, because "the merge succeeded" and "the release happened" are different claims.

---

## 1. Finding the release pull request

- **REL-001** The release pull request is identified by its head branch, not by its title. A title
  can be edited; the branch is release-please's.
- **REL-002** No release pull request open is a clean outcome, not an error. There may be nothing
  to release.
- **REL-003** More than one is refused, naming them. Guessing which to merge is not acceptable.
- **REL-004** The version being released is read from the pull request, not inferred from the
  title.

## 2. Before merging

- **REL-005** The flow refuses to merge while any check is failing.
- **REL-006** The flow refuses to merge while any check is still running.
- **REL-007** A pull request with no checks at all is refused, not merged. Nothing having run is
  not the same as everything having passed.
- **REL-008** The flow halts for the owner rather than toggling the pull request's state to
  restart checks.
- **REL-009** A halt says exactly what is wrong and what would resolve it.

## 3. The squash title

- **REL-010** The title is `chore(main): release X.Y.Z`, composed from the version.
- **REL-011** The title is never taken from the pull request's own title.
- **REL-012** A title that is not a valid Conventional Commit is refused before merging.

## 4. Forcing a version

- **REL-020** A release may be forced to a specific version with a `Release-As:` footer, so a
  milestone boundary and a version can be made to match.
- **REL-021** A forced version must be a valid semantic version.
- **REL-022** A forced version lower than the current one is refused.

## 5. Verifying afterwards

- **REL-030** After merging, the tag is confirmed to exist.
- **REL-031** The GitHub release is confirmed to exist.
- **REL-032** The recorded version is confirmed to match what was released.
- **REL-033** A missing tag or release is reported as an incomplete release, distinctly from a
  failed merge.
- **REL-034** Verification is retried briefly, because tagging follows the merge by a moment.

---

## Traceability

| Section | IDs | Tests |
|---|---|---|
| Finding the release pull request | REL-001–004 | `test_release_find.py` |
| Before merging | REL-005–009 | `test_release_gate.py` |
| The squash title | REL-010–012 | `test_release_gate.py` |
| Forcing a version | REL-020–022 | `test_release_version.py` |
| Verifying afterwards | REL-030–034 | `test_release_verify.py` |

**23 requirements, all `auto`.**
