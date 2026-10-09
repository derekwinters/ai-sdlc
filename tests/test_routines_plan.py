"""RTN-020 to RTN-034 — choosing what a repository wants, and saying exactly
what creating it means.

The plan is everything `create_trigger` needs, so the agent applying it
decides nothing the plan did not say — and it is byte-stable, so comparing it
to live routines on two runs gives one answer.
"""

import io
import json
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import _routines  # noqa: F401
from _routines import PIPELINE, definition, directory, load_main, repository
from _support import ROOT
from routines import RoutineError, dumps, plan, read_config

routines_main = load_main()

SAMPLES = {
    "fired": definition(id="fired", name="{repo_name} Fired", requires="pipeline", api=True),
    "weekly": definition(id="weekly", name="{repo_name} Weekly", requires="hygiene",
                         schedule="CRON_TZ=America/Chicago 52 7 * * 1"),
}


def planned(config, names=SAMPLES, repo="derekwinters/example"):
    return plan(repository(config), repo, directory(names))


def problems(config, names=SAMPLES):
    with unittest.TestCase().assertRaises(RoutineError) as caught:
        planned(config, names)
    return caught.exception.problems


class TestReadingTheConfiguration(unittest.TestCase):
    def test_the_three_keys_are_read(self):  # RTN-020
        root = repository(PIPELINE + "routines:\n  - fired\n")
        config = read_config(root)
        self.assertEqual(config["routines"], ["fired"])
        self.assertIn("pipeline", config["capabilities"])
        self.assertEqual(config["fire"]["token_secret"], "ROUTINE_FIRE_TOKEN")

    def test_it_agrees_with_the_loader_on_every_example(self):  # RTN-020
        from lib.config import load

        for path in sorted((ROOT / "examples").glob("*.yml")) + [
            ROOT / ".ai-sdlc" / "repo-config.yml"
        ]:
            with self.subTest(example=path.name):
                root = repository(path.read_text())
                ours = read_config(root)
                theirs = load(path=path)
                self.assertEqual(set(ours["capabilities"]) | {"substrate"},
                                 set(theirs.capabilities))
                self.assertEqual(ours["routines"], theirs.routines)
                self.assertEqual(ours["fire"].get("endpoint_secret"),
                                 theirs.fire.endpoint_secret)
                self.assertEqual(ours["fire"].get("token_secret"), theirs.fire.token_secret)

    def test_a_missing_file_names_the_path(self):  # RTN-020
        with self.assertRaises(RoutineError) as caught:
            read_config(repository(None))
        self.assertIn(".ai-sdlc/repo-config.yml", str(caught.exception))


class TestSelection(unittest.TestCase):
    def test_the_named_routines_are_planned_in_order(self):  # RTN-021
        result = planned(PIPELINE + "routines:\n  - weekly\n  - fired\n  - weekly\n")
        self.assertEqual([r["id"] for r in result["routines"]], ["weekly", "fired"])

    def test_naming_none_plans_none(self):  # RTN-021
        self.assertEqual(planned(PIPELINE)["routines"], [])
        self.assertEqual(planned(PIPELINE + "routines: []\n")["routines"], [])

    def test_an_unknown_name_lists_what_exists(self):  # RTN-022
        found = " ".join(problems(PIPELINE + "routines:\n  - nightly\n"))
        self.assertIn("nightly", found)
        self.assertIn("fired", found)
        self.assertIn("weekly", found)

    def test_a_missing_capability_is_refused_by_name(self):  # RTN-023
        found = " ".join(problems("capabilities:\n  - hygiene\nroutines:\n  - fired\n"))
        self.assertIn("fired", found)
        self.assertIn("pipeline", found)

    def test_substrate_is_always_installed(self):  # RTN-023
        names = {"base": definition(id="base", api=True)}
        result = planned("capabilities: []\nroutines:\n  - base\n", names)
        self.assertEqual(len(result["routines"]), 1)

    def test_every_problem_is_reported_and_nothing_planned(self):  # RTN-024
        found = problems("capabilities:\n  - hygiene\nroutines:\n  - fired\n  - nightly\n")
        self.assertEqual(len(found), 2)

    def test_the_command_exits_non_zero_and_prints_no_plan(self):  # RTN-024
        root = repository("capabilities:\n  - hygiene\nroutines:\n  - triage\n")
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = routines_main.main(["main.py", "plan", "--repo", "a/b"], root=root)
        self.assertEqual(code, 1)
        self.assertEqual(out.getvalue(), "")
        self.assertIn("pipeline", err.getvalue())


