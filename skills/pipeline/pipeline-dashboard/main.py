#!/usr/bin/env python3
"""Entry point for the dashboard workflow."""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path.cwd()))

from fetch_state import fetch  # noqa: E402
from lib.config import load  # noqa: E402
from lib.github import GitHub  # noqa: E402
from render_dashboard import render  # noqa: E402


def main():
    config = load()
    if not config.has("pipeline"):
        print("dashboard: the pipeline capability is not enabled; nothing to render")
        return 0

    api = GitHub(os.environ["GITHUB_TOKEN"], os.environ["GITHUB_REPOSITORY"])
    state = fetch(
        api,
        labels=config.labels,
        bot_login=config.bot.login,
        dashboard_issue=config.dashboard_issue,
    )
    page = render(state)

    # The only write: the dashboard's own body. A named operation rather than
    # a raw request, so a test can assert it happened.
    api.set_body(config.dashboard_issue, page)

    total = sum(len(v) for v in state["faults"].values())
    print(f"dashboard: rendered {len(state['issues'])} issues, {total} needing attention")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
