"""PROF-001 to PROF-013 — selecting profiles, and what mkdocs provides."""

import unittest
from pathlib import Path

from _adopt import MKDOCS_MARKER, PYTHON_MARKER, repository, PIN
import _adopt  # noqa: F401
from _support import ROOT
from adopt import apply, detect
from lib.config import ConfigError, PROFILES, parse_config

MKDOCS_WORKFLOW = ROOT / ".github" / "workflows" / "reusable-docs-build.yml"


class TestSelection(unittest.TestCase):
    def test_a_profile_is_enabled_by_configuration(self):  # PROF-001
        config = parse_config("capabilities:\n  - hygiene\nprofiles:\n  - mkdocs")
        self.assertEqual(config.profiles, ["mkdocs"])

    def test_nothing_is_enabled_by_default(self):  # PROF-001
        self.assertEqual(parse_config("capabilities:\n  - hygiene").profiles, [])

    def test_detection_only_proposes(self):  # PROF-002
        found = detect(repository({"mkdocs.yml": MKDOCS_MARKER}))
        self.assertTrue(found.proposed)

    def test_a_detected_profile_is_not_thereby_enabled(self):  # PROF-002
        root = repository({
            "mkdocs.yml": MKDOCS_MARKER,
            ".ai-sdlc/repo-config.yml": "capabilities:\n  - hygiene\n",
        })
        from lib.config import load

        self.assertEqual(load(root=root).profiles, [])

    def test_an_unknown_profile_is_refused(self):  # PROF-003
        with self.assertRaises(ConfigError):
            parse_config("capabilities:\n  - hygiene\nprofiles:\n  - wobble")

    def test_mkdocs_is_a_known_profile(self):  # PROF-003
        self.assertIn("mkdocs", PROFILES)


class TestInertness(unittest.TestCase):
    """PROF-004 — installing ai-sdlc must not run a gate nobody asked for."""

    def test_an_unselected_profile_adds_no_files(self):
        from adopt import plan

        root = repository({".ai-sdlc/repo-config.yml": "capabilities:\n  - hygiene\n"})
        planned = plan(root, pin=PIN)
        self.assertFalse([p for p in planned.creates if "docs" in p])

    def test_a_repository_with_a_docs_directory_is_still_not_gated(self):
        from adopt import plan

        root = repository({
            ".ai-sdlc/repo-config.yml": "capabilities:\n  - hygiene\n",
            "docs/index.md": "# x\n",
        })
        planned = plan(root, pin=PIN)
        self.assertFalse([p for p in planned.creates if "docs" in p])


class TestTheMkdocsBuildWorkflow(unittest.TestCase):
    """PROF-010, PROF-011 — the profile's strict build.

    It builds and stops. The publisher it used to be bundled with is gone
    (#100): publishing is repository-specific, and bundling the two meant the
    build could not be installed without the publisher, so neither was.
    """

    def setUp(self):
        self.text = MKDOCS_WORKFLOW.read_text()

    def test_it_exists(self):  # PROF-010
        self.assertTrue(MKDOCS_WORKFLOW.is_file())

    def test_it_builds_strictly(self):  # PROF-010, PROF-011
        self.assertIn("--strict", self.text)

    def test_it_declares_no_trigger_of_its_own(self):  # PROF-010
        """A reusable workflow is trigger-agnostic.

        `pull_request` cannot be centralised — it must be declared in the
        repository the pull request is opened against — so the caller owns it
        and this file must not.
        """
        self.assertNotIn("pull_request:", self.text)

    def test_it_is_a_reusable_workflow(self):  # PROF-010
        self.assertIn("workflow_call", self.text)

    def test_it_publishes_nothing(self):  # PROF-012
        """The profile installs no publisher.

        Asserted on the mechanisms rather than the intent, because every one of
        these is a way to publish that a reviewer might add back without
        thinking of it as adding a publisher.
        """
        for mechanism in (
            "gh-deploy", "mike deploy", "gh-pages",
            "upload-pages-artifact", "configure-pages", "deploy-pages",
        ):
            self.assertNotIn(mechanism, self.text)

    def test_it_asks_for_no_write_access(self):  # PROF-012
        """A build needs to read. Anything more is a publisher in waiting."""
        self.assertIn("contents: read", self.text)
        for grant in ("contents: write", "pages: write", "id-token: write"):
            self.assertNotIn(grant, self.text)


