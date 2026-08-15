#!/usr/bin/env python3
"""Require a pull request that changes code to change documentation too.

Not because every change needs a paragraph, but because deciding it does not
should be a decision somebody made rather than one nobody thought about. The
`skip-docs` label is that decision, recorded on the pull request.

Like every other gate here, the label makes the check **pass** — it never makes
it skip. A skipped required check stays pending forever and blocks the merge it
was meant to permit.

Standard library only, and no network: the changed files and the labels are
supplied by the workflow.

Specification: docs/spec/profiles.md (`PROF`), §3.
"""

from __future__ import annotations

import fnmatch
import os
import sys

EXEMPT_LABEL = "skip-docs"

#: A path is documentation if it is under one of these directories, or matches
#: one of these globs.
DEFAULT_DOC_PATTERNS = ("docs/", "*.md", "*.rst")

#: Nothing to reconcile, and not code either.
IGNORED_PATTERNS = (".gitignore", ".gitattributes", "LICENSE", "*.lock")

MAX_DETAIL = 1_500


class Result:
    __slots__ = ("satisfied", "exempt", "detail")

    def __init__(self, satisfied, exempt=False, detail=""):
        self.satisfied = satisfied
        self.exempt = exempt
        self.detail = detail


def _matches(path, patterns):
    for pattern in patterns:
        if pattern.endswith("/") and path.startswith(pattern):
            return True
        if fnmatch.fnmatch(path, pattern) or fnmatch.fnmatch(os.path.basename(path), pattern):
            return True
    return False


def check(changed, labels=(), doc_patterns=None):
    """Whether documentation was reconciled, and why."""
    patterns = tuple(doc_patterns) if doc_patterns else DEFAULT_DOC_PATTERNS

    docs, code = [], []
    for path in changed:
        path = path.strip()
        if not path or _matches(path, IGNORED_PATTERNS):
            continue
        (docs if _matches(path, patterns) else code).append(path)

    if EXEMPT_LABEL in set(labels or ()):
        return Result(
            True,
            exempt=True,
            detail=(
                f"Exempt: labelled {EXEMPT_LABEL!r}. Deciding this change needs no "
                f"documentation is a decision, and it is recorded on the pull request."
            ),
        )

    if not code:
        return Result(True, detail=_summary(code, docs, "nothing to reconcile"))

    if docs:
        return Result(True, detail=_summary(code, docs, "documentation was changed too"))

    return Result(
        False,
        detail=_summary(
            code, docs,
            f"code changed and no documentation did. Update the pages this affects, "
            f"or apply the {EXEMPT_LABEL!r} label if it genuinely needs none.",
        ),
    )


def _summary(code, docs, verdict):
    lines = [verdict, ""]
    lines.append(f"code ({len(code)}): {_listed(code)}")
    lines.append(f"docs ({len(docs)}): {_listed(docs)}")
    return "\n".join(lines)[:MAX_DETAIL]


def _listed(paths):
    if not paths:
        return "(none)"
    shown = ", ".join(sorted(paths)[:10])
    return shown + (f", and {len(paths) - 10} more" if len(paths) > 10 else "")


def main():
    changed = [line for line in sys.stdin.read().splitlines() if line.strip()]
    labels = [name.strip() for name in os.environ.get("PR_LABELS", "").split(",")]
    result = check(changed, labels)

    print(result.detail)
    return 0 if result.satisfied else 1


if __name__ == "__main__":
    raise SystemExit(main())
