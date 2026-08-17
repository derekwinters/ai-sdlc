#!/usr/bin/env python3
"""Glue for the sweep workflow: read the board, plan, poke.

The decisions live in `sweep.plan`, which is pure and tested. This is the I/O
around it — fetching the board, asking the routine, and saying what happened.

Requeueing pokes the routine **directly** rather than by removing and
re-applying the triage label. Both would start a session, but a label
round-trip also emits `labeled`, which the label handler answers with a second
poke; one intent would become two sessions, and the sweep's whole purpose is
bounding how many sessions exist.

Specification: docs/spec/gatekeeper.md (`GK-138`–`GK-144`).
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path.cwd()))

from sweep import plan  # noqa: E402


def has_analysis(api, issue, *, author):
    """Whether anything has already analysed this issue.

    True when a comment exists from somebody other than the issue's author.
    The owner's own `/admit` is a command rather than analysis, and counting it
    would mark every admitted issue as analysed — which reads as "nothing is
    stranded" and turns the backstop off exactly where it is needed.

    An unreadable comment list answers False, so the issue stays eligible. That
    errs toward spending rather than toward silence, which is only defensible
    because `GK-139` and `GK-141` bound what that can cost.
    """
    try:
        comments = api.comments(issue["number"]) or []
    except Exception:  # noqa: BLE001 - a degraded read must not fail the run
        return False
    for comment in comments:
        login = ((comment or {}).get("user") or {}).get("login")
        if login and login != author:
            return True
    return False


def board(api, *, triage_label, now):
    """The snapshot `sweep.plan` needs, and nothing more.

    Only issues carrying the triage label are inspected for comments: the
    comment read is one request per issue, and the rest of the board cannot be
    stranded by definition.
    """
    issues = []
    for issue in api.issues(state="open") or []:
        if "pull_request" in issue:
            continue
        labels = [l.get("name") for l in (issue.get("labels") or [])
                  if isinstance(l, dict)] or list(issue.get("labels") or [])
        entry = {
            "number": issue.get("number"),
            "state": issue.get("state", "open"),
            "labels": labels,
            "updated_at": issue.get("updated_at"),
            "has_analysis": False,
        }
        if triage_label in labels:
            entry["has_analysis"] = has_analysis(
                api, issue, author=((issue.get("user") or {}).get("login")))
        issues.append(entry)
    return {"now": now, "issues": issues}


def summarise(result):
    """One line per outcome. Every branch says something, including the empty
    one — a backstop nobody can see working is one nobody trusts (`GK-144`).
    """
    lines = [f"sweep: requeued {len(result['requeue'])}"]
    if result["clear"]:
        lines.append(
            f"sweep: cleared stale markers from {len(result['clear'])} issues: "
            f"{result['clear']}"
        )
    if result["stalled"]:
        lines.append(
            f"sweep: {len(result['stalled'])} issues were poked twice and never "
            f"answered — these need a human, not another poke: "
            f"{result['stalled']}"
        )
    if result["skipped"]:
        lines.append(
            f"sweep: {len(result['skipped'])} stranded issues left for the next "
            f"run — the ceiling was reached, which means something is wrong "
            f"rather than busy: {result['skipped']}"
        )
    if result["withheld"]:
        lines.append(
            f"sweep: {len(result['withheld'])} stranded on the event path, "
            f"requeueing deferred to the schedule: {result['withheld']}"
        )
    return lines


def set_marker(api, number, marker, markers):
    """Advance an issue to `marker`, replacing whichever it carried.

    One write, not a remove and an add: two writes are two events, two audit
    entries, and a window in which the issue carries no marker at all — which
    is the window a concurrent read would misinterpret as "never poked".
    """
    try:
        current = [l["name"] for l in (api.issue(number).get("labels") or [])]
        wanted = [n for n in current if n not in set(markers)]
        if marker:
            wanted.append(marker)
        if set(wanted) != set(current):
            api.set_labels(number, wanted)
    except Exception:  # noqa: BLE001 - bookkeeping must not fail the run
        return False
    return True


def run(api, config, fire, *, now, events_only):
    """Plan and apply one sweep. Returns the plan, for the caller to report."""
    markers = config.markers()
    result = plan(
        board(api, triage_label=config.label("triage"), now=now),
        triage_label=config.label("triage"),
        markers=markers,
        ceiling=config.sweep.ceiling,
        stale_after=config.sweep.stale_after,
        events_only=events_only,
    )

    for number in result["requeue"]:
        # Best-effort, exactly as the gatekeeper's own fire is: a backstop that
        # fails the run when the routine is unreachable is a backstop that goes
        # red overnight and gets muted.
        sent = fire.send(number, api.repository)
        # Marked only when a session actually started, so a routine that could
        # not be reached does not consume the issue's one retry (`GK-138`).
        if sent and sent.attempted and not sent.failed:
            set_marker(api, number, result["mark"].get(number), markers)

    for number in result["clear"]:
        set_marker(api, number, None, markers)

    return result
