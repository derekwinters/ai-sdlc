"""Path setup for the triage skill."""

import sys

from _support import ROOT

SKILL = ROOT / "skills" / "pipeline" / "triage-issue"
if str(SKILL) not in sys.path:
    sys.path.insert(0, str(SKILL))
