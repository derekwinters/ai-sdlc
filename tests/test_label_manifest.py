"""LBL-001 to LBL-014 — reading and validating the two manifests."""

import tempfile
import unittest
from pathlib import Path

import _labels  # noqa: F401
from label_sync import ManifestError, load_manifests

CORE = """
labels:
  - name: ai-triage
    color: "1D76DB"
    description: In the pipeline, awaiting analysis
"""

REPO = """
labels:
  - name: area:build
    color: "546E7A"
    description: CI, packaging and releases
"""


class Tree(unittest.TestCase):
    def build(self, core=CORE, repo=REPO):
        root = Path(tempfile.mkdtemp())
        (root / "labels.core.yml").write_text(core)
        if repo is not None:
            (root / "labels.repo.yml").write_text(repo)
        return root

    def refused(self, **kwargs):
        try:
            load_manifests(self.build(**kwargs))
        except ManifestError as error:
            return str(error)
        raise AssertionError("expected a ManifestError")


class TestTheUnion(Tree):
    def test_both_manifests_are_read(self):  # LBL-003
        found = load_manifests(self.build())
        self.assertEqual({l["name"] for l in found.labels}, {"ai-triage", "area:build"})

    def test_the_repo_manifest_is_hand_written_and_optional(self):  # LBL-002
        """Its labels are applied alongside the core's, from a separate file."""
        found = load_manifests(self.build())
        repo_labels = [l for l in found.labels if l["source"] == "labels.repo.yml"]
        self.assertEqual([l["name"] for l in repo_labels], ["area:build"])

    def test_separate_files_mean_an_upgrade_cannot_conflict(self):  # LBL-004
        """The core can be replaced wholesale without touching local labels."""
        found = load_manifests(self.build(core=CORE.replace("ai-triage", "renamed")))
        self.assertIn("area:build", [l["name"] for l in found.labels])

    def test_a_missing_repo_manifest_is_fine(self):  # LBL-006
        found = load_manifests(self.build(repo=None))
        self.assertEqual({l["name"] for l in found.labels}, {"ai-triage"})

    def test_a_missing_core_manifest_is_an_error(self):  # LBL-001
        root = Path(tempfile.mkdtemp())
        (root / "labels.repo.yml").write_text(REPO)
        with self.assertRaises(ManifestError):
            load_manifests(root)

    def test_each_label_knows_which_file_defined_it(self):  # LBL-005
        found = load_manifests(self.build())
        source = {l["name"]: l["source"] for l in found.labels}
        self.assertEqual(source["ai-triage"], "labels.core.yml")
        self.assertEqual(source["area:build"], "labels.repo.yml")


class TestCollisions(Tree):
    def test_a_label_in_both_files_is_an_error(self):  # LBL-005
        message = self.refused(repo=CORE)
        self.assertIn("ai-triage", message)

    def test_the_error_names_both_files(self):  # LBL-005
        message = self.refused(repo=CORE)
        self.assertIn("labels.core.yml", message)
        self.assertIn("labels.repo.yml", message)

    def test_a_duplicate_within_one_file_is_an_error(self):  # LBL-014
        doubled = CORE + CORE.replace("labels:\n", "")
        self.assertIn("ai-triage", self.refused(core=doubled))


class TestWhatALabelNeeds(Tree):
    def test_a_complete_label_is_accepted(self):  # LBL-010
        self.assertEqual(len(load_manifests(self.build()).labels), 2)

    def test_a_missing_description_is_an_error(self):  # LBL-011
        core = 'labels:\n  - name: x\n    color: "1D76DB"\n'
        self.assertIn("description", self.refused(core=core).lower())

    def test_an_empty_description_is_an_error(self):  # LBL-011
        core = 'labels:\n  - name: x\n    color: "1D76DB"\n    description: ""\n'
        self.assertIn("description", self.refused(core=core).lower())

    def test_a_missing_colour_is_an_error(self):  # LBL-012
        core = "labels:\n  - name: x\n    description: y\n"
        self.assertIn("colour", self.refused(core=core).lower())

    def test_a_hash_prefix_is_rejected(self):  # LBL-012
        core = 'labels:\n  - name: x\n    color: "#1D76DB"\n    description: y\n'
        self.assertIn("x", self.refused(core=core))

    def test_a_short_colour_is_rejected(self):  # LBL-013
        core = 'labels:\n  - name: x\n    color: "1D7"\n    description: y\n'
        self.assertIn("x", self.refused(core=core))

    def test_a_non_hex_colour_is_rejected(self):  # LBL-013
        core = 'labels:\n  - name: x\n    color: "ZZZZZZ"\n    description: y\n'
        self.assertIn("x", self.refused(core=core))

    def test_lowercase_hex_is_accepted(self):  # LBL-012
        core = 'labels:\n  - name: x\n    color: "1d76db"\n    description: y\n'
        self.assertEqual(len(load_manifests(self.build(core=core, repo=None)).labels), 1)


class TestDeletions(Tree):
    def test_a_deletion_list_is_read(self):  # LBL-024
        core = CORE + "\ndelete:\n  - old-label\n"
        self.assertEqual(load_manifests(self.build(core=core)).delete, ["old-label"])

    def test_deleting_something_also_defined_is_an_error(self):  # LBL-026
        core = CORE + "\ndelete:\n  - ai-triage\n"
        self.assertIn("ai-triage", self.refused(core=core))

    def test_deletions_from_both_files_combine(self):  # LBL-024
        core = CORE + "\ndelete:\n  - a\n"
        repo = REPO + "\ndelete:\n  - b\n"
        self.assertEqual(sorted(load_manifests(self.build(core=core, repo=repo)).delete),
                         ["a", "b"])


if __name__ == "__main__":
    unittest.main()
