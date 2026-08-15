#!/usr/bin/env python3
"""Check that a pull request title is a valid Conventional Commit.

Pull requests here merge by squash, so this title becomes the one commit
release-please ever sees. A title it cannot parse drives no version bump and
appears in no changelog — the change ships unreleased and unaccounted for.
Checking the title before merge is the only point at which that is cheap to
fix.

Usage:  check_pr_title.py "<title>"
Exits 0 when the title is valid, 1 otherwise with an explanation on stderr.
"""

from __future__ import annotations

import re
import sys

VALID_TYPES = (
    "feat",
    "fix",
    "chore",
    "ci",
    "docs",
    "build",
    "refactor",
    "test",
    "perf",
    "revert",
)

# type, optional (scope), optional ! for a breaking change, colon, description.
# The scope may not be empty: "feat(): x" is a mistake, not a scopeless commit.
_PATTERN = re.compile(
    r"^(?P<type>[a-z]+)"
    r"(?:\((?P<scope>[^()\s][^()]*)\))?"
    r"(?P<breaking>!)?"
    r": *(?P<description>.*)$"
)


def check(title: str) -> str | None:
    """Return None when the title is valid, or an explanation of why it is not."""
    problem = _problem(title)
    if problem is None:
        return None
    return (
        f"{problem}\n\n"
        f"  offending title: {title!r}\n\n"
        f"  expected: type(optional-scope): description\n"
        f"  valid types: {', '.join(VALID_TYPES)}\n"
        f"  a breaking change is marked with ! after the type or scope\n\n"
        f"  Pick the type for the actual semver impact of the change, not for\n"
        f"  whatever the branch happened to be called."
    )


def _problem(title: str) -> str | None:
    if not title or not title.strip():
        return "The pull request title is empty."

    match = _PATTERN.match(title)
    if match is None:
        return "The pull request title is not a Conventional Commit."

    kind = match.group("type")
    if kind not in VALID_TYPES:
        return f"{kind!r} is not a valid Conventional Commit type."

    if not match.group("description").strip():
        return "The pull request title has no description after the colon."

    return None


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(f"usage: {argv[0]} \"<title>\"", file=sys.stderr)
        return 2

    problem = check(argv[1])
    if problem is not None:
        print(problem, file=sys.stderr)
        return 1

    print(f"OK: {argv[1]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
