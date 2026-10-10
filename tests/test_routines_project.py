"""RTN-025 to RTN-028, RTN-031, RTN-035, RTN-036 — a routine shared by every
repository of a project.

The property everything here protects: each member plans the shared routine
from its own configuration, and when their `project:` agrees they all plan the
same bytes, so the exact-name match finds one live routine from any of them.
"""

import unittest

import _routines  # noqa: F401
from _routines import DEFINITIONS, PIPELINE, definition, directory, repository
from routines import RoutineError, dumps, plan

API = "derekwinters/doggiehood-api"
GAME = "derekwinters/lucas-doggiehood"

PROJECT = f"project:\n  name: Doggiehood\n  repos:\n    - {GAME}\n    - {API}\n"
REORDERED = f"project:\n  name: Doggiehood\n  repos:\n    - {API}\n    - {GAME}\n    - {API}\n"

SHARED = {
    "shared": definition(id="shared", name="{project} Shared", requires="pipeline", api=True,
                         body="Only for:\n\n{project_repos}\n", extra="scope: project"),
    "own": definition(id="own", name="{repo_name} Own", requires="pipeline", api=True),
}


def planned(config, repo=GAME, names=SHARED):
    return plan(repository(config), repo, directory(names))


def problems(config, repo=GAME, names=SHARED):
    with unittest.TestCase().assertRaises(RoutineError) as caught:
        planned(config, repo, names)
    return " ".join(caught.exception.problems)


class TestTriageWasRenamed(unittest.TestCase):
    def test_it_names_both_replacements(self):  # RTN-025
        root = repository(PIPELINE + "routines:\n  - triage\n")
        with self.assertRaises(RoutineError) as caught:
            plan(root, GAME, DEFINITIONS)
        (problem,) = caught.exception.problems
        self.assertIn("'triage'", problem)
        self.assertIn("repo-triage", problem)
        self.assertIn("project-triage", problem)
        self.assertIn("renamed", problem)


class TestTheProjectIsRequired(unittest.TestCase):
    def test_without_project_a_project_routine_is_refused(self):  # RTN-026
        found = problems(PIPELINE + "routines:\n  - shared\n")
        self.assertIn("shared", found)
        self.assertIn("project:", found)

    def test_a_repository_routine_does_not_need_one(self):  # RTN-026
        self.assertEqual(len(planned(PIPELINE + "routines:\n  - own\n")["routines"]), 1)


class TestTheRepositoryMustBeAMember(unittest.TestCase):
    def test_a_repository_outside_the_list_is_refused(self):  # RTN-027
        found = problems(PIPELINE + PROJECT + "routines:\n  - shared\n", repo="derekwinters/other")
        self.assertIn("derekwinters/other", found)
        self.assertIn("shared", found)
        self.assertIn("project.repos", found)

    def test_comparison_is_exact(self):  # RTN-027
        found = problems(PIPELINE + PROJECT + "routines:\n  - shared\n",
                         repo="DerekWinters/lucas-doggiehood")
        self.assertIn("DerekWinters/lucas-doggiehood", found)


class TestOneTriageOnly(unittest.TestCase):
    def test_both_triage_routines_together_are_refused(self):  # RTN-028
        root = repository(PIPELINE + PROJECT + "routines:\n  - repo-triage\n  - project-triage\n")
        with self.assertRaises(RoutineError) as caught:
            plan(root, GAME, DEFINITIONS)
        found = " ".join(caught.exception.problems)
        self.assertIn("repo-triage", found)
        self.assertIn("project-triage", found)

    def test_either_alone_is_fine(self):  # RTN-028
        for name in ("repo-triage", "project-triage"):
            with self.subTest(name=name):
                root = repository(PIPELINE + PROJECT + f"routines:\n  - {name}\n")
                self.assertEqual(len(plan(root, GAME, DEFINITIONS)["routines"]), 1)


class TestEveryMemberPlansTheSameRoutine(unittest.TestCase):
    def test_name_and_prompt_are_byte_identical_across_members(self):  # RTN-031
        one = planned(PIPELINE + PROJECT + "routines:\n  - shared\n", repo=GAME)["routines"][0]
        two = planned(PIPELINE + REORDERED + "routines:\n  - shared\n", repo=API)["routines"][0]
        self.assertEqual(one["name"], "Doggiehood Shared")
        self.assertEqual(one["name"], two["name"])
        self.assertEqual(one["prompt"].encode(), two["prompt"].encode())
        self.assertEqual(one["project_repos"], two["project_repos"])

    def test_the_entry_carries_its_scope_and_repositories(self):  # RTN-031
        entry = planned(PIPELINE + PROJECT + "routines:\n  - shared\n")["routines"][0]
        self.assertEqual(entry["scope"], "project")
        self.assertEqual(entry["project_repos"], [API, GAME])

    def test_the_plan_is_still_stable(self):  # RTN-030
        config = PIPELINE + PROJECT + "routines:\n  - shared\n"
        self.assertEqual(dumps(planned(config)), dumps(planned(config)))


class TestTheManualTasks(unittest.TestCase):
    def tasks(self, config=PIPELINE + PROJECT + "routines:\n  - shared\n", repo=GAME):
        return planned(config, repo)["routines"][0]["manual_tasks"]

    def test_every_member_is_attached(self):  # RTN-035
        attach = [t for t in self.tasks() if "attach" in t]
        self.assertEqual(len(attach), 1)
        self.assertIn(API, attach[0])
        self.assertIn(GAME, attach[0])

    def test_the_trigger_is_added_once(self):  # RTN-036
        (trigger,) = [t for t in self.tasks() if "API trigger" in t]
        self.assertIn("once", trigger)
        self.assertRegex(trigger, r"(?i)already")

    def test_the_same_secrets_go_in_every_member(self):  # RTN-036
        (trigger,) = [t for t in self.tasks() if "API trigger" in t]
        for needle in ("same", API, GAME, "ROUTINE_FIRE_URL", "ROUTINE_FIRE_TOKEN"):
            with self.subTest(needle=needle):
                self.assertIn(needle, trigger)

    def test_every_member_gets_the_same_tasks(self):  # RTN-036
        self.assertEqual(self.tasks(repo=GAME),
                         self.tasks(PIPELINE + REORDERED + "routines:\n  - shared\n", repo=API))


if __name__ == "__main__":
    unittest.main()
