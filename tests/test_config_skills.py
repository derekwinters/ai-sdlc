"""CFG-060 to CFG-063 — the list of skills a repository installs.

The list lives here rather than in a workflow input for two reasons. A caller
is an `adopt`-managed file, so hand-editing one turns it into a `CONFLICT` and
it stops being upgraded. And a central registry deciding what a repository
should have is precisely what reverted local work the two previous times a
skill sync was built in this fleet.
"""

import unittest

from _support import ROOT  # noqa: F401 - puts the repository root on sys.path
from lib.config import ConfigError, parse_config


def config(text):
    return parse_config(text)


def problems(text):
    with unittest.TestCase().assertRaises(ConfigError) as caught:
        parse_config(text)
    return caught.exception.problems


class TestTheListIsRead(unittest.TestCase):
    def test_the_named_skills_are_exposed(self):  # CFG-060
        self.assertEqual(
            config("skills:\n  - ci-watch\n  - triage-issue\n").skills,
            ["ci-watch", "triage-issue"],
        )

    def test_order_is_preserved(self):  # CFG-060
        self.assertEqual(config("skills:\n  - b\n  - a\n").skills, ["b", "a"])

    def test_a_repository_naming_none_installs_none(self):  # CFG-060
        self.assertEqual(config("capabilities:\n  - hygiene\n").skills, [])

    def test_an_empty_list_is_not_an_error(self):  # CFG-060
        self.assertEqual(config("skills:\n").skills, [])


class TestTheEntriesAreChecked(unittest.TestCase):
    def test_a_number_is_refused(self):  # CFG-061
        self.assertIn("skills[0]", problems("skills:\n  - 7\n")[0])

    def test_an_empty_string_is_refused(self):  # CFG-061
        self.assertIn("skills[0]", problems('skills:\n  - ""\n')[0])

    def test_the_problem_names_what_was_found(self):  # CFG-061
        self.assertIn("int", problems("skills:\n  - 7\n")[0])

    def test_a_scalar_instead_of_a_list_is_refused(self):  # CFG-061
        self.assertIn("skills", problems("skills: ci-watch\n")[0])

    def test_every_bad_entry_is_reported(self):  # CFG-061
        # CFG-014: validation reports every problem it can find, not the first.
        self.assertEqual(len(problems("skills:\n  - 7\n  - 9\n")), 2)


class TestRepeatsCollapse(unittest.TestCase):
    def test_a_repeated_name_appears_once(self):  # CFG-062
        self.assertEqual(config("skills:\n  - ci-watch\n  - ci-watch\n").skills, ["ci-watch"])

    def test_a_repeat_is_not_an_error(self):  # CFG-062
        self.assertEqual(config("skills:\n  - a\n  - b\n  - a\n").skills, ["a", "b"])


class TestTheLoaderDoesNotResolveNames(unittest.TestCase):
    """CFG-063 — the loader is pure, so it cannot check a name against a tree."""

    def test_a_name_no_capability_owns_still_loads(self):  # CFG-063
        # Not a judgement that this is sensible; a judgement that the *loader*
        # is the wrong place to make it. DIST-016 catches it where the source
        # is present.
        config("capabilities:\n  - hygiene\nskills:\n  - pipeline-dev\n")

    def test_a_name_ai_sdlc_does_not_ship_still_loads(self):  # CFG-063
        self.assertEqual(config("skills:\n  - not-a-real-skill\n").skills, ["not-a-real-skill"])


if __name__ == "__main__":
    unittest.main()
