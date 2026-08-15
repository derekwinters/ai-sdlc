#!/usr/bin/env python3
"""The only module in ai-sdlc that performs network I/O.

Everything else receives a client and never constructs its own. That is what
makes the rest of the system testable with no network, no credentials, and no
live repository: a seam one module wide can be faked completely, where a dozen
scattered `urlopen` calls cannot.

The operation vocabulary is deliberately small — labels, milestones, comments,
reactions, and reads. There is no operation that closes, reopens, or deletes an
issue, and none that edits an issue body. A command set able to do irreversible
things eventually does one by accident.

Specification: docs/spec/github-api.md (`API`).
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request

API_VERSION = "2022-11-28"
PAGE_SIZE = 100
MAX_PAGES = 100

#: Error bodies are truncated to this many characters. A large HTML error page
#: is not more informative than its first few hundred characters, and it will
#: happily fill a log.
MAX_DETAIL = 500


class GitHubError(RuntimeError):
    """A request that did not succeed.

    Carries the status, method and path so a caller can decide whether to
    degrade or fail, and a bounded excerpt of the body for a human reading the
    log. A transport failure has a status of ``None``.
    """

    def __init__(self, message, status=None, method=None, path=None, detail=""):
        super().__init__(message)
        self.message = message
        self.status = status
        self.method = method
        self.path = path
        self.detail = detail[:MAX_DETAIL]

    def __str__(self):
        parts = [self.message]
        if self.method and self.path:
            parts.append(f"({self.method} {self.path})")
        if self.detail:
            parts.append(f"— {self.detail}")
        return " ".join(parts)


def _urllib_transport(method, url, headers, body):
    """The real transport. Injected so tests never reach it."""
    data = body.encode() if body is not None else None
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(request) as response:  # noqa: S310 - fixed https base
        return _Response(
            response.status,
            response.read().decode("utf-8", "replace"),
            dict(response.headers),
        )


def post_json(url, headers, body):
    """POST a JSON body to an arbitrary URL, returning (status, text).

    Here rather than in a caller because this module is the only one permitted
    to open a socket. The gatekeeper's routine fire is not a GitHub call, but
    it is still network I/O, and the seam is about where I/O happens rather
    than about who it talks to.
    """
    request = urllib.request.Request(
        url, data=body.encode(), headers=headers, method="POST"
    )
    try:
        with urllib.request.urlopen(request) as response:  # noqa: S310
            return response.status, response.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as error:
        return error.code, error.read().decode("utf-8", "replace")


class _Response:
    __slots__ = ("status", "body", "headers")

    def __init__(self, status, body, headers):
        self.status = status
        self.body = body
        self.headers = headers


class GitHub:
    """A small, typed GitHub client.

    ``transport`` is a callable ``(method, url, headers, body) -> response``
    with ``.status``, ``.body`` and ``.headers``. Tests substitute one; nothing
    in the constructor performs I/O.
    """

    def __init__(
        self,
        token,
        repository,
        transport=None,
        base_url="https://api.github.com",
        max_pages=MAX_PAGES,
    ):
        self._token = token
        self.repository = repository
        self.base_url = base_url.rstrip("/")
        self.max_pages = max_pages
        self._transport = transport or _urllib_transport
        #: Set when a paginated read stopped at the page cap rather than at the
        #: end of the collection. A caller reporting a list must say so.
        self.truncated = False

    def __repr__(self):
        # Never the token: a repr reaches logs and exception chains.
        return f"<GitHub {self.repository} at {self.base_url}>"

    # ---------------------------------------------------------------- requests

    def request(self, method, path, payload=None):
        url = self._url(path)
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": API_VERSION,
            "Authorization": f"Bearer {self._token}",
            "User-Agent": "ai-sdlc",
        }
        body = None
        if payload is not None:
            body = json.dumps(payload)
            headers["Content-Type"] = "application/json"

        try:
            response = self._transport(method, url, headers, body)
        except urllib.error.HTTPError as error:  # pragma: no cover - real transport only
            response = _Response(
                error.code, error.read().decode("utf-8", "replace"), dict(error.headers or {})
            )
        except Exception as error:
            raise GitHubError(
                "The request could not be sent.",
                status=None,
                method=method,
                path=path,
                detail=str(error),
            ) from error

        if not 200 <= response.status < 300:
            raise self._failure(response, method, path)

        return self._decode(response, method, path)

    def paginate(self, path, **params):
        """Read a collection, following pages until one arrives short."""
        collected = []
        self.truncated = False

        for page_number in range(1, self.max_pages + 1):
            query = dict(params, per_page=PAGE_SIZE, page=page_number)
            items = self.request("GET", f"{path}?{urllib.parse.urlencode(query)}")
            if not items:
                return collected
            collected.extend(items)
            if len(items) < PAGE_SIZE:
                return collected

        # Fell out of the loop: every page was full, so there is probably more.
        self.truncated = True
        return collected

    # -------------------------------------------------------------- operations

    def issue(self, number):
        return self.request("GET", f"/issues/{number}")

    def issues(self, **filters):
        return self.paginate("/issues", **filters)

    def comments(self, issue):
        return self.paginate(f"/issues/{issue}/comments", direction="asc")

    def milestones(self, state="all"):
        return self.paginate("/milestones", state=state)

    def labels(self):
        return self.paginate("/labels")

    def create_label(self, name, color, description):
        return self.request(
            "POST", "/labels",
            {"name": name, "color": color, "description": description},
        )

    def update_label(self, name, color, description):
        import urllib.parse

        quoted = urllib.parse.quote(name, safe="")
        return self.request(
            "PATCH", f"/labels/{quoted}",
            {"color": color, "description": description},
        )

    def delete_label(self, name):
        """The one deletion in the vocabulary, and it is a label rather than an
        issue. Guarded by the manifest's explicit `delete:` list — see `LBL`."""
        import urllib.parse

        return self.request("DELETE", f"/labels/{urllib.parse.quote(name, safe='')}")

    def create_milestone(self, title, description=None, due_on=None):
        payload = {"title": title}
        if description is not None:
            payload["description"] = description
        if due_on is not None:
            payload["due_on"] = due_on
        return self.request("POST", "/milestones", payload)

    def update_milestone(self, number, **fields):
        """Change only the fields given. A milestone's state is one of them:
        unlike an issue, closing a milestone is reversible and loses nothing."""
        return self.request("PATCH", f"/milestones/{number}", dict(fields))

    def blocked_by(self, issue):
        return self.paginate(f"/issues/{issue}/dependencies/blocked_by")

    def add_blocked_by(self, issue, blocker):
        return self.request(
            "POST", f"/issues/{issue}/dependencies/blocked_by", {"issue_id": blocker}
        )

    def remove_blocked_by(self, issue, blocker):
        return self.request(
            "DELETE", f"/issues/{issue}/dependencies/blocked_by/{blocker}"
        )

    def reactions(self, comment):
        return self.paginate(f"/issues/comments/{comment}/reactions")

    def set_labels(self, issue, labels):
        return self.request("PUT", f"/issues/{issue}/labels", {"labels": list(labels)})

    def set_milestone(self, issue, number):
        return self.request("PATCH", f"/issues/{issue}", {"milestone": number})

    def comment(self, issue, body):
        return self.request("POST", f"/issues/{issue}/comments", {"body": body})

    def react(self, comment, content):
        return self.request(
            "POST", f"/issues/comments/{comment}/reactions", {"content": content}
        )

    def unreact(self, comment, reaction):
        return self.request(
            "DELETE", f"/issues/comments/{comment}/reactions/{reaction}"
        )

    # ----------------------------------------------------------------- private

    def _url(self, path):
        if path.startswith("http://") or path.startswith("https://"):
            return path
        return f"{self.base_url}/repos/{self.repository}{path}"

    def _failure(self, response, method, path):
        status = response.status
        if status == 401:
            message = "The credential was rejected — check the token, not the request."
        elif status == 403 and response.headers.get("X-RateLimit-Remaining") == "0":
            message = "Refused: the API rate limit is exhausted."
        elif status == 403:
            message = "Refused: the credential lacks permission for this resource."
        elif status == 404:
            message = "Not found."
        else:
            message = f"The request failed with status {status}."
        return GitHubError(
            message, status=status, method=method, path=path, detail=response.body
        )

    def _decode(self, response, method, path):
        if not response.body.strip():
            return None
        try:
            return json.loads(response.body)
        except ValueError as error:
            raise GitHubError(
                "The response was not JSON.",
                status=response.status,
                method=method,
                path=path,
                detail=response.body,
            ) from error
