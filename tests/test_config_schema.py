"""CFG-010 — the published schema and the loader cannot drift apart.

The loader validates in Python (stdlib only, no jsonschema). The schema file is
the published contract that editors and `adopt` read. Two descriptions of the
same thing drift unless something compares them, so this does.
"""

import json
import unittest

from _support import ROOT
from lib.config import (
    BOT_IDENTITIES,
    CAPABILITIES,
    ORDERING_STRATEGIES,
    PROFILES,
    STATES,
    _NESTED_KEYS,
    _SCHEMA_KEYS,
    load,
)

SCHEMA = json.loads((ROOT / "schema" / "repo-config.schema.json").read_text())


class TestTheSchemaMatchesTheLoader(unittest.TestCase):
    def test_the_same_top_level_keys(self):
        self.assertEqual(set(SCHEMA["properties"]), set(_SCHEMA_KEYS))

    def test_unknown_keys_are_refused_by_both(self):
        self.assertFalse(SCHEMA["additionalProperties"])

    def test_the_same_capabilities(self):
        self.assertEqual(
            set(SCHEMA["properties"]["capabilities"]["items"]["enum"]), set(CAPABILITIES)
        )

    def test_the_same_profiles(self):
        self.assertEqual(set(SCHEMA["properties"]["profiles"]["items"]["enum"]), set(PROFILES))

    def test_the_same_ordering_strategies(self):
        self.assertEqual(
            set(SCHEMA["properties"]["milestone_ordering"]["enum"]), set(ORDERING_STRATEGIES)
        )

    def test_the_same_bot_identities(self):
        self.assertEqual(
            set(SCHEMA["properties"]["bot"]["properties"]["identity"]["enum"]),
            set(BOT_IDENTITIES),
        )

    def test_the_same_pipeline_states(self):
        self.assertEqual(set(SCHEMA["properties"]["labels"]["properties"]), set(STATES))

    def test_the_same_nested_keys(self):
        for section, keys in _NESTED_KEYS.items():
            self.assertEqual(
                set(SCHEMA["properties"][section]["properties"]), set(keys), section
            )

    def test_the_defaults_agree(self):
        self.assertEqual(SCHEMA["properties"]["milestone_ordering"]["default"], "semver")
        bot = SCHEMA["properties"]["bot"]["properties"]
        self.assertEqual(bot["identity"]["default"], "github-actions")
        self.assertEqual(bot["login"]["default"], "github-actions[bot]")


class TestTheExamplesAreValid(unittest.TestCase):
    """An example that does not load is worse than no example."""

    def test_the_minimal_example_loads(self):
        config = load(path=ROOT / "examples" / "repo-config.minimal.yml")
        self.assertEqual(config.capabilities, ["substrate", "hygiene"])

    def test_the_minimal_example_installs_no_pipeline(self):
        self.assertFalse(load(path=ROOT / "examples" / "repo-config.minimal.yml").has("pipeline"))

    def test_the_full_example_loads(self):
        config = load(path=ROOT / "examples" / "repo-config.full.yml")
        self.assertTrue(config.has("pipeline"))

    def test_the_full_example_has_an_owner_and_a_dashboard(self):
        config = load(path=ROOT / "examples" / "repo-config.full.yml")
        self.assertEqual(config.owners, ["derekwinters"])
        self.assertEqual(config.dashboard_issue, 193)

    def test_the_full_example_exercises_every_top_level_key(self):
        """Otherwise a key can be added and never demonstrated."""
        text = (ROOT / "examples" / "repo-config.full.yml").read_text()
        for key in _SCHEMA_KEYS:
            self.assertIn(f"{key}:", text, key)


if __name__ == "__main__":
    unittest.main()
