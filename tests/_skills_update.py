"""Path setup and doubles for the skills-update skill.

The two seams — reading ai-sdlc's own copy of a skill at a ref, and running
`gh skill install` — are injected here, so the suite never reaches the network
and never needs `gh` on the machine running it.
"""

import sys
import tempfile
from pathlib import Path

from _support import ROOT

SKILL = ROOT / "skills" / "substrate" / "skills-update"
if str(SKILL) not in sys.path:
    sys.path.insert(0, str(SKILL))

PIN = "v0.4.17"
OLDER = "v0.4.0"


def frontmatter(name, description="A skill.", provenance=None):
    """A `SKILL.md`, with the provenance `gh skill` injects when asked for."""
    lines = [f"name: {name}", f"description: {description}"]
    if provenance:
        lines += [
            f"github-repo: https://github.com/derekwinters/ai-sdlc",
            f"github-ref: {provenance}",
            f"github-path: skills/pipeline/{name}",
            f"github-tree-sha: {'0' * 40}",
        ]
    return "---\n" + "\n".join(lines) + "\n---\n\n# " + name + "\n\nWhat it does.\n"


def source_skill(name, description="A skill."):
    """ai-sdlc's own copy: the same file, without the injected keys."""
    return {
        "SKILL.md": frontmatter(name, description),
        "main.py": f"print({name!r})\n",
    }


def installed_skill(name, ref, description="A skill."):
    """A consumer's copy, as `gh skill install` leaves it."""
    files = source_skill(name, description)
    files["SKILL.md"] = frontmatter(name, description, provenance=ref)
    return files


class Unreadable(Exception):
    """Stands in for a ref the checkout does not carry."""


class Source:
    """ai-sdlc's tree, at each ref that matters. Injected as the reader."""

    def __init__(self, tree=None, unreadable=()):
        #: {ref: {name: {relpath: text}}}
        self.tree = tree or {}
        self.unreadable = set(unreadable)
        self.asked = []

    def __call__(self, name, ref):
        self.asked.append((name, ref))
        if ref in self.unreadable:
            from skills_update import SourceUnavailable

            raise SourceUnavailable(f"{ref} is not in this checkout")
        return self.tree.get(ref, {}).get(name)


def source_at(refs, names, description="A skill."):
    """A `Source` carrying `names` at every ref in `refs`."""
    return Source({ref: {n: source_skill(n, description) for n in names} for ref in refs})


class Installer:
    """Records what would have been installed. Never runs anything."""

    def __init__(self, fails=()):
        self.calls = []
        self.fails = set(fails)

    def __call__(self, name, ref):
        self.calls.append((name, ref))
        if name in self.fails:
            raise RuntimeError(f"gh skill install failed for {name}")


def consumer(skills=None, extra=None):
    """A throwaway repository with `skills` installed under .claude/skills."""
    root = Path(tempfile.mkdtemp())
    for name, files in (skills or {}).items():
        for relative, text in files.items():
            path = root / ".claude" / "skills" / name / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)
    for relative, text in (extra or {}).items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    return root
