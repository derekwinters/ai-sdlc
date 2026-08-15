"""API-001 to API-007 — how a request is formed."""

import json
import unittest

from _support import RecordingTransport, Response
from lib.github import API_VERSION, GitHub


def client(transport=None, **kwargs):
    return GitHub(
        token="s3cret",
        repository="derekwinters/ai-sdlc",
        transport=transport or RecordingTransport(Response(200, "{}")),
        **kwargs,
    )


class TestConstruction(unittest.TestCase):
    def test_it_takes_a_token_and_a_repository(self):  # API-001
        self.assertEqual(client().repository, "derekwinters/ai-sdlc")

    def test_the_default_base_url_is_the_public_api(self):  # API-002
        self.assertEqual(client().base_url, "https://api.github.com")

    def test_the_base_url_is_injectable(self):  # API-002
        self.assertEqual(
            client(base_url="https://ghe.example.com/api/v3").base_url,
            "https://ghe.example.com/api/v3",
        )


class TestHeaders(unittest.TestCase):
    def setUp(self):
        self.transport = RecordingTransport(Response(200, "{}"))
        client(self.transport).request("GET", "/issues/1")
        self.headers = self.transport.requests[0]["headers"]

    def test_it_accepts_the_github_json_media_type(self):  # API-003
        self.assertEqual(self.headers["Accept"], "application/vnd.github+json")

    def test_it_pins_the_api_version(self):  # API-004
        self.assertEqual(self.headers["X-GitHub-Api-Version"], API_VERSION)

    def test_the_api_version_is_a_named_constant(self):  # API-004
        self.assertRegex(API_VERSION, r"^\d{4}-\d{2}-\d{2}$")

    def test_it_authenticates_as_a_bearer_credential(self):  # API-005
        self.assertEqual(self.headers["Authorization"], "Bearer s3cret")


class TestPathResolution(unittest.TestCase):
    def url_for(self, path):
        transport = RecordingTransport(Response(200, "{}"))
        client(transport).request("GET", path)
        return transport.requests[0]["url"]

    def test_a_relative_path_resolves_against_the_repository(self):  # API-006
        self.assertEqual(
            self.url_for("/issues/1"),
            "https://api.github.com/repos/derekwinters/ai-sdlc/issues/1",
        )

    def test_an_absolute_path_is_used_unchanged(self):  # API-006
        self.assertEqual(
            self.url_for("https://api.github.com/rate_limit"),
            "https://api.github.com/rate_limit",
        )


class TestTheTokenIsNeverExposed(unittest.TestCase):
    def test_the_repr_does_not_contain_the_token(self):  # API-007
        self.assertNotIn("s3cret", repr(client()))

    def test_an_error_does_not_contain_the_token(self):  # API-007
        transport = RecordingTransport(Response(404, "not found"))
        from lib.github import GitHubError

        with self.assertRaises(GitHubError) as caught:
            client(transport).request("GET", "/issues/1")
        self.assertNotIn("s3cret", str(caught.exception))


class TestBodies(unittest.TestCase):
    def test_a_payload_is_sent_as_json(self):
        transport = RecordingTransport(Response(200, "{}"))
        client(transport).request("POST", "/issues/1/comments", {"body": "hi"})
        self.assertEqual(json.loads(transport.requests[0]["body"]), {"body": "hi"})

    def test_a_get_sends_no_body(self):
        transport = RecordingTransport(Response(200, "{}"))
        client(transport).request("GET", "/issues/1")
        self.assertIsNone(transport.requests[0]["body"])


if __name__ == "__main__":
    unittest.main()
