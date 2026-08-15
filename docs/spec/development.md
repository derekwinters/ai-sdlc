# Specification — Development queue (`DEV`)

Which approved issue gets built next, and the rules the builder works under.

The queue is where the derived-blockedness decision pays off. An issue's eligibility is computed
from the dependency graph every time the queue is built, so an issue whose blocker closed becomes
available on its own — nothing has to notice and wake it. That is why there is no blocked label,
and why the revisit machinery that used to maintain one no longer exists.

`DEV` belongs to the **pipeline** capability.

Every requirement below is `auto` (covered by a named test) unless marked otherwise.

---

## Invariants

> **Invariant — blockedness is derived at selection time, never stored.** An issue blocked today
> and unblocked tomorrow needs nothing done to it. Storing the state means maintaining it, and
> maintaining it means a sweep.

> **Invariant — a hard blocker gates; a soft dependency only orders.** Conflating them either
> stalls work that could proceed or builds things in the wrong order.

> **Invariant — one issue, one branch, one pull request.** A pull request closing four issues is
> not reviewable, and cannot be reverted for one of them.

---

## 1. Eligibility

- **DEV-001** An issue is eligible when it carries the approved state.
- **DEV-002** A closed issue is never eligible.
- **DEV-003** A parked issue is never eligible.
- **DEV-004** An issue already building is not eligible; it is already taken.
- **DEV-005** An issue with an unresolved hard blocker is not eligible.
- **DEV-006** An issue whose blockers are all resolved is eligible, with nothing having updated it.
- **DEV-007** An issue with an unknown blocker is not eligible; not knowing is not the same as
  resolved.
- **DEV-008** An issue with an open pull request is not eligible; the work exists already.

## 2. Ordering

- **DEV-010** Eligible issues are ordered so that a soft dependency is built before its dependent.
- **DEV-011** A soft dependency on an ineligible issue does not remove the dependent from the
  queue; it only cannot be ordered against it.
- **DEV-012** Issues with no ordering relationship keep issue-number order, so a run is
  reproducible.
- **DEV-013** A cycle among soft dependencies degrades to issue-number order rather than looping
  or dropping work.
- **DEV-014** The focus milestone is preferred: its issues come before others.

## 3. The cap

- **DEV-020** The queue is limited by the configured concurrency cap.
- **DEV-021** Issues already building count against the cap.
- **DEV-022** A cap already met yields an empty queue rather than an error.
- **DEV-023** No cap configured means no limit.
- **DEV-024** A truncated queue reports how many were left, so a partial run is not mistaken for a
  complete one.

## 4. Taking an issue

- **DEV-030** Taking an issue moves it to the building state.
- **DEV-031** Taking is refused if the issue is no longer eligible — the world may have changed
  since the queue was built.
- **DEV-032** One issue is taken at a time; the builder never holds two.
- **DEV-033** The branch name derives from the issue number, so the association is recoverable
  from the branch alone.

## 5. The agent's contract

Rules the `dev` agent works under, enforced by review and by the gates rather than by this module.

- **DEV-040** The agent writes the specification or contract change before the code.
- **DEV-041** The agent writes a failing test before the implementation, and shows the failure.
- **DEV-042** The agent's pull request body opens with a plain-English lead.
- **DEV-043** The agent's pull request body carries a `## Deviations and Decisions` section, even
  when empty.
- **DEV-044** The agent reconciles the documentation it affects in the same pull request.
- **DEV-045** The agent's pull request closes exactly one issue, with a closing keyword.
- **DEV-046** The agent reads the repository's own configuration for stack specifics rather than
  assuming a stack. *(manual: verified by the agent working unchanged across repositories.)*

---

## Traceability

| Section | IDs | Tests |
|---|---|---|
| Eligibility | DEV-001–008 | `test_dev_queue.py` |
| Ordering | DEV-010–014 | `test_dev_queue.py` |
| The cap | DEV-020–024 | `test_dev_queue.py` |
| Taking an issue | DEV-030–033 | `test_dev_take.py` |
| The agent's contract | DEV-040–046 | `test_dev_agent.py` |

**33 requirements, 32 `auto` and 1 `manual`.**