class TestASelectedProfileInstallsItsFiles(unittest.TestCase):
    """PROF-005 — selecting a profile installs the profile's files.

    `mkdocs` was specified in full — a strict build check, a documentation
    reconciliation gate — and installed nothing, because `_files_for` handled
    capabilities and never looked at profiles. PROF-004 says an absent
    profile's files are "inert rather than an error", which made a profile that
    installs nothing indistinguishable from one that is working.

    Fourth instance of a capability or profile shipping incomplete: #71, #75,
    #78, this.
    """

    def _apply(self, profiles):
        root = repository({
            ".ai-sdlc/repo-config.yml":
                "capabilities:\n  - hygiene\nprofiles:\n"
                + "".join(f"  - {p}\n" for p in profiles),
        })
        apply(root, pin=PIN)
        return root

    def test_mkdocs_installs_the_docs_gate(self):  # PROF-005
        root = self._apply(["mkdocs"])
        self.assertTrue((root / ".github/workflows/docs-gate.yml").is_file())

    def test_the_gate_calls_the_shared_action(self):  # PROF-005
        root = self._apply(["mkdocs"])
        text = (root / ".github/workflows/docs-gate.yml").read_text()
        self.assertIn(".github/actions/docs-gate@", text)

    def test_the_gate_runs_on_pull_request(self):  # PROF-005
        root = self._apply(["mkdocs"])
        text = (root / ".github/workflows/docs-gate.yml").read_text()
        self.assertIn("pull_request:", text)

    def test_labeled_is_among_the_triggers(self):  # PROF-005
        # Load-bearing: adding `skip-docs` to an already-failed pull request
        # has to start a fresh run, or the escape hatch does not work.
        root = self._apply(["mkdocs"])
        text = (root / ".github/workflows/docs-gate.yml").read_text()
        self.assertIn("labeled", text)

    def test_mkdocs_installs_the_strict_build(self):  # PROF-005, PROF-010
        root = self._apply(["mkdocs"])
        self.assertTrue((root / ".github/workflows/docs-build.yml").is_file())

    def test_the_build_calls_the_shared_workflow(self):  # PROF-005
        root = self._apply(["mkdocs"])
        text = (root / ".github/workflows/docs-build.yml").read_text()
        self.assertIn("reusable-docs-build.yml@", text)

    def test_the_build_runs_on_pull_request(self):  # PROF-005, PROF-010
        root = self._apply(["mkdocs"])
        text = (root / ".github/workflows/docs-build.yml").read_text()
        self.assertIn("pull_request:", text)

    def test_the_build_caller_grants_only_read(self):  # PROF-005
        """ADOPT-068 — exactly what the called workflow asks for.

        Too little and the run fails as `startup_failure`, with no jobs and no
        annotation. Too much and adoption quietly widens what a caller may do.
        """
        root = self._apply(["mkdocs"])
        text = (root / ".github/workflows/docs-build.yml").read_text()
        self.assertIn("contents: read", text)
        # Asserted on the grants themselves rather than on the bare substring
        # "write", which also occurs in the prose explaining that `apply`
        # rewrites the pin.
        for grant in ("contents: write", "pages: write", "id-token: write",
                      "issues: write"):
            self.assertNotIn(grant, text)

    def test_an_unselected_profile_installs_nothing(self):  # PROF-005
        root = self._apply([])
        self.assertFalse((root / ".github/workflows/docs-gate.yml").exists())
        self.assertFalse((root / ".github/workflows/docs-build.yml").exists())


