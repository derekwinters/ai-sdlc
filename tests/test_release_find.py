"""REL-001 to REL-004 — identifying the release pull request."""

import unittest

from _release import RELEASE_BRANCH, pull_request
import _release  # noqa: F401
from release_flow import ReleaseError, find_release_pull_request


def find(pulls):
    return find_release_pull_request(pulls)


def refused(pulls):
    try:
        find(pulls)
    except ReleaseError as error:
        return str(error)
    raise AssertionError("expected a ReleaseError")


class TestIdentifying(unittest.TestCase):
    def test_it_is_found_by_branch(self):  # REL-001
        self.assertEqual(find([pull_request()])["number"], 99)

    def test_a_renamed_pull_request_is_still_found(self):  # REL-001
        renamed = pull_request(title="Please merge me")
        self.assertEqual(find([renamed])["number"], 99)

    def test_an_ordinary_pull_request_is_not_it(self):  # REL-001
        self.assertIsNone(find([pull_request(head="claude/issue-7")]))

    def test_a_pull_request_titled_like_a_release_is_not_it(self):  # REL-001
        """A title is not evidence; anyone can write one."""
        impostor = pull_request(head="claude/issue-7", title="chore(main): release 9.9.9")
        self.assertIsNone(find([impostor]))

    def test_it_is_found_among_others(self):  # REL-001
        pulls = [pull_request(head="claude/issue-7", number=1), pull_request(number=99)]
        self.assertEqual(find(pulls)["number"], 99)


class TestNoneOrMany(unittest.TestCase):
    def test_none_open_is_not_an_error(self):  # REL-002
        self.assertIsNone(find([]))

    def test_none_matching_is_not_an_error(self):  # REL-002
        self.assertIsNone(find([pull_request(head="claude/issue-7")]))

    def test_two_release_pull_requests_are_refused(self):  # REL-003
        pulls = [pull_request(number=98), pull_request(number=99)]
        self.assertIn("98", refused(pulls))

    def test_the_refusal_names_both(self):  # REL-003
        pulls = [pull_request(number=98), pull_request(number=99)]
        message = refused(pulls)
        self.assertIn("98", message)
        self.assertIn("99", message)


class TestTheVersion(unittest.TestCase):
    def test_it_is_read_from_the_body(self):  # REL-004
        from release_flow import version_of

        self.assertEqual(version_of(pull_request()), "0.3.0")

    def test_a_renamed_pull_request_still_yields_the_version(self):  # REL-004
        from release_flow import version_of

        self.assertEqual(version_of(pull_request(title="Please merge me")), "0.3.0")

    def test_no_version_anywhere_is_none(self):  # REL-004
        from release_flow import version_of

        bare = {"number": 1, "title": "x", "head": {"ref": "y"}, "body": "nothing"}
        self.assertIsNone(version_of(bare))


if __name__ == "__main__":
    unittest.main()
