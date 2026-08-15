"""VAL-001 to VAL-015 — requirement identifiers, and whether tests cover them."""

import tempfile
import unittest
from pathlib import Path

from _support import ROOT  # noqa: F401
from lib.validators.specs import collect_requirements, validate_specs

PAGE = """# Specification — Example (`EX`)

Belongs to the **substrate** capability.

- **EX-001** The first thing.
- **EX-002** The second thing.
"""


class Tree(unittest.TestCase):
    def build(self, pages, tests=None):
        root = Path(tempfile.mkdtemp())
        (root / "docs" / "spec").mkdir(parents=True)
        for name, text in pages.items():
            (root / "docs" / "spec" / name).write_text(text)
        (root / "tests").mkdir()
        for name, text in (tests or {}).items():
            (root / "tests" / name).write_text(text)
        return root


class TestCollecting(Tree):
    def test_it_finds_declared_requirements(self):  # VAL-001
        found = collect_requirements(self.build({"ex.md": PAGE}))
        self.assertEqual({r.identifier for r in found}, {"EX-001", "EX-002"})

    def test_prose_mentioning_an_identifier_is_not_a_declaration(self):  # VAL-001
        page = PAGE + "\nSee EX-001 for details, and **EX-003** in passing.\n"
        found = collect_requirements(self.build({"ex.md": page}))
        self.assertNotIn("EX-003", {r.identifier for r in found})

    def test_a_requirement_knows_its_page(self):  # VAL-011
        found = collect_requirements(self.build({"ex.md": PAGE}))
        self.assertTrue(next(iter(found)).page.endswith("ex.md"))

    def test_gaps_in_numbering_are_fine(self):  # VAL-005
        page = PAGE.replace("EX-002", "EX-050")
        problems = validate_specs(self.build({"ex.md": page}, {"t.py": "# EX-001 EX-050"}))
        self.assertEqual(problems, [])


class TestUniqueness(Tree):
    def test_a_duplicate_identifier_is_reported(self):  # VAL-002
        root = self.build({"a.md": PAGE, "b.md": PAGE})
        self.assertTrue(any("EX-001" in p for p in validate_specs(root)))

    def test_the_duplicate_report_names_both_pages(self):  # VAL-003
        root = self.build({"a.md": PAGE, "b.md": PAGE})
        message = " ".join(validate_specs(root))
        self.assertIn("a.md", message)
        self.assertIn("b.md", message)


class TestAreaConsistency(Tree):
    def test_a_requirement_outside_the_page_area_is_reported(self):  # VAL-004
        page = PAGE + "- **ZZ-001** Belongs elsewhere.\n"
        self.assertTrue(any("ZZ-001" in p for p in validate_specs(self.build({"ex.md": page}))))

    def test_a_page_with_no_declared_area_is_reported(self):  # VAL-004
        page = "# Specification — Example\n\n- **EX-001** A thing.\n"
        self.assertTrue(any("area" in p.lower() for p in validate_specs(self.build({"ex.md": page}))))


class TestCoverage(Tree):
    def test_a_requirement_named_in_a_test_is_covered(self):  # VAL-010
        root = self.build({"ex.md": PAGE}, {"t.py": "def test_x():  # EX-001\n    pass\n"})
        self.assertTrue(all("EX-001" not in p for p in validate_specs(root)))

    def test_a_requirement_named_in_a_docstring_is_covered(self):  # VAL-010
        root = self.build({"ex.md": PAGE}, {"t.py": '"""EX-001 and EX-002."""\n'})
        self.assertEqual(validate_specs(root), [])

    def test_an_uncovered_requirement_is_reported(self):  # VAL-011
        root = self.build({"ex.md": PAGE}, {"t.py": "# EX-001\n"})
        self.assertTrue(any("EX-002" in p for p in validate_specs(root)))

    def test_the_report_names_the_page(self):  # VAL-011
        root = self.build({"ex.md": PAGE}, {"t.py": "# EX-001\n"})
        self.assertTrue(any("ex.md" in p for p in validate_specs(root) if "EX-002" in p))

    def test_every_uncovered_requirement_is_reported_not_just_the_first(self):
        root = self.build({"ex.md": PAGE}, {"t.py": "# nothing\n"})
        problems = " ".join(validate_specs(root))
        self.assertIn("EX-001", problems)
        self.assertIn("EX-002", problems)


