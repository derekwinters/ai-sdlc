# Specification — Dashboard (`DASH`)

One issue rendered from live state, showing what the pipeline is doing and what has gone wrong
with it. The only scheduled job in the pipeline, and it never writes to any issue but its own.

It is also where every fault the pipeline deliberately does not repair becomes visible. The
reconcile sweep was removed because auto-repair hid problems and occasionally caused them; the
bargain was that faults would be *reported* instead. This page is that half of the bargain.

`DASH` belongs to the **pipeline** capability.

Every requirement below is `auto` (covered by a named test) unless marked otherwise.

---

## Invariants

> **Invariant — the dashboard never writes to an issue other than itself.** It reports; it does not
> repair. A renderer that fixes things is a sweep by another name.

> **Invariant — rendering is pure.** Given the same state it produces the same text, so the output
> is diffable and a re-render that changes nothing is visible as such.

> **Invariant — a fault the pipeline chose not to repair appears here.** Every "reported, not
> fixed" decision elsewhere is a promise that this page keeps.

---

## 1. Fetching and rendering are separate

- **DASH-001** Fetching gathers state through the client and returns plain data.
- **DASH-002** Rendering takes that data and returns Markdown, touching no client.
- **DASH-003** Rendering is deterministic: identical state gives identical text.
- **DASH-004** Ordering is by issue number throughout, so a diff shows changes rather than
  shuffling.
- **DASH-005** A fetch failure for one section degrades that section rather than losing the page.

## 2. What it shows

- **DASH-010** The focus milestone, with its open and closed counts.
- **DASH-011** Issues by pipeline state, each linked and titled.
- **DASH-012** The ready queue, in the order the builder would take it.
- **DASH-013** An issue's blockers are named where it is blocked.
- **DASH-014** The concurrency cap and how many issues are in progress against it.
- **DASH-015** Every issue needing attention, not only those in the focus milestone. An issue
  parked in an unrelated milestone is still stuck.

## 3. Fault flags

Each of these corresponds to a repair the pipeline deliberately does not perform.

- **DASH-020** **Stalled command** — a comment carrying a bare 👀 by the bot, whose run died
  mid-flight.
- **DASH-021** **Stalled work** — an issue `in-progress` with no open pull request.
- **DASH-022** **Blocked but approved** — an approved issue whose blockers are unresolved, with
  them named.
- **DASH-023** **Unverifiable dependency** — a blocker whose milestone the configured ordering
  strategy cannot compare, so the ordering gate could not check it.
- **DASH-024** **Untracked** — an open issue carrying no pipeline state at all.
- **DASH-025** **Stale state** — a closed issue still carrying a pipeline label, meaning a close
  event was missed.
- **DASH-026** **Prose dependency** — a `Blocked by #N` written as text, invisible to the queue.
- **DASH-027** A section with no faults is omitted rather than shown empty, so the page is short
  when things are well.
- **DASH-028** A count of all faults appears near the top, so the page can be judged at a glance.

## 4. Overrides

- **DASH-030** `focus` and `cap` set by the gatekeeper are read as render overrides.
- **DASH-031** An override takes precedence over the milestone description marker for that render.
- **DASH-032** The dashboard issue's body is the render target; no other issue body is patched.

---

## Traceability

| Section | IDs | Tests |
|---|---|---|
| Fetching and rendering | DASH-001–005 | `test_dashboard_fetch.py` |
| What it shows | DASH-010–015 | `test_dashboard_render.py` |
| Fault flags | DASH-020–028 | `test_dashboard_faults.py` |
| Overrides | DASH-030–032 | `test_dashboard_fetch.py` |

**24 requirements, all `auto`.**
