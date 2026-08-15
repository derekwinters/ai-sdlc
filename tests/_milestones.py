"""Path setup and fixtures for the milestone-ops skill."""

import sys

from _support import ROOT

SKILL = ROOT / "skills" / "pipeline" / "milestone-ops"
if str(SKILL) not in sys.path:
    sys.path.insert(0, str(SKILL))


def milestone(number, title, state="open", description="", open_issues=0, closed_issues=0):
    return {
        "number": number,
        "title": title,
        "state": state,
        "description": description,
        "open_issues": open_issues,
        "closed_issues": closed_issues,
    }


DEFAULT = [
    milestone(1, "v0.1 — Gatekeeper pilot", "closed", "focus. the pilot", 0, 14),
    milestone(2, "v0.2 — Pipeline state", "open", "state and visibility", 4),
    milestone(3, "v0.3 — The working loop", "open", "frozen. scope is settled", 4),
    milestone(6, "Direct Involvement Needed", "open", "human-only tasks", 3),
]
