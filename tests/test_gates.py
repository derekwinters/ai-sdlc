"""GK-050 to GK-065 — the rules that refuse a command before any write.

The ordering gate is the one with a history: refusing when a blocker's
milestone could not be ordered made any issue blocked by an issue in a
standing non-version milestone permanently unapprovable. It now refuses only
on evidence of inversion.
"""

import unittest

import _gatekeeper  # noqa: F401
from gates import Verdict, run_gates
from parse_commands import parse

MILESTONES = [
    {"number": 1, "title": "v0.1", "state": "open"},
    {"number": 2, "title": "v0.2", "state": "open"},
    {"number": 6, "title": "Direct Involvement Needed", "state": "open"},
]


def issue(milestone="v0.1", state="open"):
    return {"number": 7, "state": state,
            "milestone": {"title": milestone} if milestone else None}


def blocker(number=42, milestone="v0.1", state="open", kind="blocked_by"):
    return {"number": number, "state": state, "kind": kind,
            "milestone": {"title": milestone} if milestone else None}


def gate(text, subject=None, blockers=(), ordering="semver"):
    return run_gates(
        parse(text).actions,
        issue=subject if subject is not None else issue(),
        blockers=list(blockers),
        milestones=MILESTONES,
        ordering=ordering,
    )


def applied(result):
    return [a.command for a in result.actions]


def reasons(result):
    return [s.reason for s in result.skips]


class TestMilestonePresence(unittest.TestCase):
    def test_approve_with_a_milestone_passes(self):  # GK-050
        self.assertEqual(applied(gate("/approve")), ["approve"])

    def test_approve_without_one_is_refused(self):  # GK-050
        self.assertEqual(reasons(gate("/approve", subject=issue(milestone=None))),
                         ["no-milestone"])

    def test_an_empty_string_milestone_is_absent(self):  # GK-052
        self.assertEqual(reasons(gate("/approve", subject=issue(milestone=""))),
                         ["no-milestone"])

    def test_the_refusal_asks_which_milestone(self):  # GK-051
        skip = gate("/approve", subject=issue(milestone=None)).skips[0]
        self.assertIn("which milestone", skip.detail.lower())

    def test_the_gate_never_picks_one(self):  # GK-051
        """It asks; it does not choose. Nothing writable comes out of a refusal."""
        result = gate("/approve", subject=issue(milestone=None))
        self.assertEqual(applied(result), [])
        self.assertFalse(hasattr(result.skips[0], "chosen_milestone"))

    def test_the_presence_gate_does_not_apply_to_milestone(self):  # GK-059
        self.assertEqual(applied(gate("/milestone v0.2", subject=issue(milestone=None))),
                         ["milestone"])

    def test_park_is_never_gated(self):  # GK-060
        self.assertEqual(applied(gate("/park", subject=issue(milestone=None))), ["park"])

    def test_unpark_is_not_gated_either(self):  # GK-060
        self.assertEqual(applied(gate("/unpark", subject=issue(milestone=None))), ["unpark"])


class TestNoInlineMilestone(unittest.TestCase):
    """GK-053 — `/milestone` then `/approve`, in separate comments."""

    def test_approve_with_an_argument_is_refused(self):
        self.assertEqual(reasons(gate("/approve v0.2", subject=issue(milestone=None))),
                         ["approve-takes-no-argument"])

    def test_the_refusal_explains_the_two_step(self):
        skip = gate("/approve v0.2").skips[0]
        self.assertIn("/milestone", skip.detail)

    def test_approve_with_an_argument_is_refused_even_with_a_milestone(self):
        self.assertEqual(reasons(gate("/approve v0.2")), ["approve-takes-no-argument"])


