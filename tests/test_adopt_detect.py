"""ADOPT-001 to ADOPT-005 — working out what a repository is."""

import unittest

from _adopt import (KOTLIN_MARKER, MKDOCS_MARKER, NODE_MARKER, PYTHON_MARKER,
                    UNITY_MARKER, repository)
import _adopt  # noqa: F401
from adopt import detect


class TestDetection(unittest.TestCase):
    def test_a_python_repository(self):  # ADOPT-001
        self.assertIn("python", detect(repository({"pyproject.toml": PYTHON_MARKER})).profiles)

    def test_a_node_repository(self):  # ADOPT-001
        self.assertIn("node", detect(repository({"package.json": NODE_MARKER})).profiles)

    def test_a_unity_repository(self):  # ADOPT-001
        found = detect(repository({"ProjectSettings/ProjectVersion.txt": UNITY_MARKER}))
        self.assertIn("unity", found.profiles)

    def test_a_mkdocs_repository(self):  # ADOPT-001
        self.assertIn("mkdocs", detect(repository({"mkdocs.yml": MKDOCS_MARKER})).profiles)

    def test_a_kotlin_repository(self):  # ADOPT-001
        found = detect(repository({"build.gradle.kts": KOTLIN_MARKER}))
        self.assertIn("kotlin", found.profiles)

    def test_several_profiles_at_once(self):  # ADOPT-001
        found = detect(repository({"pyproject.toml": PYTHON_MARKER,
                                   "mkdocs.yml": MKDOCS_MARKER}))
        self.assertEqual(sorted(found.profiles), ["mkdocs", "python"])


class TestItOnlyProposes(unittest.TestCase):
    def test_detection_returns_a_proposal(self):  # ADOPT-002
        found = detect(repository({"pyproject.toml": PYTHON_MARKER}))
        self.assertTrue(found.proposed)

    def test_detection_writes_nothing(self):  # ADOPT-002
        root = repository({"pyproject.toml": PYTHON_MARKER})
        before = sorted(p.name for p in root.rglob("*"))
        detect(root)
        self.assertEqual(sorted(p.name for p in root.rglob("*")), before)

    def test_the_evidence_is_reported(self):  # ADOPT-004
        found = detect(repository({"pyproject.toml": PYTHON_MARKER}))
        self.assertIn("pyproject.toml", str(found.evidence))


class TestUndetectable(unittest.TestCase):
    def test_an_empty_repository_detects_nothing(self):  # ADOPT-003
        self.assertEqual(detect(repository()).profiles, [])

    def test_it_says_so_rather_than_guessing(self):  # ADOPT-003
        self.assertTrue(detect(repository()).undetectable)

    def test_a_detected_repository_is_not_undetectable(self):  # ADOPT-003
        self.assertFalse(detect(repository({"pyproject.toml": PYTHON_MARKER})).undetectable)


class TestExistingConfiguration(unittest.TestCase):
    def test_an_existing_config_wins(self):  # ADOPT-005
        root = repository({
            "pyproject.toml": PYTHON_MARKER,
            ".ai-sdlc/repo-config.yml": "capabilities:\n  - hygiene\nprofiles:\n  - unity\n",
        })
        self.assertEqual(detect(root).profiles, ["unity"])

    def test_it_is_reported_as_configured_not_detected(self):  # ADOPT-005
        root = repository({
            "pyproject.toml": PYTHON_MARKER,
            ".ai-sdlc/repo-config.yml": "capabilities:\n  - hygiene\nprofiles:\n  - unity\n",
        })
        self.assertFalse(detect(root).proposed)


if __name__ == "__main__":
    unittest.main()
