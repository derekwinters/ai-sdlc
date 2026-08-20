"""BLK-020 to BLK-022 — the prose form, found by the dashboard.

Soft `Depends on:` lines are read by an agent building the queue now, so their
rules are stated rather than executed (`test_blockers_rules.py`). The prose
`Blocked by #N` form stays code: the dashboard reports it as drift on every
render, with nobody watching.
"""

import unittest

import _blockers  # noqa: F401
from blocker_state import prose_blockers


class TestProseBlockersAreDrift(unittest.TestCase):
    """A hard blocker written as prose is one the queue cannot see, so the
    builder starts the issue anyway. Honouring it would make the broken form
    work, and it would stay."""

    def test_it_is_found(self):  # BLK-020
        self.assertEqual(prose_blockers("Blocked by #42"), [42])

    def test_several_on_one_line_are_found(self):  # BLK-020
        self.assertEqual(prose_blockers("Blocked by: #42, #43"), [42, 43])

    def test_several_lines_are_found(self):  # BLK-020
        self.assertEqual(prose_blockers("Blocked by #42\nBlocked by #43"), [42, 43])

    def test_case_insensitive(self):  # BLK-020
        self.assertEqual(prose_blockers("blocked by #42"), [42])

    def test_the_colon_is_optional(self):  # BLK-020
        self.assertEqual(prose_blockers("Blocked by: #42"), [42])

    def test_a_duplicate_is_reported_once(self):  # BLK-020
        self.assertEqual(prose_blockers("Blocked by #42\nBlocked by #42"), [42])

    def test_inside_a_code_fence_is_ignored(self):  # BLK-020
        """An example of the drift is not the drift."""
        self.assertEqual(prose_blockers("```\nBlocked by #42\n```"), [])

    def test_after_a_closed_fence_is_read(self):  # BLK-020
        self.assertEqual(prose_blockers("```\nexample\n```\nBlocked by #42"), [42])

    def test_a_mention_in_prose_is_not_one(self):  # BLK-020
        self.assertEqual(prose_blockers("See #42 for background"), [])

    def test_a_soft_dependency_is_not_a_prose_blocker(self):  # BLK-022
        self.assertEqual(prose_blockers("Depends on: #42"), [])

    def test_an_empty_body_has_none(self):  # BLK-021
        self.assertEqual(prose_blockers(""), [])

    def test_a_missing_body_has_none(self):  # BLK-021
        self.assertEqual(prose_blockers(None), [])


if __name__ == "__main__":
    unittest.main()
