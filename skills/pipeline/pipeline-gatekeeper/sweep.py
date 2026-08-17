#!/usr/bin/env python3
"""The backstop: find issues a lost fire left stranded, and poke them again.

Firing is best-effort by design — the label move is the gatekeeper's job, and a
routine that never starts must not fail the run. The cost of that choice is
that a lost poke is silent: the issue sits in triage, with no analysis, and
nothing looks at it again. This decides which of those to poke.

Pure, and deliberately so. A scheduled job that starts sessions spends the
owner's usage limits while nobody is watching, so the rules that bound it are
worth asserting directly rather than through a network.

Two bounds, and they fail differently:

  * the **ceiling** limits one run, so a fault that marks the whole board
    stranded cannot become a hundred sessions;
  * the **markers** limit one issue across every run. Whoever fires the routine
    records that it did, as a label, and the record only advances: absent →
    pending → stalled, and a stalled issue is never poked again.

The markers replaced a give-up *duration*, which did not work. A duration is
measured against a clock — last update, last comment — and ordinary activity
resets every clock available here, so a passing comment resurrected issues that
had already been given up on. Marker state has nothing to reset.

Specification: docs/spec/gatekeeper.md (`GK-138`–`GK-146`).
"""

from __future__ import annotations

from datetime import datetime, timezone

__all__ = ["plan", "next_marker", "seconds_between"]


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


def next_marker(present, markers):
    """The marker a poke would advance to, or `None` when there is no next one.

    `markers` is the progression in order, ending at the terminal one. Both
    markers present at once is somebody's hand or a half-applied write; the
    terminal reading wins, because the safe interpretation of an ambiguous
    board is the one that spends nothing.
    """
    terminal = markers[-1]
    if terminal in present:
        return None
    for marker in markers:
        if marker not in present:
            return marker
    return None


def plan(board, *, triage_label, markers, ceiling, stale_after, events_only=False):
    """Decide what one sweep run should do.

    Returns, each sorted or keyed by issue number:

      ``requeue``   poke these now
      ``mark``      issue -> the marker to apply, recording that poke
      ``skipped``   stranded, but past this run's ceiling
      ``stalled``   already terminal; reported so somebody sees them
      ``clear``     carrying a marker they should no longer carry
      ``withheld``  stranded, but this is the event path, which may not requeue

    `events_only` is the re-pick gate (`GK-142`). On a webhook a healthy issue
    can momentarily look stranded — a just-merged issue before GitHub finishes
    closing it, a just-set label before the analysis comment is visible — and
    requeueing in that window is what turns two states into a loop that fires a
    session on every flip. Clearing is still done on that path: it spends
    nothing and cannot loop, so withholding it would only let dead markers
    accumulate between schedules.
    """
    now = (board or {}).get("now")
    terminal = markers[-1]
    candidates, stalled, clear = [], [], []

    for issue in (board or {}).get("issues") or []:
        number = issue.get("number")
        if number is None:
            continue
        labels = set(issue.get("labels") or [])
        carried = labels & set(markers)
        in_triage = (triage_label in labels
                     and issue.get("state", "open") == "open")

        if not in_triage:
            # Left triage, or closed, and still carrying a marker. A marker
            # that outlives its episode is a slower version of the bug it
            # prevents: the next episode inherits a spent budget (`GK-145`).
            if carried:
                clear.append(number)
            continue

        if issue.get("has_analysis"):
            continue
        if terminal in carried:
            stalled.append(number)
            continue

        age = seconds_between(issue.get("updated_at"), now)
        if age is None or age < stale_after:
            # Still warm: something may be working on it, and a second poke is
            # how one stranded issue becomes two concurrent sessions.
            continue
        candidates.append((number, carried))

    # Ordered before truncation (`GK-143`), so a capped run drains the board
    # from one end instead of starving whichever issues sort late.
    candidates.sort()
    stalled.sort()
    clear.sort()

    if events_only:
        return {
            "requeue": [], "mark": {}, "skipped": [],
            "stalled": stalled, "clear": clear,
            "withheld": [n for n, _ in candidates],
        }

    taken, remainder = candidates[:ceiling], candidates[ceiling:]
    return {
        "requeue": [n for n, _ in taken],
        # Only what is actually poked is marked: a mark records an attempt, and
        # recording one for an issue the ceiling skipped would spend a retry on
        # a session that never happened.
        "mark": {n: next_marker(carried, markers) for n, carried in taken},
        "skipped": [n for n, _ in remainder],
        "stalled": stalled,
        "clear": clear,
        "withheld": [],
    }
