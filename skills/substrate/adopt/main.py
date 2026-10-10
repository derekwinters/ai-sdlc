#!/usr/bin/env python3
"""Command line for adopt: plan, apply, verify, tasks."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path.cwd()))

import json  # noqa: E402

from adopt import (  # noqa: E402
    AdoptRefused, apply, as_pin, client_from_environment, plan, task_line, task_report,
    task_summary, verify,
)


def _report_tasks(tasks):
    print("\nmanual tasks:")
    for task in tasks:
        print(f"  - {task_line(task)}")
    if tasks:
        print(task_summary(tasks))


def _report_plan(result):
    print(f"detected profiles: {', '.join(result.detection.profiles) or '(none)'}")
    if result.detection.undetectable:
        print("  the stack could not be detected; set `profiles` in repo-config.yml")

    for old, new in result.migrations:
        print(f"  move     {old} -> {new}")
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

    _report_tasks(result.manual_tasks)


def main(argv):
    if len(argv) < 3:
        raise SystemExit(f"usage: {argv[0]} plan|apply|verify|tasks <pin> [--ack <workflow>...]")

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

    # A read client when the environment offers one, for checking the manual
    # tasks. None is fine: every task is then reported `unknown`.
    github = client_from_environment(root) if command in ("plan", "apply", "tasks") else None

    if command == "tasks":
        # Read-only, and nothing but JSON on stdout, so an agent can parse it.
        result = plan(root, pin, acknowledged=acknowledged, github=github)
        print(json.dumps(task_report(result.manual_tasks), indent=2))
        return 0

    print(f"ai-sdlc {pin[0]} = {pin[1]}")

    if command == "plan":
        _report_plan(plan(root, pin, acknowledged=acknowledged, github=github))
        return 0

    if command == "apply":
        try:
            result = apply(root, pin, acknowledged=acknowledged, github=github)
        except AdoptRefused as error:
            print(f"refused: {error}", file=sys.stderr)
            return 1
        for old, new in result.migrated:
            print(f"  moved    {old} -> {new}")
        for path in result.written:
            print(f"  wrote    {path}")
        for path in result.skipped:
            print(f"  skipped  {path} (conflict)")
        _report_tasks(result.manual_tasks)
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