class TestTheDocsArePublishedFromABranch(unittest.TestCase):
    """PROF-014 — the site is published by pushing `gh-pages`, not an artifact.

    Three third-party actions became none. That matters here because this
    repository requires actions to be SHA-pinned *and the policy reaches inside
    composite actions*: `upload-pages-artifact@v3` calls
    `actions/upload-artifact@v4` unpinned in its own `action.yml`, so the step
    was refused before it ran (#64, #93). Moving to v5 fixed it by depending on
    someone else's pinning discipline. A branch push has no such surface.
    """

    WORKFLOW = ROOT / ".github" / "workflows" / "docs.yml"

    def setUp(self):
        raw = self.WORKFLOW.read_text()
        # Comments are stripped before asserting. The comment explaining *why*
        # the Pages actions were removed names them, and a test that cannot
        # tell an explanation from a dependency would forbid explaining
        # anything — which is worse than the rule it enforces.
        self.text = "\n".join(
            line for line in raw.splitlines() if not line.lstrip().startswith("#")
        )

    def test_no_pages_action_is_used(self):  # PROF-014
        for action in ("upload-pages-artifact", "configure-pages", "deploy-pages"):
            with self.subTest(action=action):
                self.assertNotIn(action, self.text)

    def test_it_pushes_gh_pages(self):  # PROF-014
        self.assertIn("gh-pages", self.text)

    def test_it_can_write_to_the_repository(self):  # PROF-014
        # Pushing a branch needs it; the artifact pipeline did not.
        self.assertIn("contents: write", self.text)

    def test_it_no_longer_asks_for_pages_or_id_token(self):  # PROF-014
        # Grants that only the artifact pipeline needed. Leaving them behind
        # would be a permission nobody can explain a year from now.
        self.assertNotIn("pages: write", self.text)
        self.assertNotIn("id-token: write", self.text)

    def test_publication_is_restricted_to_main(self):  # PROF-013
        self.assertIn("github.ref == 'refs/heads/main'", self.text)

    def test_the_strict_build_still_runs(self):  # PROF-013
        self.assertIn("mkdocs build --strict", self.text)

    def test_publishing_cannot_precede_the_build(self):  # PROF-013
        # A deploy that ran before, or instead of, the strict build would
        # publish exactly the broken site the gate exists to catch.
        self.assertLess(
            self.text.index("mkdocs build --strict"),
            self.text.index("mike deploy"),
        )


class TestTheDocsAreVersioned(unittest.TestCase):
    """PROF-015 — the published site is versioned with `mike`.

    Consumers pin ai-sdlc by version and read its specification to know what
    that version does. An unversioned site answers only for `main`, so a
    repository pinned three releases back is reading documentation for code it
    is not running — and has no way to tell.
    """

    WORKFLOW = ROOT / ".github" / "workflows" / "docs.yml"
    REQUIREMENTS = ROOT / "docs" / "requirements.txt"
    MKDOCS = ROOT / "mkdocs.yml"

    def setUp(self):
        raw = self.WORKFLOW.read_text()
        self.text = "\n".join(
            line for line in raw.splitlines() if not line.lstrip().startswith("#")
        )

    def test_mike_is_a_pinned_dependency(self):  # PROF-015
        requirements = self.REQUIREMENTS.read_text()
        self.assertIn("mike==", requirements)

    def test_the_theme_offers_the_version_selector(self):  # PROF-015
        # Without this the versions exist but nobody can switch between them.
        config = self.MKDOCS.read_text()
        self.assertIn("provider: mike", config)

    def test_publishing_uses_mike(self):  # PROF-015
        self.assertIn("mike deploy", self.text)

    def test_the_newest_version_is_aliased(self):  # PROF-015
        # A reader arriving at the bare URL must land somewhere current.
        self.assertIn("latest", self.text)

    def test_the_version_is_not_hard_coded(self):  # PROF-015
        # A literal here is a second copy of the version, and second copies
        # drift — /VERSION has been wrong for eight releases (#97).
        self.assertNotIn("mike deploy --push --update-aliases 0.4", self.text)

    def test_the_version_comes_from_the_release_manifest(self):  # PROF-015
        self.assertIn("release-please/manifest.json", self.text)

    def test_it_still_publishes_only_from_main(self):  # PROF-013
        self.assertIn("github.ref == 'refs/heads/main'", self.text)


if __name__ == "__main__":
    unittest.main()
