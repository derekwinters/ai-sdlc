#!/usr/bin/env python3
"""The backstop: notice a session that never answered, and say so.

Firing is best-effort by design — the label move is the gatekeeper's job, and a
routine that never starts must not fail the run. The cost of that choice is
that a lost poke is silent: the issue sits in `running`, nothing answers, and
nothing looks at it again. This finds those.

**It starts no sessions.** It observes and relabels. Deciding to spend another
session is a person's job, done with `/admit`.

That division is why this module is as small as it is. An earlier design had
the sweep re-poke automatically, and everything expensive about it followed
from that one choice: a per-run ceiling so a fault could not turn a whole board
into sessions, a give-up horizon so one issue could not be retried for ever,
attempt markers once the horizon turned out to be resettable by any passing
comment, and a gate stopping the event path from looping. A sweep that cannot
start a session needs none of them — whatever it gets wrong, it writes a label.

Specification: docs/spec/gatekeeper.md (`GK-139`–`GK-143`).
"""

from __future__ import annotations

from datetime import datetime, timezone

__all__ = ["plan", "seconds_between"]


def _parsed(stamp):
    """A GitHub timestamp as an aware datetime, or `None` if unreadable.

    Unreadable rather than raising: a snapshot with one malformed timestamp
    should cost that issue its turn, not the whole run.
    """
    if not stamp:
        return None
    try:
        parsed = datetime.fromisoformat(str(stamp).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def seconds_between(earlier, later):
    """Age in seconds, or `None` when either end is unreadable."""
    start, end = _parsed(earlier), _parsed(later)
    if start is None or end is None:
        return None
    return (end - start).total_seconds()


def plan(board, *, labels, stale_after):
    """Which issues have a session that never answered.

    Returns `{"stall": [numbers]}` — one key, deliberately. A planner that
    cannot express "fire this" cannot be made to fire one by a later edit, and
    `GK-140` is the invariant the rest of the design leans on.

    Only `running` is considered. A `queued` issue that has sat a long time
    means the fire never happened, which is a different fault and not one a
    stall label would describe honestly. A `stalled` issue is terminal: nothing
    automatic moves it, which is what stops this being a slow loop (`GK-142`).
    """
    now = (board or {}).get("now")
    running = (labels or {}).get("triage_running")
    stalled = []

    for issue in (board or {}).get("issues") or []:
        number = issue.get("number")
        if number is None:
            continue
        if issue.get("state", "open") != "open":
            continue
        if running not in (issue.get("labels") or []):
            continue
        if issue.get("has_analysis"):
            # Something answered. That the label has not caught up is a
            # different problem, and calling this stalled would be a lie.
            continue

        age = seconds_between(issue.get("updated_at"), now)
        if age is None or age < stale_after:
            # Still warm, or unreadable. Either way, leaving it alone is the
            # answer that cannot mislabel live work as dead.
            continue
        stalled.append(number)

    return {"stall": sorted(stalled)}
