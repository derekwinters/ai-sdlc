"""Path setup and fixtures for the routines skill.

The skill is installed into consumers, so it cannot import `lib` (DIST-042).
These helpers put the skill's own directory on the path, and build throwaway
repositories and definition directories so no test depends on the shipped
definitions unless it is about them.
"""

import importlib.util
import sys
import tempfile
from pathlib import Path

from _support import ROOT

SKILL = ROOT / "skills" / "substrate" / "routines"
DEFINITIONS = SKILL / "definitions"
if str(SKILL) not in sys.path:
    sys.path.insert(0, str(SKILL))

PIPELINE = (
    "capabilities:\n  - hygiene\n  - consistency\n  - labels\n  - release\n"
    "  - pipeline\nowners:\n  - someone\ndashboard_issue: 7\n"
    "fire:\n  endpoint_secret: ROUTINE_FIRE_URL\n  token_secret: ROUTINE_FIRE_TOKEN\n"
)


def definition(id="sample", name="{repo_name} Sample", requires="substrate",
               schedule=None, api=None, connectors=None, session="fresh",
               body="Do the thing in {repo}.\n", extra=""):
    """A definition file's text, with only the keys asked for."""
    lines = ["---", f"id: {id}", f'name: "{name}"', f"requires: {requires}"]
    if schedule is not None:
        lines.append(f'schedule: "{schedule}"')
    if api is not None:
        lines.append(f"api: {'true' if api else 'false'}")
    if connectors is not None:
        if connectors:
            lines.append("connectors:")
            lines += [f"  - {c}" for c in connectors]
        else:
            lines.append("connectors: []")
    if session is not None:
        lines.append(f"session: {session}")
    if extra:
        lines.append(extra)
    lines.append("---")
    return "\n".join(lines) + "\n" + body


def directory(files):
    """A temporary definitions directory holding `{id: text}`."""
    path = Path(tempfile.mkdtemp())
    for stem, text in files.items():
        (path / f"{stem}.md").write_text(text)
    return path


def repository(config=None):
    """A temporary repository root, with `.ai-sdlc/repo-config.yml` if given."""
    root = Path(tempfile.mkdtemp())
    if config is not None:
        (root / ".ai-sdlc").mkdir()
        (root / ".ai-sdlc" / "repo-config.yml").write_text(config)
    return root


def load_main():
    """The skill's `main.py`, under a name no other skill's `main.py` takes.

    Several skills have a `main.py`; importing `main` would return whichever
    one some earlier test put in `sys.modules`.
    """
    spec = importlib.util.spec_from_file_location("routines_main", SKILL / "main.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
