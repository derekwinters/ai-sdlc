"""API-050 to API-055 — the double every other suite injects."""

import unittest

import _support  # noqa: F401  (puts the repository root on sys.path)
from lib.fake_github import FakeGitHub, FakeFailure
from lib.github import PAGE_SIZE, GitHubError


def fake(**state):
    return FakeGitHub(**state)


class TestConstruction(unittest.TestCase):
    def test_it_is_built_from_plain_state(self):  # API-050
        api = fake(issues=[{"number": 1, "labels": [{"name": "ai-triage-queued"}]}])
        self.assertEqual(api.issue(1)["number"], 1)

    def test_an_unknown_issue_raises_like_the_real_client(self):  # API-050
        with self.assertRaises(GitHubError):
            fake().issue(99)

    def test_it_offers_the_same_operations_as_the_real_client(self):  # API-050
        from lib.github import GitHub

        real = {n for n in dir(GitHub) if not n.startswith("_")}
        self.assertTrue(real.issubset({n for n in dir(FakeGitHub) if not n.startswith("_")}))


class TestWritesMutateState(unittest.TestCase):
    def test_set_labels_is_visible_on_a_later_read(self):  # API-051
        api = fake(issues=[{"number": 1, "labels": []}])
        api.set_labels(1, ["parked"])
        self.assertEqual([l["name"] for l in api.issue(1)["labels"]], ["parked"])

    def test_a_comment_is_visible_on_a_later_read(self):  # API-051
        api = fake(issues=[{"number": 1}])
        api.comment(1, "hello")
        self.assertEqual(api.comments(1)[-1]["body"], "hello")

    def test_a_reaction_is_visible_on_a_later_read(self):  # API-051
        api = fake(issues=[{"number": 1}], comments={1: [{"id": 5, "body": "/approve"}]})
        api.react(5, "eyes")
        self.assertEqual(api.reactions(5)[0]["content"], "eyes")

    def test_unreact_removes_it(self):  # API-051
        api = fake(issues=[{"number": 1}], comments={1: [{"id": 5, "body": "x"}]})
        api.react(5, "eyes")
        api.unreact(5, api.reactions(5)[0]["id"])
        self.assertEqual(api.reactions(5), [])

    def test_a_reaction_records_its_author(self):
        api = fake(issues=[{"number": 1}], comments={1: [{"id": 5, "body": "x"}]}, actor="a-bot")
        api.react(5, "eyes")
        self.assertEqual(api.reactions(5)[0]["user"]["login"], "a-bot")


class TestItRecordsRequests(unittest.TestCase):
    def test_every_call_is_recorded_in_order(self):  # API-052
        api = fake(issues=[{"number": 1, "labels": []}])
        api.issue(1)
        api.set_labels(1, ["parked"])
        self.assertEqual([c[0] for c in api.calls], ["issue", "set_labels"])

    def test_a_test_can_assert_something_was_never_called(self):  # API-052
        api = fake(issues=[{"number": 1}])
        api.issue(1)
        self.assertNotIn("comment", [c[0] for c in api.calls])


class TestInjectedFailure(unittest.TestCase):
    def test_a_named_operation_can_be_made_to_fail(self):  # API-053
        api = fake(issues=[{"number": 1}], fail={"blocked_by": FakeFailure("upstream is down")})
        with self.assertRaises(GitHubError):
            api.blocked_by(1)

    def test_other_operations_still_work(self):  # API-053
        api = fake(issues=[{"number": 1}], fail={"blocked_by": FakeFailure("down")})
        self.assertEqual(api.issue(1)["number"], 1)


class TestItPaginatesLikeTheRealThing(unittest.TestCase):
    def test_a_long_collection_is_returned_whole(self):  # API-054
        api = fake(issues=[{"number": n} for n in range(1, PAGE_SIZE * 2 + 4)])
        self.assertEqual(len(api.issues()), PAGE_SIZE * 2 + 3)

    def test_order_is_preserved(self):  # API-054
        api = fake(issues=[{"number": n} for n in range(1, PAGE_SIZE + 5)])
        numbers = [i["number"] for i in api.issues()]
        self.assertEqual(numbers, sorted(numbers))


class TestItTouchesNothing(unittest.TestCase):
    def test_the_module_imports_no_network_library(self):  # API-055
        """Checked by import, not by grepping source.

        An earlier version of this test searched the file for the substring
        "requests" and failed on a section comment. A test a prose change can
        break is testing the wrong thing.
        """
        import ast

        from _support import ROOT

        tree = ast.parse((ROOT / "lib" / "fake_github.py").read_text())
        roots = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                roots.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                roots.add(node.module.split(".")[0])

        self.assertEqual(roots & {"urllib", "http", "socket", "requests", "ssl"}, set())


if __name__ == "__main__":
    unittest.main()


class TestItModelsIdentityChangingAtTheBoundary(unittest.TestCase):
    """API-056 — a double where two identities are equal hides the bug (#155)."""

    def github(self):
        return FakeGitHub(issues=[{"number": 42, "state": "open"}])

    def test_an_issue_has_an_id_that_is_not_its_number(self):  # API-056
        self.assertNotEqual(self.github().issue(42)["id"], 42)

    def test_an_edge_carries_both_identities(self):  # API-056
        github = self.github()
        github.add_blocked_by(7, github.issue_id(42))
        edge = github.blocked_by(7)[0]
        self.assertEqual((edge["number"], edge["id"]), (42, github.issue(42)["id"]))

    def test_writing_a_number_where_an_id_belongs_does_not_name_that_issue(self):  # API-056
        """The defect, reproduced: the wrong identity is accepted and stores
        an edge to something else, exactly as the real API did."""
        github = self.github()
        github.add_blocked_by(7, 42)
        self.assertNotEqual(github.blocked_by(7)[0]["id"], github.issue(42)["id"])


if __name__ == "__main__":
    unittest.main()
