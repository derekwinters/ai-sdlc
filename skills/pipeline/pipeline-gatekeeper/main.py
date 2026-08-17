#!/usr/bin/env python3
"""Entry point for the gatekeeper workflows.

Reads the event GitHub wrote to disk, loads the repository's configuration,
and calls the handler. Everything interesting is in the modules this imports;
this file exists so a workflow step is one line.

Specification: docs/spec/gatekeeper.md (`GK`).
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path.cwd()))

from downstream import Fire, fire_summary  # noqa: E402
from lib.config import load  # noqa: E402
from lib.github import GitHub  # noqa: E402
from lifecycle import on_issue_closed  # noqa: E402
from on_labeled import on_label_added  # noqa: E402
from run_comment_event import Settings, handle_comment  # noqa: E402


def _event():
    path = os.environ.get("GITHUB_EVENT_PATH")
    if not path or not Path(path).is_file():
        raise SystemExit("no event payload: GITHUB_EVENT_PATH is unset or missing")
    return json.loads(Path(path).read_text())


def _client(config):
    token = os.environ.get("GITHUB_TOKEN")
    repository = os.environ.get("GITHUB_REPOSITORY")
    if not token or not repository:
        raise SystemExit("GITHUB_TOKEN and GITHUB_REPOSITORY are required")
    return GitHub(token, repository)


def main(argv):
    if len(argv) != 2 or argv[1] not in ("comment", "closed", "labeled", "sweep"):
        raise SystemExit(f"usage: {argv[0]} comment|closed|labeled|sweep")

    config = load()
    api = _client(config)

    if argv[1] == "sweep":
        # No event payload: the sweep reads the board rather than reacting to
        # one thing, and the scheduled path has no event to read.
        from datetime import datetime, timezone  # noqa: PLC0415

        from run_sweep import run, summarise  # noqa: PLC0415

        fire = Fire(os.environ.get("FIRE_ENDPOINT"), os.environ.get("FIRE_TOKEN"))
        events_only = os.environ.get("EVENTS_ONLY", "true").lower() != "false"
        result = run(
            api, config, fire,
            now=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            events_only=events_only,
        )
        for line in summarise(result):
            print(line)
        return 0

    event = _event()

    if argv[1] == "closed":
        removed = on_issue_closed(api, event["issue"]["number"], config.labels)
        print(f"removed: {', '.join(removed) or '(nothing)'}")
        return 0

    fire = Fire(os.environ.get("FIRE_ENDPOINT"), os.environ.get("FIRE_TOKEN"))

    if argv[1] == "labeled":
        settings = Settings.from_config(config, fire=fire)
        print(fire_summary(on_label_added(api, event, settings)))
        return 0

    result = handle_comment(api, event, Settings.from_config(config, fire=fire))

    print(f"applied: {[a.command for a in result.applied] or '(nothing)'}")
    print(f"refused: {[s.reason for s in result.refused] or '(nothing)'}")
    # Every run says what became of the analysis routine. Without this a run
    # that fired and one that silently skipped are indistinguishable (#121).
    print(fire_summary(result.fired))
    if result.unverifiable:
        print(f"unverifiable dependencies: {[b['number'] for b in result.unverifiable]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
