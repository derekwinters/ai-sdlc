"""BLK-030 to BLK-035 — creating and removing native relationships."""

import unittest

import _blockers  # noqa: F401
from issue_blockers import Blockers, BlockerError
from lib.fake_github import FakeGitHub


def issue(number, state="open"):
    return {"number": number, "state": state, "milestone": {"title": "v0.1"}}


def blockers(graph=None):
    github = FakeGitHub(
        issues=[issue(n) for n in (7, 8, 42, 43)],
        blocked_by=graph or {},
        actor="sdlc-bot[bot]",
    )
    return Blockers(github), github


def refused(call, *args):
    try:
        call(*args)
    except BlockerError as error:
        return str(error)
    raise AssertionError("expected a BlockerError")


class TestBlocking(unittest.TestCase):
    def test_a_relationship_is_created(self):  # BLK-030
        ops, _ = blockers()
        ops.block(7, 42)
        self.assertEqual([b.number for b in ops.blockers_of(7)], [42])

    def test_a_second_blocker_is_added(self):  # BLK-030
        ops, _ = blockers()
        ops.block(7, 42)
        ops.block(7, 43)
        self.assertEqual(sorted(b.number for b in ops.blockers_of(7)), [42, 43])

    def test_creating_an_existing_one_is_a_no_op(self):  # BLK-031
        ops, _ = blockers()
        ops.block(7, 42)
        ops.block(7, 42)
        self.assertEqual([b.number for b in ops.blockers_of(7)], [42])

    def test_a_duplicate_makes_no_write_request(self):  # BLK-031
        ops, github = blockers({7: [{"number": 42}]})
        before = len([c for c in github.calls if c[0] == "add_blocked_by"])
        ops.block(7, 42)
        after = len([c for c in github.calls if c[0] == "add_blocked_by"])
        self.assertEqual(before, after)


class TestUnblocking(unittest.TestCase):
    def test_a_relationship_is_removed(self):  # BLK-032
        ops, _ = blockers({7: [{"number": 42}]})
        ops.unblock(7, 42)
        self.assertEqual(ops.blockers_of(7), [])

    def test_removing_an_absent_one_is_a_no_op(self):  # BLK-033
        ops, _ = blockers()
        ops.unblock(7, 42)
        self.assertEqual(ops.blockers_of(7), [])

    def test_it_removes_only_the_named_one(self):  # BLK-032
        ops, _ = blockers({7: [{"number": 42}, {"number": 43}]})
        ops.unblock(7, 42)
        self.assertEqual([b.number for b in ops.blockers_of(7)], [43])


class TestRefusals(unittest.TestCase):
    def test_an_issue_may_not_block_itself(self):  # BLK-034
        ops, _ = blockers()
        self.assertIn("itself", refused(ops.block, 7, 7).lower())

    def test_a_direct_cycle_is_refused(self):  # BLK-035
        ops, _ = blockers({42: [{"number": 7}]})
        self.assertIn("cycle", refused(ops.block, 7, 42).lower())

    def test_the_cycle_refusal_names_the_path(self):  # BLK-035
        ops, _ = blockers({42: [{"number": 7}]})
        message = refused(ops.block, 7, 42)
        self.assertIn("#7", message)
        self.assertIn("#42", message)

    def test_an_indirect_cycle_is_refused(self):  # BLK-035
        ops, _ = blockers({42: [{"number": 43}], 43: [{"number": 7}]})
        self.assertIn("cycle", refused(ops.block, 7, 42).lower())

    def test_a_refused_cycle_writes_nothing(self):  # BLK-035
        ops, github = blockers({42: [{"number": 7}]})
        try:
            ops.block(7, 42)
        except BlockerError:
            pass
        self.assertNotIn("add_blocked_by", [name for name, _ in github.calls])

    def test_a_diamond_is_not_a_cycle(self):  # BLK-035
        """Two issues may both depend on the same third one."""
        ops, _ = blockers({7: [{"number": 42}]})
        ops.block(8, 42)
        self.assertEqual([b.number for b in ops.blockers_of(8)], [42])


if __name__ == "__main__":
    unittest.main()
