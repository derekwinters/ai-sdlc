"""PROF-001 to PROF-013 — selecting profiles, and what mkdocs provides."""

import unittest
from pathlib import Path

from _adopt import MKDOCS_MARKER, PYTHON_MARKER, repository, PIN
import _adopt  # noqa: F401
from _support import ROOT
from adopt import detect
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
