"""ADOPT-020 to ADOPT-025 — deciding what may be written."""

import unittest

from _adopt import repository
import _adopt  # noqa: F401
from adopt import ABSENT, CONFLICT, CURRENT, STALE, classify, provenance_header, content_hash

PIN = "v0.4.0"


def managed(text, ref=PIN):
    """A file carrying provenance, as apply would have written it."""
    return provenance_header(ref, content_hash(text)) + text


class TestClassification(unittest.TestCase):
    def test_a_missing_file_is_absent(self):  # ADOPT-020
        root = repository()
        self.assertEqual(classify(root, "a.yml", "body", PIN), ABSENT)

    def test_a_managed_file_at_the_pin_is_current(self):  # ADOPT-021
        root = repository({"a.yml": managed("body")})
        self.assertEqual(classify(root, "a.yml", "body", PIN), CURRENT)

    def test_a_managed_file_from_an_earlier_pin_is_stale(self):  # ADOPT-022
        root = repository({"a.yml": managed("body", ref="v0.1.0")})
        self.assertEqual(classify(root, "a.yml", "body", PIN), STALE)

    def test_an_unmanaged_file_is_a_conflict(self):  # ADOPT-023
        root = repository({"a.yml": "somebody wrote this"})
        self.assertEqual(classify(root, "a.yml", "body", PIN), CONFLICT)

    def test_a_file_with_no_provenance_is_never_overwritten(self):  # ADOPT-023
        root = repository({"a.yml": "somebody wrote this"})
        self.assertNotIn(classify(root, "a.yml", "body", PIN), (CURRENT, STALE))


class TestLocalEdits(unittest.TestCase):
    """ADOPT-025 — an edited managed file is a conflict, not a stale file."""

    def test_an_edited_managed_file_is_a_conflict(self):
        root = repository({"a.yml": managed("body") + "\nlocal edit\n"})
        self.assertEqual(classify(root, "a.yml", "body", PIN), CONFLICT)

    def test_it_is_a_conflict_even_at_the_current_pin(self):
        root = repository({"a.yml": managed("body") + "\nedit\n"})
        self.assertNotEqual(classify(root, "a.yml", "body", PIN), CURRENT)

    def test_an_unedited_file_is_not_a_conflict(self):
        root = repository({"a.yml": managed("body")})
        self.assertNotEqual(classify(root, "a.yml", "body", PIN), CONFLICT)


class TestProvenance(unittest.TestCase):
    def test_it_records_the_source_repository(self):  # ADOPT-024
        self.assertIn("ai-sdlc", provenance_header(PIN, "abc"))

    def test_it_records_the_ref(self):  # ADOPT-024
        self.assertIn(PIN, provenance_header(PIN, "abc"))

    def test_it_records_the_content_hash(self):  # ADOPT-024
        self.assertIn("abc", provenance_header(PIN, "abc"))

    def test_it_is_a_comment(self):  # ADOPT-024
        for line in provenance_header(PIN, "abc").strip().splitlines():
            self.assertTrue(line.startswith("#"), line)

    def test_the_hash_is_stable(self):  # ADOPT-025
        self.assertEqual(content_hash("body"), content_hash("body"))

    def test_different_content_hashes_differently(self):  # ADOPT-025
        self.assertNotEqual(content_hash("body"), content_hash("other"))


if __name__ == "__main__":
    unittest.main()
