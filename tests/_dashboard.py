"""Path setup and state fixtures for the dashboard skill."""

import sys

from _support import ROOT

SKILL = ROOT / "skills" / "pipeline" / "pipeline-dashboard"
if str(SKILL) not in sys.path:
    sys.path.insert(0, str(SKILL))

REPO = "derekwinters/ai-sdlc"

LABELS = {
    "triage": "ai-triage",
    "pending_approval": "pending-approval",
    "clarification": "needs-clarification",
    "approved": "ready-for-work",
    "building": "in-progress",
    "parked": "parked",
}


def state(**overrides):
    """A plain-data snapshot, as fetch produces and render consumes."""
    base = {
        "repository": REPO,
        "focus": {"title": "v0.2", "number": 2, "open": 2, "closed": 2},
        "cap": 2,
        # Open milestones, for the first chart. Empty ones belong here: an
        # empty milestone is how you see there is planning runway left.
        "milestones": [
            {"title": "v0.2", "number": 2, "open": 2},
            {"title": "v0.3", "number": 3, "open": 0},
        ],
        "issues": [],
        "faults": {},
        "labels": dict(LABELS),
    }
    base.update(overrides)
    return base


def issue(number, title="A thing", state_label="ready-for-work", milestone="v0.2",
          milestone_number=2, blockers=(), has_pr=False, closed=False, marker=None):
    """One issue as fetch prepares it.

    `closed` matters: the focus chart's Done bucket is closed issues by
    definition (DASH-008), so closed issues are part of the snapshot rather
    than being dropped during the fetch.
    """
    return {
        "number": number,
        "title": title,
        "state_label": state_label,
        "marker": marker,
        "milestone": milestone,
        "milestone_number": milestone_number,
        "blockers": list(blockers),
        "has_open_pr": has_pr,
        "closed": closed,
    }
