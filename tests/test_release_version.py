"""REL-020 to REL-022 — forcing a version at a milestone boundary."""

import unittest

import _release  # noqa: F401
from release_flow import ReleaseError, release_as_footer, is_higher


def refused(current, wanted):
    try:
        release_as_footer(wanted, current=current)
    except ReleaseError as error:
        return str(error)
    raise AssertionError("expected a ReleaseError")


class TestTheFooter(unittest.TestCase):
    def test_it_produces_a_release_as_line(self):  # REL-020
        self.assertIn("Release-As: 0.4.0", release_as_footer("0.4.0", current="0.3.0"))

    def test_it_is_a_footer_on_its_own_line(self):  # REL-020
        footer = release_as_footer("0.4.0", current="0.3.0")
        self.assertTrue(footer.strip().startswith("Release-As:"))

    def test_a_milestone_boundary_can_be_matched(self):  # REL-020
        """v0.4 the milestone, v0.4.0 the tag."""
        self.assertIn("0.4.0", release_as_footer("0.4.0", current="0.3.9"))


class TestValidation(unittest.TestCase):
    def test_a_non_version_is_refused(self):  # REL-021
        self.assertIn("version", refused("0.3.0", "next").lower())

    def test_a_partial_version_is_refused(self):  # REL-021
        self.assertIn("version", refused("0.3.0", "0.4").lower())

    def test_a_v_prefix_is_refused(self):  # REL-021
        """The footer takes a bare version; the tag gets the prefix."""
        self.assertIn("version", refused("0.3.0", "v0.4.0").lower())

    def test_going_backwards_is_refused(self):  # REL-022
        self.assertIn("0.2.0", refused("0.3.0", "0.2.0"))

    def test_the_same_version_is_refused(self):  # REL-022
        self.assertIn("0.3.0", refused("0.3.0", "0.3.0"))

    def test_a_lower_patch_is_refused(self):  # REL-022
        self.assertIn("0.3.0", refused("0.3.1", "0.3.0"))

    def test_no_current_version_allows_anything_valid(self):  # REL-022
        self.assertIn("0.1.0", release_as_footer("0.1.0", current=None))


class TestComparison(unittest.TestCase):
    def test_a_minor_bump_is_higher(self):  # REL-022
        self.assertTrue(is_higher("0.4.0", "0.3.0"))

    def test_a_patch_bump_is_higher(self):  # REL-022
        self.assertTrue(is_higher("0.3.1", "0.3.0"))

    def test_numeric_not_lexical(self):  # REL-022
        self.assertTrue(is_higher("0.10.0", "0.9.0"))

    def test_equal_is_not_higher(self):  # REL-022
        self.assertFalse(is_higher("0.3.0", "0.3.0"))


if __name__ == "__main__":
    unittest.main()
