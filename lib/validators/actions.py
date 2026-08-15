#!/usr/bin/env python3
"""Check that every third-party action is pinned to a full commit SHA.

A tag is a moving pointer. `@v4` today and `@v4` next month can be different
code, published by someone who is not us, running with the workflow's token —
which is why GitHub lets a repository require full-length SHAs, and why a
repository that has switched that on rejects a tag reference outright.

That rejection happens when the *step starts*, not when the workflow is
parsed, so nothing in an ordinary test suite sees it. This repository learned
that from `release-please.yml`: it referenced
`googleapis/release-please-action@v4`, every run failed with "not allowed …
all actions must be pinned to a full-length commit SHA", and no gate here
noticed because no gate read workflow files at all.

Nothing is exempt on the strength of who publishes it — `actions/checkout@v4`
is refused exactly like anyone else's action. Only a reference that resolves
to no external ref is: a local `./…` workflow, or a `docker://` image.

Specification: docs/spec/validators.md (`VAL`), §6.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

#: `uses: owner/repo@ref` with whatever trails it, comment included.
USES = re.compile(r"^\s*(?:-\s*)?uses:\s*(?P<ref>\S+)(?P<rest>.*)$")

SHA = re.compile(r"^[0-9a-f]{40}$")


def _exempt(reference):
    """Only a reference that resolves to no external ref at all.

    Not `actions/*`: the repository's policy exempts nobody, GitHub included.
    Assuming otherwise is a mistake this validator made on the first attempt.

    A reusable *workflow* is exempt, though — that is a different thing from an
    action, and ai-sdlc distributes its own by tag on purpose. `adopt` writes
    those callers; a rule flagging the line its own skill generates would be a
    rule at war with itself.
    """
    if reference.startswith("./") or reference.startswith("docker://"):
        return True
    path, _, _ = reference.partition("@")
    return "/.github/workflows/" in path and path.endswith((".yml", ".yaml"))


def validate_actions(root):
    """Return every unpinned or unlabelled action reference, in file order."""
    workflows = Path(root) / ".github" / "workflows"
    if not workflows.is_dir():
        return []

    problems = []
    files = sorted(
        p for p in workflows.iterdir() if p.suffix in (".yml", ".yaml") and p.is_file()
    )
    for path in files:
        where = path.relative_to(root).as_posix()
        for number, line in enumerate(path.read_text().splitlines(), start=1):
            match = USES.match(line)
            if not match:
                continue
            reference = match.group("ref").strip("\"'")
            if _exempt(reference):
                continue

            _, _, ref = reference.partition("@")
            if not SHA.match(ref):
                problems.append(
                    f"{where}:{number}: {reference} is not pinned to a "
                    f"full-length commit SHA"
                )
            elif "#" not in match.group("rest"):
                problems.append(
                    f"{where}:{number}: {reference} is pinned but carries no "
                    f"trailing comment naming the version it pins"
                )
    return problems


def main(root="."):
    problems = validate_actions(root)
    for problem in problems:
        print(f"  - {problem}", file=sys.stderr)
    if problems:
        print(f"actions: {len(problems)} problem(s)", file=sys.stderr)
        return 1
    print("actions: every action is pinned to a commit SHA")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
