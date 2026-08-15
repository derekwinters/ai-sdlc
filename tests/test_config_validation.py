"""CFG-010 to CFG-015 — refusing what it cannot understand."""

import unittest

import _support  # noqa: F401
from lib.config import ConfigError, parse_config


def bad(text):
    try:
        parse_config(text)
    except ConfigError as error:
        return str(error)
    raise AssertionError("expected a ConfigError")


class TestUnknownKeys(unittest.TestCase):
    def test_an_unknown_top_level_key_is_refused(self):  # CFG-011
        self.assertIn("wobble", bad("wobble: 1"))

    def test_the_refusal_suggests_the_valid_keys(self):  # CFG-011
        message = bad("wobble: 1")
        self.assertIn("capabilities", message)

    def test_a_near_miss_is_named(self):  # CFG-011
        self.assertIn("capabilities", bad("capabilties:\n  - hygiene"))

    def test_an_unknown_nested_key_is_refused(self):  # CFG-011
        self.assertIn("bot.wobble", bad("bot:\n  wobble: 1"))


class TestTypes(unittest.TestCase):
    def test_a_wrong_type_names_the_key(self):  # CFG-012
        self.assertIn("capabilities", bad("capabilities: hygiene"))

    def test_a_wrong_type_names_the_expected_type(self):  # CFG-012
        self.assertIn("list", bad("capabilities: hygiene").lower())

    def test_a_wrong_type_names_what_was_found(self):  # CFG-012
        self.assertIn("str", bad("capabilities: hygiene").lower())

    def test_a_nested_key_path_is_reported(self):  # CFG-013
        self.assertIn("bot.identity", bad("bot:\n  identity: 3"))


class TestEveryProblemIsReported(unittest.TestCase):
    def test_two_problems_are_both_reported(self):  # CFG-014
        message = bad("wobble: 1\nfizz: 2")
        self.assertIn("wobble", message)
        self.assertIn("fizz", message)


class TestDefaults(unittest.TestCase):
    def setUp(self):
        self.config = parse_config("capabilities:\n  - hygiene")

    def test_bot_identity_defaults(self):  # CFG-015, CFG-032
        self.assertEqual(self.config.bot.identity, "github-actions")

    def test_bot_login_defaults(self):  # CFG-034
        self.assertEqual(self.config.bot.login, "github-actions[bot]")

    def test_milestone_ordering_defaults(self):  # CFG-040
        self.assertEqual(self.config.milestone_ordering, "semver")

    def test_labels_default_to_the_canonical_vocabulary(self):  # CFG-042
        self.assertEqual(self.config.labels["approved"], "ready-for-work")

    def test_optional_commands_are_present_and_empty(self):  # CFG-015
        self.assertIsNone(self.config.commands.test)

    def test_a_caller_never_needs_a_fallback(self):  # CFG-015
        for name in ("capabilities", "profiles", "owners", "labels", "milestone_ordering"):
            self.assertIsNotNone(getattr(self.config, name), name)


if __name__ == "__main__":
    unittest.main()
