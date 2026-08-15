"""Path setup and fixtures for the release-flow skill."""

import sys

from _support import ROOT

SKILL = ROOT / "skills" / "release" / "release-flow"
if str(SKILL) not in sys.path:
    sys.path.insert(0, str(SKILL))

RELEASE_BRANCH = "release-please--branches--main"


def pull_request(number=99, head=RELEASE_BRANCH, title="chore(main): release 0.3.0",
                 version="0.3.0"):
    return {
        "number": number,
        "title": title,
        "head": {"ref": head},
        "body": f"## 0.3.0\n\nSome notes.\n",
        "version": version,
    }
