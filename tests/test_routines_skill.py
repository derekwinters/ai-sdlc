"""RTN-040 to RTN-046, RTN-060 — the instructions an agent follows to make
live routines match the plan.

There is no API to call from a test: the trigger tools exist only inside a
cloud session. So, as with `DIST-043` and `API-070`, the rules are asserted to
be *stated*, each with the words an agent would have to read to follow it.
"""

import re
import sys
import unittest

import _routines  # noqa: F401
from _routines import SKILL
from _support import ROOT

TEXT = (SKILL / "SKILL.md").read_text()


def flat():
    return re.sub(r"\s+", " ", TEXT)


class TestWhereItRuns(unittest.TestCase):
    def test_it_says_a_cloud_session_in_the_target_repository(self):  # RTN-040
        self.assertIn("cloud session", flat())
        self.assertIn("target repository", flat())

    def test_it_says_to_stop_without_the_tools(self):  # RTN-040
        self.assertRegex(flat(), r"(?i)stop")
        self.assertIn("create_trigger", TEXT)

    def test_it_runs_the_plan(self):  # RTN-040
        self.assertIn("main.py plan", TEXT)


class TestMatching(unittest.TestCase):
    def test_it_lists_including_completed(self):  # RTN-041
        self.assertIn("list_triggers", TEXT)
        self.assertIn("include_completed", TEXT)

    def test_it_matches_by_exact_name(self):  # RTN-041
        self.assertIn("exact name", flat())


class TestConfirmation(unittest.TestCase):
    def test_it_asks_before_writing(self):  # RTN-042
        self.assertRegex(flat(), r"(?i)confirm")
        self.assertRegex(flat(), r"(?i)before (writing|any write|you write)")


class TestCreatingAndUpdating(unittest.TestCase):
    def test_create_carries_the_fixed_arguments(self):  # RTN-043
        for needle in ("create_trigger", "create_new_session_on_fire", "human_request",
                       "connectors"):
            with self.subTest(needle=needle):
                self.assertIn(needle, TEXT)

    def test_update_is_by_the_matched_id(self):  # RTN-043
        self.assertIn("update_trigger", TEXT)
        self.assertIn("trig_", TEXT)


class TestNeverDeleteNeverDuplicate(unittest.TestCase):
    def test_it_never_deletes(self):  # RTN-044
        self.assertRegex(flat(), r"(?i)never delete")
        self.assertNotIn("delete_trigger(", TEXT)

    def test_it_never_duplicates(self):  # RTN-044
        self.assertRegex(flat(), r"(?i)never create a second")

    def test_an_ambiguous_name_is_left_alone(self):  # RTN-044
        self.assertRegex(flat(), r"(?i)more than one")


class TestTheEnd(unittest.TestCase):
    def test_it_hands_over_the_manual_tasks(self):  # RTN-045
        self.assertIn("manual_tasks", TEXT)

    def test_it_never_publishes_a_link_or_token(self):  # RTN-045
        self.assertRegex(flat(), r"(?i)never write .*(token|session link)")


class TestAProjectRoutineUpdate(unittest.TestCase):
    def section(self):
        match = re.search(r"(?s)## Project routines\n(.*?)\n## ", TEXT)
        self.assertIsNotNone(match, "SKILL.md has no '## Project routines' section")
        return re.sub(r"\s+", " ", match.group(1))

    def test_it_names_the_repository_list_difference(self):  # RTN-046
        text = self.section()
        self.assertIn("project_repos", text)
        self.assertRegex(text, r"(?i)adds")
        self.assertRegex(text, r"(?i)removes")

    def test_it_names_the_likely_cause(self):  # RTN-046
        self.assertRegex(self.section(), r"(?i)another member.*project\.repos")

    def test_it_needs_an_explicit_confirmation_of_that_update(self):  # RTN-046
        text = self.section()
        self.assertRegex(text, r"(?i)explicit")
        self.assertRegex(text, r"(?i)general (yes|confirmation) is not enough")

    def test_otherwise_it_reports_and_leaves_it_alone(self):  # RTN-046
        self.assertRegex(self.section(), r"(?i)report .*leave .*alone")

    def test_the_match_table_points_at_it(self):  # RTN-046
        self.assertRegex(flat(), r"(?i)project routine.*Project routines")


class TestDistribution(unittest.TestCase):
    def test_it_is_installable_from_substrate(self):  # RTN-060
        sys.path.insert(0, str(ROOT / "skills" / "substrate" / "adopt"))
        from adopt import INVOKED_LOCALLY

        self.assertIn("routines", INVOKED_LOCALLY["substrate"])

    def test_no_module_imports_lib(self):  # RTN-060
        for path in sorted(SKILL.glob("*.py")):
            with self.subTest(module=path.name):
                self.assertNotRegex(path.read_text(), r"(?m)^\s*(from|import) lib\b")

    def test_the_frontmatter_names_it(self):  # RTN-060
        self.assertTrue(TEXT.startswith("---\nname: routines\n"))


if __name__ == "__main__":
    unittest.main()