class TestThePlanIsStable(unittest.TestCase):
    CONFIG = PIPELINE + "routines:\n  - fired\n  - weekly\n"

    def test_the_same_inputs_give_the_same_bytes(self):  # RTN-030
        self.assertEqual(dumps(planned(self.CONFIG)), dumps(planned(self.CONFIG)))

    def test_it_is_json_with_sorted_keys(self):  # RTN-030
        text = dumps(planned(self.CONFIG))
        self.assertEqual(text, json.dumps(json.loads(text), indent=2, sort_keys=True) + "\n")

    def test_the_command_prints_it(self):  # RTN-030
        root = repository(PIPELINE + "routines:\n  - triage\n")
        out = io.StringIO()
        with redirect_stdout(out):
            code = routines_main.main(["main.py", "plan", "--repo", "a/b"], root=root)
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out.getvalue())["routines"][0]["name"], "b Triage")


class TestWhatAPlannedRoutineCarries(unittest.TestCase):
    CONFIG = PIPELINE + "routines:\n  - fired\n  - weekly\n"

    def test_everything_create_trigger_needs(self):  # RTN-031
        fired, weekly = planned(self.CONFIG)["routines"]
        self.assertEqual(fired["name"], "example Fired")
        self.assertEqual(fired["prompt"], "Do the thing in derekwinters/example.")
        self.assertIsNone(fired["cron"])
        self.assertTrue(fired["api"])
        self.assertEqual(fired["connectors"], [])
        self.assertTrue(fired["create_new_session_on_fire"])
        self.assertEqual(weekly["cron"], "CRON_TZ=America/Chicago 52 7 * * 1")
        self.assertFalse(weekly["api"])

    def test_the_repository_is_named(self):  # RTN-031
        self.assertEqual(planned(self.CONFIG)["repository"], "derekwinters/example")

    def test_an_api_trigger_names_the_secrets(self):  # RTN-032
        fired = planned(self.CONFIG)["routines"][0]
        tasks = " ".join(fired["manual_tasks"])
        self.assertIn("API trigger", tasks)
        self.assertIn("ROUTINE_FIRE_URL", tasks)
        self.assertIn("ROUTINE_FIRE_TOKEN", tasks)

    def test_without_fire_names_it_says_to_choose_them(self):  # RTN-032
        config = PIPELINE.split("fire:")[0] + "routines:\n  - fired\n"
        tasks = " ".join(planned(config)["routines"][0]["manual_tasks"])
        self.assertIn("fire.endpoint_secret", tasks)
        self.assertIn("fire.token_secret", tasks)

    def test_a_scheduled_routine_needs_no_api_trigger(self):  # RTN-032
        weekly = planned(self.CONFIG)["routines"][1]
        self.assertNotIn("API trigger", " ".join(weekly["manual_tasks"]))

    def test_every_routine_says_to_confirm_the_repository(self):  # RTN-033
        for routine in planned(self.CONFIG)["routines"]:
            with self.subTest(routine=routine["id"]):
                tasks = " ".join(routine["manual_tasks"])
                self.assertIn("derekwinters/example", tasks)
                self.assertIn("attached", tasks)


class TestPlanningIsReadOnly(unittest.TestCase):
    def test_no_file_is_written(self):  # RTN-034
        root = repository(PIPELINE + "routines:\n  - fired\n")
        before = sorted((p, p.read_bytes()) for p in root.rglob("*") if p.is_file())
        plan(root, "a/b", directory(SAMPLES))
        after = sorted((p, p.read_bytes()) for p in root.rglob("*") if p.is_file())
        self.assertEqual(before, after)

    def test_the_skill_imports_no_network_library(self):  # RTN-034
        for path in sorted(Path(_routines.SKILL).glob("*.py")):
            text = path.read_text()
            for library in ("urllib", "http", "socket", "requests"):
                with self.subTest(module=path.name, library=library):
                    self.assertNotIn(f"import {library}", text)


if __name__ == "__main__":
    unittest.main()
