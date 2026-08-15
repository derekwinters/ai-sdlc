"""API-042, API-043 — milestone create and edit on the client."""

import json
import unittest

from _support import RecordingTransport, Response
from lib.github import GitHub


def client(body="{}"):
    transport = RecordingTransport(Response(200, body))
    return GitHub("t", "o/r", transport=transport), transport


class TestCreate(unittest.TestCase):
    def test_it_posts_the_title(self):  # API-042
        api, transport = client()
        api.create_milestone("v0.4")
        self.assertEqual(transport.requests[0]["method"], "POST")
        self.assertEqual(json.loads(transport.requests[0]["body"]), {"title": "v0.4"})

    def test_a_description_is_included(self):  # API-042
        api, transport = client()
        api.create_milestone("v0.4", description="next")
        self.assertEqual(json.loads(transport.requests[0]["body"])["description"], "next")

    def test_an_omitted_field_is_not_sent(self):  # API-042
        api, transport = client()
        api.create_milestone("v0.4")
        self.assertNotIn("due_on", json.loads(transport.requests[0]["body"]))

    def test_it_returns_the_created_milestone(self):  # API-042
        api, _ = client('{"number": 7, "title": "v0.4"}')
        self.assertEqual(api.create_milestone("v0.4")["number"], 7)


class TestUpdate(unittest.TestCase):
    def test_it_patches_only_what_it_is_given(self):  # API-043
        api, transport = client()
        api.update_milestone(2, state="closed")
        self.assertEqual(transport.requests[0]["method"], "PATCH")
        self.assertEqual(json.loads(transport.requests[0]["body"]), {"state": "closed"})

    def test_several_fields_at_once(self):  # API-043
        api, transport = client()
        api.update_milestone(2, title="x", description="y")
        self.assertEqual(json.loads(transport.requests[0]["body"]),
                         {"title": "x", "description": "y"})

    def test_it_targets_the_milestone_by_number(self):  # API-043
        api, transport = client()
        api.update_milestone(2, state="open")
        self.assertTrue(transport.requests[0]["url"].endswith("/milestones/2"))


if __name__ == "__main__":
    unittest.main()


class TestLabelOperations(unittest.TestCase):
    """API-044 to API-046 — the label vocabulary on the client."""

    def test_labels_are_paginated(self):  # API-044
        api, _ = client("[]")
        self.assertEqual(api.labels(), [])

    def test_create_posts_all_three_fields(self):  # API-045
        api, transport = client()
        api.create_label("x", "ABCDEF", "words")
        self.assertEqual(
            json.loads(transport.requests[0]["body"]),
            {"name": "x", "color": "ABCDEF", "description": "words"},
        )

    def test_update_patches_colour_and_description(self):  # API-045
        api, transport = client()
        api.update_label("x", "ABCDEF", "words")
        self.assertEqual(transport.requests[0]["method"], "PATCH")

    def test_a_label_name_is_url_encoded(self):  # API-045
        api, transport = client()
        api.update_label("area:build", "ABCDEF", "words")
        self.assertIn("area%3Abuild", transport.requests[0]["url"])

    def test_delete_issues_a_delete(self):  # API-046
        api, transport = client("")
        api.delete_label("x")
        self.assertEqual(transport.requests[0]["method"], "DELETE")
