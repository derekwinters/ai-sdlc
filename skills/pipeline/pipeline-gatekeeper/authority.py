#!/usr/bin/env python3
"""Who may command the gatekeeper, and who its writes are authored by.

The gatekeeper is the only thing that moves an issue through the pipeline, so
this is the whole security model. There is deliberately no clever part: a list
of logins, compared case-insensitively, and nothing else grants authority.

In particular GitHub's `author_association` is not consulted. It describes
repository permissions, and reading authority from it would silently widen who
can drive the pipeline every time repository access changes — a decision the
pipeline should not inherit from somewhere else.

A refusal is silent. Replying to someone who is not an owner would let anyone
make the bot post on demand, which is both a nuisance and a way to fill an
issue with noise.

Pure: given a comment payload it returns a decision and performs no I/O.

Specification: docs/spec/gatekeeper.md (`GK`), §2.
"""

from __future__ import annotations

BOT_SUFFIX = "[bot]"


def is_bot_login(login):
    """True for GitHub's app logins, which always end in the bot suffix.

    Exact: `robotham` is a person, and `x[bot]y` is not a login GitHub issues.
    """
    return bool(login) and login.endswith(BOT_SUFFIX)


class Decision:
    """Whether a comment may be acted on, and if not, why — for the log only."""

    __slots__ = ("honoured", "reason", "acknowledgement")

    def __init__(self, honoured, reason=None, acknowledgement=None):
        self.honoured = honoured
        self.reason = reason
        self.acknowledgement = acknowledgement

    def __repr__(self):
        return f"<Decision honoured={self.honoured} reason={self.reason!r}>"


class Authority:
    """The owner list and the bot identity, as configured."""

    __slots__ = ("owners", "bot_login")

    def __init__(self, owners, bot_login):
        self.owners = list(owners)
        self.bot_login = bot_login

    @classmethod
    def from_config(cls, config):
        return cls(owners=config.owners, bot_login=config.bot.login)

    @property
    def write_as(self):
        """The identity every write is authored by — never the owner's account."""
        return self.bot_login

    def may_command(self, payload):
        return self.decide(payload).honoured

    def decide(self, payload):
        """Decide whether this comment payload may be acted on."""
        issue = payload.get("issue") or {}
        if issue.get("pull_request"):
            # The gatekeeper acts on issues. A pull request has its own
            # lifecycle, and commands there would move an issue nobody named.
            return Decision(False, reason="pull-request")

        login = ((payload.get("user") or {}).get("login")) or ""

        # Checked before the owner list: the bot must never act on its own
        # acknowledgements even if someone lists it as an owner by mistake.
        if is_bot_login(login):
            return Decision(False, reason="bot")

        if not self.owners:
            # Missing configuration must not fall back to something permissive.
            return Decision(False, reason="no-owners")

        if login.lower() not in {owner.lower() for owner in self.owners}:
            return Decision(False, reason="not-owner")

        return Decision(True)
