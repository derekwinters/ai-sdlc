"""API-030 to API-041 — the operation vocabulary, and what it deliberately omits."""

import json
import unittest

from _support import RecordingTransport, Response, page
from lib.github import GitHub


def client(*bodies):
    transport = RecordingTransport([Response(200, b) for b in bodies] or [Response(200, "{}")])
    return GitHub("s3cret", "derekwinters/ai-sdlc", transport=transport), transport


class TestReads(unittest.TestCase):
    def test_issue_reads_one_issue(self):  # API-030
        api, transport = client('{"number": 7}')
        self.assertEqual(api.issue(7)["number"], 7)
        self.assertTrue(transport.requests[0]["url"].endswith("/issues/7"))

    def test_issues_paginates(self):  # API-031
        api, _ = client(page(3))
        self.assertEqual(len(api.issues(state="open")), 3)

    def test_comments_are_ascending(self):  # API-032
        api, transport = client(page(2))
        api.comments(7)
        self.assertIn("direction=asc", transport.requests[0]["url"])

    def test_milestones_paginate(self):  # API-039
        api, _ = client(page(2))
        self.assertEqual(len(api.milestones()), 2)

    def test_blocked_by_reads_native_dependencies(self):  # API-040
        api, transport = client(page(1))
        api.blocked_by(7)
        self.assertIn("/issues/7/dependencies/blocked_by", transport.requests[0]["url"])


class TestWrites(unittest.TestCase):
    def sent(self, transport):
        return json.loads(transport.requests[0]["body"])

    def test_set_labels_replaces_the_set(self):  # API-033
        api, transport = client("[]")
        api.set_labels(7, ["ready-for-work"])
        self.assertEqual(transport.requests[0]["method"], "PUT")
        self.assertEqual(self.sent(transport), {"labels": ["ready-for-work"]})

    def test_set_milestone_sets_a_number(self):  # API-034
        api, transport = client("{}")
        api.set_milestone(7, 3)
        self.assertEqual(self.sent(transport), {"milestone": 3})

    def test_set_milestone_clears_with_none(self):  # API-034
        api, transport = client("{}")
        api.set_milestone(7, None)
        self.assertEqual(self.sent(transport), {"milestone": None})

    def test_comment_posts_a_body(self):  # API-035
        api, transport = client("{}")
        api.comment(7, "hello")
        self.assertEqual(transport.requests[0]["method"], "POST")
        self.assertEqual(self.sent(transport), {"body": "hello"})

    def test_react_adds_a_reaction(self):  # API-037
        api, transport = client("{}")
        api.react(42, "eyes")
        self.assertEqual(self.sent(transport), {"content": "eyes"})

    def test_unreact_deletes_one(self):  # API-038
        api, transport = client("")
        api.unreact(42, 99)
        self.assertEqual(transport.requests[0]["method"], "DELETE")


class TestReactionsCarryTheirAuthor(unittest.TestCase):
    def test_reactions_include_who_left_them(self):  # API-036
        body = json.dumps([{"id": 1, "content": "eyes", "user": {"login": "a-bot"}}])
        api, _ = client(body)
        self.assertEqual(api.reactions(42)[0]["user"]["login"], "a-bot")


class TestTheVocabularyIsSmall(unittest.TestCase):
    """API-041 — a command set that can do irreversible things eventually does one."""

    FORBIDDEN = ("close_issue", "reopen_issue", "delete_issue", "edit_body", "update_issue")

    def test_no_operation_closes_reopens_deletes_or_edits(self):
        api, _ = client()
        for name in self.FORBIDDEN:
            self.assertFalse(hasattr(api, name), name)

    def test_no_public_method_mentions_those_verbs(self):
        api, _ = client()
        public = [n for n in dir(api) if not n.startswith("_")]
        for name in public:
            self.assertNotIn("delete", name)
            self.assertNotIn("close", name)


if __name__ == "__main__":
    unittest.main()
