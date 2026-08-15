---
name: milestone-ops
description: Create, edit, close, reopen and inspect GitHub milestones, including the create and edit the MCP server does not provide. Use whenever a milestone must be made, renamed, re-described, closed at the end of a release, or checked for remaining open work.
allowed-tools: Bash, Read
---

# Milestone ops

The GitHub MCP server exposes **no** milestone operations at all. This skill is how milestones are
managed — including creating and editing them, which the earlier implementations of this skill
lacked despite calling themselves "milestone CRUD".

That gap matters more than it looks: the focus milestone is matched live from a milestone's
**description**, so one created through the web interface without the right marker exists and is
invisible to the pipeline meant to consume it.

## Reading

```python
from milestone_ops import Milestones
ms = Milestones(api)

ms.list()                      # every milestone, ordered by number
ms.find("v0.4")                # exact title, or unique prefix; never guesses
ms.open_issue_count("v0.4")    # how much work remains
ms.focus()                     # the milestone marked focus, or None
```

An ambiguous prefix resolves to nothing. Two candidates means picking one would be a guess.

## Creating and editing

```python
ms.create("v0.4 — Adoption", description="focus. the adopt command")
ms.edit("v0.4", description="new words")     # only what you name changes
ms.edit("v0.4", title="v0.4 — Renamed")
```

`edit`'s first argument finds the milestone; the keywords change it. An omitted field is left
alone — editing is not replacement.

**Editing a description preserves markers you did not mention.** Rewriting the prose of the focus
milestone does not silently stop it being the focus.

## Closing

```python
ms.close("v0.4")               # refuses while open issues remain
ms.close("v0.4", force=True)   # closes anyway, reports how many it orphaned
ms.reopen("v0.4")
```

The refusal is not bureaucracy: issues in a closed milestone carry a milestone that no longer
appears in any open list, so they become hard to find again.

**Nothing here deletes a milestone**, and nothing ever will. Deleting detaches it from every issue
that carried it and cannot be undone. Closing is always available and always reversible.

## The markers

The description carries machine-read markers alongside prose:

| Marker | Meaning |
| --- | --- |
| `focus.` | the milestone the pipeline is currently working through |
| `frozen.` | scope is settled; no more issues should be added |

```python
ms.set_focus("v0.4")   # marks this one, clears the marker from any other
```

Exactly one milestone is the focus, which `set_focus` enforces rather than assumes.

Specification: `docs/spec/milestones.md` (`MS`), 27 requirements.
