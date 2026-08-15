"""BLK-010 to BLK-022 — text forms: soft dependencies, and prose drift."""

import unittest

import _blockers  # noqa: F401
from issue_blockers import depends_on, prose_blockers


class TestSoftDependencies(unittest.TestCase):
    def test_a_single_reference(self):  # BLK-010
        self.assertEqual(depends_on("Depends on: #42"), [42])

    def test_several_on_one_line(self):  # BLK-011
        self.assertEqual(depends_on("Depends on: #42, #43"), [42, 43])

    def test_several_lines(self):  # BLK-012
        self.assertEqual(depends_on("Depends on: #42\nDepends on: #43"), [42, 43])

    def test_case_insensitive(self):  # BLK-013
        self.assertEqual(depends_on("depends on: #42"), [42])

    def test_without_the_colon(self):  # BLK-013
        self.assertEqual(depends_on("Depends on #42"), [42])

    def test_surrounded_by_prose(self):  # BLK-013
        self.assertEqual(depends_on("Some words.\n\nDepends on: #42\n\nMore."), [42])

    def test_a_bare_mention_is_not_a_dependency(self):  # BLK-014
        self.assertEqual(depends_on("Related to #42"), [])

    def test_a_number_in_prose_is_not_a_dependency(self):  # BLK-014
        self.assertEqual(depends_on("See #42 for background"), [])

    def test_inside_a_code_fence_is_ignored(self):  # BLK-015
        self.assertEqual(depends_on("```\nDepends on: #42\n```"), [])

    def test_outside_a_fence_still_counts(self):  # BLK-015
        self.assertEqual(depends_on("```\nexample\n```\nDepends on: #42"), [42])

    def test_duplicates_are_collapsed(self):  # BLK-010
        self.assertEqual(depends_on("Depends on: #42\nDepends on: #42"), [42])

    def test_the_order_is_stable(self):  # BLK-012
        self.assertEqual(depends_on("Depends on: #43\nDepends on: #42"), [42, 43])

    def test_a_soft_dependency_never_gates(self):  # BLK-016
        """It orders the queue. Only a native blocked-by makes work ineligible."""
        from issue_blockers import is_eligible

        self.assertTrue(is_eligible(7, []).eligible)

    def test_an_empty_body(self):  # BLK-010
        self.assertEqual(depends_on(""), [])
        self.assertEqual(depends_on(None), [])


class TestProseBlockersAreDrift(unittest.TestCase):
    """BLK-020 to BLK-022 — the invisible-to-tooling form.

    A hard blocker written as prose is one the queue cannot see, so the builder
    starts the issue anyway. Honouring it here would make the broken form work,
    and it would stay.
    """

    def test_it_is_found(self):  # BLK-020
        self.assertEqual(prose_blockers("Blocked by #42"), [42])

    def test_several_are_found(self):  # BLK-020
        self.assertEqual(prose_blockers("Blocked by: #42, #43"), [42, 43])

    def test_case_insensitive(self):  # BLK-020
        self.assertEqual(prose_blockers("blocked by #42"), [42])

    def test_inside_a_code_fence_is_ignored(self):  # BLK-020
        self.assertEqual(prose_blockers("```\nBlocked by #42\n```"), [])

    def test_a_soft_dependency_is_not_a_prose_blocker(self):  # BLK-022
        self.assertEqual(prose_blockers("Depends on: #42"), [])

    def test_a_prose_blocker_is_not_a_soft_dependency(self):  # BLK-022
        self.assertEqual(depends_on("Blocked by #42"), [])

    def test_an_empty_body_has_none(self):  # BLK-021
        self.assertEqual(prose_blockers(""), [])


if __name__ == "__main__":
    unittest.main()
