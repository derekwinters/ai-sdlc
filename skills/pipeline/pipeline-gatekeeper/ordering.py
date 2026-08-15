#!/usr/bin/env python3
"""Compare milestone titles, under whichever scheme a repository uses.

Milestones meaning versions is a property of how a repository names them, not
a universal fact. A repository may use versions, dates, themes, or a mix — and
almost every repository ends up with at least one standing milestone that
names no version at all, such as `Direct Involvement Needed`.

A title the strategy cannot read is UNORDERED. That is an absence of
information, and callers must treat it as such: the ordering gate refuses only
on evidence of inversion, never on absence of evidence.

Specification: docs/spec/gatekeeper.md (`GK`), §4 (Milestone ordering).
"""

from __future__ import annotations

import re

#: Not comparable under this strategy. Never treat as "later" or "earlier".
UNORDERED = None

_SEMVER = re.compile(r"^v?(\d+)\.(\d+)(?:\.(\d+))?\b", re.IGNORECASE)
_DATE = re.compile(r"^(\d{4})-(\d{2})(?:-(\d{2}))?\b")


def ordering_for(strategy):
    """Return a rank function for a configured strategy."""
    try:
        return _STRATEGIES[strategy]
    except KeyError:
        raise ValueError(
            f"unknown milestone ordering strategy {strategy!r}; "
            f"expected one of {', '.join(sorted(_STRATEGIES))}"
        ) from None


def _semver(title):
    match = _SEMVER.match((title or "").strip())
    if not match:
        return UNORDERED
    major, minor, patch = match.groups()
    return (int(major), int(minor), int(patch or 0))


def _date(title):
    match = _DATE.match((title or "").strip())
    if not match:
        return UNORDERED
    year, month, day = match.groups()
    return (int(year), int(month), int(day or 0))


def _lexical(title):
    cleaned = (title or "").strip().lower()
    return cleaned or UNORDERED


def _never(_title):
    """The `none` strategy: nothing is comparable, so the gate never runs."""
    return UNORDERED


_STRATEGIES = {
    "semver": _semver,
    "date": _date,
    "lexical": _lexical,
    "none": _never,
}
