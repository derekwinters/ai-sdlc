---
name: pipeline-dev
description: Build the development queue from approved issues and claim one for work. Use when deciding what to build next, or when working out why an approved issue is not being picked up.
allowed-tools: Bash, Read
---

# Development queue

Which approved issue gets built next, and claiming it.

## Eligibility is derived, every time

An issue is eligible when it is approved, open, not parked, not already building, has no open pull
request, and **every hard blocker is resolved** — computed from the dependency graph at the moment
the queue is built.

That last part is why there is no blocked label. An issue whose blocker closed becomes eligible on
its own, with nothing having noticed or updated it. Storing blockedness would mean maintaining it,
and maintaining it is what the deleted revisit sweep did.

## Hard blockers gate; soft dependencies only order

| | Effect |
| --- | --- |
| Native blocked-by | the issue is **not eligible** until it resolves |
| `Depends on: #N` | eligible regardless, but built **after** what it follows |

Conflating them either stalls work that could proceed, or builds things in the wrong order.

## Ordering

Topological on soft dependencies first, then the focus milestone, then issue number. A dependency
always beats the focus preference — building a dependent before its dependency is wrong in a way
that "wrong milestone first" is not.

A cycle among soft dependencies **degrades to issue-number order**. Dropping the issues would hide
work; looping would hang the run.

## The cap

Issues already building count against it, so a cap of 2 with one in flight yields one issue. A cap
already met yields an empty queue, not an error. When the cap truncates, the result says how many
were left — a silent cap makes a partial run look complete.

## Claiming

```python
take(api, 7, labels=config.labels)   # → in-progress, returns the branch
```

**Taking re-checks eligibility before writing.** The queue was built from a snapshot; between then
and now the issue may have been parked, taken, or closed. The branch is `claude/issue-<number>`, so
a branch found months later still says which issue it belongs to.

Specification: `docs/spec/development.md` (`DEV`), 33 requirements.
