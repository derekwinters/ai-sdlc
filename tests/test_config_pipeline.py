"""CFG-040 to CFG-046 — the pipeline's own settings."""

import unittest

import _support  # noqa: F401
from lib.config import STATES, ConfigError, parse_config

BASE = """
capabilities:
  - hygiene
  - consistency
  - labels
  - release
  - pipeline
owners:
  - derekwinters
dashboard_issue: 5
"""


def bad(text):
    try:
        parse_config(text)
    except ConfigError as error:
        return str(error)
    raise AssertionError("expected a ConfigError")


class TestMilestoneOrdering(unittest.TestCase):
    def test_semver_is_the_default(self):  # CFG-040
        self.assertEqual(parse_config(BASE).milestone_ordering, "semver")

    def test_each_strategy_is_accepted(self):  # CFG-040
        for strategy in ("semver", "date", "lexical", "none"):
            config = parse_config(BASE + f"milestone_ordering: {strategy}\n")
            self.assertEqual(config.milestone_ordering, strategy)

    def test_an_unknown_strategy_is_refused(self):  # CFG-040
        self.assertIn("milestone_ordering", bad(BASE + "milestone_ordering: vibes\n"))

    def test_the_refusal_lists_the_strategies(self):  # CFG-040
        self.assertIn("lexical", bad(BASE + "milestone_ordering: vibes\n"))


class TestDashboardIssue(unittest.TestCase):
    def test_a_positive_integer_is_accepted(self):  # CFG-041
        self.assertEqual(parse_config(BASE).dashboard_issue, 5)

    def test_pipeline_without_one_is_refused(self):  # CFG-041
        self.assertIn("dashboard_issue", bad(BASE.replace("dashboard_issue: 5", "")))

    def test_zero_is_refused(self):  # CFG-041
        self.assertIn("dashboard_issue", bad(BASE.replace("5", "0")))

    def test_a_negative_number_is_refused(self):  # CFG-041
        self.assertIn("dashboard_issue", bad(BASE.replace("dashboard_issue: 5", "dashboard_issue: -1")))


class TestLabelVocabulary(unittest.TestCase):
    def test_every_state_has_a_label_by_default(self):  # CFG-043
        labels = parse_config(BASE).labels
        for state in STATES:
            self.assertIn(state, labels)

    def test_a_partial_mapping_overrides_only_what_it_names(self):  # CFG-043
        config = parse_config(BASE + "labels:\n  approved: queued\n")
        self.assertEqual(config.labels["approved"], "queued")
        self.assertEqual(config.labels["triage_queued"], "ai-triage-queued")

    def test_an_unknown_state_name_is_refused(self):  # CFG-042
        self.assertIn("wobble", bad(BASE + "labels:\n  wobble: x\n"))

    def test_two_states_may_not_share_a_label(self):  # CFG-044
        message = bad(BASE + "labels:\n  approved: ai-triage-queued\n")
        self.assertIn("ai-triage-queued", message)

    def test_the_collision_message_names_both_states(self):  # CFG-044
        message = bad(BASE + "labels:\n  approved: ai-triage-queued\n")
        self.assertIn("approved", message)
        self.assertIn("triage", message)


class TestCommands(unittest.TestCase):
    def test_commands_are_optional(self):  # CFG-045
        self.assertIsNone(parse_config(BASE).commands.test)

    def test_a_command_is_a_shell_string(self):  # CFG-045
        config = parse_config(BASE + "commands:\n  test: python3 -m unittest\n")
        self.assertEqual(config.commands.test, "python3 -m unittest")

    def test_all_three_are_supported(self):  # CFG-045
        config = parse_config(
            BASE + "commands:\n  test: a\n  verify: b\n  spec_validator: c\n"
        )
        self.assertEqual(
            (config.commands.test, config.commands.verify, config.commands.spec_validator),
            ("a", "b", "c"),
        )


class TestFireSecretsAreNames(unittest.TestCase):
    def test_a_secret_name_is_accepted(self):  # CFG-046
        config = parse_config(BASE + "fire:\n  endpoint_secret: FIRE_URL\n")
        self.assertEqual(config.fire.endpoint_secret, "FIRE_URL")

    def test_a_url_where_a_secret_name_belongs_is_refused(self):  # CFG-046
        self.assertIn(
            "secret", bad(BASE + "fire:\n  endpoint_secret: https://example.com/fire\n").lower()
        )

    def test_a_token_like_value_is_refused(self):  # CFG-046
        self.assertIn(
            "secret",
            bad(BASE + "fire:\n  token_secret: ghp_abcdefghijklmnopqrstuvwxyz0123456789\n").lower(),
        )


if __name__ == "__main__":
    unittest.main()
