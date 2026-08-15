"""RULES-001 to RULES-022 — the shared rules fragment.

The fragment is prose, so these tests check the prose says what the pipeline
depends on it saying. A rule the fragment quietly loses is a rule that stops
being followed with no failing test anywhere.
"""

import unittest

from _adopt import repository
import _adopt  # noqa: F401
from _support import ROOT
from adopt import IMPORT_LINE, apply

FRAGMENT = ROOT / "house-rules" / "house-rules.md"
TEXT = FRAGMENT.read_text()
BODY = TEXT.lower()

PIN = "v0.4.0"
CONFIG = "capabilities:\n  - hygiene\n"


class TestTheFragment(unittest.TestCase):
    def test_it_exists_as_one_file(self):  # RULES-001
        self.assertTrue(FRAGMENT.is_file())

    def test_it_is_markdown(self):  # RULES-001
        self.assertTrue(TEXT.startswith("#"))

    def test_it_is_substantial_enough_to_be_worth_importing(self):  # RULES-001
        self.assertGreater(len(TEXT.splitlines()), 30)

    def test_it_is_installed_with_provenance(self):  # RULES-002
        root = repository({".claude/repo-config.yml": CONFIG})
        apply(root, pin=PIN)
        installed = root / ".claude" / "ai-sdlc" / "house-rules.md"
        self.assertIn("ai-sdlc:", installed.read_text())

    def test_the_installed_copy_matches_the_source(self):  # RULES-002
        root = repository({".claude/repo-config.yml": CONFIG})
        apply(root, pin=PIN)
        installed = (root / ".claude" / "ai-sdlc" / "house-rules.md").read_text()
        self.assertIn("House rules", installed)

    def test_verify_notices_when_it_is_edited(self):  # RULES-002
        from adopt import verify

        root = repository({".claude/repo-config.yml": CONFIG})
        apply(root, pin=PIN)
        (root / ".claude" / "ai-sdlc" / "house-rules.md").write_text("edited")
        self.assertFalse(verify(root, pin=PIN).ok)


class TestTheImport(unittest.TestCase):
    def adopted(self, files):
        root = repository(dict(files, **{".claude/repo-config.yml": CONFIG}))
        apply(root, pin=PIN)
        return root

    def test_the_import_line_is_appended(self):  # RULES-003
        root = self.adopted({"CLAUDE.md": "# Ours\n"})
        self.assertIn(IMPORT_LINE, (root / "CLAUDE.md").read_text())

    def test_the_existing_content_survives(self):  # RULES-003
        root = self.adopted({"CLAUDE.md": "# Ours\n\nSomething important.\n"})
        self.assertIn("Something important.", (root / "CLAUDE.md").read_text())

    def test_it_is_appended_not_prepended(self):  # RULES-003
        root = self.adopted({"CLAUDE.md": "# Ours\n"})
        text = (root / "CLAUDE.md").read_text()
        self.assertLess(text.index("# Ours"), text.index(IMPORT_LINE))

    def test_a_second_adoption_does_not_repeat_it(self):  # RULES-004
        root = self.adopted({"CLAUDE.md": "# Ours\n"})
        apply(root, pin=PIN)
        self.assertEqual((root / "CLAUDE.md").read_text().count(IMPORT_LINE), 1)

    def test_no_claude_md_means_none_is_created(self):  # RULES-005
        root = self.adopted({})
        self.assertFalse((root / "CLAUDE.md").exists())


class TestWhatItContains(unittest.TestCase):
    def test_conventional_commits(self):  # RULES-010
        self.assertIn("conventional commit", BODY)

    def test_the_squash_title_is_the_commit(self):  # RULES-010
        self.assertIn("squash title is the commit", BODY)

    def test_one_issue_one_pull_request(self):  # RULES-011
        self.assertIn("one issue, one branch, one pull request", BODY)

    def test_deviations_and_decisions(self):  # RULES-012
        self.assertIn("deviations and decisions", BODY)

    def test_it_says_when_to_include_an_item(self):  # RULES-012
        self.assertIn("might act differently", BODY)

    def test_the_plain_english_lead(self):  # RULES-013
        self.assertIn("plain-english lead", BODY)

    def test_documentation_in_the_same_pull_request(self):  # RULES-014
        self.assertIn("same pull request", BODY)

    def test_specification_before_code(self):  # RULES-015
        self.assertIn("specification before code", BODY)

    def test_a_failing_test_first(self):  # RULES-015
        self.assertIn("failing test before the implementation", BODY)

    def test_ask_rather_than_invent(self):  # RULES-016
        self.assertIn("ask rather than invent", BODY)

    def test_one_issue_per_human_task(self):  # RULES-017
        self.assertIn("one small issue per task", BODY)

    def test_it_warns_against_the_omnibus_issue(self):  # RULES-017
        self.assertIn("various setup needed", BODY)


class TestWhatItDoesNotContain(unittest.TestCase):
    def test_it_names_no_stack(self):  # RULES-020
        for stack in ("unity", "gradle", "pytest", "vitest", "dotnet", "fastapi", "react"):
            self.assertNotIn(stack, BODY, stack)

    def test_it_names_the_gate_where_one_exists(self):  # RULES-021
        """A rule CI enforces is named as enforced, not restated as advice."""
        for gate in ("pr-title-lint", "closing-keyword", "docs-gate"):
            self.assertIn(gate, BODY, gate)

    def test_enforced_rules_say_so(self):  # RULES-021
        self.assertIn("*enforced:", BODY)

    def test_it_names_no_specific_repository(self):  # RULES-022
        for repo in ("doggiehood", "chores-web", "roadtrip", "multiplying-frogs"):
            self.assertNotIn(repo, BODY, repo)

    def test_it_names_no_person(self):  # RULES-022
        for name in ("derek", "lucas", "connor"):
            self.assertNotIn(name, BODY, name)


if __name__ == "__main__":
    unittest.main()
