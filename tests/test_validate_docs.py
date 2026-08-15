"""VAL-020 to VAL-023 — the specification and the published site agree."""

import tempfile
import unittest
from pathlib import Path

from _support import ROOT
from lib.validators.docs import validate_docs

NAV = """site_name: x
nav:
  - Home: index.md
  - Specification:
      - Example: spec/ex.md
"""

PAGE = "# Specification — Example (`EX`)\n\nBelongs to the **substrate** capability.\n"


class Tree(unittest.TestCase):
    def build(self, nav=NAV, pages=None):
        root = Path(tempfile.mkdtemp())
        (root / "docs" / "spec").mkdir(parents=True)
        (root / "docs" / "index.md").write_text("# x\n")
        (root / "mkdocs.yml").write_text(nav)
        for name, text in (pages or {"ex.md": PAGE}).items():
            (root / "docs" / "spec" / name).write_text(text)
        return root


class TestNavigationCoverage(Tree):
    def test_a_page_in_the_nav_is_fine(self):  # VAL-020
        self.assertEqual(validate_docs(self.build()), [])

    def test_a_spec_page_missing_from_the_nav_is_reported(self):  # VAL-020
        root = self.build(pages={"ex.md": PAGE, "other.md": PAGE.replace("EX", "OT")})
        self.assertTrue(any("other.md" in p for p in validate_docs(root)))

    def test_a_nav_entry_with_no_page_is_reported(self):  # VAL-021
        nav = NAV.replace("spec/ex.md", "spec/gone.md")
        root = self.build(nav=nav)
        self.assertTrue(any("gone.md" in p for p in validate_docs(root)))


class TestCapabilityOwnership(Tree):
    def test_a_page_states_its_capability(self):  # VAL-022
        self.assertEqual(validate_docs(self.build()), [])

    def test_a_page_without_one_is_reported(self):  # VAL-022
        root = self.build(pages={"ex.md": "# Specification — Example (`EX`)\n"})
        self.assertTrue(any("capability" in p.lower() for p in validate_docs(root)))

    def test_an_unknown_capability_is_reported(self):  # VAL-023
        page = PAGE.replace("**substrate**", "**wobble**")
        root = self.build(pages={"ex.md": page})
        self.assertTrue(any("wobble" in p for p in validate_docs(root)))


class TestTheRealRepository(unittest.TestCase):
    def test_this_repository_is_consistent(self):  # VAL-020
        self.assertEqual(validate_docs(ROOT), [])


if __name__ == "__main__":
    unittest.main()
