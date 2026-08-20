"""BLK-010 to BLK-016, BLK-030 to BLK-036, BLK-040 to BLK-044 — stated, not run.

These were functions in an installed skill that took a client nobody supplied
(#153). They are rules an agent applies now, through `github-api`, so what a
test can hold is that the skill *states* them.

That is weaker than executing them, and deliberately so — an instruction is not
a branch and cannot be asserted like one. What it buys is a rule that works in a
consumer at all, where the function did not. Where a rule survived as code
because a script still needs it, it is tested as code: `test_blockers_read.py`
and `test_blockers_text.py`.
"""

import unittest

from _blockers import stated


class TestSoftDependencies(unittest.TestCase):
    """BLK-010 to BLK-016 — `Depends on: #N`, read by whoever builds a queue."""

    def test_the_form_is_named(self):  # BLK-010
        self.assertIn("depends on: #n", stated())

    def test_several_numbers_and_several_lines(self):  # BLK-011, BLK-012
        text = stated()
        self.assertIn("several numbers on one line", text)
        self.assertIn("several lines", text)

    def test_case_and_punctuation_are_tolerated(self):  # BLK-013
        self.assertIn("case-insensitive", stated())

    def test_a_bare_mention_is_not_a_dependency(self):  # BLK-014
        self.assertRegex(stated(), r"not\*{0,2} a dependency")

    def test_a_fenced_block_is_ignored(self):  # BLK-015
        self.assertIn("fenced code block", stated())

    def test_it_orders_and_never_gates(self):  # BLK-016
        self.assertIn("orders the queue, never gates it", stated())


class TestWriting(unittest.TestCase):
    """BLK-030 to BLK-036 — the writes, and the three checks before them."""

    def test_both_operations_are_named(self):  # BLK-030, BLK-032
        text = stated()
        self.assertIn("add_blocked_by", text)
        self.assertIn("remove_blocked_by", text)

    def test_repeating_either_is_a_no_op(self):  # BLK-031, BLK-033
        self.assertIn("no-op, not an error", stated())

    def test_self_blocking_is_refused(self):  # BLK-034
        self.assertIn("may not block itself", stated())

    def test_a_cycle_is_refused_with_its_path(self):  # BLK-035
        text = stated()
        self.assertIn("cycle", text)
        self.assertIn("draw the path", text)

    def test_a_diamond_is_not_a_cycle(self):  # BLK-035
        """The failure mode a naive traversal produces: refusing two issues
        that legitimately share a dependency."""
        self.assertIn("diamond is not a cycle", stated())

    def test_the_database_id_rule_is_stated(self):  # BLK-036
        """Both are integers, so the wrong one silently succeeds (#155)."""
        text = stated()
        self.assertIn("database `id`, not its issue number", text)
        self.assertIn("issue_id", text)


class TestEligibility(unittest.TestCase):
    """BLK-040 to BLK-044 — computed from the graph, never stored."""

    def test_resolution_is_what_makes_an_issue_eligible(self):  # BLK-040
        self.assertIn("every hard blocker is resolved", stated())

    def test_one_unresolved_blocker_is_enough(self):  # BLK-041, BLK-042
        self.assertIn("one unresolved blocker is enough", stated())

    def test_an_unknown_blocker_counts_as_unresolved(self):  # BLK-043
        self.assertIn("unknown blocker counts as unresolved", stated())

    def test_the_reason_names_the_blockers(self):  # BLK-044
        self.assertIn("name the blockers responsible", stated())

    def test_blockedness_is_never_stored(self):
        """There is no blocked label, and there never will be — which is what
        keeps eligibility correct with nothing maintaining it."""
        self.assertIn("no blocked label", stated())


if __name__ == "__main__":
    unittest.main()
