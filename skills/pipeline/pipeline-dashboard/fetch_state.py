#!/usr/bin/env python3
"""Gather the state the dashboard renders.

Separate from rendering so the render is pure and exhaustively testable
without a repository, and so a failure here degrades one section rather than
losing the page.

It reads. It never writes — not even to fix something obviously wrong. That is
the whole bargain the removed reconcile sweep was replaced by: faults are
reported, and repairing them stays a decision somebody makes.

Two things about GitHub's issues endpoint shape this file, because production
code was wrong about both (#106): it returns **pull requests** alongside
issues, and it defaults to **open only**. Counting pull requests as issues put
every open one on the board as an untriaged issue; never asking for closed issues made
`DASH-025` unreachable and the Done bucket underivable.

Specification: docs/spec/dashboard.md (`DASH`).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
for _sibling in ("issue-blockers",):
    _path = _HERE.parent / _sibling
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from issue_blockers import Blockers, prose_blockers  # noqa: E402
from lib.config import MARKERS  # noqa: E402
from lib.github import GitHubError  # noqa: E402

#: The markers the dashboard keeps in its own body. The renderer writes them
#: back out on every render, which is what makes a `/focus` survive from the
#: gatekeeper's workflow run to the dashboard's separate one.
FOCUS_MARKER = re.compile(r"<!--\s*pipeline-focus:\s*(.+?)\s*-->")
CAP_MARKER = re.compile(r"<!--\s*pipeline-cap:\s*(-?\d+)\s*-->")

#: A milestone that names a version. Anything else — a permanent bucket for
#: work only a person can do, say — is never the focus fallback.
VERSION = re.compile(r"^v(\d+)\.(\d+)(?:\.(\d+))?(?![\d.])")


def fetch(api, labels, bot_login, dashboard_issue=None, overrides=None):
    """A plain-data snapshot of the pipeline."""
    overrides = overrides or {}
    state_labels = {name: state for state, name in labels.items()}

    issues = _issues(api, dashboard_issue)
    blockers = Blockers(api)

    prepared, faults = [], _empty_faults()

    for issue in issues:
        names = [label["name"] for label in issue.get("labels") or []]
        state_label = next((n for n in names if n in state_labels), None)

        found = _safe(lambda i=issue["number"]: blockers.blockers_of(i), [])
        unresolved = [b.number for b in found if not b.resolved]
        closed = issue.get("state") == "closed"
        milestone = issue.get("milestone") or {}

        if not closed and MARKERS["triage_stalled"] in names:
            # Bounding the retries converts "retried for ever" into "ignored
            # for ever" unless somebody is told (`GK-146`). Without this the
            # issue sits in Waiting for triage looking like ordinary work.
            faults["stalled_triage"].append({"issue": issue["number"]})

        if closed:
            if state_label:
                faults["stale_state"].append({"issue": issue["number"], "labels": [state_label]})
        else:
            # An issue with no pipeline state is not a fault: it is the
            # Waiting for triage section, which is the complement of the
            # claimed states and therefore already lists every one of them.
            if state_label == labels.get("approved") and unresolved:
                faults["blocked_but_approved"].append(
                    {"issue": issue["number"], "blockers": unresolved}
                )

            prose = prose_blockers(issue.get("body"))
            if prose:
                faults["prose_dependency"].append({"issue": issue["number"], "numbers": prose})

        prepared.append(
            {
                "number": issue["number"],
                "title": issue.get("title", ""),
                "state_label": state_label,
                "milestone": milestone.get("title"),
                "milestone_number": milestone.get("number"),
                "blockers": unresolved,
                "has_open_pr": bool(issue.get("has_open_pr")),
                "closed": closed,
            }
        )

    milestones = _open_milestones(api)
    body = _dashboard_body(api, dashboard_issue)

    return {
        "repository": getattr(api, "repository", ""),
        "focus": _focus(milestones, body, prepared, labels, overrides.get("focus")),
        "cap": _cap(body, overrides.get("cap")),
        "issues": prepared,
        "milestones": milestones,
        "faults": faults,
        "labels": dict(labels),
    }


def _empty_faults():
    return {
        "stalled_command": [],
        "stalled_work": [],
        "blocked_but_approved": [],
        "unverifiable_dependency": [],
        "prose_dependency": [],
        "stale_state": [],
        "stalled_triage": [],
    }


def _issues(api, dashboard_issue):
    """Every issue, open and closed, with pull requests removed.

    `state="all"` is not a refinement: closed issues are the Done bucket by
    definition, and a fault defined as *a closed issue still carrying a label*
    cannot fire against a list that never contains one.
    """
    found = _safe(lambda: api.issues(state="all"), [])
    return [
        i for i in found
        # The dashboard issue is the render target, not work. Listing it would
        # list it as work waiting to be triaged, for ever.
        if i.get("number") != dashboard_issue
        # GitHub returns pull requests here too, each carrying this key.
        and "pull_request" not in i
    ]


def _open_milestones(api):
    """Open milestones, including empty ones.

    An empty milestone is the signal that planning runway exists, so filtering
    it out would hide the thing the chart is for.
    """
    found = _safe(lambda: api.milestones(state="open"), None)
    if found is None:
        return []
    return [
        {
            "number": m.get("number"),
            "title": m.get("title", ""),
            "open": m.get("open_issues", 0),
            "closed": m.get("closed_issues", 0),
        }
        for m in found
    ]


def _dashboard_body(api, dashboard_issue):
    if not dashboard_issue:
        return ""
    found = _safe(lambda: api.issue(dashboard_issue), None)
    return (found or {}).get("body") or ""


def _focus(milestones, body, issues, labels, override):
    """Override, then the marker, then the fallback.

    The override exists only to carry a command's value into the render that
    persists it; the marker in the dashboard's own body is the store.
    """
    live = {m["title"]: m for m in milestones}

    if override:
        named = _match(live, override)
        if named:
            return _as_focus(named)
        # Refused rather than stored. A mistyped focus renders a board where
        # every section is empty, which looks exactly like a finished
        # milestone — so falling through to the marker is the safer answer.

    found = FOCUS_MARKER.search(body)
    if found:
        named = _match(live, found.group(1))
        if named:
            return _as_focus(named)

    return _fallback(milestones, issues, labels)


def _match(live, title):
    title = str(title).strip()
    if title in live:
        return live[title]
    for name, milestone in live.items():
        if name.lower() == title.lower():
            return milestone
    return None


def _fallback(milestones, issues, labels):
    """The lowest open version milestone that has ready work.

    A repository that has never set a focus still gets one, and a milestone
    with nothing ready is not it — the focus is where work is about to happen.
    """
    approved = labels.get("approved")
    with_work = {
        i.get("milestone") for i in issues
        if not i.get("closed") and i.get("state_label") == approved
    }

    candidates = [
        m for m in milestones
        if m["title"] in with_work and VERSION.match(m["title"])
    ]
    if not candidates:
        return None
    return _as_focus(min(candidates, key=lambda m: _version_of(m["title"])))


def _version_of(title):
    found = VERSION.match(title)
    return tuple(int(part or 0) for part in found.groups()) if found else (0, 0, 0)


def _cap(body, override):
    if override is not None:
        return override
    found = CAP_MARKER.search(body)
    return int(found.group(1)) if found else None


def _as_focus(milestone):
    return {
        "title": milestone["title"],
        "number": milestone.get("number"),
        "open": milestone.get("open", 0),
        "closed": milestone.get("closed", 0),
    }


def _safe(call, default):
    try:
        return call()
    except GitHubError:
        return default
