#!/usr/bin/env python3
"""Reading the dependency graph, for the dashboard.

This is the read half of what `issue-blockers` used to be. That skill is now
instructions an agent follows (`DIST-043`), because a skill has no caller to
hand it a client — but the dashboard is a **script**. It runs in a workflow with
no agent present, so it must read the graph in code, and this is that code.

Only reads. `block` and `unblock` are deliberately absent: the dashboard reports
the pipeline and never changes it, and a module able to write is a module that
eventually does.

Specification: docs/spec/blockers.md (`BLK`), §1 and §3.
"""

from __future__ import annotations

import re

from lib.github import GitHubError

#: A hard blocker written as text rather than as a native relationship. Found
#: and reported as drift, never honoured — honouring it would make the
#: invisible-to-tooling form work, and it would stay.
PROSE_BLOCKER = re.compile(r"^\s*blocked\s+by:?\s*(?P<refs>.+)$", re.IGNORECASE)
REFERENCE = re.compile(r"#(\d+)")
FENCE = re.compile(r"^\s*(```|~~~)")


class Blocker:
    """One blocking issue, with enough state to judge it."""

    __slots__ = ("number", "state", "milestone", "merged", "unknown")

    def __init__(self, number, state=None, milestone=None, merged=False, unknown=False):
        self.number = number
        self.state = state
        self.milestone = milestone
        self.merged = merged
        self.unknown = unknown

    @property
    def resolved(self):
        """Closed or merged. Unknown is never resolved.

        Not knowing whether the thing you depend on is finished is not the same
        as it being finished, and treating it as such makes work eligible that
        is not.
        """
        if self.unknown:
            return False
        return self.state == "closed" or bool(self.merged)

    def __repr__(self):
        return f"<Blocker #{self.number} resolved={self.resolved}>"


def _uncoded_lines(body):
    fenced, marker = False, None
    for line in (body or "").splitlines():
        fence = FENCE.match(line)
        if fence:
            if not fenced:
                fenced, marker = True, fence.group(1)
            elif fence.group(1) == marker:
                fenced, marker = False, None
            continue
        if not fenced:
            yield line


def prose_blockers(body):
    """Hard blockers written as prose — drift, reported and never honoured."""
    found = []
    for line in _uncoded_lines(body):
        match = PROSE_BLOCKER.match(line)
        if match:
            found.extend(int(n) for n in REFERENCE.findall(match.group("refs")))
    return sorted(set(found))


def read_blockers(api, issue):
    """The issues blocking this one, with their state.

    A failing read raises. Returning empty would be indistinguishable from
    "nothing blocks this", which would make blocked work eligible.
    """
    found = []
    for edge in api.blocked_by(issue):
        number = edge.get("number")
        try:
            blocking = api.issue(number)
        except GitHubError:
            found.append(Blocker(number, unknown=True))
            continue
        found.append(
            Blocker(
                number,
                state=blocking.get("state", "open"),
                milestone=(blocking.get("milestone") or {}).get("title"),
                merged=bool(blocking.get("merged")),
            )
        )
    return found
