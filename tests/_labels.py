"""Path setup for the label-sync skill."""

import sys

from _support import ROOT

SKILL = ROOT / "skills" / "labels" / "label-sync"
if str(SKILL) not in sys.path:
    sys.path.insert(0, str(SKILL))

CORE = ROOT / "skills" / "labels" / "label-sync" / "labels.core.yml"
