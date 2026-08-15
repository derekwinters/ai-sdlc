"""Path setup and a repository builder for the adopt skill."""

import sys
import tempfile
from pathlib import Path

from _support import ROOT

SKILL = ROOT / "skills" / "substrate" / "adopt"
if str(SKILL) not in sys.path:
    sys.path.insert(0, str(SKILL))


def repository(files=None):
    """A throwaway repository containing `files` (path -> text)."""
    root = Path(tempfile.mkdtemp())
    for name, text in (files or {}).items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    return root


PYTHON_MARKER = "[project]\nname = 'x'\n"
NODE_MARKER = '{"name": "x"}\n'
UNITY_MARKER = "m_EditorVersion: 2022.3.0f1\n"
MKDOCS_MARKER = "site_name: x\n"
KOTLIN_MARKER = "plugins { id 'org.jetbrains.kotlin.jvm' }\n"
