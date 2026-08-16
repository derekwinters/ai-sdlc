#!/usr/bin/env python3
"""Re-render the dashboard after a run changed something.

The board is rendered from live state, so a command that moves a label makes
it stale immediately; waiting for the next scheduled run leaves it wrong for
up to a day, at exactly the moment somebody is watching.

It is also the only way `/focus` and `/cap` persist. Their values are not
stored anywhere else — the renderer writes them into the board's own body as
markers and reads them back on the next render, so the render triggered here
*is* the write. Without it the value lives in memory until this process ends,
which is why `/focus` used to reply `Done` and change nothing (#105).

Specification: docs/spec/gatekeeper.md (`GK-114`, `GK-116`).
"""

from __future__ import annotations

import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
for _sibling in ("pipeline-dashboard", "issue-blockers"):
    _path = _HERE.parent / _sibling
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from fetch_state import fetch  # noqa: E402
from lib.github import GitHubError  # noqa: E402
from render_dashboard import render  # noqa: E402


def refresh_dashboard(api, settings, overrides=None):
    """Re-render the board, carrying any overrides into it.

    Returns True when the board was rewritten. A repository with no dashboard
    configured is not an error — it simply has no board to refresh.
    """
    if not settings.dashboard_issue:
        return False

    state = fetch(
        api,
        labels=settings.labels,
        bot_login=settings.bot_login,
        dashboard_issue=settings.dashboard_issue,
        overrides=overrides or {},
    )
    api.set_body(settings.dashboard_issue, render(state))
    return True


def refresh_quietly(api, settings, overrides=None):
    """As above, but a failure degrades the board rather than the run.

    The commands have already been applied and acknowledged by this point. If
    re-rendering fails, the labels are still right and the next scheduled run
    will redraw; losing the whole run — and its exit code — over a stale board
    would be the worse trade.
    """
    try:
        return refresh_dashboard(api, settings, overrides)
    except GitHubError:
        return False
