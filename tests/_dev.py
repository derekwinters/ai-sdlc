"""Path setup for the development-queue skill."""

import sys

from _support import ROOT

SKILL = ROOT / "skills" / "pipeline" / "pipeline-dev"
if str(SKILL) not in sys.path:
    sys.path.insert(0, str(SKILL))
BLOCKERS = ROOT / "skills" / "pipeline" / "issue-blockers"
if str(BLOCKERS) not in sys.path:
    sys.path.insert(0, str(BLOCKERS))
