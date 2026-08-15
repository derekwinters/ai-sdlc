#!/usr/bin/env python3
"""The watermark: what makes a command apply at most once.

Three states, not two:

    👀  seen — the run has started
    👍  acted — the command was applied
    👎  refused — a gate said no

The third state is what earns its keep. With only success marked, a refused
command carries no record that it was ever considered, so a later pass
reconsiders and re-refuses it forever. And with only two states, a bare 👀
would mean both "in flight" and "finished, refused" — ambiguous exactly when
you need to know.

With three, a comment still showing a bare 👀 after its run should have ended
means one thing: the run died mid-flight. That is a fact stored on GitHub
rather than inferred from timestamps, and it is what lets catch-up (#10) find
unfinished work without a time window.

An unreadable reaction lookup counts as finished. Ambiguity must never cause a
second application; the cost of skipping a comment is a `/retry`, and the cost
of applying one twice is a state change nobody asked for.

Specification: docs/spec/gatekeeper.md (`GK`), §5.
"""

from __future__ import annotations

from lib.github import GitHubError

SEEN = "eyes"
ACTED = "+1"
REFUSED = "-1"

#: The states meaning "this comment has been dealt with".
RESOLVED = (ACTED, REFUSED)


class Watermark:
    """Reads and writes the gatekeeper's marks on a comment."""

    __slots__ = ("api", "bot_login")

    def __init__(self, api, bot_login):
        self.api = api
        self.bot_login = bot_login

    # -------------------------------------------------------------- marking

    def seen(self, comment):
        """Mark before doing anything, so a crash leaves evidence."""
        self.api.react(comment, SEEN)

    def acted(self, comment):
        self._resolve(comment, ACTED)

    def refused(self, comment):
        self._resolve(comment, REFUSED)

    def ignore(self, comment):
        """Deliberately leave no trace.

        A comment from someone without authority gets nothing at all — a
        reaction would let anyone make the bot act on demand.
        """
        return None

    # -------------------------------------------------------------- reading

    def is_finished(self, comment):
        """True when this comment has been resolved, or cannot be read."""
        marks = self._mine(comment)
        if marks is None:
            return True  # unreadable: assume done rather than risk repeating
        return any(mark in RESOLVED for mark in marks)

    def is_unfinished(self, comment):
        """True only when a bare `seen` is present — a run that died."""
        marks = self._mine(comment)
        if marks is None:
            return False
        return SEEN in marks and not any(mark in RESOLVED for mark in marks)

    # -------------------------------------------------------------- private

    def _resolve(self, comment, content):
        for reaction in self._reactions(comment) or []:
            if reaction.get("content") == SEEN and self._is_mine(reaction):
                self.api.unreact(comment, reaction["id"])
        self.api.react(comment, content)

    def _reactions(self, comment):
        try:
            return self.api.reactions(comment)
        except GitHubError:
            return None

    def _mine(self, comment):
        reactions = self._reactions(comment)
        if reactions is None:
            return None
        return [r.get("content") for r in reactions if self._is_mine(r)]

    def _is_mine(self, reaction):
        return ((reaction.get("user") or {}).get("login")) == self.bot_login
