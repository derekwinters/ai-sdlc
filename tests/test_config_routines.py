"""CFG-070 to CFG-076 — the routines a repository wants created, and the
project a repository belongs to for the routines it shares.

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
            parse_config("routines:\n  - repo-triage\n  - dependabot\n").routines,
            ["repo-triage", "dependabot"],
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
        self.assertIn("routines", problems("routines: repo-triage\n")[0])

    def test_every_bad_entry_is_reported(self):  # CFG-071
        self.assertEqual(len(problems("routines:\n  - 7\n  - 9\n")), 2)


class TestRepeatsCollapse(unittest.TestCase):
    def test_a_repeated_name_appears_once(self):  # CFG-072
        self.assertEqual(
            parse_config("routines:\n  - repo-triage\n  - repo-triage\n").routines,
            ["repo-triage"],
        )


class TestTheLoaderDoesNotResolveNames(unittest.TestCase):
    def test_an_unknown_name_still_loads(self):  # CFG-073
        self.assertEqual(parse_config("routines:\n  - not-real\n").routines, ["not-real"])

    def test_a_routine_whose_capability_is_absent_still_loads(self):  # CFG-073
        # `repo-triage` requires pipeline; that is RTN-023's business, not the loader's.
        parse_config("capabilities:\n  - hygiene\nroutines:\n  - repo-triage\n")


PROJECT = (
    "project:\n  name: Doggiehood\n  repos:\n"
    "    - derekwinters/lucas-doggiehood\n    - derekwinters/doggiehood-api\n"
)


class TestTheProject(unittest.TestCase):
    def test_it_defaults_to_absent(self):  # CFG-074
        self.assertIsNone(parse_config("capabilities:\n  - hygiene\n").project)

    def test_the_name_and_repositories_are_read(self):  # CFG-074
        project = parse_config(PROJECT).project
        self.assertEqual(project.name, "Doggiehood")
        self.assertEqual(
            project.repos, ["derekwinters/doggiehood-api", "derekwinters/lucas-doggiehood"]
        )

    def test_both_keys_are_required(self):  # CFG-074
        self.assertIn("project.repos", " ".join(problems("project:\n  name: X\n")))
        found = " ".join(problems("project:\n  repos:\n    - a/b\n"))
        self.assertIn("project.name", found)

    def test_an_empty_name_or_list_is_refused(self):  # CFG-074
        found = " ".join(problems('project:\n  name: ""\n  repos: []\n'))
        self.assertIn("project.name", found)
        self.assertIn("project.repos", found)

    def test_a_repository_must_be_owner_slash_name(self):  # CFG-074
        found = problems("project:\n  name: X\n  repos:\n    - a/b\n    - nope\n    - 7\n")
        self.assertEqual(len(found), 2)
        self.assertIn("project.repos[1]", found[0])
        self.assertIn("project.repos[2]", found[1])

    def test_an_unknown_project_key_is_refused(self):  # CFG-074
        found = " ".join(problems(PROJECT + "  owner: someone\n"))
        self.assertIn("project.owner", found)

    def test_a_scalar_list_is_refused(self):  # CFG-074
        self.assertIn("project.repos", " ".join(problems("project:\n  name: X\n  repos: a/b\n")))

    def test_the_list_is_sorted_and_collapsed(self):  # CFG-075
        project = parse_config(
            "project:\n  name: X\n  repos:\n    - z/z\n    - a/a\n    - z/z\n"
        ).project
        self.assertEqual(project.repos, ["a/a", "z/z"])

    def test_the_loader_does_not_cross_check_routines(self):  # CFG-076
        # A project routine without `project:`, and both triage routines at
        # once, are RTN-026 and RTN-028: the loader cannot know which
        # definitions are project-scoped, nor which repository it is in.
        parse_config("routines:\n  - project-triage\n")
        parse_config(PROJECT + "routines:\n  - repo-triage\n  - project-triage\n")


if __name__ == "__main__":
    unittest.main()
