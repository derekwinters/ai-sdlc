#!/usr/bin/env python3
"""The backstop: find issues a lost fire left stranded, and poke them again.

Firing is best-effort by design — the label move is the gatekeeper's job, and
a routine that never starts must not fail the run. The cost of that choice is
that a lost poke is silent: the issue sits in triage, with no analysis, and
nothing looks at it again. This decides which of those to poke.

Pure, and deliberately so. A scheduled job that starts sessions spends the
owner's usage limits while nobody is watching, so the rules that bound it are
worth asserting directly rather than through a network.

Two bounds, because they fail differently:

  * the **ceiling** limits one run — a fault that marks the whole board
    stranded cannot turn into a hundred sessions;
  * the **give-up horizon** limits one issue across every run — an issue that
    can never succeed stops costing anything, which a ceiling alone does not
    give you, since a permanently broken issue inside the ceiling is retried
    forever.

Specification: docs/spec/gatekeeper.md (`GK-138`–`GK-144`).
"""

from __future__ import annotations

from datetime import datetime, timezone

#: Requeueing is the only action here that costs money, so it is the only one
#: the event path is denied. Reporting is free and stays on both paths.
__all__ = ["plan", "seconds_between"]


def _parsed(stamp):
    """A GitHub timestamp as an aware datetime, or `None` if unreadable.

    Unreadable rather than raising: a snapshot with one malformed timestamp
    should cost that issue its turn, not the whole run.
    """
    if not stamp:
        return None
    try:
        text = stamp.replace("Z", "+00:00")
        parsed = datetime.fromisoformat(text)
    except (ValueError, TypeError, AttributeError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def seconds_between(earlier, later):
    """Age in seconds, or `None` when either end is unreadable."""
    start, end = _parsed(earlier), _parsed(later)
    if start is None or end is None:
        return None
    return (end - start).total_seconds()


def _is_stranded(issue, triage_label):
    """Open, in triage, and nothing has analysed it (`GK-138`).

    The analysis flag is what separates "the routine never ran" from "the
    routine ran and the label is stale". Requeueing the second would re-analyse
    finished work, which costs a session to produce a duplicate.
    """
    if issue.get("state", "open") != "open":
        return False
    if triage_label not in (issue.get("labels") or []):
        return False
    return not issue.get("has_analysis")


def plan(board, *, triage_label, ceiling, stale_after, give_up_after,
         events_only=False):
    """Decide what one sweep run should do.

    Returns four disjoint lists of issue numbers, each sorted:

      ``requeue``    poke these now
      ``skipped``    stranded, but past this run's ceiling
      ``abandoned``  stranded so long that retrying is no longer justified
      ``withheld``   stranded, but this is the event path, which may not requeue

    `events_only` is the re-pick gate (`GK-142`). On a webhook, a healthy issue
    can momentarily look stranded — a just-merged issue before GitHub finishes
    closing it, a just-set label before the analysis comment is visible — and
    requeueing in that window is what turns two states into a loop that fires a
    session on every flip. A genuine stall has no triggering event, so waiting
    for the schedule loses nothing.
    """
    now = (board or {}).get("now")
    stranded, abandoned = [], []

    for issue in (board or {}).get("issues") or []:
        if not _is_stranded(issue, triage_label):
            continue
        number = issue.get("number")
        if number is None:
            continue

        age = seconds_between(issue.get("updated_at"), now)
        if age is None or age < stale_after:
            # Still warm: something may be working on it, and a second poke is
            # how one stranded issue becomes two concurrent sessions.
            continue
        if age > give_up_after:
            # Past saving by poking (`GK-141`). Reported, never requeued, and
            # deliberately not counted against the ceiling — otherwise a
            # handful of permanently broken issues would crowd out every issue
            # the sweep could still help.
            abandoned.append(number)
            continue
        stranded.append(number)

    # Ordered before truncation (`GK-143`), so a run that hits the ceiling takes
    # the same issues every time and the board drains from one end instead of
    # starving whichever issues sort late.
    stranded.sort()

    if events_only:
        return {
            "requeue": [],
            "skipped": [],
            "abandoned": sorted(abandoned),
            "withheld": stranded,
        }

    return {
        "requeue": stranded[:ceiling],
        "skipped": stranded[ceiling:],
        "abandoned": sorted(abandoned),
        "withheld": [],
    }
