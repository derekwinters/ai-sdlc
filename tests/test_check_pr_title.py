"""Conventional Commits validation for pull request titles.

The squash-merge title becomes the one commit release-please parses, so an
unparseable title is not a style problem: it silently produces no release
entry. These tests are the definition of what is parseable.
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / ".github" / "scripts"))

from check_pr_title import VALID_TYPES, check  # noqa: E402


class TestAcceptedTitles(unittest.TestCase):
    def test_a_plain_type_and_description(self):
        self.assertIsNone(check("feat: add the gatekeeper"))

    def test_every_valid_type_is_accepted(self):
        for kind in VALID_TYPES:
            self.assertIsNone(check(f"{kind}: something happened"), kind)

    def test_a_scope_is_allowed(self):
        self.assertIsNone(check("fix(gatekeeper): stop double-applying a command"))

    def test_a_scope_may_contain_dashes_and_dots(self):
        self.assertIsNone(check("ci(pr-title.lint): tighten the pattern"))

    def test_a_breaking_change_marker_is_allowed(self):
        self.assertIsNone(check("feat!: drop the reconcile sweep"))

    def test_a_breaking_change_marker_with_a_scope_is_allowed(self):
        self.assertIsNone(check("feat(gk)!: require an owner list"))

    def test_a_release_please_title_is_accepted(self):
        self.assertIsNone(check("chore(main): release 0.1.0"))


class TestRejectedTitles(unittest.TestCase):
    def test_no_type_at_all(self):
        self.assertIsNotNone(check("Fix login bug"))

    def test_an_unknown_type(self):
        self.assertIsNotNone(check("update: change the docs"))

    def test_a_missing_description(self):
        self.assertIsNotNone(check("feat:"))

    def test_a_description_of_only_spaces(self):
        self.assertIsNotNone(check("feat:    "))

    def test_a_missing_colon(self):
        self.assertIsNotNone(check("feat add the gatekeeper"))

    def test_an_empty_scope(self):
        self.assertIsNotNone(check("feat(): add the gatekeeper"))

    def test_an_empty_title(self):
        self.assertIsNotNone(check(""))

    def test_a_type_is_case_sensitive(self):
        self.assertIsNotNone(check("Feat: add the gatekeeper"))


class TestTheMessage(unittest.TestCase):
    def test_the_failure_names_the_offending_title(self):
        self.assertIn("Fix login bug", check("Fix login bug"))

    def test_the_failure_lists_the_valid_types(self):
        message = check("Fix login bug")
        for kind in VALID_TYPES:
            self.assertIn(kind, message)

    def test_an_unknown_type_is_told_what_is_wrong_with_it(self):
        self.assertIn("update", check("update: change the docs"))


if __name__ == "__main__":
    unittest.main()
