#!/usr/bin/env python3
"""The sweep: the detector that notices a session which never answered.

Pure — a board snapshot in, a decision out — so every rule can be asserted
without a network or a clock.

What is *not* here is as important as what is. The sweep does not retry, so
there is no ceiling to test, no per-issue budget, and no gate stopping an event
path from looping. All three existed in an earlier draft purely to make
automatic retry safe, and making a stall a person's decision deleted them.

Specification: docs/spec/gatekeeper.md (`GK-139`–`GK-143`).
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(
    0, str(Path(__file__).resolve().parents[1] / "skills/pipeline/pipeline-gatekeeper")
)

from sweep import plan  # noqa: E402

NOW = "2026-08-17T12:00:00Z"
STALE = "2026-08-17T06:00:00Z"

QUEUED = "ai-triage-queued"
RUNNING = "ai-triage-running"
STALLED = "ai-triage-stalled"

LABELS = {
    "triage_queued": QUEUED,
    "triage_running": RUNNING,
    "triage_stalled": STALLED,
    "pending_approval": "pending-approval",
    "clarification": "needs-clarification",
    "approved": "ready-for-work",
    "building": "in-progress",
    "parked": "parked",
}


def issue(number, *, labels=(RUNNING,), state="open", analysis=False, updated=STALE):
    return {
        "number": number,
        "state": state,
        "labels": list(labels),
        "has_analysis": analysis,
        "updated_at": updated,
    }


def sweep(*issues, stale_after=1800, now=NOW):
    return plan({"now": now, "issues": list(issues)},
                labels=LABELS, stale_after=stale_after)


class TestWhatCountsAsStalled(unittest.TestCase):
    """GK-139 — a session that has been out too long with nothing to show."""

    def test_a_stale_running_issue_is_stalled(self):  # GK-139
        self.assertEqual(sweep(issue(322))["stall"], [322])

    def test_a_fresh_running_issue_is_left_alone(self):  # GK-139
        """Its session may be seconds old. This is the whole reason the
        threshold exists."""
        self.assertEqual(sweep(issue(322, updated=NOW))["stall"], [])

    def test_an_issue_with_analysis_is_not_stalled(self):  # GK-139
        """Something answered. That the state label has not caught up is a
        different problem, and calling it stalled would be a lie."""
        self.assertEqual(sweep(issue(322, analysis=True))["stall"], [])

    def test_a_queued_issue_is_never_stalled(self):  # GK-139
        """No session was ever started, so none can have failed. A queued issue
        sitting a long time means the fire never happened — a different fault,
        and not one a stall label would describe."""
        self.assertEqual(sweep(issue(322, labels=(QUEUED,)))["stall"], [])

    def test_a_closed_issue_is_never_stalled(self):  # GK-139
        self.assertEqual(sweep(issue(322, state="closed"))["stall"], [])

    def test_an_issue_outside_triage_is_never_stalled(self):  # GK-139
        self.assertEqual(sweep(issue(322, labels=("ready-for-work",)))["stall"], [])

    def test_an_unreadable_timestamp_is_left_alone(self):  # GK-139
        """A snapshot with one bad timestamp costs that issue its turn, not the
        whole run — and erring toward leaving it alone cannot mislabel."""
        self.assertEqual(sweep(issue(322, updated=None))["stall"], [])


class TestItStartsNothing(unittest.TestCase):
    """GK-140 — the invariant the whole design rests on."""

    def test_the_plan_has_no_way_to_ask_for_a_session(self):  # GK-140
        """Asserted on the shape of the result rather than on behaviour: a
        planner that cannot express "fire this" cannot be made to fire one by a
        later edit. A `requeue` key reappearing here is the regression."""
        result = sweep(issue(322))
        self.assertEqual(set(result), {"stall"})


class TestStalledIsTerminal(unittest.TestCase):
    """GK-142 — nothing leaves the stalled state on its own."""

    def test_a_stalled_issue_is_not_touched_again(self):  # GK-142
        self.assertEqual(sweep(issue(322, labels=(STALLED,)))["stall"], [])

    def test_a_stalled_issue_stays_untouched_however_old(self):  # GK-142
        """The failure mode of the design this replaced: a give-up horizon was
        measured from the issue's last update, so any comment resurrected it."""
        ancient = issue(322, labels=(STALLED,), updated="2020-01-01T00:00:00Z")
        touched = issue(323, labels=(STALLED,), updated=NOW)
        self.assertEqual(sweep(ancient, touched)["stall"], [])


class TestDeterminism(unittest.TestCase):
    """GK-143 — a run has to be reportable, so it has to be stable."""

    def test_results_are_ordered_by_issue_number(self):  # GK-143
        self.assertEqual(sweep(issue(339), issue(322), issue(329))["stall"],
                         [322, 329, 339])

    def test_the_same_board_gives_the_same_answer(self):  # GK-143
        issues = [issue(n) for n in (339, 322, 329)]
        self.assertEqual(sweep(*issues), sweep(*issues))

    def test_an_empty_board_is_an_empty_plan(self):  # GK-143
        self.assertEqual(sweep()["stall"], [])


if __name__ == "__main__":
    unittest.main()
