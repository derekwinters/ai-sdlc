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
from adopt import _files_for, apply
from lib.config import STATES

PERMISSIONS = re.compile(r"^permissions:\n((?:  \S+: \S+\n)+)", re.MULTILINE)
CALLS = re.compile(r"uses: derekwinters/ai-sdlc/\.github/workflows/(\S+?\.yml)@")

ALL_CAPABILITIES = ["hygiene", "consistency", "labels", "release", "pipeline"]
ALL_PROFILES = ["unity", "mkdocs", "python", "node", "kotlin"]


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
        profiles = ALL_PROFILES
        # A real configuration always carries these; the stub has to as well,
        # or it under-describes what `_files_for` is handed in production.
        labels = dict(STATES)
        fire = None
        # The skills-update caller follows the list, not a capability, so a
        # stub with an empty list would make ADOPT-069 fail for a workflow that
        # is in fact reachable.
        skills = ["ci-watch"]

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


class TestEveryReusableWorkflowIsReachable(unittest.TestCase):
    """ADOPT-069 — every reusable workflow ai-sdlc ships can be installed.

    Five defects of one shape reached a consumer before this test existed: an
    import with no file (#71), a workflow with no manifest (#75), a permissions
    block too narrow to start (#78), a profile that installed nothing (#81),
    and a dashboard nothing could install (#84).

    Each was fixed individually. This is the gate that makes a sixth fail here
    rather than in someone's repository: a reusable workflow that no capability
    or profile installs a caller for is unreachable, and unreachable is
    indistinguishable from absent.
    """

    def test_every_reusable_workflow_has_a_caller(self):  # ADOPT-069
        shipped = {
            path.name for path in (ROOT / ".github" / "workflows").glob("reusable-*.yml")
        }
        called = {called for _, _, called in _callers()}

        self.assertEqual(
            shipped - called, set(),
            "these reusable workflows are shipped but nothing installs a caller "
            "for them, so no consumer can reach them",
        )


class TestTheFireSecretsReachTheCaller(unittest.TestCase):
    """ADOPT-070 — a configured analysis routine is actually wired to one.

    `reusable-gatekeeper-comment.yml` declares `fire_endpoint` and
    `fire_token` as optional secrets and maps them to environment variables.
    Every caller `adopt` wrote omitted the `secrets:` block entirely, so both
    arrived empty and `Fire` treated the routine as unconfigured — silently,
    because GK-119 makes an unconfigured endpoint a notice rather than an
    error. Triage therefore never ran in `connor-multiplying-frogs` (#118).

    `fire.endpoint_secret` and `fire.token_secret` were the only way a
    repository could say which of its secrets to use, and nothing read them.
    """

    def _apply(self, fire):
        root = repository({
            ".claude/repo-config.yml": (
                "capabilities:\n  - hygiene\n  - consistency\n  - labels\n"
                "  - release\n  - pipeline\n"
                "owners:\n  - derekwinters\n"
                "dashboard_issue: 163\n" + fire
            ),
        })
        apply(root, pin=PIN)
        return (root / ".github/workflows/gatekeeper-comment.yml").read_text()

    def test_the_named_secrets_are_passed(self):  # ADOPT-070
        text = self._apply(
            "fire:\n  endpoint_secret: AI_TRIAGE_URL\n  token_secret: AI_TRIAGE_SECRET\n")
        self.assertIn("    secrets:", text)
        self.assertIn("fire_endpoint: ${{ secrets.AI_TRIAGE_URL }}", text)
        self.assertIn("fire_token: ${{ secrets.AI_TRIAGE_SECRET }}", text)

    def test_a_repository_naming_none_gets_no_block(self):  # ADOPT-070
        """A repository may legitimately run the pipeline with no routine.

        GK-119 keeps that a notice rather than an error, so the absence of a
        block has to stay the absence of a routine — not a broken wire.
        """
        self.assertNotIn("secrets:", self._apply(""))

    def test_the_secrets_are_named_never_inlined(self):  # ADOPT-070
        """`adopt` writes a reference; the value never passes through it."""
        text = self._apply(
            "fire:\n  endpoint_secret: AI_TRIAGE_URL\n  token_secret: AI_TRIAGE_SECRET\n")
        self.assertNotIn("secrets.fire_endpoint", text)
        for line in text.splitlines():
            if "fire_endpoint:" in line:
                self.assertIn("${{ secrets.", line)
