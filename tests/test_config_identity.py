"""CFG-030 to CFG-034 — who commands, and who writes."""

import unittest

import _support  # noqa: F401
from lib.config import ConfigError, parse_config

PIPELINE = """
capabilities:
  - hygiene
  - consistency
  - labels
  - release
  - pipeline
dashboard_issue: 5
owners:
"""


def bad(text):
    try:
        parse_config(text)
    except ConfigError as error:
        return str(error)
    raise AssertionError("expected a ConfigError")


class TestOwners(unittest.TestCase):
    def test_a_list_of_one_is_the_normal_case(self):  # CFG-031
        self.assertEqual(parse_config(PIPELINE + "  - derekwinters").owners, ["derekwinters"])

    def test_several_owners_are_allowed(self):  # CFG-030
        config = parse_config(PIPELINE + "  - derekwinters\n  - someone-else")
        self.assertEqual(len(config.owners), 2)

    def test_pipeline_without_owners_is_refused(self):  # CFG-030
        self.assertIn("owners", bad(PIPELINE.replace("owners:", "")))

    def test_an_empty_owner_list_is_refused_with_pipeline(self):  # CFG-030
        self.assertIn("owners", bad(PIPELINE + "\n"))

    def test_a_scalar_owner_is_refused(self):  # CFG-031
        self.assertIn("list", bad("capabilities:\n  - hygiene\nowners: derekwinters").lower())

    def test_owners_are_optional_without_pipeline(self):  # CFG-030
        self.assertEqual(parse_config("capabilities:\n  - hygiene").owners, [])


class TestBotIdentity(unittest.TestCase):
    def test_github_actions_is_the_default(self):  # CFG-032
        self.assertEqual(parse_config("capabilities:\n  - hygiene").bot.identity, "github-actions")

    def test_app_is_allowed(self):  # CFG-032
        text = (
            "capabilities:\n  - hygiene\nbot:\n  identity: app\n"
            "  app_id_secret: SDLC_APP_ID\n  private_key_secret: SDLC_APP_KEY"
        )
        self.assertEqual(parse_config(text).bot.identity, "app")

    def test_an_unknown_identity_is_refused(self):  # CFG-032
        self.assertIn("identity", bad("capabilities:\n  - hygiene\nbot:\n  identity: wobble"))

    def test_app_without_its_secrets_is_refused(self):  # CFG-033
        self.assertIn(
            "app_id_secret", bad("capabilities:\n  - hygiene\nbot:\n  identity: app")
        )

    def test_secrets_without_app_identity_are_refused(self):  # CFG-033
        self.assertIn(
            "app_id_secret",
            bad("capabilities:\n  - hygiene\nbot:\n  app_id_secret: SDLC_APP_ID"),
        )

    def test_the_watermark_login_defaults(self):  # CFG-034
        self.assertEqual(parse_config("capabilities:\n  - hygiene").bot.login, "github-actions[bot]")

    def test_the_watermark_login_is_configurable(self):  # CFG-034
        text = "capabilities:\n  - hygiene\nbot:\n  login: sdlc-bot[bot]"
        self.assertEqual(parse_config(text).bot.login, "sdlc-bot[bot]")


if __name__ == "__main__":
    unittest.main()
