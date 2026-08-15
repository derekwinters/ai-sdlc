#!/usr/bin/env python3
"""An in-memory GitHub, for tests.

Built from a plain dictionary of repository state. Writes mutate that state, so
a test asserts on the resulting world rather than on which calls were made —
which keeps the tests about behaviour instead of about implementation.

It also records every call in order, so a test can assert that something was
*not* done: "a refusal changes nothing" is a claim about absence, and absence
needs a record to check against.

Performs no I/O and imports nothing that could.

Specification: docs/spec/github-api.md (`API`), §5.
"""

from __future__ import annotations

import itertools

from lib.github import PAGE_SIZE, GitHubError


class FakeFailure:
    """Marks an operation to fail, so degradation paths are testable."""

    def __init__(self, detail="the request failed", status=500):
        self.detail = detail
        self.status = status


class FakeGitHub:
    """The same surface as :class:`lib.github.GitHub`, backed by a dictionary.

    ``issues`` is a list of issue dictionaries; ``comments`` maps an issue
    number to its comments; ``blocked_by`` maps an issue number to the issues
    blocking it. ``actor`` is the login that authors reactions and comments,
    which is what lets a test distinguish the bot's watermark from a human's
    identical reaction.
    """

    def __init__(
        self,
        issues=None,
        comments=None,
        milestones=None,
        blocked_by=None,
        reactions=None,
        actor="github-actions[bot]",
        fail=None,
        repository="owner/repo",
    ):
        self.repository = repository
        self.base_url = "https://api.github.com"
        self.actor = actor
        self.truncated = False

        self._issues = {issue["number"]: dict(issue) for issue in (issues or [])}
        self._comments = {n: [dict(c) for c in cs] for n, cs in (comments or {}).items()}
        self._milestones = [dict(m) for m in (milestones or [])]
        self._blocked_by = {n: list(bs) for n, bs in (blocked_by or {}).items()}
        self._reactions = {c: list(rs) for c, rs in (reactions or {}).items()}
        self._fail = dict(fail or {})
        self._ids = itertools.count(1000)

        #: Every operation, in order, as (name, args).
        self.calls = []

    def __repr__(self):
        return f"<FakeGitHub {self.repository} issues={len(self._issues)}>"

    # ---------------------------------------------------------------- requests

    def request(self, method, path, payload=None):
        """Present so the fake satisfies the client's interface. Never used."""
        raise AssertionError(
            "A test reached FakeGitHub.request; use a named operation instead."
        )

    def paginate(self, path, **params):
        raise AssertionError(
            "A test reached FakeGitHub.paginate; use a named operation instead."
        )

    # -------------------------------------------------------------- operations

    def issue(self, number):
        self._record("issue", number)
        if number not in self._issues:
            raise GitHubError("Not found.", status=404, method="GET", path=f"/issues/{number}")
        return dict(self._issues[number])

    def issues(self, **filters):
        self._record("issues", filters)
        found = [dict(i) for i in self._issues.values()]
        if "state" in filters:
            found = [i for i in found if i.get("state", "open") == filters["state"]]
        return self._page(found)

    def comments(self, issue):
        self._record("comments", issue)
        return self._page([dict(c) for c in self._comments.get(issue, [])])

    def milestones(self, state="all"):
        self._record("milestones", state)
        found = self._milestones
        if state != "all":
            found = [m for m in found if m.get("state", "open") == state]
        return self._page([dict(m) for m in found])

    def create_milestone(self, title, description=None, due_on=None):
        self._record("create_milestone", title)
        number = max((m["number"] for m in self._milestones), default=0) + 1
        created = {
            "number": number,
            "title": title,
            "state": "open",
            "description": description or "",
            "due_on": due_on,
            "open_issues": 0,
            "closed_issues": 0,
        }
        self._milestones.append(created)
        return dict(created)

    def update_milestone(self, number, **fields):
        self._record("update_milestone", number, fields)
        for milestone in self._milestones:
            if milestone["number"] == number:
                milestone.update(fields)
                return dict(milestone)
        raise GitHubError("Not found.", status=404, method="PATCH",
                          path=f"/milestones/{number}")

    def blocked_by(self, issue):
        self._record("blocked_by", issue)
        return self._page([dict(b) for b in self._blocked_by.get(issue, [])])

    def reactions(self, comment):
        self._record("reactions", comment)
        return self._page([dict(r) for r in self._reactions.get(comment, [])])

    def set_labels(self, issue, labels):
        self._record("set_labels", issue, list(labels))
        self._require(issue)
        self._issues[issue]["labels"] = [{"name": name} for name in labels]
        return list(self._issues[issue]["labels"])

    def set_milestone(self, issue, number):
        self._record("set_milestone", issue, number)
        self._require(issue)
        self._issues[issue]["milestone"] = None if number is None else {"number": number}
        return dict(self._issues[issue])

    def comment(self, issue, body):
        self._record("comment", issue, body)
        self._require(issue)
        posted = {"id": next(self._ids), "body": body, "user": {"login": self.actor}}
        self._comments.setdefault(issue, []).append(posted)
        return dict(posted)

    def react(self, comment, content):
        self._record("react", comment, content)
        reaction = {
            "id": next(self._ids),
            "content": content,
            "user": {"login": self.actor},
        }
        self._reactions.setdefault(comment, []).append(reaction)
        return dict(reaction)

    def unreact(self, comment, reaction):
        self._record("unreact", comment, reaction)
        self._reactions[comment] = [
            r for r in self._reactions.get(comment, []) if r["id"] != reaction
        ]
        return None

    # ----------------------------------------------------------------- private

    def _record(self, name, *args):
        self.calls.append((name, args))
        failure = self._fail.get(name)
        if failure is not None:
            raise GitHubError(
                "The request failed.", status=failure.status, method=name, detail=failure.detail
            )

    def _require(self, number):
        if number not in self._issues:
            raise GitHubError("Not found.", status=404, method="PATCH", path=f"/issues/{number}")

    def _page(self, items):
        """Collections come back whole, as the real client's paginate does.

        The page size still matters: a fixture longer than one page exercises
        the same code path a caller would hit in production.
        """
        self.truncated = False
        if len(items) > PAGE_SIZE * self.max_pages_equivalent:
            self.truncated = True
        return items

    #: Mirrors the real client's cap, so a fixture cannot silently exceed what
    #: production would return.
    max_pages_equivalent = 100
