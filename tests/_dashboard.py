"""Path setup and state fixtures for the dashboard skill."""

import sys

from _support import ROOT

SKILL = ROOT / "skills" / "pipeline" / "pipeline-dashboard"
if str(SKILL) not in sys.path:
    sys.path.insert(0, str(SKILL))


def state(**overrides):
    """A plain-data snapshot, as fetch produces and render consumes."""
    base = {
        "repository": "derekwinters/ai-sdlc",
        "focus": {"title": "v0.2 — Pipeline state", "open": 2, "closed": 2},
        "cap": 2,
        "issues": [],
        "faults": {},
        "labels": {
            "triage": "ai-triage",
            "pending_approval": "pending-approval",
            "clarification": "needs-clarification",
            "approved": "ready-for-work",
            "building": "in-progress",
            "parked": "parked",
        },
    }
    base.update(overrides)
    return base


def issue(number, title="A thing", state_label="ready-for-work", milestone="v0.2 — Pipeline state",
          blockers=(), has_pr=False):
    return {
        "number": number,
        "title": title,
        "state_label": state_label,
        "milestone": milestone,
        "blockers": list(blockers),
        "has_open_pr": has_pr,
    }
