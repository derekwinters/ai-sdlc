"""Path setup for the issue-blockers skill."""

import sys

from _support import ROOT

SKILL = ROOT / "skills" / "pipeline" / "issue-blockers"
if str(SKILL) not in sys.path:
    sys.path.insert(0, str(SKILL))
