#!/usr/bin/env python3
"""Command line for adopt: plan, apply, verify."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path.cwd()))

from adopt import AdoptRefused, apply, as_pin, plan, verify  # noqa: E402


def _report_plan(result):
    print(f"detected profiles: {', '.join(result.detection.profiles) or '(none)'}")
    if result.detection.undetectable:
        print("  the stack could not be detected; set `profiles` in repo-config.yml")

    for path in result.creates:
        print(f"  create   {path}")
    for path in result.updates:
        print(f"  update   {path}")
    for path in result.conflicts:
        print(f"  CONFLICT {path} — written by hand or edited; left alone")
    for collision in result.collisions:
        print(f"  COLLISION {collision.workflow} already handles {collision.event}")

    if result.current and not result.conflicts:
        print("  nothing to do; this repository is current")

    print("\nmanual tasks:")
    for task in result.manual_tasks:
        print(f"  - {task}")


def main(argv):
    if len(argv) < 3:
        raise SystemExit(f"usage: {argv[0]} plan|apply|verify <pin> [--ack <workflow>...]")

    command, version = argv[1], argv[2]
    acknowledged = [a for a in argv[4:]] if "--ack" in argv else []
    root = Path.cwd()

    # Resolved once, here, so a version reaches the network at most once per
    # run and every later step works from the same commit.
    try:
        pin = as_pin(version)
    except AdoptRefused as error:
        print(f"refused: {error}", file=sys.stderr)
        return 1

    print(f"ai-sdlc {pin[0]} = {pin[1]}")

    if command == "plan":
        _report_plan(plan(root, pin, acknowledged=acknowledged))
        return 0

    if command == "apply":
        try:
            result = apply(root, pin, acknowledged=acknowledged)
        except AdoptRefused as error:
            print(f"refused: {error}", file=sys.stderr)
            return 1
        for path in result.written:
            print(f"  wrote    {path}")
        for path in result.skipped:
            print(f"  skipped  {path} (conflict)")
        print("\nmanual tasks:")
        for task in result.manual_tasks:
            print(f"  - {task}")
        return 0

    if command == "verify":
        result = verify(root, pin)
        for problem in result.problems:
            print(f"  - {problem}", file=sys.stderr)
        print("adopt: matches its pin" if result.ok
              else f"adopt: {len(result.problems)} problem(s)")
        return 0 if result.ok else 1

    raise SystemExit(f"unknown command {command!r}")


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
