#!/usr/bin/env python3
"""Where a command is valid.

Two kinds of scope, for two different reasons.

Some commands configure the pipeline rather than an issue — `focus` and `cap`
— and only mean something on the dashboard issue. Honouring them anywhere
would make the pipeline's configuration depend on which issue somebody
happened to be reading.

And an epic is a container whose children are the work. Admitting or approving
an epic would queue the container itself for building, which produces a pull
request against nothing. Parking or re-milestoning a whole epic is still
reasonable, so the exclusion is per command rather than blanket.

Pure: actions in, actions and refusals out.

Specification: docs/spec/gatekeeper.md (`GK`), §3 (Scope).
"""

from __future__ import annotations

from parse_commands import Parsed, Skip

#: Configure the pipeline, not an issue.
DASHBOARD_ONLY = ("focus", "cap")

#: Would queue an epic for building. Its children are the work.
EPIC_EXCLUDED = ("admit", "approve", "revise", "redo", "propose")

EPIC_LABEL = "type:epic"


class Subject:
    """The issue a comment was written on."""

    __slots__ = ("number", "labels", "dashboard_issue")

    def __init__(self, number, labels=(), dashboard_issue=None):
        self.number = number
        self.labels = list(labels)
        self.dashboard_issue = dashboard_issue

    @property
    def is_dashboard(self):
        return self.dashboard_issue is not None and self.number == self.dashboard_issue

    @property
    def is_epic(self):
        return EPIC_LABEL in self.labels

    @classmethod
    def from_issue(cls, issue, dashboard_issue=None):
        return cls(
            number=issue.get("number"),
            labels=[label.get("name") for label in issue.get("labels") or []],
            dashboard_issue=dashboard_issue,
        )


def check_scope(actions, subject, skips=None):
    """Split `actions` into those valid here and those refused."""
    kept, refused = [], list(skips or [])

    for action in actions:
        reason = _out_of_scope(action, subject)
        if reason is None:
            kept.append(action)
        else:
            refused.append(
                Skip(action.command, reason, line=action.line)
            )

    return Parsed(kept, refused)


def _out_of_scope(action, subject):
    if action.command in DASHBOARD_ONLY:
        return None if subject.is_dashboard else "dashboard-only"

    if subject.is_dashboard:
        # Everything else acts on an issue, and the dashboard is not one.
        return "not-on-dashboard"

    if subject.is_epic and action.command in EPIC_EXCLUDED:
        return "epic"

    return None
