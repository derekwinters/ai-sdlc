#!/usr/bin/env python3
"""Dependency relationships between issues.

GitHub's issue-dependency API has no MCP tool, so without this there is no way
for an agent to create or read a native relationship. That absence is why
dependencies in these repositories were written as prose in issue bodies —
where the queue cannot see them, so the builder starts the issue anyway.

Three kinds of reference, deliberately distinguished:

* a **native blocked-by** relationship is a hard gate, and the only real one;
* a **soft `Depends on:`** line orders the queue but never gates it, because
  GitHub has no native form for "prefer this order";
* a **prose `Blocked by #N`** is drift. It is found and reported, and never
  honoured: honouring it would make the invisible-to-tooling form work, and it
  would stay.

Blockedness is not stored anywhere. Eligibility is computed from the graph at
selection time, which is what keeps it correct without anything maintaining it.

Specification: docs/spec/blockers.md (`BLK`).
"""

from __future__ import annotations

import re

from lib.github import GitHubError

DEPENDS_ON = re.compile(r"^\s*depends\s+on:?\s*(?P<refs>.+)$", re.IGNORECASE)
PROSE_BLOCKER = re.compile(r"^\s*blocked\s+by:?\s*(?P<refs>.+)$", re.IGNORECASE)
REFERENCE = re.compile(r"#(\d+)")
FENCE = re.compile(r"^\s*(```|~~~)")


class BlockerError(RuntimeError):
    """A relationship that would be meaningless or unsatisfiable."""


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


class Eligibility:
    __slots__ = ("eligible", "reason")

    def __init__(self, eligible, reason=""):
        self.eligible = eligible
        self.reason = reason


# ------------------------------------------------------------------- text


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


def _references(body, pattern):
    found = []
    for line in _uncoded_lines(body):
        match = pattern.match(line)
        if match:
            found.extend(int(n) for n in REFERENCE.findall(match.group("refs")))
    return sorted(set(found))


def depends_on(body):
    """Soft ordering hints. These order the queue; they never gate it."""
    return _references(body, DEPENDS_ON)


def prose_blockers(body):
    """Hard blockers written as prose — drift, reported and never honoured."""
    return _references(body, PROSE_BLOCKER)


# ------------------------------------------------------------------ graph


class Blockers:
    """Reads and writes native dependency relationships."""

    def __init__(self, api):
        self.api = api

    def blockers_of(self, issue):
        """The issues blocking this one, with their state.

        A failing read raises. Returning empty would be indistinguishable from
        "nothing blocks this", which would make blocked work eligible.
        """
        edges = self.api.blocked_by(issue)
        found = []
        for edge in edges:
            number = edge.get("number")
            try:
                blocking = self.api.issue(number)
            except GitHubError:
                found.append(Blocker(number, unknown=True))
                continue
            milestone = (blocking.get("milestone") or {}).get("title")
            found.append(
                Blocker(
                    number,
                    state=blocking.get("state", "open"),
                    milestone=milestone,
                    merged=bool(blocking.get("merged")),
                )
            )
        return found

    def block(self, issue, by):
        if issue == by:
            raise BlockerError(f"#{issue} cannot block itself")

        path = self._path_to(by, issue)
        if path:
            drawn = " → ".join(f"#{n}" for n in [issue, by] + path[1:])
            raise BlockerError(
                f"that would make a cycle: {drawn}. Both issues would wait for "
                f"each other and neither would ever be eligible."
            )

        if any(b.number == by for b in self.blockers_of(issue)):
            return None
        # Numbers in, id across the API boundary. `block(50, 42)` reads the way
        # a person says it; what GitHub is told is #42's database id.
        return self.api.add_blocked_by(issue, self.api.issue_id(by))

    def unblock(self, issue, by):
        if not any(b.number == by for b in self.blockers_of(issue)):
            return None
        return self.api.remove_blocked_by(issue, self.api.issue_id(by))

    def _path_to(self, start, target, seen=None):
        """A path from `start` to `target` through blocked-by edges, or None."""
        seen = seen or set()
        if start in seen:
            return None
        seen.add(start)

        for edge in self.api.blocked_by(start):
            number = edge.get("number")
            if number == target:
                return [start, number]
            onward = self._path_to(number, target, seen)
            if onward:
                return [start] + onward
        return None


def is_eligible(issue, blockers):
    """Whether every hard blocker is resolved."""
    unresolved = [b for b in blockers if not b.resolved]
    if not unresolved:
        return Eligibility(True)

    named = ", ".join(
        f"#{b.number}" + (" (state unknown)" if b.unknown else "") for b in unresolved
    )
    return Eligibility(False, f"blocked by {named}")
