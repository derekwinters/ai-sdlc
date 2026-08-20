"""A reader for the development-queue skill.

`select_queue.py` was pure and `take_issue.py` took a client; neither had a
caller in a consumer (#153). Both are instructions now, and no script builds a
development queue — the dashboard renders one from state it fetches itself.
"""

from _support import ROOT

SKILL = ROOT / "skills" / "pipeline" / "pipeline-dev" / "SKILL.md"


def stated():
    """The skill's text, lowercased with whitespace collapsed."""
    return " ".join(SKILL.read_text().lower().split())
