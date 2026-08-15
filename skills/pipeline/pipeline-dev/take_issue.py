#!/usr/bin/env python3
"""A builder claiming an issue.

Re-checks eligibility before writing. The queue was built from a snapshot, and
between building it and acting on it the owner may have parked the issue,
another builder may have taken it, or it may have closed. Taking on stale
information is how two builders end up on one issue.

Specification: docs/spec/development.md (`DEV`), §4.
"""

from __future__ import annotations


class TakeRefused(RuntimeError):
    """The issue is no longer available."""


class Taken:
    __slots__ = ("issue", "branch")

    def __init__(self, issue, branch):
        self.issue = issue
        self.branch = branch


def branch_name(issue):
    """Derived from the issue number, so the association survives everything.

    A branch found months later with no pull request still says which issue it
    belongs to.
    """
    return f"claude/issue-{issue}"


def take(api, issue, labels):
    """Move an issue into the building state, refusing if it has moved on."""
    current = api.issue(issue)

    if current.get("state") == "closed":
        raise TakeRefused(f"#{issue} is closed")

    names = [label["name"] for label in current.get("labels") or []]
    state = next((n for n in names if n in set(labels.values())), None)

    if state != labels["approved"]:
        raise TakeRefused(
            f"#{issue} is {state or 'in no pipeline state'}, not "
            f"{labels['approved']}; it changed since the queue was built"
        )

    state_labels = set(labels.values())
    kept = [name for name in names if name not in state_labels]
    api.set_labels(issue, kept + [labels["building"]])

    return Taken(issue, branch_name(issue))
