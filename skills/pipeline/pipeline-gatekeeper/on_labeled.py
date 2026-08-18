#!/usr/bin/env python3
"""Fire the analysis routine when a label puts an issue into triage.

One of two triggers, covering the labels the gatekeeper did not apply itself:
a hand on the web UI, an app, anything added later. Before this existed, the
routine was reachable only through `/admit`, so labelling an issue by hand —
the obvious thing to do — poked nothing at all.

The gatekeeper fires for its own moves, and the two cannot collide. It writes
labels with `GITHUB_TOKEN`, and GitHub starts no workflow run from an event
that token authored, so its own label move never arrives here. That is a
property of the token, not a deduplication step — see the invariant on
`GK-122` before giving the gatekeeper a different one.

This writes nothing. Firing is a poke; what happens next is the routine's
decision, and a handler that also moved labels would be a second gatekeeper.

Specification: docs/spec/gatekeeper.md (`GK-122`).
"""

from __future__ import annotations

from downstream import FireResult, record_started


def on_label_added(api, event, settings):
    """Poke the routine when the label added is the configured triage label.

    Returns the `FireResult`, so the run can report what happened — the same
    reason `GK-121` exists: a poke nobody can see is indistinguishable from
    one that never went out.
    """
    added = ((event or {}).get("label") or {}).get("name")
    wanted = (settings.labels or {}).get("triage_queued")

    if not added or added != wanted:
        return FireResult(attempted=False, detail=f"{added!r} is not the triage label")

    if not settings.fire:
        return FireResult(attempted=False, detail="no analysis routine configured")

    issue = (event.get("issue") or {}).get("number")
    if not issue:
        return FireResult(attempted=False, detail="the event names no issue")

    result = settings.fire.send(issue, api.repository)
    # The component that knows a poke went out is the one that sent it, so it
    # records the attempt (`GK-138`). A marker, never a pipeline state — that
    # remains the routine's decision, which is what `GK-122` protects.
    record_started(api, issue, result, settings.labels)
    return result
