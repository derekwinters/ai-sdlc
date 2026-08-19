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


#: A database id for an issue number, deliberately nothing like it.
#:
#: The real API's `issue_id` is a repository-wide database key with no relation
#: to the number in the repository. A fake where the two were equal — or where
#: `id` did not exist, as here until #155 — cannot express a client sending one
#: where the other is meant, which is why 29 `auto` requirements passed over
#: exactly that bug.
def _issue_id(number):
    return 5_000_000 + number * 7


def _with_id(issue):
    stored = dict(issue)
    stored.setdefault("id", _issue_id(stored["number"]))
    return stored


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
        labels=None,
        actor="github-actions[bot]",
        fail=None,
        repository="owner/repo",
    ):
        self.repository = repository
        self.base_url = "https://api.github.com"
        self.actor = actor
        self.truncated = False

        self._issues = {issue["number"]: _with_id(issue) for issue in (issues or [])}
        self._comments = {n: [dict(c) for c in cs] for n, cs in (comments or {}).items()}
        self._milestones = [dict(m) for m in (milestones or [])]
        self._blocked_by = {
            n: [self._edge(b) for b in bs] for n, bs in (blocked_by or {}).items()
        }
        self._reactions = {c: list(rs) for c, rs in (reactions or {}).items()}
        self._labels = [dict(label) for label in (labels or [])]
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

    def issue_id(self, number):
        self._record("issue_id", number)
        return self.issue(number)["id"]

    def issues(self, **filters):
        """Mirrors GitHub, including the parts that surprise people.

        Two behaviours are deliberate rather than incidental, because
        production code has been wrong about both:

        - **The default is `state="open"`.** A fake that returned closed
          issues to a caller that never asked for them let `DASH-025` — a
          fault about closed issues — keep a green test while being
          unreachable in production (#106).
        - **Pull requests come back too.** GitHub's issues endpoint returns
          both, each pull request carrying a `pull_request` key. A fake that
          omitted them would hide every miscount they cause.
        """
        self._record("issues", filters)
        found = [dict(i) for i in self._issues.values()]
        wanted = filters.get("state", "open")
        if wanted != "all":
            found = [i for i in found if i.get("state", "open") == wanted]
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

    def labels(self):
        self._record("labels")
        return [dict(label) for label in self._labels]

    def create_label(self, name, color, description):
        self._record("create_label", name)
        self._labels.append({"name": name, "color": color, "description": description})
        return dict(self._labels[-1])

    def update_label(self, name, color, description):
        self._record("update_label", name)
        for label in self._labels:
            if label["name"] == name:
                label.update(color=color, description=description)
                return dict(label)
        raise GitHubError("Not found.", status=404, method="PATCH", path=f"/labels/{name}")

    def delete_label(self, name):
        self._record("delete_label", name)
        self._labels = [label for label in self._labels if label["name"] != name]
        return None

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

    def add_blocked_by(self, issue, blocker_id):
        """``blocker_id`` is a database **id**, as the real API requires.

        Modelled faithfully because this is the one place the two identities
        differ and the difference is invisible: both are integers, so a client
        sending the wrong one is accepted and stores an edge to whichever issue
        that value happens to identify (#155).
        """
        self._record("add_blocked_by", issue, blocker_id)
        edge = self._edge_by_id(blocker_id)
        edges = self._blocked_by.setdefault(issue, [])
        if not any(e["id"] == edge["id"] for e in edges):
            edges.append(edge)
        return dict(edge)

    def remove_blocked_by(self, issue, blocker_id):
        self._record("remove_blocked_by", issue, blocker_id)
        self._blocked_by[issue] = [
            e for e in self._blocked_by.get(issue, []) if e["id"] != blocker_id
        ]
        return None

    def _edge(self, blocker):
        """An edge for a graph a *test* wrote, named however reads best.

        Lenient on purpose, and only here: a fixture saying "#7 is blocked by
        #42" should not have to be written in database ids. The operations are
        strict, which is where the distinction has to hold.
        """
        if isinstance(blocker, dict):
            blocker = blocker.get("id") or blocker["number"]

        for number, issue in self._issues.items():
            if blocker in (issue["id"], number):
                return {"number": number, "id": issue["id"]}

        # An issue the fake was not given. A read of it will 404, which is the
        # "unknown blocker" case BLK relies on.
        return {"number": blocker, "id": _issue_id(blocker)}

    def _edge_by_id(self, blocker_id):
        """An edge for a *write*, matched on database id and nothing else.

        Strict, because being forgiving here would defeat the entire point of
        the fake carrying two identities: a client sending a number would be
        quietly understood, which is precisely the bug that reached production
        (#155). The real API is not forgiving either — it resolved the number it
        was sent as an id, found a different issue, and linked that one.
        """
        for number, issue in self._issues.items():
            if issue["id"] == blocker_id:
                return {"number": number, "id": blocker_id}

        # No issue here has that id. The real API links whatever does have it,
        # somewhere in the repository; the fake cannot know what, so it records
        # the edge with no resolvable number and a read of it reports unknown.
        return {"number": None, "id": blocker_id}

    def reactions(self, comment):
        self._record("reactions", comment)
        return self._page([dict(r) for r in self._reactions.get(comment, [])])

    def set_labels(self, issue, labels):
        self._record("set_labels", issue, list(labels))
        self._require(issue)
        self._issues[issue]["labels"] = [{"name": name} for name in labels]
        return list(self._issues[issue]["labels"])

    def set_body(self, issue, body):
        self._record("set_body", issue, body)
        if issue in self._issues:
            self._issues[issue] = dict(self._issues[issue], body=body)
        return dict(self._issues.get(issue) or {"number": issue, "body": body})

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
