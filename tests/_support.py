"""Shared test helpers. Imports nothing that can reach the network."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class Response:
    """One canned HTTP response for the transport double."""

    def __init__(self, status=200, body="", headers=None):
        self.status = status
        self.body = body
        self.headers = headers or {}


class RecordingTransport:
    """Stands in for the network. Records requests, returns canned responses.

    A list of responses is consumed in order; a single response repeats.
    """

    def __init__(self, responses=None, error=None):
        if isinstance(responses, Response):
            self._responses, self._repeat = [responses], True
        else:
            self._responses, self._repeat = list(responses or []), False
        self.error = error
        self.requests = []

    def __call__(self, method, url, headers, body):
        self.requests.append(
            {"method": method, "url": url, "headers": headers, "body": body}
        )
        if self.error is not None:
            raise self.error
        if not self._responses:
            return Response(200, "[]")
        if self._repeat:
            return self._responses[0]
        return self._responses.pop(0)


def page(count, start=1):
    """A JSON array of `count` numbered items, for pagination tests."""
    import json

    return json.dumps([{"number": n} for n in range(start, start + count)])
