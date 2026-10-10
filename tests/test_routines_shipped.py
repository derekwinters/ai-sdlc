"""RTN-050 to RTN-055 — the routines every repository has been typing in by
hand, rendered for a sample repository and checked for what they must say.
"""

import re
import unittest

import _routines  # noqa: F401
from _routines import DEFINITIONS, PIPELINE, repository
from routines import load_definitions, plan

REPO = "derekwinters/example"

PROJECT = (
    "project:\n  name: Doggiehood\n  repos:\n"
    "    - derekwinters/lucas-doggiehood\n    - derekwinters/doggiehood-api\n"
)


def rendered(routine_id, config=PIPELINE, repo=REPO):
    root = repository(config + f"routines:\n  - {routine_id}\n")
    (entry,) = plan(root, repo, DEFINITIONS)["routines"]
    return entry


def words(text):
    return re.sub(r"\s+", " ", text)


class TestRepoTriage(unittest.TestCase):
    def setUp(self):
        self.definition = load_definitions(DEFINITIONS)["repo-triage"]
        self.entry = rendered("repo-triage")

    def test_its_shape(self):  # RTN-050
        self.assertEqual(self.definition.scope, "repository")
        self.assertEqual(self.definition.requires, "pipeline")
        self.assertTrue(self.definition.api)
        self.assertIsNone(self.definition.schedule)
        self.assertEqual(self.definition.connectors, [])
        self.assertEqual(self.entry["name"], "example Triage")

    def test_its_prompt(self):  # RTN-050
        prompt = words(self.entry["prompt"])
        self.assertIn("<routine-fire-payload>", prompt)
        self.assertIn("single", prompt)
        self.assertIn("issue number", prompt)
        self.assertRegex(prompt, r"(?i)ignore any other text")
        self.assertIn("triage-issue", prompt)
        self.assertIn(REPO, prompt)

    def test_it_stays_short(self):  # RTN-050
        self.assertLess(len(self.entry["prompt"]), 600)


class TestProjectTriage(unittest.TestCase):
    def setUp(self):
        self.definition = load_definitions(DEFINITIONS)["project-triage"]
        self.entry = rendered("project-triage", PIPELINE + PROJECT,
                              "derekwinters/lucas-doggiehood")
        self.prompt = words(self.entry["prompt"])

    def test_its_shape(self):  # RTN-054
        self.assertEqual(self.definition.scope, "project")
        self.assertEqual(self.definition.requires, "pipeline")
        self.assertTrue(self.definition.api)
        self.assertIsNone(self.definition.schedule)
        self.assertEqual(self.definition.connectors, [])
        self.assertEqual(self.definition.name, "{project} Triage")
        self.assertEqual(self.entry["name"], "Doggiehood Triage")

    def test_the_payload_is_untrusted(self):  # RTN-054
        self.assertIn("<routine-fire-payload>", self.prompt)
        self.assertIn("untrusted", self.prompt)

    def test_it_extracts_exactly_one_issue_and_one_repository(self):  # RTN-054
        self.assertIn("exactly one issue number", self.prompt)
        self.assertIn("exactly one `owner/name` repository", self.prompt)

    def test_it_stops_on_anything_doubtful(self):  # RTN-054
        self.assertRegex(self.prompt, r"(?i)missing or ambiguous")
        self.assertIn("stop without changing anything", self.prompt)

    def test_the_allowlist_is_the_rendered_project(self):  # RTN-054
        self.assertIn(
            "- derekwinters/doggiehood-api\n- derekwinters/lucas-doggiehood",
            self.entry["prompt"],
        )
        self.assertIn("not in this list", self.prompt)

    def test_it_runs_triage_issue_in_that_repository(self):  # RTN-054
        self.assertIn("/triage-issue", self.prompt)
        self.assertIn("in that repository", self.prompt)

    def test_it_stays_short(self):  # RTN-054
        self.assertLess(len(self.entry["prompt"]), 700)


