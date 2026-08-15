#!/usr/bin/env python3
"""What happens when an issue closes or a pull request merges.

Almost nothing, and that is the design rather than an omission.

Closing an issue strips its pipeline-state label, because a closed issue
carrying `in-progress` misreports the board. It touches no other issue: an
issue blocked by this one becomes eligible on its own, since blockedness is
derived from the dependency graph at selection time rather than stored as a
label. Waking other issues is precisely what the deleted revisit machinery
existed to do, and it existed only because blockedness had been stored.

A merged pull request does nothing here at all. With a closing keyword, GitHub
closes the issue itself and raises `issues.closed`, which is handled above —
acting on the merge as well would be a second write for one event. Without a
keyword, the merge is respected: the work landed and the issue is not finished,
which is sometimes exactly what the owner meant. An issue left `in-progress`
is reported by the dashboard, never advanced automatically.

Nothing in this module runs on a schedule.

Specification: docs/spec/gatekeeper.md (`GK`), §7.
"""

from __future__ import annotations

import re

#: A GitHub closing keyword and the issue it closes.
CLOSING_KEYWORD = re.compile(
    r"\b(close[sd]?|fix(e[sd])?|resolve[sd]?)\b[\s:]+#(\d+)", re.IGNORECASE
)


def on_issue_closed(api, number, labels):
    """Strip pipeline-state labels from a closed issue. Returns what it removed."""
    state_labels = set(labels.values())

    issue = api.issue(number)
    current = [label["name"] for label in issue.get("labels") or []]

    removed = [name for name in current if name in state_labels]
    if not removed:
        # Nothing to do, and a write that changes nothing is still a write:
        # it shows in the audit trail and invites a re-render.
        return []

    api.set_labels(number, [name for name in current if name not in state_labels])
    return removed


def on_pull_request_closed(api, pull_request, labels):
    """Take no action on a merge. Present so the decision is explicit.

    Returns the issue numbers the pull request said it closes, for the log.
    """
    if not pull_request.get("merged"):
        return []

    # With a keyword GitHub closes the issue and `issues.closed` handles it;
    # without one the merge is deliberate and is not overruled. Either way
    # there is nothing to write here.
    return closing_references(pull_request.get("body"))


def closing_references(body):
    """Issue numbers a pull request body says it closes."""
    return [int(match.group(3)) for match in CLOSING_KEYWORD.finditer(body or "")]
