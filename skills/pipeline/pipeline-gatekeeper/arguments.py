#!/usr/bin/env python3
"""Whether a command's argument means anything.

A command with a bad argument is refused rather than applied with a guess. The
two that carry one — a milestone title and a concurrency cap — both have a way
to be wrong that looks close enough to right that guessing would be plausible
and wrong.

Milestone matching accepts a prefix, because typing `/milestone v0.4` should
not require the full "v0.4 — Something Something". An ambiguous prefix is not a
match: two candidates means picking one would be a guess.

Pure: actions and a milestone list in, resolved actions and refusals out.

Specification: docs/spec/gatekeeper.md (`GK`), §3 (Arguments).
"""

from __future__ import annotations

from parse_commands import Parsed, Skip

MILESTONE_COMMANDS = ("milestone", "focus")


def match_milestone(title, milestones):
    """Resolve a title against the open milestones, or None.

    Exact match wins outright. Otherwise a unique case-insensitive prefix
    match; anything ambiguous or unmatched returns None.
    """
    if not title:
        return None

    open_ones = [m for m in milestones if m.get("state", "open") == "open"]
    wanted = title.strip().lower()

    for milestone in open_ones:
        if milestone["title"].lower() == wanted:
            return milestone

    matches = [m for m in open_ones if m["title"].lower().startswith(wanted)]
    return matches[0] if len(matches) == 1 else None


def open_titles(milestones):
    return [m["title"] for m in milestones if m.get("state", "open") == "open"]


def check_arguments(actions, milestones, skips=None):
    """Resolve arguments, refusing anything that does not mean something."""
    kept, refused = [], list(skips or [])

    for action in actions:
        if action.command == "cap":
            problem = _resolve_cap(action)
        elif action.command in MILESTONE_COMMANDS:
            problem = _resolve_milestone(action, milestones)
        else:
            problem = None

        if problem is None:
            kept.append(action)
        else:
            reason, detail = problem
            skip = Skip(action.command, reason, line=action.line)
            skip.detail = detail
            refused.append(skip)

    return Parsed(kept, refused)


def _resolve_cap(action):
    raw = action.argument.strip()
    try:
        value = int(raw)
    except ValueError:
        return ("cap-not-a-number", f"{raw!r} is not a whole number")

    if value <= 0:
        return ("cap-not-positive", f"a cap of {value} would stop all work")

    action.value = value
    return None


def _resolve_milestone(action, milestones):
    milestone = match_milestone(action.argument, milestones)
    if milestone is None:
        titles = open_titles(milestones)
        listed = "\n".join(f"  - {title}" for title in titles) or "  (none open)"
        return (
            "no-such-milestone",
            f"no open milestone matches {action.argument!r}. Open milestones:\n{listed}",
        )

    action.value = milestone["number"]
    action.milestone = milestone
    return None
