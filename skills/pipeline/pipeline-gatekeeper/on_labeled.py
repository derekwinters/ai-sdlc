#!/usr/bin/env python3
"""Fire the analysis routine when an issue enters triage.

The single trigger. Adding the triage label used to fire nothing unless a
comment command caused it: the gatekeeper listens on `issue_comment`, so the
routine was reachable only through `/admit`, and only at the instant of the
transition. Labelling an issue by hand — the obvious thing to do — poked
nothing at all.

Keyed on the label event instead, so "the issue entered triage" fires exactly
once however it got there. The gatekeeper no longer fires, because firing in
both places would poke the routine twice for every `/admit`, and
deduplicating two independent workflows is harder than having one.

This writes nothing. Firing is a poke; what happens next is the routine's
decision, and a handler that also moved labels would be a second gatekeeper.

Specification: docs/spec/gatekeeper.md (`GK-122`).
"""

from __future__ import annotations

from downstream import FireResult


def on_label_added(api, event, settings):
    """Poke the routine when the label added is the configured triage label.

    Returns the `FireResult`, so the run can report what happened — the same
    reason `GK-121` exists: a poke nobody can see is indistinguishable from
    one that never went out.
    """
    added = ((event or {}).get("label") or {}).get("name")
    wanted = (settings.labels or {}).get("triage")

    if not added or added != wanted:
        return FireResult(attempted=False, detail=f"{added!r} is not the triage label")

    if not settings.fire:
        return FireResult(attempted=False, detail="no analysis routine configured")

    issue = (event.get("issue") or {}).get("number")
    if not issue:
        return FireResult(attempted=False, detail="the event names no issue")

    return settings.fire.send(issue, api.repository)
