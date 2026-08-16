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

The page is two charts and then five sections, in that order.

### Charts

- **DASH-010** A chart of open issues per **open milestone**, including milestones with none.
  An empty milestone is the signal that more planning runway exists; hiding it hides the thing
  the chart is for.
- **DASH-011** A chart of the focus milestone's issues by bucket, ordered **Unplanned → In
  planning → Ready → Done**, so it reads as a flow. Done is closed; Ready is approved or being
  built; In planning is any of the three planning states; Unplanned is everything left — the
  issues nobody has decided about yet.

  A **parked** issue appears in no bucket at all. Work deliberately set aside is not work waiting
  to be planned, and counting it as Unplanned put the same issue in two places in two different
  senses, when it already has a section of its own. The chart therefore counts fewer issues than
  the milestone holds, which is the honest reading: it shows the work in play.
- **DASH-012** Where no focus milestone resolves, the second chart is replaced by a line saying
  so. An empty chart is worse than a sentence: it looks like a finished milestone.

> **Invariant — a chart never hides a value behind another.** Mermaid's `xychart-beta` draws
> multiple `bar` series *overlaid from zero* rather than stacked, so a taller series conceals a
> shorter one entirely. Every chart is single-series.

- **DASH-013** Charts are horizontal. Labels then sit on the vertical axis with room to render in
  full; mermaid neither wraps nor rotates axis labels, so a horizontal chart is what removes the
  need to truncate them.
- **DASH-014** Chart height is derived from the number of bars, so the same chart is compact with
  three milestones and legible with twelve.
- **DASH-015** A label is escaped before it reaches the chart, so a milestone title containing a
  quote cannot break the syntax.

### Sections

- **DASH-016** Five sections — ready for work, pending approval, needs clarification, waiting for
  triage, parked — each collapsible, each carrying its count, each containing exactly one table.
- **DASH-017** A section renders even when empty, showing zero. The board's shape is then
  constant, and a missing section means a defect rather than an empty queue.
- **DASH-018** Every row links the issue, its milestone and its blockers, and shows `-` where
  there is no milestone or no blocker. A milestone link reads as the milestone's **name** and
  targets its number: `v0.5` identifies it, `#13` does not, and both go to the same page. Any text
  placed in a cell has its pipes escaped, or the row ends early and the table loses its shape.
- **DASH-019** Ready for work holds both approved and in-progress issues, and is the only section
  carrying a status column. Merging two states into one section makes it the only place where a
  row is otherwise ambiguous.

### What is counted

> **Invariant — a pull request is not an issue.** GitHub's issues endpoint returns both, and
> counting them together inflates every section and every chart.

- **DASH-006** Pull requests are excluded from every count, section and chart.
- **DASH-007** Closed issues are fetched, not only open ones. The Done bucket is closed issues by
  definition, and a fault about closed issues cannot fire against a list that never contains one.
- **DASH-008** Done is counted from the issues themselves, never from a milestone's
  `closed_issues` field, which counts pull requests too.

## 3. Fault flags

Each of these corresponds to a repair the pipeline deliberately does not perform.

- **DASH-020** **Stalled command** — a comment carrying a bare 👀 by the bot, whose run died
  mid-flight.
- **DASH-021** **Stalled work** — an issue `in-progress` with no open pull request.
- **DASH-022** **Blocked but approved** — an approved issue whose blockers are unresolved, with
  them named.
- **DASH-023** **Unverifiable dependency** — a blocker whose milestone the configured ordering
  strategy cannot compare, so the ordering gate could not check it.
- **DASH-025** **Stale state** — a closed issue still carrying a pipeline label, meaning a close
  event was missed.

> **How the spec is changing (#106).** `DASH-024` flagged an open issue carrying no pipeline
> state as a fault, under *Open issues outside the pipeline*. That list is now exactly the
> **Waiting for triage** section — which is defined as the complement of the five claimed states,
> so it already contains every untracked issue — and printing it twice made the fault count read
> as 28 problems when the real answer was none. The requirement is removed rather than reworded:
> the section is where an untriaged issue belongs, and a fault report should hold things that need
> a decision the board cannot show on its own.

- **DASH-026** **Prose dependency** — a `Blocked by #N` written as text, invisible to the queue.
- **DASH-027** A fault section with nothing in it is omitted rather than shown empty, so a page
  with nothing wrong carries no fault report at all. The charts and the five issue sections are a
  fixed skeleton and always render (`DASH-017`), so it is the presence of a fault heading, not the
  page's length, that signals attention is needed.
- **DASH-028** A count of all faults appears near the top, so the page can be judged at a glance.

## 4. Focus and cap

> **Invariant — the dashboard's own body is where focus and cap are stored.** The renderer writes
> the marker it just read, which is what makes the value survive between two independent workflow
> runs with no storage anywhere else.

- **DASH-030** Focus and cap are recorded as markers in the dashboard issue's body, and re-emitted
  by every render.
- **DASH-031** Precedence is override, then marker, then fallback. The override exists only to
  carry a command's value into the render that persists it.
- **DASH-032** The dashboard issue's body is the render target; no other issue body is patched.
- **DASH-033** The focus fallback is the lowest open version milestone with ready work, under the
  configured milestone ordering, so a repository that has never set a focus still has one.
- **DASH-034** An override naming no live milestone is refused rather than stored. A mistyped
  focus otherwise renders a board where every section is empty, which is indistinguishable from a
  finished milestone.

> **How the spec is changing (#106).** §4 used to say focus and cap were read from a marker on the
> **milestone's description**, and that an override applied for one render. Neither worked: nothing
> ever wrote the milestone marker — `set_focus()` has a passing test and no production caller — and
> the override was an in-memory value discarded when the gatekeeper's run ended, which cannot reach
> the dashboard's separate run. `/focus` therefore replied `Done` and changed nothing (#105). The
> store is now the dashboard's own body, which is what both `lucas-doggiehood` and
> `connor-multiplying-frogs` do, and the reason it works is that the renderer re-emits the marker
> rather than treating it as something a render would overwrite.

> **How the spec is changing (#106) — §2.** What the page showed was previously described as a
> focus headline, a board grouped by label, and a ready queue. It is now two charts and five
> collapsible sections with linked tables. The parts about *what is counted* — `DASH-005a` to
> `DASH-007` — are new rules rather than changed ones: the fetch counted pull requests as issues
> and never asked for closed issues at all, so `DASH-025` could not fire and a Done count was not
> derivable.

---

## Traceability

| Section | IDs | Tests |
|---|---|---|
| Fetching and rendering | DASH-001–005 | `test_dashboard_fetch.py` |
| What it shows — charts | DASH-010–015 | `test_dashboard_render.py` |
| What it shows — sections | DASH-016–019 | `test_dashboard_render.py` |
| What is counted | DASH-006–008 | `test_dashboard_fetch.py` |
| Fault flags | DASH-020–028 | `test_dashboard_faults.py` |
| Focus and cap | DASH-030–034 | `test_dashboard_fetch.py` |

**31 requirements, all `auto`.**