class TestOrderingInversion(unittest.TestCase):
    def test_a_blocker_in_a_later_milestone_refuses(self):  # GK-054
        self.assertEqual(reasons(gate("/approve", blockers=[blocker(milestone="v0.2")])),
                         ["blocker-inversion"])

    def test_a_blocker_in_the_same_milestone_passes(self):  # GK-055
        self.assertEqual(applied(gate("/approve", blockers=[blocker(milestone="v0.1")])),
                         ["approve"])

    def test_a_blocker_in_an_earlier_milestone_passes(self):  # GK-055
        subject = issue(milestone="v0.2")
        self.assertEqual(
            applied(gate("/approve", subject=subject, blockers=[blocker(milestone="v0.1")])),
            ["approve"],
        )

    def test_a_closed_blocker_is_ignored(self):  # GK-056
        blocked = [blocker(milestone="v0.2", state="closed")]
        self.assertEqual(applied(gate("/approve", blockers=blocked)), ["approve"])

    def test_a_soft_dependency_uses_the_same_rule(self):  # GK-057
        blocked = [blocker(milestone="v0.2", kind="depends_on")]
        self.assertEqual(reasons(gate("/approve", blockers=blocked)), ["blocker-inversion"])

    def test_a_closed_soft_dependency_is_ignored(self):  # GK-056
        blocked = [blocker(milestone="v0.2", state="closed", kind="depends_on")]
        self.assertEqual(applied(gate("/approve", blockers=blocked)), ["approve"])

    def test_every_offending_blocker_is_named(self):  # GK-058
        blocked = [blocker(number=42, milestone="v0.2"), blocker(number=43, milestone="v0.2")]
        detail = gate("/approve", blockers=blocked).skips[0].detail
        self.assertIn("#42", detail)
        self.assertIn("#43", detail)

    def test_a_passing_blocker_is_not_named(self):  # GK-058
        blocked = [blocker(number=42, milestone="v0.2"), blocker(number=43, milestone="v0.1")]
        detail = gate("/approve", blockers=blocked).skips[0].detail
        self.assertNotIn("#43", detail)

    def test_the_ordering_gate_applies_to_milestone(self):  # GK-059
        blocked = [blocker(milestone="v0.2")]
        self.assertEqual(reasons(gate("/milestone v0.1", blockers=blocked)),
                         ["blocker-inversion"])

    def test_no_blockers_passes(self):  # GK-055
        self.assertEqual(applied(gate("/approve")), ["approve"])


class TestAbsenceOfEvidence(unittest.TestCase):
    """GK-064 — the defect that motivated the capability restructure.

    Refusing when a blocker's milestone could not be ordered made any issue
    blocked by an issue in `Direct Involvement Needed` permanently
    unapprovable, with a message about ordering rather than about the cause.
    """

    def test_a_blocker_in_an_unorderable_milestone_does_not_refuse(self):
        blocked = [blocker(milestone="Direct Involvement Needed")]
        self.assertEqual(applied(gate("/approve", blockers=blocked)), ["approve"])

    def test_a_blocker_with_no_milestone_does_not_refuse(self):
        self.assertEqual(applied(gate("/approve", blockers=[blocker(milestone=None)])),
                         ["approve"])

    def test_an_unscheduled_subject_does_not_refuse_on_ordering(self):
        subject = issue(milestone="Direct Involvement Needed")
        blocked = [blocker(milestone="v0.2")]
        self.assertEqual(applied(gate("/approve", subject=subject, blockers=blocked)),
                         ["approve"])

    def test_an_unverifiable_dependency_is_reported_not_swallowed(self):  # GK-065
        blocked = [blocker(number=42, milestone="Direct Involvement Needed")]
        result = gate("/approve", blockers=blocked)
        self.assertEqual([u["number"] for u in result.unverifiable], [42])

    def test_a_verifiable_dependency_is_not_reported(self):  # GK-065
        result = gate("/approve", blockers=[blocker(milestone="v0.1")])
        self.assertEqual(result.unverifiable, [])

    def test_a_closed_unorderable_blocker_is_not_reported(self):  # GK-065
        blocked = [blocker(milestone=None, state="closed")]
        self.assertEqual(gate("/approve", blockers=blocked).unverifiable, [])


class TestTheNoneStrategy(unittest.TestCase):
    def test_the_ordering_gate_does_not_run_at_all(self):  # GK-063
        blocked = [blocker(milestone="v0.2")]
        self.assertEqual(applied(gate("/approve", blockers=blocked, ordering="none")),
                         ["approve"])

    def test_milestone_presence_is_unaffected(self):  # GK-063
        result = gate("/approve", subject=issue(milestone=None), ordering="none")
        self.assertEqual(reasons(result), ["no-milestone"])

    def test_nothing_is_reported_as_unverifiable(self):  # GK-063
        blocked = [blocker(milestone="Direct Involvement Needed")]
        self.assertEqual(gate("/approve", blockers=blocked, ordering="none").unverifiable, [])


class TestARefusalChangesNothing(unittest.TestCase):
    def test_a_refusal_leaves_no_action(self):  # GK-062
        self.assertEqual(applied(gate("/approve", subject=issue(milestone=None))), [])

    def test_a_refusal_carries_no_milestone_write(self):  # GK-062
        result = gate("/approve", blockers=[blocker(milestone="v0.2")])
        self.assertEqual(result.actions, [])

    def test_a_verdict_knows_it_refused(self):  # GK-062
        verdict = Verdict(refused=True, reason="x", detail="y")
        self.assertTrue(verdict.refused)

    def test_a_passing_verdict_has_no_reason(self):  # GK-062
        self.assertIsNone(Verdict(refused=False).reason)


if __name__ == "__main__":
    unittest.main()
