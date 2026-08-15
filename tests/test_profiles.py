"""PROF-001 to PROF-013 — selecting profiles, and what mkdocs provides."""

import unittest
from pathlib import Path

from _adopt import MKDOCS_MARKER, PYTHON_MARKER, repository, PIN
import _adopt  # noqa: F401
from _support import ROOT
from adopt import apply, detect
from lib.config import ConfigError, PROFILES, parse_config

MKDOCS_WORKFLOW = ROOT / ".github" / "workflows" / "reusable-docs.yml"


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
            ".claude/repo-config.yml": "capabilities:\n  - hygiene\n",
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

        root = repository({".claude/repo-config.yml": "capabilities:\n  - hygiene\n"})
        planned = plan(root, pin=PIN)
        self.assertFalse([p for p in planned.creates if "docs" in p])

    def test_a_repository_with_a_docs_directory_is_still_not_gated(self):
        from adopt import plan

        root = repository({
            ".claude/repo-config.yml": "capabilities:\n  - hygiene\n",
            "docs/index.md": "# x\n",
        })
        planned = plan(root, pin=PIN)
        self.assertFalse([p for p in planned.creates if "docs" in p])


class TestTheMkdocsWorkflow(unittest.TestCase):
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

    def test_it_publishes_only_from_the_default_branch(self):  # PROF-012
        self.assertIn("refs/heads/main", self.text)

    def test_publication_needs_the_build(self):  # PROF-013
        self.assertIn("needs: build", self.text)

    def test_it_is_a_reusable_workflow(self):  # PROF-010
        self.assertIn("workflow_call", self.text)


if __name__ == "__main__":
    unittest.main()


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
            ".claude/repo-config.yml":
                "capabilities:\n  - hygiene\nprofiles:\n"
                + "".join(f"  - {p}\n" for p in profiles),
        })
        apply(root, pin=PIN)
        return root

    def test_mkdocs_installs_the_docs_gate(self):  # PROF-005
        root = self._apply(["mkdocs"])
        self.assertTrue((root / ".github/workflows/docs-gate.yml").is_file())

    def test_the_gate_calls_the_shared_workflow(self):  # PROF-005
        root = self._apply(["mkdocs"])
        text = (root / ".github/workflows/docs-gate.yml").read_text()
        self.assertIn("reusable-docs-gate.yml@", text)

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

    def test_an_unselected_profile_installs_nothing(self):  # PROF-005
        root = self._apply([])
        self.assertFalse((root / ".github/workflows/docs-gate.yml").exists())
