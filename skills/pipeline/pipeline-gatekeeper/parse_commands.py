#!/usr/bin/env python3
"""Read the commands out of a comment.

The parser's job is to be boring and predictable. Every rule here exists
because the alternative is acting on something the author did not mean: a URL
containing a slash-word, an example inside a code fence, or a typo silently
read as a nearby command.

An unknown command is never guessed at. Suggesting the closest match is
helpful; applying it is not, because the cost of guessing wrong is a state
change nobody asked for.

Pure: text in, actions out. No I/O, and no knowledge of GitHub.

Specification: docs/spec/gatekeeper.md (`GK`), §3 (Parsing).
"""

from __future__ import annotations

import difflib
import re

#: The whole vocabulary. Ten carried over from the existing implementations,
#: plus `retry`, which re-processes a comment whose run died mid-flight.
COMMANDS = (
    "admit",      # bring an issue into the pipeline
    "propose",    # ask analysis for a plan
    "approve",    # the plan is right — queue it for work
    "revise",     # the plan is not right; re-triage with these notes
    "redo",       # the built work is wrong; queue it again
    "park",       # set aside deliberately
    "unpark",     # bring it back
    "milestone",  # set the issue's milestone, by title
    "focus",      # set the pipeline's focus milestone
    "cap",        # set the maximum concurrent building issues
    "retry",      # re-process this issue's unfinished commands
)

#: A command occupies a whole line, after at most three spaces. Four spaces is
#: an indented code block in Markdown, and a command mid-line is prose — most
#: often a URL, which is why the pattern anchors rather than searching.
COMMAND_LINE = re.compile(r"^ {0,3}/([A-Za-z][\w-]*)(?:[ \t]+(.*))?$")

FENCE = re.compile(r"^\s*(```|~~~)")

#: Below this similarity a suggestion is noise rather than help.
SUGGESTION_CUTOFF = 0.6


class Action:
    """A recognised command and its argument."""

    __slots__ = ("command", "argument", "line")

    def __init__(self, command, argument="", line=0):
        self.command = command
        self.argument = argument
        self.line = line

    def __repr__(self):
        return f"<Action /{self.command} {self.argument!r}>"

    def __eq__(self, other):
        return (
            isinstance(other, Action)
            and (self.command, self.argument) == (other.command, other.argument)
        )


class Skip:
    """Something command-shaped that was not acted on, and why."""

    __slots__ = ("command", "reason", "suggestion", "line")

    def __init__(self, command, reason, suggestion=None, line=0):
        self.command = command
        self.reason = reason
        self.suggestion = suggestion
        self.line = line

    def __repr__(self):
        return f"<Skip /{self.command} {self.reason}>"


class Parsed:
    """What a comment asked for, and what it got wrong."""

    __slots__ = ("actions", "skips")

    def __init__(self, actions, skips):
        self.actions = actions
        self.skips = skips

    def __bool__(self):
        return bool(self.actions or self.skips)

    def __repr__(self):
        return f"<Parsed actions={self.actions} skips={self.skips}>"


def parse(body):
    """Read `body` and return the actions it asks for, in the order written."""
    actions, skips = [], []

    for number, line in enumerate(_uncoded_lines(body or ""), start=1):
        match = COMMAND_LINE.match(line)
        if not match:
            continue

        name, argument = match.group(1), (match.group(2) or "").strip()

        if name in COMMANDS:
            actions.append(Action(name, argument, line=number))
        else:
            skips.append(
                Skip(name, "unknown-command", suggestion=_closest(name), line=number)
            )

    return Parsed(actions, skips)


def _uncoded_lines(body):
    """Yield lines outside fenced code blocks.

    An unclosed fence swallows the rest of the comment. That is deliberate:
    reading nothing is safer than guessing where the author meant the block to
    end and acting on what follows.
    """
    fenced = False
    marker = None

    for line in body.splitlines():
        fence = FENCE.match(line)
        if fence:
            if not fenced:
                fenced, marker = True, fence.group(1)
            elif fence.group(1) == marker:
                fenced, marker = False, None
            continue
        if not fenced:
            yield line


def _closest(name):
    matches = difflib.get_close_matches(name, COMMANDS, n=1, cutoff=SUGGESTION_CUTOFF)
    return matches[0] if matches else None
