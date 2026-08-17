#!/usr/bin/env python3
"""Glue for the sweep workflow: read the board, decide, relabel.

The decision lives in `sweep.plan`, which is pure and tested. This is the I/O
around it — fetching the board, writing the state, and saying what happened.

There is no fire here, and that absence is the design. The sweep observes; a
person decides whether to spend another session, with `/admit`. A scheduled job
that cannot start a session cannot spend an account's usage limits while nobody
is watching, however wrong it gets things.

Specification: docs/spec/gatekeeper.md (`GK-139`–`GK-143`).
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path.cwd()))

from sweep import plan  # noqa: E402


def has_analysis(api, issue, *, author):
    """Whether anything has already analysed this issue.

    True when a comment exists from somebody other than the issue's author. The
    owner's own `/admit` is a command rather than analysis, and counting it
    would mark every admitted issue as analysed — which reads as "nothing is
    stalled" and turns the backstop off exactly where it is needed.

    An unreadable comment list answers False. The issue then stays eligible for
    a stall label, which is the direction that reports a problem rather than
    hiding one, and the worst it can cost is a label a person can remove.
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


def board(api, *, running_label, now):
    """The snapshot `sweep.plan` needs, and nothing more.

    Only issues carrying the running label are inspected for comments: that
    read is one request per issue, and nothing else on the board can be a
    session that never answered.
    """
    issues = []
    for issue in api.issues(state="open") or []:
        if "pull_request" in issue:
            continue
        names = [l.get("name") for l in (issue.get("labels") or [])
                 if isinstance(l, dict)] or list(issue.get("labels") or [])
        entry = {
            "number": issue.get("number"),
            "state": issue.get("state", "open"),
            "labels": names,
            "updated_at": issue.get("updated_at"),
            "has_analysis": False,
        }
        if running_label in names:
            entry["has_analysis"] = has_analysis(
                api, issue, author=((issue.get("user") or {}).get("login")))
        issues.append(entry)
    return {"now": now, "issues": issues}


def summarise(result):
    """What the run did, including when it did nothing.

    A backstop nobody can see working is one nobody trusts (`GK-143`), and a
    silent run is indistinguishable from a broken one — which is the whole
    failure this component exists to end.
    """
    if not result["stall"]:
        return ["sweep: nothing stalled"]
    return [
        f"sweep: {len(result['stall'])} sessions never answered and are now "
        f"stalled — these need a person, not another poke: {result['stall']}"
    ]


def move_to_stalled(api, number, labels):
    """Replace whichever triage state the issue carries with stalled.

    One write rather than a remove and an add: two writes are two events, two
    audit entries, and a window in which the issue carries no state at all —
    which a concurrent read would see as an issue outside the pipeline.
    """
    triage_states = {labels[name] for name in
                     ("triage_queued", "triage_running", "triage_stalled")
                     if name in labels}
    try:
        current = [l["name"] for l in (api.issue(number).get("labels") or [])]
        wanted = [n for n in current if n not in triage_states]
        wanted.append(labels["triage_stalled"])
        api.set_labels(number, wanted)
    except Exception:  # noqa: BLE001 - one issue must not fail the run
        return False
    return True


def run(api, config, *, now, stale_after):
    """Observe the board and stall what never answered. Starts no sessions."""
    result = plan(
        board(api, running_label=config.label("triage_running"), now=now),
        labels=config.labels,
        stale_after=stale_after,
    )
    for number in result["stall"]:
        move_to_stalled(api, number, config.labels)
    return result
