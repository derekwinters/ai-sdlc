"""API-010 to API-016 — what happens when a request does not succeed."""

import unittest

from _support import RecordingTransport, Response
from lib.github import GitHub, GitHubError


def client(transport):
    return GitHub("s3cret", "derekwinters/ai-sdlc", transport=transport)


def failing(status, body="", headers=None):
    return client(RecordingTransport(Response(status, body, headers)))


class TestTheTypedError(unittest.TestCase):
    def raise_it(self, status, body="", headers=None):
        with self.assertRaises(GitHubError) as caught:
            failing(status, body, headers).request("GET", "/issues/1")
        return caught.exception

    def test_a_non_2xx_raises(self):  # API-010
        self.assertEqual(self.raise_it(500).status, 500)

    def test_the_error_carries_the_method_and_path(self):  # API-010
        error = self.raise_it(500)
        self.assertEqual(error.method, "GET")
        self.assertIn("/issues/1", error.path)

    def test_the_error_carries_a_body_excerpt(self):  # API-010
        self.assertIn("boom", self.raise_it(500, "boom").detail)

    def test_the_excerpt_is_bounded(self):  # API-011
        error = self.raise_it(500, "x" * 10_000)
        self.assertLess(len(error.detail), 1_000)

    def test_a_401_says_the_credential_is_wrong(self):  # API-012
        self.assertIn("credential", str(self.raise_it(401)).lower())

    def test_a_403_with_no_remaining_quota_is_a_rate_limit(self):  # API-013
        error = self.raise_it(403, headers={"X-RateLimit-Remaining": "0"})
        self.assertIn("rate limit", str(error).lower())

    def test_a_403_with_quota_left_is_a_permission_failure(self):  # API-013
        error = self.raise_it(403, headers={"X-RateLimit-Remaining": "4999"})
        self.assertIn("permission", str(error).lower())

    def test_a_2xx_does_not_raise(self):
        self.assertEqual(client(RecordingTransport(Response(200, "{}"))).request("GET", "/x"), {})


class TestTransportFailure(unittest.TestCase):
    def test_a_transport_failure_becomes_the_typed_error(self):  # API-014
        broken = RecordingTransport(error=OSError("no route to host"))
        with self.assertRaises(GitHubError) as caught:
            client(broken).request("GET", "/issues/1")
        self.assertIsNone(caught.exception.status)

    def test_the_underlying_reason_reaches_the_detail(self):  # API-014
        broken = RecordingTransport(error=OSError("no route to host"))
        with self.assertRaises(GitHubError) as caught:
            client(broken).request("GET", "/issues/1")
        self.assertIn("no route to host", caught.exception.detail)


class TestBodies(unittest.TestCase):
    def test_unparseable_json_raises_the_typed_error(self):  # API-015
        with self.assertRaises(GitHubError):
            client(RecordingTransport(Response(200, "<html>nope"))).request("GET", "/x")

    def test_an_empty_body_is_none(self):  # API-016
        self.assertIsNone(client(RecordingTransport(Response(200, ""))).request("GET", "/x"))

    def test_a_204_is_none_and_does_not_raise(self):  # API-016
        self.assertIsNone(client(RecordingTransport(Response(204, ""))).request("DELETE", "/x"))


if __name__ == "__main__":
    unittest.main()
