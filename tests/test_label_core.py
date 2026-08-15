"""LBL-030 to LBL-034 — the shared vocabulary is complete and shared."""

import unittest

import _labels  # noqa: F401
from _labels import SKILL
from label_sync import load_manifests
from lib.config import STATES


def core():
    return {label.name: label for label in load_manifests(SKILL).labels}


class TestItCoversThePipeline(unittest.TestCase):
    def test_every_state_has_a_label(self):  # LBL-030, LBL-033
        for state, name in STATES.items():
            self.assertIn(name, core(), f"state {state!r} has no label in the core manifest")

    def test_the_control_labels_are_present(self):  # LBL-031
        for name in ("skip-docs", "no-closing-keyword"):
            self.assertIn(name, core())

    def test_type_epic_is_present(self):  # LBL-032
        self.assertIn("type:epic", core())

    def test_it_defines_no_area_label(self):  # LBL-034
        offenders = [name for name in core() if name.startswith("area:")]
        self.assertEqual(offenders, [])


class TestItIsWellFormed(unittest.TestCase):
    def test_it_loads(self):  # LBL-001
        self.assertTrue(load_manifests(SKILL).labels)

    def test_every_label_has_a_description(self):  # LBL-011
        for label in core().values():
            self.assertTrue(label.description.strip(), label.name)

    def test_every_colour_is_valid(self):  # LBL-012
        import re

        for label in core().values():
            self.assertRegex(label.color, r"^[0-9a-fA-F]{6}$", label.name)

    def test_state_labels_have_distinct_colours(self):  # LBL-010
        colours = [core()[name].color.lower() for name in STATES.values()]
        self.assertEqual(len(set(colours)), len(colours))

    def test_it_lists_nothing_for_deletion(self):  # LBL-026
        """A shipped manifest that deletes labels would delete them everywhere."""
        self.assertEqual(load_manifests(SKILL).delete, [])


if __name__ == "__main__":
    unittest.main()
