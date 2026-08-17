#!/usr/bin/env python3
"""The sweep's I/O layer: what it reads, what it pokes, and what it says.

The decisions are tested in `test_sweep.py` against the pure planner. What is
left here is the part that can spend money — that a requeue is one poke and not
two, that a degraded read cannot turn into an unbounded one, and that every run
says what it did.

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

from lib.fake_github import FakeGitHub  # noqa: E402
from downstream import FireResult  # noqa: E402
from run_sweep import board, has_analysis, run, summarise  # noqa: E402

TRIAGE = "ai-triage"
PENDING = "ai-triage-pending"
STALLED = "ai-triage-stalled"
MARKERS = (PENDING, STALLED)
OLD = "2026-08-17T06:00:00Z"
NOW = "2026-08-17T12:00:00Z"


class _Config:
    """Just the surface `run` reads."""

    class _Sweep:
        ceiling = 10
        stale_after = 1800

    sweep = _Sweep()

    def label(self, state):
        return TRIAGE

    def markers(self):
        return MARKERS


class _Fire:
    """Records pokes instead of sending them, and reports each as a real fire
    so the marker path runs."""

    def __init__(self, ok=True):
        self.sent = []
        self.ok = ok

    def send(self, issue, repository):
        self.sent.append(issue)
        return FireResult(attempted=True) if self.ok else FireResult(
            True, failed=True, detail="502")


def api_with(*issues, comments=None):
    return FakeGitHub(issues=list(issues), comments=comments or {})


def an_issue(number, *, labels=(TRIAGE,), updated=OLD, author="derekwinters"):
    return {
        "number": number,
        "state": "open",
        "labels": [{"name": n} for n in labels],
        "updated_at": updated,
        "user": {"login": author},
    }


class TestDetectingAnalysis(unittest.TestCase):
    """GK-138 — the signal that separates 'never ran' from 'already ran'."""

    def test_no_comments_means_no_analysis(self):  # GK-138
        api = api_with(an_issue(1))
        self.assertFalse(has_analysis(api, {"number": 1}, author="derekwinters"))

    def test_the_authors_own_comment_is_not_analysis(self):  # GK-138
        """`/admit` is a command. Counting it would mark every admitted issue
        analysed, which reads as 'nothing is stranded' and silently disables the
        backstop exactly where it is needed."""
        api = api_with(an_issue(1), comments={
            1: [{"user": {"login": "derekwinters"}, "body": "/admit"}]})
        self.assertFalse(has_analysis(api, {"number": 1}, author="derekwinters"))

    def test_somebody_elses_comment_is_analysis(self):  # GK-138
        api = api_with(an_issue(1), comments={
            1: [{"user": {"login": "some-bot"}, "body": "analysis"}]})
        self.assertTrue(has_analysis(api, {"number": 1}, author="derekwinters"))


class TestPoking(unittest.TestCase):
    """GK-139 — a requeue is one session, and never more than the ceiling."""

    def test_a_stranded_issue_is_poked_once(self):  # GK-139
        api, fire = api_with(an_issue(322)), _Fire()
        run(api, _Config(), fire, now=NOW, events_only=False)
        self.assertEqual(fire.sent, [322])

    def test_the_ceiling_bounds_the_pokes_not_just_the_plan(self):  # GK-139
        """The bound has to hold where the money is spent, not only where the
        decision is made."""
        config = _Config()
        config.sweep.ceiling = 2
        api = api_with(*[an_issue(n) for n in range(1, 10)])
        fire = _Fire()
        run(api, config, fire, now=NOW, events_only=False)
        self.assertEqual(len(fire.sent), 2)
        config.sweep.ceiling = 10  # shared class attribute; restore

    def test_the_event_path_pokes_nothing(self):  # GK-142
        api, fire = api_with(an_issue(322)), _Fire()
        run(api, _Config(), fire, now=NOW, events_only=True)
        self.assertEqual(fire.sent, [])

    def test_a_fresh_issue_is_not_poked(self):  # GK-138
        api, fire = api_with(an_issue(322, updated=NOW)), _Fire()
        run(api, _Config(), fire, now=NOW, events_only=False)
        self.assertEqual(fire.sent, [])


class TestTheMarkerIsActuallyApplied(unittest.TestCase):
    """GK-140 — the bound is only real if the record survives the run."""

    def labels(self, api, number):
        return {l["name"] for l in api.issue(number).get("labels") or []}

    def test_poking_an_unmarked_issue_marks_it_pending(self):  # GK-140
        api, fire = api_with(an_issue(322)), _Fire()
        run(api, _Config(), fire, now=NOW, events_only=False)
        self.assertIn(PENDING, self.labels(api, 322))

    def test_poking_a_pending_issue_advances_it_to_stalled(self):  # GK-140
        api = api_with(an_issue(322, labels=(TRIAGE, PENDING)))
        run(api, _Config(), _Fire(), now=NOW, events_only=False)
        marks = self.labels(api, 322)
        self.assertIn(STALLED, marks)
        self.assertNotIn(PENDING, marks)  # advanced, not accumulated

    def test_a_failed_fire_leaves_the_marker_alone(self):  # GK-138
        """No session started, so the issue has not spent its retry."""
        api = api_with(an_issue(322))
        run(api, _Config(), _Fire(ok=False), now=NOW, events_only=False)
        self.assertNotIn(PENDING, self.labels(api, 322))

    def test_a_marker_outside_triage_is_cleared(self):  # GK-145
        api = api_with(an_issue(322, labels=("pending-approval", PENDING)))
        run(api, _Config(), _Fire(), now=NOW, events_only=False)
        self.assertNotIn(PENDING, self.labels(api, 322))

    def test_clearing_keeps_the_other_labels(self):  # GK-145
        api = api_with(an_issue(322, labels=("pending-approval", PENDING, "area:ui")))
        run(api, _Config(), _Fire(), now=NOW, events_only=False)
        self.assertIn("area:ui", self.labels(api, 322))


class TestTheBoardRead(unittest.TestCase):
    def test_pull_requests_are_not_issues(self):  # GK-138
        """GitHub returns pull requests from the issues endpoint. A PR carrying
        the triage label would otherwise be poked as a stranded issue."""
        a_pull_request = dict(an_issue(2), pull_request={})
        api = api_with(an_issue(1), a_pull_request)
        seen = [i["number"] for i in
                board(api, triage_label=TRIAGE, now=NOW)["issues"]]
        self.assertEqual(seen, [1])


class TestReporting(unittest.TestCase):
    """GK-140/GK-144 — a run that hides what it skipped reads as a clear board."""

    EMPTY = {"requeue": [], "skipped": [], "stalled": [], "clear": [],
             "withheld": [], "mark": {}}

    def test_the_skipped_remainder_is_named(self):  # GK-144
        lines = summarise(dict(self.EMPTY, requeue=[1], skipped=[2, 3]))
        self.assertTrue(any("[2, 3]" in l for l in lines))

    def test_the_stalled_are_named(self):  # GK-146
        lines = summarise(dict(self.EMPTY, stalled=[9]))
        self.assertTrue(any("9" in l for l in lines))

    def test_an_empty_run_still_says_something(self):  # GK-144
        lines = summarise(dict(self.EMPTY))
        self.assertTrue(lines and "0" in lines[0])


if __name__ == "__main__":
    unittest.main()