class TestTheFireNamesWhatProjectTriageNeeds(unittest.TestCase):
    def test_the_gatekeeper_text_names_one_issue_and_one_repository(self):  # RTN-055
        import json

        import _gatekeeper  # noqa: F401
        from downstream import Fire

        sent = {}

        def record(url, headers, body):
            sent["body"] = body
            return 200, '{"claude_code_session_id": "x"}'

        Fire("https://example.invalid", "t", transport=record).send(
            12, "derekwinters/doggiehood-api"
        )
        text = json.loads(sent["body"])["text"]
        self.assertEqual(re.findall(r"#(\d+)", text), ["12"])
        self.assertEqual(re.findall(r"\b[\w.-]+/[\w.-]+\b", text),
                         ["derekwinters/doggiehood-api"])


class TestDependabot(unittest.TestCase):
    def setUp(self):
        self.definition = load_definitions(DEFINITIONS)["dependabot"]
        self.entry = rendered("dependabot")
        self.prompt = words(self.entry["prompt"])

    def test_its_shape(self):  # RTN-051
        self.assertEqual(self.definition.requires, "hygiene")
        self.assertFalse(self.definition.api)
        self.assertEqual(self.definition.connectors, [])
        self.assertEqual(self.entry["name"], "example Dependabot")

    def test_weekly_monday_morning_central_off_the_hour(self):  # RTN-051
        zone, minute, hour, day, month, weekday = self.definition.schedule.split()
        self.assertEqual(zone, "CRON_TZ=America/Chicago")
        self.assertNotEqual(minute, "0")
        self.assertTrue(5 <= int(hour) <= 11)
        self.assertEqual((day, month, weekday), ("*", "*", "1"))

    def test_it_names_the_repository_and_the_author(self):  # RTN-052
        self.assertIn(REPO, self.prompt)
        self.assertIn("dependabot[bot]", self.prompt)

    def test_it_reads_both_kinds_of_ci(self):  # RTN-052
        self.assertIn("check runs", self.prompt)
        self.assertIn("commit statuses", self.prompt)
        self.assertIn("mergeab", self.prompt)

    def test_green_is_squash_merged_with_a_conventional_title(self):  # RTN-052
        self.assertIn("squash", self.prompt)
        self.assertIn("chore(deps):", self.prompt)
        self.assertIn("pr-title-lint", self.prompt)

    def test_behind_is_updated_through_the_api_not_a_comment(self):  # RTN-052
        self.assertIn("update-branch", self.prompt)
        self.assertIn("@dependabot", self.prompt)
        self.assertRegex(self.prompt, r"(?i)do not use `?@dependabot")

    def test_running_is_left(self):  # RTN-052
        self.assertRegex(self.prompt, r"(?i)still running")

    def test_failing_is_reported_once_and_never_touched(self):  # RTN-052
        self.assertIn("logs", self.prompt)
        self.assertRegex(self.prompt, r"(?i)search open issues")
        self.assertRegex(self.prompt, r"(?i)one issue")
        self.assertIn("redact", self.prompt)
        self.assertRegex(self.prompt, r"(?i)never push to, close, or merge")

    def test_nothing_else_is_merged(self):  # RTN-052
        self.assertRegex(self.prompt, r"(?i)never merge anything .*not authored by")

    def test_no_link_is_published(self):  # RTN-052
        self.assertIn("session link", self.prompt)
        self.assertIn("tokenized URL", self.prompt)

    def test_it_ends_with_a_summary(self):  # RTN-052
        for word in ("merged", "updated", "waiting", "filed"):
            self.assertIn(word, self.prompt.split("summary")[-1])

    def test_it_states_its_authority(self):  # RTN-053
        self.assertIn("standing instruction", self.prompt)
        self.assertIn("github-api", self.prompt)


if __name__ == "__main__":
    unittest.main()
