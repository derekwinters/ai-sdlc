#!/usr/bin/env python3
"""Gather the state the dashboard renders.

Separate from rendering so the render is pure and exhaustively testable
without a repository, and so a failure here degrades one section rather than
losing the page.

It reads. It never writes — not even to fix something obviously wrong. That is
the whole bargain the removed reconcile sweep was replaced by: faults are
reported, and repairing them stays a decision somebody makes.

Specification: docs/spec/dashboard.md (`DASH`).
"""

from __future__ import annotations

import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
for _sibling in ("issue-blockers",):
    _path = _HERE.parent / _sibling
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from issue_blockers import Blockers, prose_blockers  # noqa: E402
from lib.github import GitHubError  # noqa: E402


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

        if issue.get("state") == "closed":
            if state_label:
                faults["stale_state"].append({"issue": issue["number"], "labels": [state_label]})
            continue

        if state_label is None:
            faults["untracked"].append({"issue": issue["number"]})
        elif state_label == labels.get("approved") and unresolved:
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
                "milestone": (issue.get("milestone") or {}).get("title"),
                "blockers": unresolved,
                "has_open_pr": bool(issue.get("has_open_pr")),
            }
        )

    return {
        "repository": getattr(api, "repository", ""),
        "focus": _focus(api, overrides.get("focus")),
        "cap": overrides.get("cap"),
        "issues": prepared,
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
        "untracked": [],
    }


def _issues(api, dashboard_issue):
    found = _safe(lambda: api.issues(), [])
    # The dashboard issue is the render target, not work. Listing it would make
    # it permanently "untracked" and permanently in its own fault list.
    return [i for i in found if i.get("number") != dashboard_issue]


def _focus(api, override):
    milestones = _safe(lambda: api.milestones(state="open"), None)
    if milestones is None:
        return None

    if override:
        for milestone in milestones:
            if milestone["title"].lower().startswith(override.strip().lower()):
                return _as_focus(milestone)
        # An override naming nothing is still the owner's stated intent; show it
        # rather than silently falling back to the marker.
        return {"title": override, "open": 0, "closed": 0}

    for milestone in milestones:
        description = (milestone.get("description") or "").lower()
        if description.startswith("focus."):
            return _as_focus(milestone)
    return None


def _as_focus(milestone):
    return {
        "title": milestone["title"],
        "open": milestone.get("open_issues", 0),
        "closed": milestone.get("closed_issues", 0),
    }


def _safe(call, default):
    try:
        return call()
    except GitHubError:
        return default
