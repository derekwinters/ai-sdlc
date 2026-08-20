"""MS-001 to MS-045 — stated, not run.

`milestone-ops` was `class Milestones(api)`. In ai-sdlc's own tests the caller
handing over the client was the test; in `connor-multiplying-frogs`, which
installed the skill, there was no caller at all (#153).

Every rule it enforced is now an instruction an agent applies through
`github-api`, and what a test can hold is that the skill states it. That is
weaker than executing it, and it is the cost of the conversion; what it buys is
a rule that works where the class did not.
"""

import unittest

from _milestones import stated


class TestReading(unittest.TestCase):
    def test_what_a_listing_carries(self):  # MS-001
        text = stated()
        for field in ("number", "title", "state", "open and closed issue counts"):
            with self.subTest(field=field):
                self.assertIn(field, text)

    def test_the_order_is_stable(self):  # MS-002
        self.assertIn("by number", stated())

    def test_an_exact_title_matches(self):  # MS-003
        self.assertIn("exact title** matches", stated())

    def test_a_unique_prefix_matches(self):  # MS-004
        self.assertIn("unique prefix** matches", stated())

    def test_an_ambiguous_prefix_matches_nothing(self):  # MS-005
        self.assertIn("ambiguous prefix matches nothing", stated())

    def test_closed_milestones_are_searched_too(self):  # MS-006
        self.assertIn("search open **and** closed", stated())

    def test_remaining_work_is_readable(self):  # MS-007
        self.assertIn("how much work remains", stated())


class TestCreating(unittest.TestCase):
    def test_the_fields_a_milestone_may_have(self):  # MS-010
        self.assertIn("a title, and may have a description and a due date", stated())

    def test_a_duplicate_title_is_refused(self):  # MS-011
        self.assertIn("title that already exists is refused", stated())

    def test_an_empty_title_is_refused(self):  # MS-012
        self.assertIn("empty title is refused", stated())

    def test_the_assigned_number_is_reported(self):  # MS-013
        self.assertIn("with its assigned number", stated())

    def test_nothing_is_created_closed(self):  # MS-014
        self.assertIn("never create a milestone closed", stated())


class TestEditing(unittest.TestCase):
    def test_what_may_change(self):  # MS-020
        self.assertIn("title, description and due date may all change", stated())

    def test_an_omitted_field_is_left_alone(self):  # MS-021
        self.assertIn("omitted field is left unchanged", stated())

    def test_editing_something_absent_is_refused_by_name(self):  # MS-022
        self.assertIn("naming what was searched for", stated())

    def test_renaming_onto_an_existing_title_is_refused(self):  # MS-023
        self.assertIn("renaming to a title another milestone already has is refused", stated())

    def test_markers_survive_a_description_edit(self):  # MS-024
        self.assertIn("preserves the markers you did not mention", stated())


class TestClosingAndReopening(unittest.TestCase):
    def test_closing_refuses_while_work_remains(self):  # MS-030
        self.assertIn("refuses while open issues remain, and says how many", stated())

    def test_forcing_reports_what_it_orphaned(self):  # MS-031
        self.assertIn("how many issues it orphaned", stated())

    def test_repeating_either_is_a_no_op(self):  # MS-032, MS-034
        self.assertIn("no-op, not an error", stated())

    def test_reopening_is_always_available(self):  # MS-033
        self.assertIn("reopening a closed milestone is always available", stated())

    def test_nothing_deletes_a_milestone(self):  # MS-035
        """Deleting detaches it from every issue that carried it. `API-041`
        says the client has no such operation; this says why."""
        text = stated()
        self.assertIn("nothing deletes a milestone", text)
        self.assertIn("cannot be undone", text)


class TestTheMarkers(unittest.TestCase):
    def test_focus_is_a_prefix(self):  # MS-040
        self.assertIn("`focus.` marks the focus when the description **begins** with it", stated())

    def test_exactly_one_milestone_is_the_focus(self):  # MS-041
        text = stated()
        self.assertIn("exactly one milestone is the focus", text)
        self.assertIn("clearing it from every other", text)

    def test_frozen_means_scope_is_settled(self):  # MS-042
        self.assertIn("scope is settled", stated())

    def test_markers_are_read_case_insensitively(self):  # MS-043
        self.assertIn("case-insensitively", stated())

    def test_setting_or_clearing_preserves_the_prose(self):  # MS-044, MS-045
        self.assertIn("preserves the prose around it", stated())


if __name__ == "__main__":
    unittest.main()
