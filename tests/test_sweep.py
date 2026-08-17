#!/usr/bin/env python3
"""The sweep: the backstop that re-pokes issues a lost fire left stranded.

`sweep.plan` is pure — a board snapshot in, a decision out — so every bound
that matters can be asserted without a network or a clock. What is guarded here
is mostly *spend*: a scheduled job that starts sessions costs money while
nobody is watching.

The bound on retries is the **markers**, not a duration. That distinction is
the point of several tests below: a duration is measured against a clock that
ordinary activity resets, so a passing comment can resurrect an issue that had
already been given up on. A marker only advances.

Specification: docs/spec/gatekeeper.md (`GK-138`–`GK-146`).
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(
    0, str(Path(__file__).resolve().parents[1] / "skills/pipeline/pipeline-gatekeeper")
)

from sweep import next_marker, plan  # noqa: E402

NOW = "2026-08-17T12:00:00Z"
STALE = "2026-08-17T06:00:00Z"
TRIAGE = "ai-triage"
PENDING = "ai-triage-pending"
STALLED = "ai-triage-stalled"
MARKERS = (PENDING, STALLED)


def issue(number, *, labels=(TRIAGE,), state="open", analysis=False, updated=STALE):
    return {
        "number": number,
        "state": state,
        "labels": list(labels),
        "has_analysis": analysis,
        "updated_at": updated,
    }


def sweep(*issues, ceiling=10, stale_after=1800, events_only=False, now=NOW):
    return plan(
        {"now": now, "issues": list(issues)},
        triage_label=TRIAGE,
        markers=MARKERS,
        ceiling=ceiling,
        stale_after=stale_after,
        events_only=events_only,
    )


class TestWhatCountsAsStranded(unittest.TestCase):
    """GK-139 — only an issue nothing is doing anything about."""

    def test_a_stranded_issue_is_requeued(self):  # GK-139
        self.assertEqual(sweep(issue(322))["requeue"], [322])

    def test_an_issue_with_analysis_is_not_stranded(self):  # GK-139
        """It was triaged. Requeueing would re-analyse finished work."""
        self.assertEqual(sweep(issue(322, analysis=True))["requeue"], [])

    def test_an_issue_not_in_triage_is_not_stranded(self):  # GK-139
        self.assertEqual(sweep(issue(322, labels=["type:bug"]))["requeue"], [])

    def test_a_closed_issue_is_not_stranded(self):  # GK-139
        self.assertEqual(sweep(issue(322, state="closed"))["requeue"], [])

    def test_a_recently_touched_issue_is_left_alone(self):  # GK-139
        """Its session may still be running. Poking now is how one stranded
        issue becomes two concurrent sessions."""
        self.assertEqual(sweep(issue(322, updated=NOW))["requeue"], [])


class TestTheMarkersBoundRetries(unittest.TestCase):
    """GK-140 — the bound is structural, not temporal."""

    def test_an_unmarked_issue_is_poked_and_becomes_pending(self):  # GK-140
        result = sweep(issue(322))
        self.assertEqual(result["requeue"], [322])
        self.assertEqual(result["mark"], {322: PENDING})

    def test_a_pending_issue_is_poked_once_more_and_becomes_stalled(self):  # GK-140
        result = sweep(issue(322, labels=(TRIAGE, PENDING)))
        self.assertEqual(result["requeue"], [322])
        self.assertEqual(result["mark"], {322: STALLED})

    def test_a_stalled_issue_is_never_poked_again(self):  # GK-140
        result = sweep(issue(322, labels=(TRIAGE, STALLED)))
        self.assertEqual(result["requeue"], [])
        self.assertEqual(result["stalled"], [322])

    def test_activity_cannot_resurrect_a_stalled_issue(self):  # GK-140
        """The bug this design replaces. A give-up *horizon* was measured from
        the issue's last update, so a comment on a hopeless issue reset the
        clock and it became eligible again — for ever. Marker state has no
        clock to reset."""
        touched_just_now = issue(322, labels=(TRIAGE, STALLED), updated=NOW)
        long_forgotten = issue(323, labels=(TRIAGE, STALLED),
                               updated="2026-01-01T00:00:00Z")
        result = sweep(touched_just_now, long_forgotten)
        self.assertEqual(result["requeue"], [])

    def test_the_progression_never_runs_backwards(self):  # GK-140
        self.assertEqual(next_marker(set(), MARKERS), PENDING)
        self.assertEqual(next_marker({PENDING}, MARKERS), STALLED)
        self.assertIsNone(next_marker({STALLED}, MARKERS))
        # Both present — somebody's hand, or a half-applied write. Terminal
        # wins: the safe reading of an ambiguous board is the one that spends
        # nothing.
        self.assertIsNone(next_marker({PENDING, STALLED}, MARKERS))


class TestClearingMarkers(unittest.TestCase):
    """GK-145 — a marker that outlives its episode is a slower version of the
    bug it prevents: the next episode inherits a spent budget."""

    def test_a_marker_on_an_issue_out_of_triage_is_cleared(self):  # GK-145
        result = sweep(issue(322, labels=("pending-approval", PENDING)))
        self.assertEqual(result["clear"], [322])

    def test_a_marker_on_a_closed_issue_is_cleared(self):  # GK-145
        result = sweep(issue(322, labels=(TRIAGE, PENDING), state="closed"))
        self.assertEqual(result["clear"], [322])

    def test_an_issue_in_triage_keeps_its_marker(self):  # GK-145
        """Clearing here would reset the budget on every run, which is an
        unbounded retry loop wearing a bound's clothes."""
        result = sweep(issue(322, labels=(TRIAGE, PENDING)))
        self.assertEqual(result["clear"], [])


