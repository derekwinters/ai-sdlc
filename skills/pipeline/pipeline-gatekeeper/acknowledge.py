#!/usr/bin/env python3
"""What the gatekeeper says back.

Short. A command that was applied gets a line naming the change and what
happens next; a refusal gets a line explaining why and stating plainly that
nothing changed.

Refusals used to be silent, and that is the behaviour that made the pipeline
feel broken: a command vanished, and the only evidence was a state that had not
moved. Silence is reserved for the two cases where replying would be worse —
a comment from someone without authority, where a reply would let anyone make
the bot post on demand, and a comment already dealt with, where a reply would
post the same acknowledgement twice.

Internal reason codes never appear. They are for the log; the reader gets
prose.

Pure: actions and skips in, text out.

Specification: docs/spec/gatekeeper.md (`GK`), §5.
"""

from __future__ import annotations

from parse_commands import COMMANDS

#: Refusals nobody is told about, and why.
SILENT = {
    "not-owner": "replying would let anyone make the bot post",
    "bot": "the bot must not answer itself",
    "no-owners": "nothing is configured to answer to",
    "pull-request": "the gatekeeper acts on issues",
    "already-applied": "a reply would post the same acknowledgement twice",
}

#: What each destination state means for the reader. Both halves matter: the
#: label is the concrete change, and someone wondering why the builder has not
#: picked an issue up needs to see which state it actually landed in; the
#: consequence is why they should care.
NEXT = {
    "ai-triage": "the next triage run will pick it up",
    "ready-for-work": "the builder can pick it up next",
    "parked": "the pipeline will leave it alone until `/unpark`",
}


def acknowledge(actions, skips, state=None):
    """Compose the reply, or None when there is nothing to say."""
    audible = [skip for skip in skips if skip.reason not in SILENT]

    if not actions and not audible:
        return None

    lines = []

    if actions:
        lines.append(_applied(actions, state))

    for skip in audible:
        lines.append(_refused(skip))

    return "\n\n".join(lines)


def _applied(actions, state):
    done = ", ".join(_describe(action) for action in actions)
    consequence = NEXT.get(state)
    if consequence:
        return f"Done: {done} → `{state}`, so {consequence}."
    return f"Done: {done}."


def _describe(action):
    if action.argument:
        return f"`/{action.command} {action.argument}`"
    return f"`/{action.command}`"


def _refused(skip):
    if skip.reason == "unknown-command":
        return _unknown(skip)

    detail = skip.detail or "that command cannot be applied here"
    return f"Refused `/{skip.command}`: {detail} Nothing changed."


def _unknown(skip):
    if skip.suggestion:
        return (
            f"`/{skip.command}` is not a command — did you mean "
            f"`/{skip.suggestion}`? Nothing changed."
        )
    vocabulary = " · ".join(f"`/{command}`" for command in COMMANDS)
    return (
        f"`/{skip.command}` is not a command. Nothing changed.\n\n"
        f"Available: {vocabulary}"
    )
