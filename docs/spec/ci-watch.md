# Specification — CI watch (`CIW`)

Watching a pull request's checks to completion and reporting what happened.

It reports; it never fixes. A watcher that also repairs is a watcher whose reports you cannot
trust, because you can no longer tell whether a green result means the change was good or the
watcher patched it.

`CIW` belongs to the **pipeline** capability.

Every requirement below is `auto` (covered by a named test) unless marked otherwise.

---

## Invariants

> **Invariant — the watcher never modifies the pull request.** No pushes, no re-runs, no label
> changes. Resolution is the caller's decision.

> **Invariant — polling is bounded.** A watch that can run forever will, on the day a check hangs.

> **Invariant — silence is never success.** A watch that ends without a conclusive result says so,
> rather than returning something a caller will read as passing.

---

## 1. Waiting

- **CIW-001** The watcher polls until every check has completed.
- **CIW-002** A check that is queued or in progress is not complete.
- **CIW-003** Polling stops at a deadline, and a timeout is reported as a distinct outcome — not
  as a failure and not as a pass.
- **CIW-004** Polling stops after a maximum number of attempts as well as a deadline, so a
  mis-set clock cannot make it run forever.
- **CIW-005** The interval between polls is configurable, and defaults to something that does not
  hammer the API.
- **CIW-006** A pull request with no checks at all is reported as such rather than as passing.
  Nothing having run is not the same as everything having passed.

## 2. Reporting

- **CIW-010** The result names every check and its conclusion.
- **CIW-011** Checks are reported in a stable order.
- **CIW-012** A skipped check is not a failure.
- **CIW-013** A neutral conclusion is not a failure.
- **CIW-014** A cancelled check is a failure: it did not pass, and treating it as neutral hides a
  cancelled run.
- **CIW-015** The overall result is passing only when every check concluded successfully or was
  skipped or neutral.
- **CIW-016** A transient read failure is retried rather than ending the watch.
- **CIW-017** Repeated read failures end the watch as unreachable, reported distinctly from a
  check failure.

## 3. Failure detail

- **CIW-020** A failed check's log excerpt is included.
- **CIW-021** The excerpt is bounded, so one enormous log cannot flood the output.
- **CIW-022** The excerpt is taken from the end of the log, where the failure usually is.
- **CIW-023** A check whose log cannot be read is reported with the check name and the reason,
  rather than being omitted.
- **CIW-024** Check names are reported exactly as the API gives them, not prettified. A name that
  does not match the API cannot be used to configure a required check.

---

## Traceability

| Section | IDs | Tests |
|---|---|---|
| Waiting | CIW-001–006 | `test_ci_watch.py` |
| Reporting | CIW-010–017 | `test_ci_watch.py` |
| Failure detail | CIW-020–024 | `test_ci_watch_detail.py` |

**23 requirements, all `auto`.**
