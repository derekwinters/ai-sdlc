"""MS-010 to MS-035 — creating, editing, closing and reopening."""

import unittest

from _milestones import DEFAULT, milestone
from lib.fake_github import FakeGitHub
from milestone_ops import Milestones, MilestoneError


def ops(items=None):
    api = FakeGitHub(milestones=list(items if items is not None else DEFAULT))
    return Milestones(api), api


def refused(call, *args, **kwargs):
    try:
        call(*args, **kwargs)
    except MilestoneError as error:
        return str(error)
    raise AssertionError("expected a MilestoneError")


class TestCreating(unittest.TestCase):
    def test_a_milestone_is_created(self):  # MS-010
        milestones, _ = ops()
        milestones.create("v0.4")
        self.assertIsNotNone(milestones.find("v0.4"))

    def test_a_description_is_stored(self):  # MS-010
        milestones, _ = ops()
        milestones.create("v0.4", description="the next one")
        self.assertEqual(milestones.find("v0.4")["description"], "the next one")

    def test_a_due_date_is_stored(self):  # MS-010
        milestones, _ = ops()
        milestones.create("v0.4", due_on="2026-12-01T00:00:00Z")
        self.assertEqual(milestones.find("v0.4")["due_on"], "2026-12-01T00:00:00Z")

    def test_it_returns_the_new_milestone_with_its_number(self):  # MS-013
        milestones, _ = ops()
        created = milestones.create("v0.4")
        self.assertIsInstance(created["number"], int)

    def test_the_number_is_usable_immediately(self):  # MS-013
        milestones, _ = ops()
        created = milestones.create("v0.4")
        self.assertEqual(milestones.find("v0.4")["number"], created["number"])

    def test_a_duplicate_title_is_refused(self):  # MS-011
        milestones, _ = ops()
        self.assertIn("v0.2", refused(milestones.create, "v0.2 — Pipeline state"))

    def test_the_refusal_names_the_existing_number(self):  # MS-011
        milestones, _ = ops()
        self.assertIn("#2", refused(milestones.create, "v0.2 — Pipeline state"))

    def test_an_empty_title_is_refused(self):  # MS-012
        milestones, _ = ops()
        self.assertIn("title", refused(milestones.create, "").lower())

    def test_a_whitespace_title_is_refused(self):  # MS-012
        milestones, _ = ops()
        self.assertIn("title", refused(milestones.create, "   ").lower())

    def test_a_created_milestone_is_open(self):  # MS-014
        milestones, _ = ops()
        self.assertEqual(milestones.create("v0.4")["state"], "open")


class TestEditing(unittest.TestCase):
    def test_the_title_can_change(self):  # MS-020
        milestones, _ = ops()
        milestones.edit("v0.2", title="v0.2 — State and visibility")
        self.assertIsNotNone(milestones.find("v0.2 — State and visibility"))

    def test_the_description_can_change(self):  # MS-020
        milestones, _ = ops()
        milestones.edit("v0.2", description="new words")
        self.assertEqual(milestones.find("v0.2")["description"], "new words")

    def test_the_due_date_can_change(self):  # MS-020
        milestones, _ = ops()
        milestones.edit("v0.2", due_on="2026-12-01T00:00:00Z")
        self.assertEqual(milestones.find("v0.2")["due_on"], "2026-12-01T00:00:00Z")

    def test_an_omitted_field_is_unchanged(self):  # MS-021
        milestones, _ = ops()
        milestones.edit("v0.2", description="new words")
        self.assertEqual(milestones.find("v0.2")["title"], "v0.2 — Pipeline state")

    def test_editing_only_the_title_keeps_the_description(self):  # MS-021
        milestones, _ = ops()
        milestones.edit("v0.2", title="v0.2 — Renamed")
        self.assertEqual(milestones.find("v0.2")["description"], "state and visibility")

    def test_an_unknown_milestone_is_refused(self):  # MS-022
        milestones, _ = ops()
        self.assertIn("v9.9", refused(milestones.edit, "v9.9", title="x"))

    def test_renaming_onto_another_title_is_refused(self):  # MS-023
        milestones, _ = ops()
        self.assertIn("v0.3", refused(milestones.edit, "v0.2",
                                      title="v0.3 — The working loop"))

    def test_renaming_to_its_own_title_is_allowed(self):  # MS-023
        milestones, _ = ops()
        milestones.edit("v0.2", title="v0.2 — Pipeline state", description="same")
        self.assertEqual(milestones.find("v0.2")["description"], "same")

    def test_editing_the_description_preserves_a_marker(self):  # MS-024
        from milestone_ops import is_frozen

        milestones, _ = ops()
        milestones.edit("v0.3", description="new words")
        self.assertTrue(is_frozen(milestones.find("v0.3")["description"]))


class TestClosing(unittest.TestCase):
    def test_a_finished_milestone_closes(self):  # MS-030
        items = [milestone(1, "v0.1", open_issues=0)]
        milestones, _ = ops(items)
        milestones.close("v0.1")
        self.assertEqual(milestones.find("v0.1")["state"], "closed")

    def test_open_work_refuses_the_close(self):  # MS-030
        milestones, _ = ops()
        self.assertIn("4", refused(milestones.close, "v0.2"))

    def test_the_refusal_says_how_many_remain(self):  # MS-030
        milestones, _ = ops()
        self.assertIn("open issue", refused(milestones.close, "v0.2").lower())

    def test_force_closes_anyway(self):  # MS-031
        milestones, _ = ops()
        milestones.close("v0.2", force=True)
        self.assertEqual(milestones.find("v0.2")["state"], "closed")

    def test_force_reports_what_it_orphaned(self):  # MS-031
        milestones, _ = ops()
        self.assertEqual(milestones.close("v0.2", force=True).orphaned, 4)

    def test_closing_a_closed_milestone_is_a_no_op(self):  # MS-032
        milestones, api = ops()
        milestones.close("v0.1")
        self.assertEqual(milestones.find("v0.1")["state"], "closed")


class TestReopening(unittest.TestCase):
    def test_a_closed_milestone_reopens(self):  # MS-033
        milestones, _ = ops()
        milestones.reopen("v0.1")
        self.assertEqual(milestones.find("v0.1")["state"], "open")

    def test_reopening_an_open_milestone_is_a_no_op(self):  # MS-034
        milestones, _ = ops()
        milestones.reopen("v0.2")
        self.assertEqual(milestones.find("v0.2")["state"], "open")

    def test_reopening_an_unknown_milestone_is_refused(self):  # MS-033
        milestones, _ = ops()
        self.assertIn("v9.9", refused(milestones.reopen, "v9.9"))


class TestNothingDeletes(unittest.TestCase):
    """MS-035 — deleting detaches a milestone from every issue, irreversibly."""

    def test_no_delete_operation_is_exposed(self):
        milestones, _ = ops()
        for name in dir(milestones):
            self.assertNotIn("delete", name.lower())
            self.assertNotIn("remove", name.lower())

    def test_the_module_issues_no_delete_request(self):
        from _support import ROOT

        source = (ROOT / "skills" / "pipeline" / "milestone-ops" / "milestone_ops.py").read_text()
        self.assertNotIn('"DELETE"', source)


if __name__ == "__main__":
    unittest.main()
