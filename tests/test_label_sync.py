"""LBL-020 to LBL-028 — applying a taxonomy to a repository."""

import unittest

import _labels  # noqa: F401
from label_sync import Label, apply_labels
from lib.fake_github import FakeGitHub


def label(name, color="1D76DB", description="a thing"):
    return Label(name=name, color=color, description=description, source="labels.core.yml")


def api(existing=()):
    return FakeGitHub(labels=list(existing))


def existing(name, color="1D76DB", description="a thing"):
    return {"name": name, "color": color, "description": description}


class TestCreating(unittest.TestCase):
    def test_a_missing_label_is_created(self):  # LBL-020
        github = api()
        result = apply_labels(github, [label("ai-triage")], [])
        self.assertEqual(result.created, ["ai-triage"])

    def test_it_exists_afterwards(self):  # LBL-020
        github = api()
        apply_labels(github, [label("ai-triage")], [])
        self.assertIn("ai-triage", [l["name"] for l in github.labels()])

    def test_its_colour_and_description_are_set(self):  # LBL-020
        github = api()
        apply_labels(github, [label("ai-triage", "ABCDEF", "words")], [])
        made = [l for l in github.labels() if l["name"] == "ai-triage"][0]
        self.assertEqual((made["color"], made["description"]), ("ABCDEF", "words"))


class TestUpdating(unittest.TestCase):
    def test_a_changed_colour_is_updated(self):  # LBL-021
        github = api([existing("ai-triage", color="000000")])
        result = apply_labels(github, [label("ai-triage", color="ABCDEF")], [])
        self.assertEqual(result.updated, ["ai-triage"])

    def test_a_changed_description_is_updated(self):  # LBL-021
        github = api([existing("ai-triage", description="old")])
        result = apply_labels(github, [label("ai-triage", description="new")], [])
        self.assertEqual(result.updated, ["ai-triage"])

    def test_the_new_values_are_stored(self):  # LBL-021
        github = api([existing("ai-triage", description="old")])
        apply_labels(github, [label("ai-triage", description="new")], [])
        found = [l for l in github.labels() if l["name"] == "ai-triage"][0]
        self.assertEqual(found["description"], "new")

    def test_colour_comparison_ignores_case(self):  # LBL-021
        github = api([existing("ai-triage", color="abcdef")])
        result = apply_labels(github, [label("ai-triage", color="ABCDEF")], [])
        self.assertEqual(result.updated, [])


class TestLeavingAlone(unittest.TestCase):
    def test_a_matching_label_is_unchanged(self):  # LBL-022
        github = api([existing("ai-triage")])
        result = apply_labels(github, [label("ai-triage")], [])
        self.assertEqual(result.unchanged, ["ai-triage"])

    def test_no_request_is_made_for_it(self):  # LBL-022
        github = api([existing("ai-triage")])
        apply_labels(github, [label("ai-triage")], [])
        self.assertNotIn("update_label", [name for name, _ in github.calls])

    def test_an_unmanaged_label_is_left_alone(self):  # LBL-023
        github = api([existing("someone-elses")])
        apply_labels(github, [label("ai-triage")], [])
        self.assertIn("someone-elses", [l["name"] for l in github.labels()])

    def test_an_unmanaged_label_is_not_reported(self):  # LBL-023
        github = api([existing("someone-elses")])
        result = apply_labels(github, [label("ai-triage")], [])
        self.assertNotIn("someone-elses", result.created + result.updated + result.deleted)


class TestDeleting(unittest.TestCase):
    def test_a_listed_label_is_deleted(self):  # LBL-024
        github = api([existing("old-label")])
        result = apply_labels(github, [], ["old-label"])
        self.assertEqual(result.deleted, ["old-label"])

    def test_it_is_gone_afterwards(self):  # LBL-024
        github = api([existing("old-label")])
        apply_labels(github, [], ["old-label"])
        self.assertEqual(github.labels(), [])

    def test_deleting_something_absent_is_not_an_error(self):  # LBL-025
        github = api()
        result = apply_labels(github, [], ["never-existed"])
        self.assertEqual(result.deleted, [])

    def test_nothing_outside_the_delete_list_is_removed(self):  # LBL-023
        github = api([existing("keep-me"), existing("old-label")])
        apply_labels(github, [], ["old-label"])
        self.assertEqual([l["name"] for l in github.labels()], ["keep-me"])


class TestIdempotence(unittest.TestCase):
    def test_a_second_run_changes_nothing(self):  # LBL-027
        github = api()
        apply_labels(github, [label("ai-triage")], [])
        result = apply_labels(github, [label("ai-triage")], [])
        self.assertEqual((result.created, result.updated, result.deleted), ([], [], []))

    def test_a_second_run_makes_no_write_requests(self):  # LBL-027
        github = api()
        apply_labels(github, [label("ai-triage")], [])
        before = len(github.calls)
        apply_labels(github, [label("ai-triage")], [])
        writes = [c for c in github.calls[before:] if c[0] != "labels"]
        self.assertEqual(writes, [])


class TestTheReport(unittest.TestCase):
    def test_every_category_is_reported(self):  # LBL-028
        github = api([existing("stale", description="old"), existing("old-label")])
        result = apply_labels(
            github,
            [label("new-one"), label("stale", description="new")],
            ["old-label"],
        )
        self.assertEqual(result.created, ["new-one"])
        self.assertEqual(result.updated, ["stale"])
        self.assertEqual(result.deleted, ["old-label"])

    def test_the_report_is_ordered(self):  # LBL-028
        github = api()
        result = apply_labels(github, [label("b"), label("a")], [])
        self.assertEqual(result.created, ["a", "b"])


if __name__ == "__main__":
    unittest.main()
