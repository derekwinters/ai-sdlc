#!/usr/bin/env python3
"""Find commands on this issue whose run died mid-flight.

This replaces a comment-replay sweep that ran on a schedule across the whole
repository. Replay had to guess a time window, re-read every recent comment,
and could act on something the owner had since changed their mind about — the
last of which is the reason it is gone.

Catch-up is different in one decisive way: it is scoped to the single issue
whose event just fired. It cannot race another issue's handler, it needs no
window, and it triggers only when the owner is already interacting with that
issue. The cost is that a missed webhook is not self-healing — but the
dashboard reports a lingering 👀, and `/retry` fixes it deliberately. Visible
beats silent.

It needs no timestamps because the watermark already records the fact: a bare
👀 by the bot means the run started and did not finish. Anything else — no
reaction, or a resolved one — is not this function's business.

Reads only. Returns the comments a caller should re-process.

Specification: docs/spec/gatekeeper.md (`GK`), §6.
"""

from __future__ import annotations

from authority import is_bot_login
from lib.github import GitHubError
from parse_commands import parse


def unfinished_comments(api, issue, watermark, owners):
    """Owner comments on `issue` that carry a bare `seen` and no resolution.

    Ascending, so a later command lands after an earlier one — the same order
    they would have been applied in live.
    """
    try:
        comments = api.comments(issue)
    except GitHubError:
        # A failed read is not evidence that there is nothing to do, but it is
        # also not something to guess about. The triggering comment still gets
        # handled; the dashboard still reports the lingering mark.
        return []

    unfinished = []
    for comment in comments:
        if not _is_owner_command(comment, owners):
            continue
        if watermark.is_unfinished(comment["id"]):
            unfinished.append(comment)

    return unfinished


def _is_owner_command(comment, owners):
    login = ((comment.get("user") or {}).get("login")) or ""
    if is_bot_login(login):
        return False
    if login.lower() not in {owner.lower() for owner in owners}:
        return False
    return bool(parse(comment.get("body")).actions or parse(comment.get("body")).skips)
