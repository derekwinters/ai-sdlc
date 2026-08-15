---
name: issue-blockers
description: Create, remove and read native GitHub issue dependency relationships, and detect dependencies written as prose where the pipeline cannot see them. Use whenever one issue must finish before another may start, or when checking why an issue is not eligible for work.
allowed-tools: Bash, Read
---

# Issue blockers

GitHub's issue-dependency API has **no MCP tool**. Without this skill there is no way for an agent
to create or read a native relationship — which is why dependencies here have historically been
written as prose in issue bodies, where the queue cannot see them and the builder starts the issue
anyway.

## Three kinds of reference, and only one is a gate

| Form | Meaning | Effect |
| --- | --- | --- |
| Native blocked-by | a hard gate | the issue is ineligible until resolved |
| `Depends on: #N` | an ordering hint | orders the queue, never gates it |
| `Blocked by #N` in prose | **drift** | found, reported, never honoured |

The third is deliberate. Honouring a prose blocker would make the invisible-to-tooling form work,
and it would stay. It is reported so it can be converted.

## Using it

```python
from issue_blockers import Blockers, is_eligible

ops = Blockers(api)
ops.block(50, 42)            # #50 is blocked by #42
ops.unblock(50, 42)

blockers = ops.blockers_of(50)
is_eligible(50, blockers)    # .eligible, and .reason naming what blocks it
```

Both writes are no-ops when already in the wanted state, so they are safe to repeat.

## What is refused

- An issue blocking itself.
- A cycle, direct or indirect — the refusal draws the path. Two issues each waiting for the other
  are both permanently ineligible, which is a mess to diagnose after the fact.

A diamond is not a cycle: two issues may both depend on the same third one.

## Blockedness is never stored

There is no blocked label, and there never will be. Eligibility is computed from the graph at
selection time, which is what keeps it correct without anything having to maintain it. An issue
whose blocker closes becomes eligible on its own — nothing needs to wake it.

**An unknown blocker counts as unresolved.** Not knowing whether the thing you depend on is
finished is not the same as it being finished.

Specification: `docs/spec/blockers.md` (`BLK`), 29 requirements.
