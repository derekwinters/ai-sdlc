"""Path setup for the blocker code, and a reader for the skill that replaced it.

`issue-blockers` used to be a Python module with an injected client. It is
instructions now (`DIST-043`), and the only blocker code left is the read half
the dashboard needs — which lives with the dashboard, because the dashboard is
a script and scripts talk to GitHub in code.
"""

import sys

from _support import ROOT

SKILL = ROOT / "skills" / "pipeline" / "issue-blockers" / "SKILL.md"

DASHBOARD = ROOT / "skills" / "pipeline" / "pipeline-dashboard"
if str(DASHBOARD) not in sys.path:
    sys.path.insert(0, str(DASHBOARD))


def stated():
    """The skill's text, lowercased with whitespace collapsed.

    Collapsed because the file is hard-wrapped: a rule that reads as one
    sentence is two lines on disk, and a test that broke when a paragraph
    reflowed would be a test about formatting.
    """
    return " ".join(SKILL.read_text().lower().split())
