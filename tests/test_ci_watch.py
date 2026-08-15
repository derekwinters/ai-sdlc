"""CIW-001 to CIW-017 — waiting for checks, and judging them."""

import unittest

from _ciwatch import Checks, Clock, check
import _ciwatch  # noqa: F401
from ci_watch import Outcome, watch


def run(*rounds, clock=None, **kwargs):
    clock = clock or Clock()
    kwargs.setdefault("interval", 10)
    kwargs.setdefault("deadline", 600)
    return watch(Checks(*rounds), clock=clock, **kwargs), clock


class TestWaiting(unittest.TestCase):
    def test_it_returns_when_everything_has_completed(self):  # CIW-001
        result, _ = run([check("build")])
        self.assertEqual(result.outcome, Outcome.PASSED)

    def test_a_queued_check_is_not_complete(self):  # CIW-002
        result, clock = run(
            [check("build", status="queued", conclusion=None)], [check("build")]
        )
        self.assertEqual(result.outcome, Outcome.PASSED)
        self.assertEqual(len(clock.slept), 1)

    def test_an_in_progress_check_is_not_complete(self):  # CIW-002
        result, _ = run(
            [check("build", status="in_progress", conclusion=None)], [check("build")]
        )
        self.assertEqual(result.outcome, Outcome.PASSED)

    def test_it_waits_the_configured_interval(self):  # CIW-005
        _, clock = run([check("b", status="queued", conclusion=None)], [check("b")],
                       interval=30)
        self.assertEqual(clock.slept, [30])

    def test_no_wait_is_needed_when_already_complete(self):  # CIW-001
        _, clock = run([check("build")])
        self.assertEqual(clock.slept, [])


class TestBounds(unittest.TestCase):
    def test_a_deadline_ends_the_watch(self):  # CIW-003
        result, _ = run([check("b", status="queued", conclusion=None)],
                        interval=100, deadline=250)
        self.assertEqual(result.outcome, Outcome.TIMED_OUT)

    def test_a_timeout_is_not_a_pass(self):  # CIW-003
        result, _ = run([check("b", status="queued", conclusion=None)],
                        interval=100, deadline=250)
        self.assertNotEqual(result.outcome, Outcome.PASSED)

    def test_a_timeout_is_not_a_failure(self):  # CIW-003
        result, _ = run([check("b", status="queued", conclusion=None)],
                        interval=100, deadline=250)
        self.assertNotEqual(result.outcome, Outcome.FAILED)

    def test_an_attempt_cap_ends_the_watch(self):  # CIW-004
        result, _ = run([check("b", status="queued", conclusion=None)],
                        interval=0, deadline=10_000, max_attempts=5)
        self.assertEqual(result.outcome, Outcome.TIMED_OUT)

    def test_the_attempt_cap_is_respected_exactly(self):  # CIW-004
        checks = Checks([check("b", status="queued", conclusion=None)])
        watch(checks, clock=Clock(), interval=0, deadline=10_000, max_attempts=5)
        self.assertEqual(checks.calls, 5)


class TestNoChecks(unittest.TestCase):
    def test_no_checks_is_reported_distinctly(self):  # CIW-006
        result, _ = run([])
        self.assertEqual(result.outcome, Outcome.NO_CHECKS)

    def test_no_checks_is_not_a_pass(self):  # CIW-006
        result, _ = run([])
        self.assertNotEqual(result.outcome, Outcome.PASSED)


class TestJudging(unittest.TestCase):
    def test_all_successful_passes(self):  # CIW-015
        result, _ = run([check("a"), check("b")])
        self.assertEqual(result.outcome, Outcome.PASSED)

    def test_one_failure_fails(self):  # CIW-015
        result, _ = run([check("a"), check("b", conclusion="failure")])
        self.assertEqual(result.outcome, Outcome.FAILED)

    def test_a_skipped_check_is_not_a_failure(self):  # CIW-012
        result, _ = run([check("a"), check("b", conclusion="skipped")])
        self.assertEqual(result.outcome, Outcome.PASSED)

    def test_a_neutral_check_is_not_a_failure(self):  # CIW-013
        result, _ = run([check("a"), check("b", conclusion="neutral")])
        self.assertEqual(result.outcome, Outcome.PASSED)

    def test_a_cancelled_check_is_a_failure(self):  # CIW-014
        result, _ = run([check("a", conclusion="cancelled")])
        self.assertEqual(result.outcome, Outcome.FAILED)

    def test_a_timed_out_check_is_a_failure(self):  # CIW-014
        result, _ = run([check("a", conclusion="timed_out")])
        self.assertEqual(result.outcome, Outcome.FAILED)

    def test_only_skipped_checks_is_not_a_pass_by_accident(self):  # CIW-012
        result, _ = run([check("a", conclusion="skipped")])
        self.assertEqual(result.outcome, Outcome.PASSED)


class TestReporting(unittest.TestCase):
    def test_every_check_is_named(self):  # CIW-010
        result, _ = run([check("a"), check("b", conclusion="failure")])
        self.assertEqual({c.name for c in result.checks}, {"a", "b"})

    def test_each_carries_its_conclusion(self):  # CIW-010
        result, _ = run([check("a", conclusion="failure")])
        self.assertEqual(result.checks[0].conclusion, "failure")

    def test_the_order_is_stable(self):  # CIW-011
        result, _ = run([check("b"), check("a"), check("c")])
        self.assertEqual([c.name for c in result.checks], ["a", "b", "c"])

    def test_failures_are_listed_separately(self):  # CIW-010
        result, _ = run([check("a"), check("b", conclusion="failure")])
        self.assertEqual([c.name for c in result.failures], ["b"])


class TestReadFailures(unittest.TestCase):
    def test_a_transient_failure_is_retried(self):  # CIW-016
        checks = Checks([check("build")], errors=1)
        result = watch(checks, clock=Clock(), interval=1, deadline=600)
        self.assertEqual(result.outcome, Outcome.PASSED)

    def test_repeated_failures_end_as_unreachable(self):  # CIW-017
        checks = Checks([check("build")], errors=99)
        result = watch(checks, clock=Clock(), interval=1, deadline=600, max_attempts=4)
        self.assertEqual(result.outcome, Outcome.UNREACHABLE)

    def test_unreachable_is_not_a_failure(self):  # CIW-017
        checks = Checks([check("build")], errors=99)
        result = watch(checks, clock=Clock(), interval=1, deadline=600, max_attempts=4)
        self.assertNotEqual(result.outcome, Outcome.FAILED)

    def test_unreachable_is_not_a_pass(self):  # CIW-017
        checks = Checks([check("build")], errors=99)
        result = watch(checks, clock=Clock(), interval=1, deadline=600, max_attempts=4)
        self.assertNotEqual(result.outcome, Outcome.PASSED)


if __name__ == "__main__":
    unittest.main()
