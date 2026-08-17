#!/usr/bin/env python3
"""Attempt markers: the record that a poke went out.

The component that knows a poke happened is the one that sent it, so every
fire site records the attempt. The record is a label because a label is
durable, visible on the board, and — the property the bound rests on — cannot
be reset by ordinary activity the way a timestamp can.

Specification: docs/spec/gatekeeper.md (`GK-138`, `GK-141`, `GK-145`).
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(
    0, str(Path(__file__).resolve().parents[1] / "skills/pipeline/pipeline-gatekeeper")
)

from apply_actions import plan_labels  # noqa: E402
from downstream import FireResult, record_attempt  # noqa: E402
from lib.fake_github import FakeGitHub  # noqa: E402

TRIAGE = "ai-triage"
PENDING = "ai-triage-pending"
STALLED = "ai-triage-stalled"
MARKERS = (PENDING, STALLED)

LABELS = {
    "triage": TRIAGE,
    "pending_approval": "pending-approval",
    "clarification": "needs-clarification",
    "approved": "ready-for-work",
    "building": "in-progress",
    "parked": "parked",
}


class _Action:
    def __init__(self, command):
        self.command = command


def api_with(number, labels):
    return FakeGitHub(issues=[{
        "number": number, "state": "open",
        "labels": [{"name": n} for n in labels],
    }])


def labels_on(api, number):
    return {l["name"] for l in api.issue(number).get("labels") or []}


class TestRecordingAnAttempt(unittest.TestCase):
    """GK-138 — recorded only when a session actually started."""

    def test_a_successful_fire_is_recorded(self):  # GK-138
        api = api_with(7, [TRIAGE])
        record_attempt(api, 7, FireResult(attempted=True), PENDING)
        self.assertIn(PENDING, labels_on(api, 7))

    def test_a_failed_fire_is_not_recorded(self):  # GK-138
        """It started nothing, so recording an attempt would spend the issue's
        one retry on a session that never existed."""
        api = api_with(7, [TRIAGE])
        record_attempt(api, 7, FireResult(True, failed=True, detail="502"), PENDING)
        self.assertNotIn(PENDING, labels_on(api, 7))

    def test_an_unconfigured_routine_is_not_recorded(self):  # GK-138
        api = api_with(7, [TRIAGE])
        record_attempt(api, 7, FireResult(attempted=False), PENDING)
        self.assertNotIn(PENDING, labels_on(api, 7))

    def test_recording_an_already_present_marker_writes_nothing(self):  # GK-138
        """A write that changes nothing is still a write: it shows in the audit
        trail and invites a re-render. Asserted against the writes themselves
        rather than a total call count, which would also pass for the wrong
        reason if the read went away."""
        api = api_with(7, [TRIAGE, PENDING])
        record_attempt(api, 7, FireResult(attempted=True), PENDING)
        writes = [name for name, _ in api.calls if name == "set_labels"]
        self.assertEqual(writes, [])
        self.assertEqual(labels_on(api, 7), {TRIAGE, PENDING})

    def test_recording_keeps_every_other_label(self):  # GK-138
        api = api_with(7, [TRIAGE, "area:ui", "type:bug"])
        record_attempt(api, 7, FireResult(attempted=True), PENDING)
        self.assertEqual(labels_on(api, 7),
                         {TRIAGE, "area:ui", "type:bug", PENDING})

    def test_a_failed_record_never_raises(self):  # GK-138
        """The poke already went out. Failing the run now would report a fire
        that happened as a fire that did not."""
        class Broken(FakeGitHub):
            def set_labels(self, issue, labels):
                raise RuntimeError("no")

        api = Broken(issues=[{"number": 7, "state": "open",
                              "labels": [{"name": TRIAGE}]}])
        record_attempt(api, 7, FireResult(attempted=True), PENDING)  # no raise


class TestMarkersAreClearedOnStateChange(unittest.TestCase):
    """GK-141/GK-145 — the next episode must not inherit a spent budget."""

    def test_leaving_triage_clears_the_markers(self):  # GK-145
        after = plan_labels([TRIAGE, PENDING], [_Action("approve")], LABELS,
                            markers=MARKERS)
        self.assertNotIn(PENDING, after)

    def test_re_entering_triage_clears_the_markers(self):  # GK-141
        """A fresh `/admit` is a new episode and deserves a fresh budget."""
        after = plan_labels([TRIAGE, STALLED], [_Action("admit")], LABELS,
                            markers=MARKERS)
        self.assertNotIn(STALLED, after)
        self.assertIn(TRIAGE, after)

    def test_classification_labels_still_survive(self):  # GK-145
        after = plan_labels([TRIAGE, PENDING, "area:ui"], [_Action("approve")],
                            LABELS, markers=MARKERS)
        self.assertIn("area:ui", after)

    def test_a_run_with_no_state_move_touches_no_marker(self):  # GK-145
        after = plan_labels([TRIAGE, PENDING], [], LABELS, markers=MARKERS)
        self.assertIn(PENDING, after)


if __name__ == "__main__":
    unittest.main()
