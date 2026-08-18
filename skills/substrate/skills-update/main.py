#!/usr/bin/env python3
"""Command line for skills-update: plan, apply.

`plan` writes nothing and says what would happen. `apply` runs the installs and
writes the report the workflow turns into a pull request body.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path.cwd()))

from skills_update import (  # noqa: E402
    Applied,
    _git_source,
    apply,
    plan,
    report,
)


def _skills(root):
    from lib.config import load

    return load(root=root).skills


def _emit(name, value):
    """A workflow output, when running in one. Harmless otherwise."""
    path = os.environ.get("GITHUB_OUTPUT")
    if path:
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(f"{name}={value}\n")


def main(argv):
    if len(argv) < 3:
        raise SystemExit(
            f"usage: {argv[0]} plan|apply <ref> [--source <ai-sdlc checkout>] "
            f"[--report <path>]"
        )

    command, ref = argv[1], argv[2]
    checkout = _option(argv, "--source", ".")
    destination = _option(argv, "--report", None)
    root = Path.cwd()

    names = _skills(root)
    if not names:
        print("no skills are configured; `skills:` in repo-config.yml names none")
        _emit("changed", "false")
        _emit("failed", "false")
        return 0

    source = _git_source(checkout)
    proposed = plan(names, ref, root=root, source=source)

    if command == "plan":
        result = Applied([], [], proposed.skipped, [], proposed.current)
        for name in proposed.install:
            print(f"  install  {name}")
        for name in proposed.update:
            print(f"  update   {name}")
        for name in proposed.current:
            print(f"  current  {name}")
        for skill in proposed.skipped:
            print(f"  SKIP     {skill.name} ({skill.state}) — {skill.detail}")
        if not proposed.changes:
            print("  nothing to do; every skill named is at the pin or left alone")
        _report(report(result, ref), destination)
        return 0

    if command != "apply":
        raise SystemExit(f"unknown command {command!r}")

    result = apply(proposed, ref, installer=None)
    text = report(result, ref)
    print(text)
    _report(text, destination)

    _emit("changed", "true" if result.changes else "false")
    _emit("failed", "true" if result.failed else "false")
    return 0


def _report(text, destination):
    """The report, to a file when asked, and to the job summary when in one."""
    if destination:
        Path(destination).write_text(text)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as handle:
            handle.write(text)


def _option(argv, flag, default):
    return argv[argv.index(flag) + 1] if flag in argv else default


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
