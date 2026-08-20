"""A reader for the milestone-ops skill.

`milestone_ops.py` was a class taking a client nobody supplied in a consumer
(#153). The rules it enforced are stated in the skill now, and nothing in the
repository executes them — no script manages milestones, so unlike blockers
there is no read half left behind.
"""

from _support import ROOT

SKILL = ROOT / "skills" / "pipeline" / "milestone-ops" / "SKILL.md"


def stated():
    """The skill's text, lowercased with whitespace collapsed.

    Collapsed because the file is hard-wrapped: a rule that reads as one
    sentence is two lines on disk, and a test that broke when a paragraph
    reflowed would be a test about formatting.
    """
    return " ".join(SKILL.read_text().lower().split())
