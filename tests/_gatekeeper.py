"""Puts the gatekeeper skill on the path.

The skill directory is `pipeline-gatekeeper`, hyphenated because `gh skill`
requires the directory name to match the skill name. A hyphen is not importable
as a package, so the directory goes on sys.path and its modules are imported by
bare name — the same arrangement the existing consumer repositories use.
"""

import sys

from _support import ROOT

SKILL = ROOT / "skills" / "pipeline" / "pipeline-gatekeeper"
if str(SKILL) not in sys.path:
    sys.path.insert(0, str(SKILL))
