"""ADOPT-050 to ADOPT-054 — is this repository still what it says it is."""

import unittest

from _adopt import repository, NEWER_PIN, OLDER_PIN, PIN
import _adopt  # noqa: F401
from adopt import apply, verify

CONFIG = "capabilities:\n  - hygiene\n"


def adopted(files=None, pin=PIN):
    files = dict(files or {})
    files.setdefault(".ai-sdlc/repo-config.yml", CONFIG)
    root = repository(files)
    apply(root, pin=pin)
    return root


class TestAHealthyRepository(unittest.TestCase):
    def test_it_matches_its_pin(self):  # ADOPT-050
        self.assertTrue(verify(adopted(), pin=PIN).ok)

    def test_nothing_is_reported(self):  # ADOPT-050
        self.assertEqual(verify(adopted(), pin=PIN).problems, [])


class TestDrift(unittest.TestCase):
    def test_an_older_pin_is_reported(self):  # ADOPT-050
        result = verify(adopted(pin=OLDER_PIN), pin=PIN)
        self.assertFalse(result.ok)

    def test_the_report_names_both_versions(self):  # ADOPT-050
        result = verify(adopted(pin=OLDER_PIN), pin=PIN)
        self.assertIn("v0.1.0", " ".join(result.problems))

    def test_a_locally_edited_managed_file_is_reported(self):  # ADOPT-052
        root = adopted()
        (root / ".github/workflows/closing-keyword.yml").write_text("edited")
        self.assertFalse(verify(root, pin=PIN).ok)

    def test_the_edited_file_is_named(self):  # ADOPT-052
        root = adopted()
        (root / ".github/workflows/closing-keyword.yml").write_text("edited")
        self.assertIn("closing-keyword", " ".join(verify(root, pin=PIN).problems))

    def test_a_missing_managed_file_is_reported(self):  # ADOPT-052
        root = adopted()
        (root / ".github/workflows/closing-keyword.yml").unlink()
        self.assertFalse(verify(root, pin=PIN).ok)


class TestCapabilityDependencies(unittest.TestCase):
    def test_a_capability_without_its_dependencies_is_reported(self):  # ADOPT-051
        root = repository({".ai-sdlc/repo-config.yml": "capabilities:\n  - pipeline\n"})
        result = verify(root, pin=PIN)
        self.assertFalse(result.ok)

    def test_the_report_says_what_is_missing(self):  # ADOPT-051
        root = repository({".ai-sdlc/repo-config.yml": "capabilities:\n  - pipeline\n"})
        self.assertIn("hygiene", " ".join(verify(root, pin=PIN).problems))


class TestExceptionsAreVisible(unittest.TestCase):
    def test_a_conflict_is_reported_not_hidden(self):  # ADOPT-053
        root = adopted({".github/workflows/closing-keyword.yml": "theirs"})
        self.assertIn("closing-keyword", " ".join(verify(root, pin=PIN).problems))

    def test_a_repository_keeping_its_own_version_is_visibly_non_standard(self):  # ADOPT-053
        root = adopted({".github/workflows/closing-keyword.yml": "theirs"})
        self.assertFalse(verify(root, pin=PIN).ok)


class TestItWritesNothing(unittest.TestCase):
    def test_verifying_creates_no_file(self):  # ADOPT-054
        root = adopted()
        before = sorted(str(p) for p in root.rglob("*"))
        verify(root, pin=PIN)
        self.assertEqual(sorted(str(p) for p in root.rglob("*")), before)

    def test_verifying_modifies_no_file(self):  # ADOPT-054
        root = adopted()
        target = root / ".github/workflows/closing-keyword.yml"
        before = target.read_text()
        verify(root, pin=PIN)
        self.assertEqual(target.read_text(), before)


if __name__ == "__main__":
    unittest.main()
