"""BLK-001 to BLK-007 — reading the graph, in the one place that still does.

The dashboard is a script: it runs in a workflow with no agent present, so it
reads the dependency graph in code. Everything else about blockers is now an
agent's work, and `test_blockers_rules.py` covers that.
"""

import unittest

import _blockers  # noqa: F401
from blocker_state import Blocker, read_blockers
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
        found = read_blockers(api({7: [{"number": 42}]}), 7)
        self.assertEqual([b.number for b in found], [42])

    def test_each_carries_its_state_and_milestone(self):  # BLK-002
        found = read_blockers(api({7: [{"number": 42}]}), 7)
        self.assertEqual((found[0].state, found[0].milestone), ("open", "v0.1"))

    def test_no_blockers_is_an_empty_list(self):  # BLK-006
        self.assertEqual(read_blockers(api(), 7), [])

    def test_a_failing_read_raises(self):  # BLK-007
        github = api({7: [{"number": 42}]}, fail={"blocked_by": FakeFailure("down")})
        with self.assertRaises(GitHubError):
            read_blockers(github, 7)

    def test_an_unreadable_blocker_issue_is_unknown_not_resolved(self):  # BLK-007
        """Degrading to "unknown" rather than raising: one unreadable blocker
        should not cost the whole board, and unknown is never resolved."""
        blocker = read_blockers(api({7: [{"number": 99}]}), 7)[0]  # 99 does not exist
        self.assertFalse(blocker.resolved)
        self.assertTrue(blocker.unknown)


class TestWhatCountsAsResolved(unittest.TestCase):
    """BLK-003 to BLK-005 — the one judgement the dashboard makes itself."""

    def test_a_closed_blocker_is_resolved(self):  # BLK-003
        github = api({7: [{"number": 42}]}, issues=[issue(7), issue(42, state="closed")])
        self.assertTrue(read_blockers(github, 7)[0].resolved)

    def test_a_merged_blocker_is_resolved(self):  # BLK-004
        github = api({7: [{"number": 42}]}, issues=[issue(7), issue(42, merged=True)])
        self.assertTrue(read_blockers(github, 7)[0].resolved)

    def test_an_open_blocker_is_not(self):  # BLK-005
        self.assertFalse(read_blockers(api({7: [{"number": 42}]}), 7)[0].resolved)

    def test_an_unknown_blocker_is_never_resolved(self):  # BLK-043
        """Not knowing whether the thing you depend on is finished is not the
        same as it being finished."""
        self.assertFalse(Blocker(42, state="closed", unknown=True).resolved)


class TestItCannotWrite(unittest.TestCase):
    """BLK-030 to BLK-035 are the agent's now, and this module has no half of
    them. A dashboard able to write is a dashboard that eventually does."""

    def test_the_module_exposes_no_write(self):  # BLK-030
        import blocker_state

        for name in ("block", "unblock", "add_blocked_by", "remove_blocked_by"):
            with self.subTest(operation=name):
                self.assertFalse(hasattr(blocker_state, name))


if __name__ == "__main__":
    unittest.main()