class TestManualExemption(Tree):
    def test_a_manual_requirement_needs_no_test(self):  # VAL-012
        page = PAGE.replace("The second thing.", "The second thing. *(manual: needs a device.)*")
        root = self.build({"ex.md": page}, {"t.py": "# EX-001\n"})
        self.assertEqual(validate_specs(root), [])

    def test_a_manual_marker_without_a_reason_is_reported(self):  # VAL-013
        page = PAGE.replace("The second thing.", "The second thing. *(manual)*")
        root = self.build({"ex.md": page}, {"t.py": "# EX-001\n"})
        self.assertTrue(any("EX-002" in p for p in validate_specs(root)))

    def test_an_empty_reason_is_reported(self):  # VAL-013
        page = PAGE.replace("The second thing.", "The second thing. *(manual: )*")
        root = self.build({"ex.md": page}, {"t.py": "# EX-001\n"})
        self.assertTrue(any("EX-002" in p for p in validate_specs(root)))


class TestOrphanedReferences(Tree):
    def test_a_test_citing_an_unknown_requirement_is_reported(self):  # VAL-014
        root = self.build({"ex.md": PAGE}, {"t.py": "# EX-001 EX-002 EX-999\n"})
        self.assertTrue(any("EX-999" in p for p in validate_specs(root)))

    def test_a_known_requirement_is_not_reported_as_orphaned(self):  # VAL-014
        root = self.build({"ex.md": PAGE}, {"t.py": "# EX-001 EX-002\n"})
        self.assertEqual(validate_specs(root), [])


class TestTheSummary(Tree):
    def test_it_counts_requirements_covered_and_manual(self):  # VAL-015
        page = PAGE.replace("The second thing.", "The second thing. *(manual: a device.)*")
        root = self.build({"ex.md": page}, {"t.py": "# EX-001\n"})
        from lib.validators.specs import summarise

        summary = summarise(root)
        self.assertEqual((summary.total, summary.covered, summary.manual), (2, 1, 1))


if __name__ == "__main__":
    unittest.main()


class TestPlannedPages(Tree):
    """VAL-016 to VAL-018 — a specification written ahead of its implementation."""

    PLANNED = PAGE.replace(
        "Belongs to the **substrate** capability.",
        "Belongs to the **substrate** capability.\n\n> **Status — planned (#42).**",
    )

    def test_a_planned_page_needs_no_tests(self):  # VAL-016
        self.assertEqual(validate_specs(self.build({"ex.md": self.PLANNED})), [])

    def test_a_planned_marker_without_an_issue_is_reported(self):  # VAL-017
        page = self.PLANNED.replace("planned (#42)", "planned")
        self.assertTrue(any("planned" in p.lower() for p in validate_specs(self.build({"ex.md": page}))))

    def test_planned_requirements_are_counted_separately(self):  # VAL-018
        from lib.validators.specs import summarise

        summary = summarise(self.build({"ex.md": self.PLANNED}))
        self.assertEqual((summary.total, summary.planned, summary.covered), (2, 2, 0))

    def test_an_implemented_page_is_still_checked(self):  # VAL-016
        root = self.build({"ex.md": PAGE}, {"t.py": "# EX-001\n"})
        self.assertTrue(any("EX-002" in p for p in validate_specs(root)))


class TestMultiLineRequirements(Tree):
    """A requirement's text runs to the end of its list item.

    Reading only the first line missed every `*(manual: …)*` marker that had
    wrapped — which was most of them, since the marker goes at the end of a
    sentence and the sentence is usually long enough to wrap. Six requirements
    across four pages were silently treated as needing coverage.
    """

    WRAPPED = """# Specification — Example (`EX`)

Belongs to the **substrate** capability.

- **EX-001** A requirement whose sentence runs on for a while and therefore
  wraps onto a second line. *(manual: needs a device.)*
- **EX-002** A short one.
"""

    def test_a_wrapped_manual_marker_is_seen(self):  # VAL-012
        root = self.build({"ex.md": self.WRAPPED}, {"t.py": "# EX-002\n"})
        self.assertEqual(validate_specs(root), [])

    def test_its_reason_is_captured(self):  # VAL-012
        found = {r.identifier: r for r in collect_requirements(self.build({"ex.md": self.WRAPPED}))}
        self.assertEqual(found["EX-001"].reason, "needs a device.")

    def test_a_following_requirement_is_still_its_own(self):  # VAL-001
        found = collect_requirements(self.build({"ex.md": self.WRAPPED}))
        self.assertEqual({r.identifier for r in found}, {"EX-001", "EX-002"})

    def test_the_second_is_not_marked_manual_by_the_first(self):  # VAL-012
        found = {r.identifier: r for r in collect_requirements(self.build({"ex.md": self.WRAPPED}))}
        self.assertFalse(found["EX-002"].manual)

    def test_a_paragraph_after_the_list_does_not_extend_it(self):  # VAL-001
        page = self.WRAPPED + "\nThis prose is not part of EX-002. *(manual: no.)*\n"
        found = {r.identifier: r for r in collect_requirements(self.build({"ex.md": page}))}
        self.assertFalse(found["EX-002"].manual)
