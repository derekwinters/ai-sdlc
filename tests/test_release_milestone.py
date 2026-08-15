"""REL-023 to REL-027 — a version milestone reserves its version number.

Versions here are named by milestones: `v0.4 — Adoption` closes when 0.4.0
releases. So a release that spends a number belonging to an open milestone
takes it permanently — a version cannot be un-released, and the milestone is
left with no number of its own.

That nearly happened. With `v0.5 — Fleet` open and none of its work started,
a `feat:` commit of pure housekeeping made release-please propose 0.5.0. The
rule existed, but only in Derek's head and half a sentence of REL-020, and
nothing checked it.
"""

import unittest

from _release import SKILL  # noqa: F401 - puts the skill on the path
from release_flow import reserved_by_milestone

FLEET = {"title": "v0.5 — Fleet", "state": "open", "open_issues": 2, "closed_issues": 0}
ADOPTION = {"title": "v0.4 — Adoption", "state": "closed", "open_issues": 0,
            "closed_issues": 3}
HUMANS = {"title": "Direct Involvement Needed", "state": "open", "open_issues": 3,
          "closed_issues": 2}


class TestReserving(unittest.TestCase):
    def test_a_version_matching_an_open_milestone_is_reserved(self):  # REL-023
        self.assertIsNotNone(reserved_by_milestone("0.5.0", [FLEET]))

    def test_the_halt_names_the_milestone(self):  # REL-023
        halt = reserved_by_milestone("0.5.0", [FLEET])
        self.assertIn("v0.5 — Fleet", halt.reason)

    def test_the_halt_says_what_to_do_instead(self):  # REL-023
        # A halt that does not say how to proceed gets worked around.
        self.assertIn("Release-As", reserved_by_milestone("0.5.0", [FLEET]).remedy)

    def test_a_patch_of_a_reserved_minor_is_allowed(self):  # REL-024
        # 0.5.1 would be strange, but 0.4.1 is exactly the escape: the point is
        # to protect the minor the milestone names, not every version near it.
        self.assertIsNone(reserved_by_milestone("0.4.1", [FLEET]))

    def test_an_unrelated_version_is_allowed(self):  # REL-024
        self.assertIsNone(reserved_by_milestone("1.2.3", [FLEET]))


class TestReleasing(unittest.TestCase):
    def test_a_closed_milestone_reserves_nothing(self):  # REL-025
        # The release this milestone was named for is exactly what should ship.
        self.assertIsNone(reserved_by_milestone("0.4.0", [ADOPTION]))

    def test_an_open_milestone_with_all_issues_closed_reserves_nothing(self):  # REL-025
        done = dict(FLEET, open_issues=0, closed_issues=2)
        self.assertIsNone(reserved_by_milestone("0.5.0", [done]))

    def test_an_open_milestone_with_no_issues_at_all_reserves_nothing(self):  # REL-025
        # An empty milestone is a placeholder, not work in progress.
        empty = dict(FLEET, open_issues=0, closed_issues=0)
        self.assertIsNone(reserved_by_milestone("0.5.0", [empty]))


class TestMatching(unittest.TestCase):
    def test_a_milestone_that_names_no_version_is_ignored(self):  # REL-026
        self.assertIsNone(reserved_by_milestone("0.5.0", [HUMANS]))

    def test_no_milestones_at_all_reserve_nothing(self):  # REL-026
        self.assertIsNone(reserved_by_milestone("0.5.0", []))

    def test_a_three_part_milestone_title_matches_too(self):  # REL-026
        milestone = dict(FLEET, title="v0.5.0 — Fleet")
        self.assertIsNotNone(reserved_by_milestone("0.5.0", [milestone]))

    def test_a_bare_version_title_matches(self):  # REL-026
        self.assertIsNotNone(reserved_by_milestone("0.5.0", [dict(FLEET, title="v0.5")]))

    def test_a_similar_number_inside_a_title_does_not_match(self):  # REL-026
        # "v0.50" is not "v0.5", and a substring match would say it was.
        self.assertIsNone(reserved_by_milestone("0.5.0", [dict(FLEET, title="v0.50")]))

    def test_the_first_reserving_milestone_is_reported(self):  # REL-027
        halt = reserved_by_milestone("0.5.0", [HUMANS, ADOPTION, FLEET])
        self.assertIn("Fleet", halt.reason)


class TestTheRealSituation(unittest.TestCase):
    def test_the_case_that_prompted_this(self):  # REL-027
        # release-please proposed 0.5.0 while v0.5 — Fleet had 2 open issues
        # and nothing closed. It should be refused, and 0.4.1 offered instead.
        halt = reserved_by_milestone("0.5.0", [FLEET, HUMANS])
        self.assertIsNotNone(halt)
        self.assertIsNone(reserved_by_milestone("0.4.1", [FLEET, HUMANS]))


if __name__ == "__main__":
    unittest.main()
