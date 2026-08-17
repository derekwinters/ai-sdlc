#!/usr/bin/env python3
"""The sweep's I/O layer: what it reads, what it writes, and what it says.

The decision is tested in `test_sweep.py` against the pure planner. What is
left here is the part that touches the world — and the most important thing
about it is what it cannot do. `run` takes no fire and has no way to obtain
one, which is `GK-140` enforced by the shape of the code rather than by a
promise in a docstring.

Specification: docs/spec/gatekeeper.md (`GK-139`–`GK-143`).
"""

from __future__ import annotations

import inspect
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(
    0, str(Path(__file__).resolve().parents[1] / "skills/pipeline/pipeline-gatekeeper")
)

from lib.fake_github import FakeGitHub  # noqa: E402
from run_sweep import board, has_analysis, run, summarise  # noqa: E402

QUEUED = "ai-triage-queued"
RUNNING = "ai-triage-running"
STALLED = "ai-triage-stalled"
OLD = "2026-08-17T06:00:00Z"
NOW = "2026-08-17T12:00:00Z"


class _Config:
    labels = {
        "triage_queued": QUEUED,
        "triage_running": RUNNING,
        "triage_stalled": STALLED,
        "pending_approval": "pending-approval",
        "clarification": "needs-clarification",
        "approved": "ready-for-work",
        "building": "in-progress",
        "parked": "parked",
    }

    def label(self, state):
        return self.labels[state]


def an_issue(number, *, labels=(RUNNING,), updated=OLD, author="derekwinters"):
    return {
        "number": number,
        "state": "open",
        "labels": [{"name": n} for n in labels],
        "updated_at": updated,
        "user": {"login": author},
    }


def api_with(*issues, comments=None):
    return FakeGitHub(issues=list(issues), comments=comments or {})


def labels_on(api, number):
    return {l["name"] for l in api.issue(number).get("labels") or []}


class TestItCannotStartASession(unittest.TestCase):
    """GK-140 — the invariant, asserted structurally.

    A behavioural test ("it did not fire") only proves this run did not. These
    prove the code has no way to, which is what stops a later edit quietly
    reintroducing one.
    """

    def test_run_takes_no_fire(self):  # GK-140
        self.assertNotIn("fire", inspect.signature(run).parameters)

    def test_the_module_never_mentions_firing(self):  # GK-140
        source = Path(__file__).resolve().parents[1] / (
            "skills/pipeline/pipeline-gatekeeper/run_sweep.py")
        body = "\n".join(
            line for line in source.read_text().splitlines()
            if not line.strip().startswith("#")
        )
        # The docstring explains why there is no fire; the code must not have
        # one. Checking for the call rather than the word keeps the prose free.
        self.assertNotIn(".send(", body)
        self.assertNotIn("Fire(", body)


class TestDetectingAnalysis(unittest.TestCase):
    """GK-139 — what separates "never answered" from "already answered"."""

    def test_no_comments_means_no_analysis(self):  # GK-139
        self.assertFalse(has_analysis(api_with(an_issue(1)), {"number": 1},
                                      author="derekwinters"))

    def test_the_authors_own_comment_is_not_analysis(self):  # GK-139
        """`/admit` is a command. Counting it would mark every admitted issue
        analysed, silently disabling the backstop where it is needed."""
        api = api_with(an_issue(1), comments={
            1: [{"user": {"login": "derekwinters"}, "body": "/admit"}]})
        self.assertFalse(has_analysis(api, {"number": 1}, author="derekwinters"))

    def test_somebody_elses_comment_is_analysis(self):  # GK-139
        api = api_with(an_issue(1), comments={
            1: [{"user": {"login": "some-bot"}, "body": "analysis"}]})
        self.assertTrue(has_analysis(api, {"number": 1}, author="derekwinters"))


class TestWritingTheState(unittest.TestCase):
    """GK-139/GK-142 — the label actually moves, and only for the right issues."""

    def test_a_stale_running_issue_becomes_stalled(self):  # GK-139
        api = api_with(an_issue(322))
        run(api, _Config(), now=NOW, stale_after=1800)
        self.assertEqual(labels_on(api, 322), {STALLED})

    def test_the_running_label_is_replaced_not_added(self):  # GK-139
        """Two triage states at once would break `GK-001`, and a reader could
        not tell which one was true."""
        api = api_with(an_issue(322))
        run(api, _Config(), now=NOW, stale_after=1800)
        self.assertNotIn(RUNNING, labels_on(api, 322))

    def test_other_labels_survive(self):  # GK-139
        api = api_with(an_issue(322, labels=(RUNNING, "area:ui", "type:bug")))
        run(api, _Config(), now=NOW, stale_after=1800)
        self.assertEqual(labels_on(api, 322), {STALLED, "area:ui", "type:bug"})

    def test_a_fresh_session_is_untouched(self):  # GK-139
        api = api_with(an_issue(322, updated=NOW))
        run(api, _Config(), now=NOW, stale_after=1800)
        self.assertEqual(labels_on(api, 322), {RUNNING})

    def test_a_queued_issue_is_untouched(self):  # GK-139
        api = api_with(an_issue(322, labels=(QUEUED,)))
        run(api, _Config(), now=NOW, stale_after=1800)
        self.assertEqual(labels_on(api, 322), {QUEUED})

    def test_an_already_stalled_issue_is_not_rewritten(self):  # GK-142
        api = api_with(an_issue(322, labels=(STALLED,)))
        run(api, _Config(), now=NOW, stale_after=1800)
        self.assertEqual([n for n, _ in api.calls if n == "set_labels"], [])


class TestTheBoardRead(unittest.TestCase):
    def test_pull_requests_are_not_issues(self):  # GK-139
        """GitHub returns pull requests from the issues endpoint."""
        api = api_with(an_issue(1), dict(an_issue(2), pull_request={}))
        seen = [i["number"] for i in
                board(api, running_label=RUNNING, now=NOW)["issues"]]
        self.assertEqual(seen, [1])


class TestTheThresholdIsRequired(unittest.TestCase):
    """GK-141 — required, not defaulted.

    Asserted in two places because they fail differently: the workflow input
    is what stops a caller omitting it, and `run` having no default is what
    stops the code quietly supplying one if the workflow contract ever slips.
    """

    def test_run_has_no_default_threshold(self):  # GK-141
        parameter = inspect.signature(run).parameters["stale_after"]
        self.assertIs(parameter.default, inspect.Parameter.empty)

    def test_the_workflow_declares_the_input_required(self):  # GK-141
        workflow = (Path(__file__).resolve().parents[1]
                    / ".github/workflows/reusable-gatekeeper-sweep.yml").read_text()
        block = workflow[workflow.index("stale_after:"):]
        self.assertIn("required: true", block[:block.index("permissions:")])

    def test_adopt_writes_thirty_minutes_into_the_caller(self):  # GK-141
        """The value belongs where somebody can see and change it."""
        adopt = (Path(__file__).resolve().parents[1]
                 / "skills/substrate/adopt/adopt.py").read_text()
        self.assertIn("stale_after: 1800", adopt)


class TestReporting(unittest.TestCase):
    """GK-143 — a silent run is indistinguishable from a broken one."""

    def test_a_run_that_stalled_something_names_it(self):  # GK-143
        self.assertTrue(any("9" in line for line in summarise({"stall": [9]})))

    def test_an_empty_run_still_says_something(self):  # GK-143
        self.assertTrue(summarise({"stall": []}))


if __name__ == "__main__":
    unittest.main()
