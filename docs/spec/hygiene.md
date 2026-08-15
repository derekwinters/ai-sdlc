# Specification — Pull request hygiene (`SYS`)

Rules about how a change lands, independent of what the change is. They apply to any repository
where pull requests are how work reaches the default branch.

`SYS` belongs to the **hygiene** capability and depends only on the substrate. In particular it
does not depend on the pipeline: a repository can adopt these checks without adopting an issue
lifecycle, and the checks must never import from it.

Every requirement below is `auto` (covered by a named test) unless marked otherwise.

---

## Invariants

> **Invariant — a required check always runs and always reports.** A check skipped by a workflow
> condition stays pending forever and blocks the merge it was meant to permit. An escape hatch
> makes a check *pass*; it never makes it absent.

> **Invariant — the escape hatch is a deliberate, visible act.** Applying a label is a decision
> recorded on the pull request, not a configuration nobody can see.

---

## 1. Closing keywords

An issue whose work has merged should close. When it does not, it sits in a working state and the
board misreports what is in flight — the condition the deleted reconcile sweep existed to repair.
Requiring the keyword removes the condition instead of detecting it.

- **SYS-001** A pull request body containing `Closes #N`, `Fixes #N` or `Resolves #N` satisfies the
  check.
- **SYS-002** Matching is case-insensitive.
- **SYS-003** The keyword's other forms — `close`, `closed`, `fix`, `fixed`, `resolve`, `resolved`
  — are accepted, as GitHub accepts them.
- **SYS-004** A cross-repository reference (`owner/repo#N`) satisfies the check.
- **SYS-005** A bare mention (`#N`) or a `Refs #N` does not. Those link without closing, which is
  the failure this check exists to prevent.
- **SYS-006** A keyword inside a fenced code block does not count, since it does not close anything
  either.
- **SYS-007** An empty or absent body does not satisfy the check.
- **SYS-008** The check reports which keyword it found and which issue, so a passing run is
  evidence rather than silence.

## 2. The escape hatch

- **SYS-010** A pull request labelled `no-closing-keyword` passes without one.
- **SYS-011** The label's effect is reported in the check's output, so the exemption is visible in
  the run rather than only on the pull request.
- **SYS-012** The check runs and passes when labelled; it is never skipped. A skipped required
  check stays pending and blocks the merge.
- **SYS-013** The label name is fixed, not configurable. A required check's escape hatch that
  varies per repository is one nobody can reason about across repositories.

## 3. Running

- **SYS-020** The check is a script runnable alone, taking the body on standard input or as an
  argument.
- **SYS-021** It exits `0` when satisfied and `1` when not.
- **SYS-022** It uses only the standard library.
- **SYS-023** It never reads the network. The body and labels are supplied by the workflow.

---

## Traceability

| Section | IDs | Tests |
|---|---|---|
| Closing keywords | SYS-001–008 | `test_closing_keyword.py` |
| The escape hatch | SYS-010–013 | `test_closing_keyword.py` |
| Running | SYS-020–023 | `test_closing_keyword.py` |

**16 requirements, all `auto`.**
