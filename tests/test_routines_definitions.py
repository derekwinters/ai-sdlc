"""RTN-001 to RTN-007 — what a routine definition is, and what it may say.

A definition is a file in the skill, so it ships and pins with the skill. Its
front matter is read by the skill's own stdlib reader, because the skill runs
in a consumer where `lib` does not exist.
"""

import unittest

import _routines  # noqa: F401 - puts the skill on sys.path
from _routines import DEFINITIONS, definition, directory
from routines import (
    CAPABILITIES,
    RoutineError,
    load_definition,
    load_definitions,
    parse_front_matter,
)


def refused(text, stem="sample"):
    path = directory({stem: text}) / f"{stem}.md"
    with unittest.TestCase().assertRaises(RoutineError) as caught:
        load_definition(path)
    return " ".join(caught.exception.problems)


def loaded(text, stem="sample"):
    return load_definition(directory({stem: text}) / f"{stem}.md")


class TestADefinitionIsAFile(unittest.TestCase):
    def test_front_matter_and_body_are_split(self):  # RTN-001
        item = loaded(definition(api=True, body="Hello {repo}.\n"))
        self.assertEqual(item.id, "sample")
        self.assertEqual(item.prompt, "Hello {repo}.")

    def test_the_id_is_the_file_name(self):  # RTN-001
        self.assertIn("file name", refused(definition(id="other", api=True)))

    def test_a_file_without_front_matter_is_refused(self):  # RTN-001
        self.assertIn("front matter", refused("Just a prompt.\n"))

    def test_definitions_are_found_by_directory(self):  # RTN-001
        found = load_definitions(directory({
            "a": definition(id="a", api=True), "b": definition(id="b", api=True),
        }))
        self.assertEqual(sorted(found), ["a", "b"])


class TestTheKeys(unittest.TestCase):
    def test_each_required_key_is_required(self):  # RTN-002
        for key in ("name", "requires", "session"):
            with self.subTest(key=key):
                kwargs = {key: None} if key == "session" else {}
                text = definition(api=True, **kwargs)
                if key != "session":
                    text = "\n".join(l for l in text.splitlines() if not l.startswith(key + ":"))
                self.assertIn(key, refused(text))

    def test_a_trigger_is_required(self):  # RTN-002
        self.assertIn("trigger", refused(definition()))

    def test_api_false_alone_is_no_trigger(self):  # RTN-002
        self.assertIn("trigger", refused(definition(api=False)))

    def test_an_unknown_key_is_named(self):  # RTN-002
        self.assertIn("colour", refused(definition(api=True, extra="colour: blue")))

    def test_every_problem_is_reported(self):  # RTN-002
        text = definition(requires="nonsense", session="reused", extra="colour: blue")
        found = refused(text)
        for word in ("nonsense", "reused", "colour", "trigger"):
            self.assertIn(word, found)


class TestTheReaderAgreesWithLib(unittest.TestCase):
    """RTN-003 — two readers of one subset, compared rather than shared."""

    def test_every_shipped_definition_reads_the_same_both_ways(self):  # RTN-003
        from lib.yaml_lite import parse

        for path in sorted(DEFINITIONS.glob("*.md")):
            with self.subTest(definition=path.name):
                text = path.read_text()
                ours, _ = parse_front_matter(text)
                block = text.split("---\n", 2)[1]
                self.assertEqual(ours, parse(block))

    def test_the_constructs_it_accepts_read_the_same_both_ways(self):  # RTN-003
        from lib.yaml_lite import parse

        block = (
            'id: x\nname: "{repo_name} # not a comment: really"\napi: true\n'
            "flag: false\nempty: []\nnothing:\nlist:\n  - a\n  - 'b'\ncount: 3  # c\n"
        )
        ours, _ = parse_front_matter("---\n" + block + "---\nbody\n")
        self.assertEqual(ours, parse(block))

    def test_a_construct_outside_the_subset_is_refused(self):  # RTN-003
        for line in ("connectors: [a, b]", "name: &anchor x", "meta:\n  nested: 1"):
            with self.subTest(line=line):
                with self.assertRaises(RoutineError):
                    parse_front_matter("---\nid: x\n" + line + "\n---\nbody\n")


class TestRequires(unittest.TestCase):
    def test_the_capability_list_matches_the_loaders(self):  # RTN-004
        from lib.config import CAPABILITIES as LOADERS

        self.assertEqual(tuple(CAPABILITIES), tuple(LOADERS))

    def test_an_unknown_capability_is_refused(self):  # RTN-004
        self.assertIn("nonsense", refused(definition(api=True, requires="nonsense")))


class TestTheSchedule(unittest.TestCase):
    def test_a_plain_cron_is_accepted(self):  # RTN-005
        self.assertEqual(loaded(definition(schedule="52 7 * * 1")).schedule, "52 7 * * 1")

    def test_a_time_zone_prefix_is_accepted(self):  # RTN-005
        cron = "CRON_TZ=America/Chicago 52 7 * * 1"
        self.assertEqual(loaded(definition(schedule=cron)).schedule, cron)

    def test_the_wrong_number_of_fields_is_refused(self):  # RTN-005
        self.assertIn("five", refused(definition(schedule="52 7 * *")))

    def test_more_often_than_hourly_is_refused(self):  # RTN-005
        for minute in ("*", "*/5", "0,30", "0-10"):
            with self.subTest(minute=minute):
                self.assertIn("hour", refused(definition(schedule=f"{minute} 7 * * 1")))

    def test_an_out_of_range_minute_is_refused(self):  # RTN-005
        self.assertIn("minute", refused(definition(schedule="60 7 * * 1")))

    def test_an_empty_zone_is_refused(self):  # RTN-005
        self.assertIn("CRON_TZ", refused(definition(schedule="CRON_TZ= 52 7 * * 1")))


class TestConnectorsAndSession(unittest.TestCase):
    def test_connectors_default_to_none(self):  # RTN-006
        self.assertEqual(loaded(definition(api=True)).connectors, [])

    def test_connectors_are_kept_as_declared(self):  # RTN-006
        item = loaded(definition(api=True, connectors=["Linear", "Slack"]))
        self.assertEqual(item.connectors, ["Linear", "Slack"])

    def test_a_connector_must_be_a_name(self):  # RTN-006
        self.assertIn("connectors", refused(definition(api=True, extra="connectors: Linear")))

    def test_only_a_fresh_session_is_accepted(self):  # RTN-006
        self.assertIn("fresh", refused(definition(api=True, session="reused")))


class TestEveryShippedDefinitionIsValid(unittest.TestCase):
    def test_they_all_load(self):  # RTN-007
        found = load_definitions(DEFINITIONS)
        self.assertEqual(sorted(found), sorted(p.stem for p in DEFINITIONS.glob("*.md")))
        self.assertIn("triage", found)
        self.assertIn("dependabot", found)


if __name__ == "__main__":
    unittest.main()
