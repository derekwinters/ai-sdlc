#!/usr/bin/env python3
"""Require a closing keyword on a pull request.

An issue whose work has merged should close. When it does not, it sits in a
working state and the board misreports what is in flight — the condition a
reconcile sweep would otherwise exist to repair. Requiring the keyword removes
the condition rather than detecting it afterwards.

Merging without one is sometimes deliberate: the work landed and the issue is
not finished. That case applies the `no-closing-keyword` label, which makes
this check **pass** — it never makes it skip. A required check skipped by a
workflow condition stays pending forever and blocks the merge it was meant to
permit, which is the trap this whole design avoids.

Standard library only, and no network: the body and labels are supplied by the
workflow.

Specification: docs/spec/hygiene.md (`SYS`).
"""

from __future__ import annotations

import os
import re
import sys

EXEMPT_LABEL = "no-closing-keyword"

#: The forms GitHub itself accepts, with an optional owner/repo prefix.
KEYWORD = re.compile(
    r"\b(?P<word>close[sd]?|fix(?:e[sd])?|resolve[sd]?)\b[\s:]+"
    r"(?P<ref>(?:[\w.-]+/[\w.-]+)?#(?P<number>\d+))",
    re.IGNORECASE,
)

FENCE = re.compile(r"^\s*(```|~~~)")

WANTED = "Closes #<issue>"


class Result:
    __slots__ = ("satisfied", "exempt", "detail")

    def __init__(self, satisfied, exempt=False, detail=""):
        self.satisfied = satisfied
        self.exempt = exempt
        self.detail = detail


def check(body, labels=()):
    """Whether this pull request may merge, and why."""
    if EXEMPT_LABEL in set(labels or ()):
        return Result(
            True,
            exempt=True,
            detail=(
                f"Exempt: labelled {EXEMPT_LABEL!r}. The work will merge without "
                f"closing an issue, which is a deliberate choice recorded on the "
                f"pull request."
            ),
        )

    match = _find(body)
    if match:
        return Result(
            True,
            detail=f"Found {match.group('word')} {match.group('ref')}.",
        )

    return Result(
        False,
        detail=(
            f"No closing keyword. Add {WANTED} to the pull request body so the "
            f"issue closes when this merges, or apply the {EXEMPT_LABEL!r} label "
            f"if it deliberately closes nothing.\n"
            f"Accepted: closes, fixes, resolves (and their other tenses), "
            f"optionally with an owner/repo prefix."
        ),
    )


def _find(body):
    """The first keyword outside a fenced code block.

    A keyword inside a fence does not close anything on GitHub either, so
    accepting one here would pass a pull request that then fails to close its
    issue — exactly the outcome being prevented.
    """
    fenced, marker = False, None
    for line in (body or "").splitlines():
        fence = FENCE.match(line)
        if fence:
            if not fenced:
                fenced, marker = True, fence.group(1)
            elif fence.group(1) == marker:
                fenced, marker = False, None
            continue
        if fenced:
            continue
        match = KEYWORD.search(line)
        if match:
            return match
    return None


def main():
    body = sys.stdin.read()
    labels = [name.strip() for name in os.environ.get("PR_LABELS", "").split(",")]
    result = check(body, labels)

    # Always print: a required check that says nothing on success gives a
    # reviewer no way to tell "passed" from "never ran".
    print(result.detail)
    return 0 if result.satisfied else 1


if __name__ == "__main__":
    raise SystemExit(main())
