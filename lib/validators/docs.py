#!/usr/bin/env python3
"""Check that the specification and the published site describe one thing.

A page that exists but is not in the navigation is a page nobody reads; a
navigation entry pointing at nothing breaks the build. Both are cheap to
create by accident when adding a specification area, which is why this runs
every time rather than being remembered.

Specification: docs/spec/validators.md (`VAL`), §3.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from lib.config import CAPABILITIES

CAPABILITY_CLAIM = re.compile(r"\*\*(" + "|".join(CAPABILITIES) + r")\*\*\s+capability")
ANY_CLAIM = re.compile(r"\*\*([a-z]+)\*\*\s+capability")

#: Nav entries are "  - Title: path.md"; the path is what matters here.
NAV_ENTRY = re.compile(r":\s*([\w./-]+\.md)\s*$")


def _nav_paths(root):
    config = Path(root) / "mkdocs.yml"
    if not config.is_file():
        return set()
    paths, in_nav = set(), False
    for line in config.read_text().splitlines():
        if line.startswith("nav:"):
            in_nav = True
            continue
        if in_nav and line and not line[0].isspace():
            break
        if in_nav:
            match = NAV_ENTRY.search(line)
            if match:
                paths.add(match.group(1))
    return paths


def validate_docs(root):
    """Return every inconsistency between the spec pages and the site."""
    root = Path(root)
    problems = []
    nav = _nav_paths(root)

    for entry in sorted(nav):
        if not (root / "docs" / entry).is_file():
            problems.append(f"mkdocs.yml lists {entry}, which does not exist")

    spec_dir = root / "docs" / "spec"
    for page in sorted(spec_dir.glob("*.md")) if spec_dir.is_dir() else []:
        relative = page.relative_to(root / "docs").as_posix()
        if relative not in nav:
            problems.append(f"{relative} is not in the site navigation")

        text = page.read_text()
        if CAPABILITY_CLAIM.search(text):
            continue
        claimed = ANY_CLAIM.search(text)
        if claimed:
            problems.append(
                f"{relative} claims the {claimed.group(1)!r} capability, which is not one of "
                f"{', '.join(CAPABILITIES)}"
            )
        else:
            problems.append(
                f"{relative} does not state which capability owns it"
            )

    return problems


def main(root="."):
    problems = validate_docs(root)
    for problem in problems:
        print(f"  - {problem}", file=sys.stderr)
    if problems:
        print(f"docs: {len(problems)} problem(s)", file=sys.stderr)
        return 1
    print("docs: specification pages and navigation agree")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