class TestTheCeiling(unittest.TestCase):
    """GK-143 — one run cannot start an unbounded number of sessions."""

    def test_a_run_requeues_at_most_the_ceiling(self):  # GK-143
        result = sweep(*[issue(n) for n in range(1, 21)], ceiling=3)
        self.assertEqual(len(result["requeue"]), 3)

    def test_the_remainder_is_reported_rather_than_dropped(self):  # GK-144
        result = sweep(*[issue(n) for n in range(1, 21)], ceiling=3)
        self.assertEqual(len(result["skipped"]), 17)
        self.assertEqual(sorted(result["requeue"] + result["skipped"]),
                         list(range(1, 21)))

    def test_a_ceiling_of_zero_starts_nothing(self):  # GK-143
        result = sweep(issue(1), issue(2), ceiling=0)
        self.assertEqual(result["requeue"], [])
        self.assertEqual(result["skipped"], [1, 2])

    def test_selection_is_ordered_before_truncation(self):  # GK-143
        """Otherwise a capped run starves whichever issues sort late."""
        result = sweep(issue(339), issue(322), issue(329), ceiling=2)
        self.assertEqual(result["requeue"], [322, 329])

    def test_a_skipped_issue_is_not_marked(self):  # GK-140
        """It was not poked, so it has not spent an attempt."""
        result = sweep(issue(1), issue(2), ceiling=1)
        self.assertEqual(list(result["mark"]), [1])


class TestTheEventGate(unittest.TestCase):
    """GK-142 — the loop that fires a session on every flip."""

    def test_the_event_path_requeues_nothing(self):  # GK-142
        self.assertEqual(sweep(issue(322), events_only=True)["requeue"], [])

    def test_the_event_path_marks_nothing(self):  # GK-142
        """A mark records a poke. Recording one without poking would spend the
        issue's retry on a session that never existed."""
        self.assertEqual(sweep(issue(322), events_only=True)["mark"], {})

    def test_the_event_path_still_reports_what_it_saw(self):  # GK-142
        self.assertEqual(sweep(issue(322), events_only=True)["withheld"], [322])

    def test_the_event_path_still_clears_stale_markers(self):  # GK-145
        """Clearing spends nothing and cannot loop, so withholding it would
        only let dead markers accumulate between schedules."""
        result = sweep(issue(322, labels=("pending-approval", PENDING)),
                       events_only=True)
        self.assertEqual(result["clear"], [322])


class TestAnEmptyRunIsFine(unittest.TestCase):
    """GK-144 — nothing to do is success."""

    def test_an_empty_board_is_an_empty_plan(self):  # GK-144
        result = sweep()
        self.assertEqual(
            (result["requeue"], result["skipped"], result["clear"]), ([], [], []))


if __name__ == "__main__":
    unittest.main()
