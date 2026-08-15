#!/usr/bin/env python3
"""Which approved issue gets built next.

This is where deriving blockedness pays off. Eligibility is computed from the
dependency graph every time the queue is built, so an issue whose blocker
closed becomes available on its own — nothing has to notice and wake it. That
is the whole reason there is no blocked label, and why the revisit machinery
that used to maintain one no longer exists.

Two kinds of dependency, kept apart deliberately. A hard blocker *gates*: the
issue is not eligible until it resolves. A soft `Depends on:` only *orders*:
the issue is eligible regardless, it simply should not be built before the
thing it follows. Conflating them either stalls work that could proceed or
builds things in the wrong order.

Pure: issues in, an ordered queue out. No I/O.

Specification: docs/spec/development.md (`DEV`), §1–3.
"""

from __future__ import annotations


class Queue:
    __slots__ = ("issues", "remaining", "building")

    def __init__(self, issues, remaining=0, building=0):
        self.issues = issues
        self.remaining = remaining
        self.building = building


def build_queue(issues, labels, cap=None, focus=None):
    """The issues a builder should take, in the order it should take them."""
    building = sum(1 for issue in issues if _state(issue, labels) == labels["building"])

    eligible = [issue for issue in issues if _is_eligible(issue, labels)]
    ordered = _order(eligible, focus)

    if cap is None:
        return Queue(ordered, remaining=0, building=building)

    room = max(0, cap - building)
    taken = ordered[:room]
    return Queue(taken, remaining=len(ordered) - len(taken), building=building)


def _state(issue, labels):
    names = {label["name"] for label in issue.get("labels") or []}
    for name in labels.values():
        if name in names:
            return name
    return None


def _is_eligible(issue, labels):
    if issue.get("state") == "closed":
        return False
    if issue.get("has_open_pr"):
        # The work exists. Building it again would open a second pull request
        # against the same issue.
        return False

    names = {label["name"] for label in issue.get("labels") or []}
    if labels["parked"] in names:
        return False
    if labels["approved"] not in names:
        return False

    for blocker in issue.get("blockers") or []:
        if not blocker.get("resolved"):
            # Unknown counts here too: not knowing whether the thing you depend
            # on is finished is not the same as it being finished.
            return False

    return True


def _order(issues, focus):
    """Topological by soft dependency, then focus milestone, then number."""
    by_number = {issue["number"]: issue for issue in issues}

    def sort_key(issue):
        in_focus = 0 if focus and issue.get("milestone") == focus else 1
        return (in_focus, issue["number"])

    remaining = sorted(issues, key=sort_key)
    placed, ordered = set(), []

    # Kahn's algorithm over in-queue soft dependencies only. A dependency
    # outside the queue cannot be ordered against and is ignored rather than
    # excluding the dependent.
    while remaining:
        ready = [
            issue
            for issue in remaining
            if all(
                number in placed
                for number in (issue.get("depends_on") or [])
                if number in by_number
            )
        ]

        if not ready:
            # A cycle. Degrading to number order keeps every issue in the queue;
            # dropping them would hide work, and looping would hang the run.
            ordered.extend(sorted(remaining, key=lambda i: i["number"]))
            return ordered

        chosen = ready[0]
        ordered.append(chosen)
        placed.add(chosen["number"])
        remaining.remove(chosen)

    return ordered
