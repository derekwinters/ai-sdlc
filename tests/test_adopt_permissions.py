"""ADOPT-068 — a caller grants what the workflow it calls asks for.

A called workflow cannot be granted more than its caller has. Every caller
`_caller()` wrote said `contents: read`, and four of the six reusable workflows
request `issues: write`, so `labels` and the whole of `pipeline` failed with
`startup_failure` — no jobs, no logs, no annotation — the moment they were
adopted (#78).

These read the **real** reusable workflow files rather than a list written
here. A second copy of the permissions is exactly what drifted the first time.
"""

import re
import unittest

from _adopt import PIN, repository
from _support import ROOT
from adopt import _files_for

PERMISSIONS = re.compile(r"^permissions:\n((?:  \S+: \S+\n)+)", re.MULTILINE)
CALLS = re.compile(r"uses: derekwinters/ai-sdlc/\.github/workflows/(\S+?\.yml)@")

ALL_CAPABILITIES = ["hygiene", "consistency", "labels", "release", "pipeline"]


def _grants(text):
    """The permissions a workflow file declares, as {scope: level}."""
    match = PERMISSIONS.search(text)
    if not match:
        return {}
    return dict(
        line.strip().split(": ", 1) for line in match.group(1).splitlines() if line.strip()
    )


def _callers():
    """Every caller adoption would write, with the workflow each one calls."""
    class Config:
        capabilities = ALL_CAPABILITIES

    for path, body in _files_for(Config(), PIN).items():
        called = CALLS.search(body)
        if called:
            yield path, body, called.group(1)


class TestEveryCallerCanStart(unittest.TestCase):
    def test_there_are_callers_to_check(self):  # ADOPT-068
        # Guards the rest: a regex that silently matched nothing would make
        # every test below vacuously pass.
        self.assertGreaterEqual(len(list(_callers())), 4)

    def test_each_caller_grants_what_its_workflow_requests(self):  # ADOPT-068
        for path, body, called in _callers():
            with self.subTest(caller=path):
                reusable = (ROOT / ".github" / "workflows" / called).read_text()
                for scope, level in _grants(reusable).items():
                    self.assertEqual(
                        _grants(body).get(scope), level,
                        f"{path} grants {_grants(body).get(scope)!r} for {scope!r}, but "
                        f"{called} requests {level!r} — the run cannot start",
                    )

    def test_the_workflow_each_caller_names_exists(self):  # ADOPT-068
        for path, _, called in _callers():
            with self.subTest(caller=path):
                self.assertTrue((ROOT / ".github" / "workflows" / called).is_file())

    def test_a_caller_grants_nothing_beyond_what_is_needed(self):  # ADOPT-068
        # The other half: a caller handing out `issues: write` to a workflow
        # that only reads is a quiet widening of what the pipeline can do.
        for path, body, called in _callers():
            with self.subTest(caller=path):
                reusable = (ROOT / ".github" / "workflows" / called).read_text()
                self.assertEqual(set(_grants(body)), set(_grants(reusable)))


class TestTheLabelsCaller(unittest.TestCase):
    """The one that actually broke, kept as a named regression."""

    def test_it_grants_issues_write(self):  # ADOPT-068
        class Config:
            capabilities = ["labels"]

        body = _files_for(Config(), PIN)[".github/workflows/labels-sync.yml"]
        self.assertEqual(_grants(body).get("issues"), "write")


if __name__ == "__main__":
    unittest.main()
