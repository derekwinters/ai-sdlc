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


#: Fixture pins, as `(version, sha)`.
#:
#: Tuples rather than bare versions on purpose: a bare version sends `adopt`
#: to its resolver, and the resolver is the network. Passing the resolved pair
#: keeps every test offline by construction rather than by remembering to
#: inject a fake each time.
PIN = ("v0.4.0", "a" * 40)
OLDER_PIN = ("v0.1.0", "b" * 40)
NEWER_PIN = ("v0.5.0", "c" * 40)


def _no_network(version):
    """The resolver every test gets, so none can reach GitHub.

    `adopt` resolves a bare version over the network. That makes any test
    passing a bare version quietly network-dependent — it passes on a laptop
    and fails in CI, which is precisely how ten of them got through review
    (#72). Replacing the default here turns that into a loud, local failure
    naming the fix, rather than a red build twenty minutes later.

    A test that genuinely exercises resolution injects its own `resolver=`.
    """
    raise AssertionError(
        f"a test asked adopt to resolve {version!r} over the network. Pass a "
        f"(version, sha) pair — PIN, OLDER_PIN, NEWER_PIN — or inject "
        f"resolver=... if resolution is what you are testing."
    )


import adopt as _adopt  # noqa: E402 - the path is set up above

_adopt._git_ls_remote = _no_network
