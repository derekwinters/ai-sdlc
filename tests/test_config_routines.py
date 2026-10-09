"""CFG-070 to CFG-073 — the routines a repository wants created.

The same shape as `skills:` and for the same reason: the repository owns the
list. The loader reads names and nothing more; whether a name is a real
definition, and whether its capability is installed, is decided where the
definitions are (`RTN-022`, `RTN-023`).
"""

import unittest

from _support import ROOT  # noqa: F401 - puts the repository root on sys.path
from lib.config import ConfigError, parse_config


def problems(text):
    with unittest.TestCase().assertRaises(ConfigError) as caught:
        parse_config(text)
    return caught.exception.problems


class TestTheListIsRead(unittest.TestCase):
    def test_the_named_routines_are_exposed_in_order(self):  # CFG-070
        self.assertEqual(
            parse_config("routines:\n  - triage\n  - dependabot\n").routines,
            ["triage", "dependabot"],
        )

    def test_it_defaults_to_none(self):  # CFG-070
        self.assertEqual(parse_config("capabilities:\n  - hygiene\n").routines, [])

    def test_an_explicit_empty_list_is_none(self):  # CFG-070
        self.assertEqual(parse_config("routines: []\n").routines, [])


class TestTheEntriesAreChecked(unittest.TestCase):
    def test_a_number_is_refused_with_its_path(self):  # CFG-071
        found = problems("routines:\n  - 7\n")
        self.assertIn("routines[0]", found[0])
        self.assertIn("int", found[0])

    def test_an_empty_string_is_refused(self):  # CFG-071
        self.assertIn("routines[0]", problems('routines:\n  - ""\n')[0])

    def test_a_scalar_instead_of_a_list_is_refused(self):  # CFG-071
        self.assertIn("routines", problems("routines: triage\n")[0])

    def test_every_bad_entry_is_reported(self):  # CFG-071
        self.assertEqual(len(problems("routines:\n  - 7\n  - 9\n")), 2)


class TestRepeatsCollapse(unittest.TestCase):
    def test_a_repeated_name_appears_once(self):  # CFG-072
        self.assertEqual(
            parse_config("routines:\n  - triage\n  - triage\n").routines, ["triage"]
        )


class TestTheLoaderDoesNotResolveNames(unittest.TestCase):
    def test_an_unknown_name_still_loads(self):  # CFG-073
        self.assertEqual(parse_config("routines:\n  - not-real\n").routines, ["not-real"])

    def test_a_routine_whose_capability_is_absent_still_loads(self):  # CFG-073
        # `triage` requires pipeline; that is RTN-023's business, not the loader's.
        parse_config("capabilities:\n  - hygiene\nroutines:\n  - triage\n")


if __name__ == "__main__":
    unittest.main()
