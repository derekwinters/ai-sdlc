#!/usr/bin/env python3
"""Check that a capability never imports from one above it.

Partial adoption is only real if the layering holds. A repository installing
`hygiene` alone must not find that its code needs something from `pipeline`,
and the only way to know that stays true is to fail the build when it stops
being true.

The order comes from lib/config.py rather than a second copy here: two
declarations of the same ordering would eventually disagree, and the one in
config is the one the loader enforces.

Specification: docs/spec/validators.md (`VAL`), §4.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

from lib.config import CAPABILITIES

ORDER = list(CAPABILITIES)

SKIP_DIRECTORIES = {".git", "site", ".venv", "node_modules", "__pycache__"}


def capability_of(path):
    """Which capability a module belongs to, from its path.

    Returns None for a path under a profile scope, which is not a capability
    and is exempt from the ordering rule.
    """
    parts = Path(path).parts
    if len(parts) >= 2 and parts[0] == "skills":
        scope = parts[1]
        return scope if scope in ORDER else None
    return "substrate"


def _imported_modules(path):
    tree = ast.parse(Path(path).read_text(), filename=str(path))
    modules = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            modules.add(node.module)
    return modules


def _capability_of_module(module):
    parts = module.split(".")
    if len(parts) >= 2 and parts[0] == "skills":
        return parts[1] if parts[1] in ORDER else None
    if parts[0] == "lib":
        return "substrate"
    return None


def validate_boundaries(root):
    """Return every upward import found."""
    root = Path(root)
    problems = []

    for path in sorted(root.rglob("*.py")):
        if any(part in SKIP_DIRECTORIES for part in path.parts):
            continue
        relative = path.relative_to(root)
        owner = capability_of(relative)
        if owner is None:
            continue

        for module in sorted(_imported_modules(path)):
            target = _capability_of_module(module)
            if target is None:
                continue
            if ORDER.index(target) > ORDER.index(owner):
                problems.append(
                    f"{relative} ({owner}) imports {module} ({target}); "
                    f"a capability may depend only on capabilities below it"
                )

    return problems


def main(root="."):
    problems = validate_boundaries(root)
    for problem in problems:
        print(f"  - {problem}", file=sys.stderr)
    if problems:
        print(f"boundaries: {len(problems)} upward import(s)", file=sys.stderr)
        return 1
    print(f"boundaries: clean across {len(ORDER)} capabilities")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
