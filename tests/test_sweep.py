#!/usr/bin/env python3
"""The sweep: the backstop that re-pokes issues a lost fire left stranded.

`sweep.plan` is pure — a board snapshot in, a decision out — so every bound
that matters can be asserted without a network or a clock. What is being
guarded here is mostly *spend*: a scheduled job that starts sessions is one
that costs money while nobody is watching, and the two bounds below fail
differently. The ceiling limits one run; the give-up horizon limits one issue
across all runs.

Specification: docs/spec/gatekeeper.md (`GK-138`–`GK-144`).
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
TRIAGE = "ai-triage"


def issue(number, *, labels=(TRIAGE,), state="open", analysis=False, updated="2026-08-17T06:00:00Z"):
    """A board entry. Defaults describe a stranded issue: in triage, no
    analysis, untouched for six hours."""
    return {
        "number": number,
        "state": state,
        "labels": list(labels),
        "has_analysis": analysis,
        "updated_at": updated,
    }


def board(*issues, now=NOW):
    return {"now": now, "issues": list(issues)}


def sweep(*issues, ceiling=10, stale_after=1800, give_up_after=21600,
          events_only=False, now=NOW):
    return plan(
        board(*issues, now=now),
        triage_label=TRIAGE,
        ceiling=ceiling,
        stale_after=stale_after,
        give_up_after=give_up_after,
        events_only=events_only,
    )


class TestWhatCountsAsStranded(unittest.TestCase):
    """GK-138 — only an issue nothing is doing anything about."""

    def test_a_stranded_issue_is_requeued(self):  # GK-138
        self.assertEqual(sweep(issue(322))["requeue"], [322])

    def test_an_issue_with_analysis_is_not_stranded(self):  # GK-138
        """It was triaged. That the label still says triage is a different
        problem, and requeueing would re-analyse finished work."""
        self.assertEqual(sweep(issue(322, analysis=True))["requeue"], [])

    def test_an_issue_not_in_triage_is_not_stranded(self):  # GK-138
        self.assertEqual(sweep(issue(322, labels=["type:bug"]))["requeue"], [])

    def test_a_closed_issue_is_not_stranded(self):  # GK-138
        self.assertEqual(sweep(issue(322, state="closed"))["requeue"], [])

    def test_a_recently_touched_issue_is_left_alone(self):  # GK-138
        """Its session may still be running. Poking it now is how one stranded
        issue becomes two concurrent sessions."""
        self.assertEqual(
            sweep(issue(322, updated="2026-08-17T11:59:00Z"))["requeue"], [])


class TestTheCeiling(unittest.TestCase):
    """GK-139/GK-140 — one run cannot start an unbounded number of sessions."""

    def test_a_run_requeues_at_most_the_ceiling(self):  # GK-139
        result = sweep(*[issue(n) for n in range(1, 21)], ceiling=3)
        self.assertEqual(len(result["requeue"]), 3)

    def test_the_remainder_is_reported_rather_than_dropped(self):  # GK-140
        result = sweep(*[issue(n) for n in range(1, 21)], ceiling=3)
        self.assertEqual(len(result["skipped"]), 17)
        self.assertEqual(sorted(result["requeue"] + result["skipped"]),
                         list(range(1, 21)))

    def test_a_ceiling_of_zero_starts_nothing(self):  # GK-139
        """The off switch. A board that must not fire anything at all is a
        setting, not a code change."""
        result = sweep(issue(1), issue(2), ceiling=0)
        self.assertEqual(result["requeue"], [])
        self.assertEqual(result["skipped"], [1, 2])


class TestTheGiveUpHorizon(unittest.TestCase):
    """GK-141 — one issue cannot cost sessions forever."""

    def test_an_issue_stranded_past_the_horizon_is_abandoned(self):  # GK-141
        result = sweep(issue(322, updated="2026-08-16T12:00:00Z"))  # 24h
        self.assertEqual(result["requeue"], [])
        self.assertEqual(result["abandoned"], [322])

    def test_an_abandoned_issue_does_not_consume_the_ceiling(self):  # GK-141
        """Otherwise a handful of permanently broken issues would crowd out
        every issue the sweep could actually help."""
        result = sweep(
            issue(1, updated="2026-08-16T12:00:00Z"),
            issue(2, updated="2026-08-16T12:00:00Z"),
            issue(3),
            ceiling=2,
        )
        self.assertEqual(result["requeue"], [3])
        self.assertEqual(result["abandoned"], [1, 2])


class TestTheEventGate(unittest.TestCase):
    """GK-142 — the loop that fires a session on every flip."""

    def test_the_event_path_requeues_nothing(self):  # GK-142
        result = sweep(issue(322), events_only=True)
        self.assertEqual(result["requeue"], [])

    def test_the_event_path_still_reports_what_it_saw(self):  # GK-142
        """Withheld, not blind: the run still says the issue is stranded, so a
        real stall is visible before the schedule comes round."""
        result = sweep(issue(322), events_only=True)
        self.assertEqual(result["withheld"], [322])

    def test_the_scheduled_path_requeues(self):  # GK-142
        self.assertEqual(sweep(issue(322), events_only=False)["requeue"], [322])


class TestDeterminism(unittest.TestCase):
    """GK-143 — a truncated run must not starve one end of the board."""

    def test_selection_is_ordered_by_issue_number(self):  # GK-143
        result = sweep(issue(339), issue(322), issue(329), ceiling=2)
        self.assertEqual(result["requeue"], [322, 329])

    def test_the_same_board_gives_the_same_answer(self):  # GK-143
        issues = [issue(n) for n in (339, 322, 329)]
        self.assertEqual(sweep(*issues, ceiling=2), sweep(*issues, ceiling=2))


class TestAnEmptyRunIsFine(unittest.TestCase):
    """GK-144 — nothing to do is success."""

    def test_an_empty_board_is_an_empty_plan(self):  # GK-144
        result = sweep()
        self.assertEqual(result["requeue"], [])
        self.assertEqual(result["skipped"], [])
        self.assertEqual(result["abandoned"], [])


if __name__ == "__main__":
    unittest.main()
