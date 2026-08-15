#!/usr/bin/env python3
"""Which issues a triage run picks up.

Pure and label-only. Eligibility must not depend on prose, or which issues get
triaged becomes unpredictable and untestable — and an issue could talk its way
out of the queue.

Specification: docs/spec/triage.md (`TRI`), §1.
"""

from __future__ import annotations

EPIC_LABEL = "type:epic"

DEFAULT_CAP = 10


class Selection:
    __slots__ = ("issues", "truncated", "remaining")

    def __init__(self, issues, truncated=False, remaining=0):
        self.issues = issues
        self.truncated = truncated
        self.remaining = remaining


def select(issues, labels, cap=DEFAULT_CAP):
    """Eligible issues, by number, capped — and honest about the cap."""
    eligible = [issue for issue in issues if _is_eligible(issue, labels)]
    eligible.sort(key=lambda issue: issue["number"])

    if cap is None or len(eligible) <= cap:
        return Selection(eligible)

    # A silent cap makes a partial run look like a complete one, which is how
    # "triage is keeping up" becomes untrue without anybody noticing.
    return Selection(eligible[:cap], truncated=True, remaining=len(eligible) - cap)


def _is_eligible(issue, labels):
    if issue.get("state") == "closed":
        return False

    names = {label["name"] for label in issue.get("labels") or []}

    if EPIC_LABEL in names:
        return False
    if labels["parked"] in names:
        return False
    if labels["pending_approval"] in names or labels["clarification"] in names:
        # Its plan or its question is waiting on a human. Re-triaging would
        # replace an answer somebody is in the middle of considering.
        return False

    return labels["triage"] in names
