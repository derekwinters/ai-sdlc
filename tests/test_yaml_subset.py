"""CFG-050 to CFG-054 — the stdlib YAML subset.

Parsing without PyYAML means the accepted subset is a decision, not an
inheritance. These tests are that decision.
"""

import unittest

import _support  # noqa: F401
from lib.yaml_lite import YamlError, parse


class TestScalars(unittest.TestCase):
    def test_a_string(self):  # CFG-050
        self.assertEqual(parse("name: ai-sdlc"), {"name": "ai-sdlc"})

    def test_an_integer(self):  # CFG-050
        self.assertEqual(parse("dashboard_issue: 42"), {"dashboard_issue": 42})

    def test_a_negative_integer(self):  # CFG-050
        self.assertEqual(parse("offset: -3"), {"offset": -3})

    def test_booleans(self):  # CFG-050
        self.assertEqual(parse("a: true\nb: false"), {"a": True, "b": False})

    def test_null(self):  # CFG-050
        self.assertEqual(parse("milestone: null"), {"milestone": None})

    def test_an_empty_value_is_null(self):  # CFG-050
        self.assertEqual(parse("milestone:"), {"milestone": None})

    def test_a_number_like_string_stays_a_string_when_quoted(self):  # CFG-053
        self.assertEqual(parse('version: "1"'), {"version": "1"})


class TestLists(unittest.TestCase):
    def test_a_list_of_strings(self):  # CFG-050
        self.assertEqual(parse("owners:\n  - derek\n  - lucas"), {"owners": ["derek", "lucas"]})

    def test_an_empty_list_literal(self):  # CFG-050
        self.assertEqual(parse("owners: []"), {"owners": []})

    def test_a_list_of_one(self):  # CFG-050
        self.assertEqual(parse("owners:\n  - derek"), {"owners": ["derek"]})

    def test_a_list_keeps_its_order(self):  # CFG-050
        self.assertEqual(parse("c:\n  - b\n  - a\n  - c")["c"], ["b", "a", "c"])


class TestNesting(unittest.TestCase):
    def test_a_nested_mapping(self):  # CFG-051
        self.assertEqual(parse("bot:\n  identity: app"), {"bot": {"identity": "app"}})

    def test_two_levels(self):  # CFG-051
        parsed = parse("a:\n  b:\n    c: 1")
        self.assertEqual(parsed, {"a": {"b": {"c": 1}}})

    def test_a_sibling_after_a_nested_block(self):  # CFG-051
        parsed = parse("bot:\n  identity: app\nowners:\n  - derek")
        self.assertEqual(parsed, {"bot": {"identity": "app"}, "owners": ["derek"]})

    def test_a_list_of_mappings(self):  # CFG-051
        parsed = parse("items:\n  - name: a\n    value: 1\n  - name: b\n    value: 2")
        self.assertEqual(parsed["items"], [{"name": "a", "value": 1}, {"name": "b", "value": 2}])


class TestComments(unittest.TestCase):
    def test_a_whole_line_comment(self):  # CFG-052
        self.assertEqual(parse("# a note\nname: x"), {"name": "x"})

    def test_a_trailing_comment(self):  # CFG-052
        self.assertEqual(parse("name: x  # a note"), {"name": "x"})

    def test_a_hash_inside_quotes_is_kept(self):  # CFG-053
        self.assertEqual(parse('name: "a # b"'), {"name": "a # b"})

    def test_a_colon_inside_quotes_is_kept(self):  # CFG-053
        self.assertEqual(parse('name: "a: b"'), {"name": "a: b"})

    def test_blank_lines_are_ignored(self):  # CFG-052
        self.assertEqual(parse("a: 1\n\n\nb: 2"), {"a": 1, "b": 2})


class TestTheUnsupportedIsRefused(unittest.TestCase):
    """CFG-054 — misreading a file is worse than refusing it."""

    def refuse(self, text):
        with self.assertRaises(YamlError) as caught:
            parse(text)
        return str(caught.exception)

    def test_an_anchor_is_refused(self):
        self.assertIn("anchor", self.refuse("a: &base\n  b: 1").lower())

    def test_an_alias_is_refused(self):
        self.assertIn("alias", self.refuse("a: *base").lower())

    def test_a_second_document_is_refused(self):
        self.assertIn("document", self.refuse("a: 1\n---\nb: 2").lower())

    def test_flow_mapping_is_refused(self):
        self.assertIn("flow", self.refuse("a: {b: 1}").lower())

    def test_a_non_empty_flow_sequence_is_refused(self):
        self.assertIn("flow", self.refuse("a: [1, 2]").lower())

    def test_tabs_are_refused(self):
        self.assertIn("tab", self.refuse("a:\n\tb: 1").lower())

    def test_the_error_names_the_line(self):
        self.assertIn("2", self.refuse("a: 1\n\ta: 2"))


if __name__ == "__main__":
    unittest.main()
