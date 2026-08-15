"""BLK-001 to BLK-007 and BLK-040 to BLK-044 — reading the graph, and eligibility."""

import unittest

import _blockers  # noqa: F401
from issue_blockers import Blockers, is_eligible
from lib.fake_github import FakeFailure, FakeGitHub
from lib.github import GitHubError


def issue(number, state="open", milestone="v0.1", merged=False):
    return {
        "number": number,
        "state": state,
        "merged": merged,
        "milestone": {"title": milestone} if milestone else None,
    }


def api(graph=None, issues=None, **kwargs):
    return FakeGitHub(
        issues=issues or [issue(7), issue(42), issue(43)],
        blocked_by=graph or {},
        actor="sdlc-bot[bot]",
        **kwargs,
    )


class TestReading(unittest.TestCase):
    def test_it_returns_the_blocking_issues(self):  # BLK-001
        found = Blockers(api({7: [{"number": 42}]})).blockers_of(7)
        self.assertEqual([b.number for b in found], [42])

    def test_each_carries_its_state_and_milestone(self):  # BLK-002
        found = Blockers(api({7: [{"number": 42}]})).blockers_of(7)
        self.assertEqual((found[0].state, found[0].milestone), ("open", "v0.1"))

    def test_no_blockers_is_an_empty_list(self):  # BLK-006
        self.assertEqual(Blockers(api()).blockers_of(7), [])

    def test_a_closed_blocker_is_resolved(self):  # BLK-003
        github = api({7: [{"number": 42}]}, issues=[issue(7), issue(42, state="closed")])
        self.assertTrue(Blockers(github).blockers_of(7)[0].resolved)

    def test_a_merged_blocker_is_resolved(self):  # BLK-004
        github = api({7: [{"number": 42}]}, issues=[issue(7), issue(42, merged=True)])
        self.assertTrue(Blockers(github).blockers_of(7)[0].resolved)

    def test_an_open_blocker_is_not(self):  # BLK-005
        self.assertFalse(Blockers(api({7: [{"number": 42}]})).blockers_of(7)[0].resolved)

    def test_a_failing_read_raises(self):  # BLK-007
        github = api({7: [{"number": 42}]}, fail={"blocked_by": FakeFailure("down")})
        with self.assertRaises(GitHubError):
            Blockers(github).blockers_of(7)

    def test_an_unreadable_blocker_issue_is_unknown_not_resolved(self):  # BLK-043
        github = api({7: [{"number": 99}]})  # 99 does not exist
        blocker = Blockers(github).blockers_of(7)[0]
        self.assertFalse(blocker.resolved)
        self.assertTrue(blocker.unknown)


class TestEligibility(unittest.TestCase):
    def test_no_blockers_is_eligible(self):  # BLK-041
        self.assertTrue(is_eligible(7, []).eligible)

    def test_all_resolved_is_eligible(self):  # BLK-040
        github = api({7: [{"number": 42}]}, issues=[issue(7), issue(42, state="closed")])
        self.assertTrue(is_eligible(7, Blockers(github).blockers_of(7)).eligible)

    def test_one_unresolved_is_not(self):  # BLK-042
        github = api({7: [{"number": 42}]})
        self.assertFalse(is_eligible(7, Blockers(github).blockers_of(7)).eligible)

    def test_partial_resolution_is_not(self):  # BLK-042
        github = api({7: [{"number": 42}, {"number": 43}]},
                     issues=[issue(7), issue(42, state="closed"), issue(43)])
        self.assertFalse(is_eligible(7, Blockers(github).blockers_of(7)).eligible)

    def test_an_unknown_blocker_makes_it_ineligible(self):  # BLK-043
        github = api({7: [{"number": 99}]})
        self.assertFalse(is_eligible(7, Blockers(github).blockers_of(7)).eligible)

    def test_the_reason_names_the_blockers(self):  # BLK-044
        github = api({7: [{"number": 42}]})
        self.assertIn("#42", is_eligible(7, Blockers(github).blockers_of(7)).reason)

    def test_the_reason_names_every_blocker(self):  # BLK-044
        github = api({7: [{"number": 42}, {"number": 43}]})
        reason = is_eligible(7, Blockers(github).blockers_of(7)).reason
        self.assertIn("#42", reason)
        self.assertIn("#43", reason)

    def test_a_resolved_blocker_is_not_named(self):  # BLK-044
        github = api({7: [{"number": 42}, {"number": 43}]},
                     issues=[issue(7), issue(42, state="closed"), issue(43)])
        self.assertNotIn("#42", is_eligible(7, Blockers(github).blockers_of(7)).reason)

    def test_an_eligible_issue_has_no_reason(self):  # BLK-041
        self.assertEqual(is_eligible(7, []).reason, "")


if __name__ == "__main__":
    unittest.main()
