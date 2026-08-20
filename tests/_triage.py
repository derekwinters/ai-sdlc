"""A reader for the triage skill.

`select_triage.py` was pure and `triage_route.py` took a client. Neither had a
caller in a consumer (#153), and the judgement they surrounded was always the
agent's — which is what makes triage the clearest case for the conversion.
"""

from _support import ROOT

SKILL = ROOT / "skills" / "pipeline" / "triage-issue" / "SKILL.md"


def stated():
    """The skill's text, lowercased with whitespace collapsed."""
    return " ".join(SKILL.read_text().lower().split())
