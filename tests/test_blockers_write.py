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


class TestTheIdentityThatCrossesTheApi(unittest.TestCase):
    """BLK-036 — a blocker is named to GitHub by its database id.

    `block(154, 153)` in the real repository did not block #154 by #153. It
    blocked it by **#4**, an unrelated issue, and reported success: the client
    sent the issue *number* as `issue_id`, GitHub read it as a database id, and
    both are integers so nothing refused it.

    Nothing caught it because the fake stored edges as `{"number": blocker}` —
    the distinction the real API turns on did not exist in it, so no test
    written against it could express the bug however many were written.
    """

    def test_the_edge_names_the_issue_that_was_asked_for(self):  # BLK-036
        ops, github = blockers()
        ops.block(7, 42)
        self.assertEqual([b.number for b in ops.blockers_of(7)], [42])

    def test_the_value_sent_is_the_blockers_database_id(self):  # BLK-036
        ops, github = blockers()
        ops.block(7, 42)
        sent = [args for name, args in github.calls if name == "add_blocked_by"]
        self.assertEqual(sent, [(7, github.issue(42)["id"])])

    def test_the_id_is_not_the_number(self):  # BLK-036
        """Guards the test above from passing vacuously."""
        _, github = blockers()
        self.assertNotEqual(github.issue(42)["id"], 42)

    def test_unblock_names_the_id_too(self):  # BLK-036
        """Covered on its own: `unblock` was never symmetric with `block`, and
        it only appeared to work because the edge it deleted held the wrong
        value that had been written in the first place."""
        ops, github = blockers()
        ops.block(7, 42)
        ops.unblock(7, 42)
        sent = [args for name, args in github.calls if name == "remove_blocked_by"]
        self.assertEqual(sent, [(7, github.issue(42)["id"])])

    def test_unblocking_actually_removes_it(self):  # BLK-036
        ops, _ = blockers()
        ops.block(7, 42)
        ops.unblock(7, 42)
        self.assertEqual(ops.blockers_of(7), [])

    def test_a_cycle_is_still_refused_across_the_two_identities(self):  # BLK-036
        """The cycle check compares numbers; the edges carry ids. If those two
        spaces disagree the check walks a graph that is not the stored one."""
        ops, _ = blockers()
        ops.block(7, 42)
        self.assertIn("cycle", refused(ops.block, 42, 7))


if __name__ == "__main__":
    unittest.main()
