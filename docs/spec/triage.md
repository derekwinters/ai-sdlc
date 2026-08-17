# Specification — Triage (`TRI`)

Turning a reported issue into a plan somebody can approve, or a question somebody must answer.

Triage is the one place in the pipeline where an LLM makes a judgement rather than following a
rule. That is why most of this specification is about what it may **not** do: the deterministic
parts — which issues are eligible, where the result goes, what a hand-back looks like — are pinned
here so the judgement is confined to the part that actually needs it.

`TRI` belongs to the **pipeline** capability.

Every requirement below is `auto` (covered by a named test) unless marked otherwise.

---

## Invariants

> **Invariant — triage never invents a design decision.** Where the specification is silent about
> what something should do, triage asks rather than choosing. A plan that quietly decides a
> question nobody asked is worse than no plan, because it looks like an answer.

> **Invariant — triage proposes; it never approves.** It moves an issue to pending approval and
> stops. The one thing it must not do is put work into the build queue on its own.

> **Invariant — an issue is triaged at most once per admission.** Re-running triage on an issue
> already carrying a plan replaces nothing until it is sent back deliberately.

---

## 1. Selecting

- **TRI-001** An issue is eligible when it is queued for triage or already running. Both, because
  the handler that fires a session and the label write that records it are two operations: a
  session can reach this check before its own `running` label lands, and rejecting it then would
  make the routine refuse the very issue it was woken for.
- **TRI-009** A stalled issue is not eligible. The sweep gave up on it deliberately, and only
  `/admit` puts it back in the queue.
- **TRI-002** A closed issue is never eligible.
- **TRI-003** A parked issue is never eligible.
- **TRI-004** An issue already at pending approval is not eligible; its plan is waiting on a human.
- **TRI-005** An epic is never eligible. Its children are the work.
- **TRI-006** Selection is ordered by issue number, so a run is reproducible.
- **TRI-007** Selection is capped, and the cap is reported when it truncates. A silent cap makes a
  partial run look like a complete one.
- **TRI-008** Eligibility is computed from labels alone; it never reads issue bodies.


## 2. Routing

Every triaged issue ends in exactly one of three places.

- **TRI-010** A plan routes the issue to pending approval.
- **TRI-011** A question routes it to clarification.
- **TRI-012** An issue triage cannot act on at all routes back to triage with a comment saying why,
  so it is visible rather than silently stuck.
- **TRI-013** Routing writes exactly one state label.
- **TRI-014** Triage never writes the approved or building states.
- **TRI-015** The routing decision is reported, so a run's outcome is auditable without reading
  every issue.

## 3. What a plan contains

- **TRI-020** A plan opens with a plain-English summary of what is wrong or wanted, before any
  file name or class name.
- **TRI-021** A plan proposes a milestone.
- **TRI-022** A plan lists the acceptance checks that would make it done.
- **TRI-023** A plan names the specification pages it affects, or states that none change.
- **TRI-024** A plan that would change specified behaviour says how the specification changes.
- **TRI-025** A plan is refused if it has no acceptance checks. A plan nobody can verify is a
  wish.

## 4. Asking instead of guessing

- **TRI-030** A question states what is undecided and what the options are.
- **TRI-031** A question never picks an option, even to suggest a default.
- **TRI-032** An issue routed to clarification names who must answer.
- **TRI-033** A question that could be answered from the specification is not a question; it is a
  plan. *(manual: judged by the reviewer, not by a test.)*

## 5. Hand-back

- **TRI-040** Every routed issue receives a comment describing the outcome.
- **TRI-041** The comment states what happens next.
- **TRI-042** A hand-back comment is posted once per routing, not once per run.
- **TRI-043** A failed triage leaves the issue in triage and reports the failure, rather than
  routing it somewhere convenient.

---

## Traceability

| Section | IDs | Tests |
|---|---|---|
| Selecting | TRI-001–009 | `test_triage_select.py` |
| Routing | TRI-010–015 | `test_triage_route.py` |
| What a plan contains | TRI-020–025 | `test_triage_plan.py` |
| Asking instead of guessing | TRI-030–033 | `test_triage_plan.py` |
| Hand-back | TRI-040–043 | `test_triage_route.py` |

**27 requirements, 26 `auto` and 1 `manual`.**
