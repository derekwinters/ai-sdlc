"""CFG-020 to CFG-025 — which capabilities are installed, and their order."""

import unittest

import _support  # noqa: F401
from lib.config import CAPABILITIES, DEPENDENCIES, ConfigError, parse_config

FULL = """
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


class TestTheList(unittest.TestCase):
    def test_the_names_are_the_six(self):  # CFG-020
        self.assertEqual(
            set(CAPABILITIES),
            {"substrate", "hygiene", "consistency", "labels", "release", "pipeline"},
        )

    def test_a_valid_selection_is_accepted(self):  # CFG-020
        self.assertIn("pipeline", parse_config(FULL).capabilities)

    def test_an_unknown_capability_is_refused(self):  # CFG-021
        self.assertIn("wobble", bad("capabilities:\n  - wobble"))

    def test_the_refusal_lists_the_valid_names(self):  # CFG-021
        message = bad("capabilities:\n  - wobble")
        for name in CAPABILITIES:
            self.assertIn(name, message)


class TestSubstrateIsImplied(unittest.TestCase):
    def test_it_is_added_when_absent(self):  # CFG-022
        self.assertIn("substrate", parse_config("capabilities:\n  - hygiene").capabilities)

    def test_listing_it_explicitly_is_allowed(self):  # CFG-022
        config = parse_config("capabilities:\n  - substrate\n  - hygiene")
        self.assertEqual(config.capabilities.count("substrate"), 1)

    def test_an_empty_list_still_has_substrate(self):  # CFG-022
        self.assertEqual(parse_config("capabilities: []").capabilities, ["substrate"])


class TestDependencies(unittest.TestCase):
    def test_pipeline_without_its_dependencies_is_refused(self):  # CFG-023
        self.assertIn("pipeline", bad("capabilities:\n  - pipeline"))

    def test_the_refusal_names_what_is_missing(self):  # CFG-023
        message = bad("capabilities:\n  - pipeline")
        self.assertIn("hygiene", message)
        self.assertIn("consistency", message)

    def test_release_requires_hygiene(self):  # CFG-023
        self.assertIn("hygiene", bad("capabilities:\n  - release"))

    def test_hygiene_alone_is_fine(self):  # CFG-023
        self.assertEqual(parse_config("capabilities:\n  - hygiene").capabilities[-1], "hygiene")

    def test_consistency_alone_is_fine(self):  # CFG-023
        self.assertIn("consistency", parse_config("capabilities:\n  - consistency").capabilities)

    def test_labels_alone_is_fine(self):  # CFG-023
        self.assertIn("labels", parse_config("capabilities:\n  - labels").capabilities)


class TestTheDependencyTable(unittest.TestCase):
    """CFG-024 — declared once, and acyclic by construction."""

    def test_every_capability_appears(self):
        self.assertEqual(set(DEPENDENCIES), set(CAPABILITIES))

    def test_every_dependency_is_a_known_capability(self):
        for name, needs in DEPENDENCIES.items():
            for need in needs:
                self.assertIn(need, CAPABILITIES, f"{name} -> {need}")

    def test_a_capability_only_depends_on_earlier_ones(self):
        order = list(CAPABILITIES)
        for name, needs in DEPENDENCIES.items():
            for need in needs:
                self.assertLess(order.index(need), order.index(name), f"{name} -> {need}")

    def test_substrate_depends_on_nothing(self):
        self.assertEqual(DEPENDENCIES["substrate"], ())


class TestProfiles(unittest.TestCase):
    def test_a_known_profile_is_accepted(self):  # CFG-025
        config = parse_config("capabilities:\n  - hygiene\nprofiles:\n  - unity")
        self.assertEqual(config.profiles, ["unity"])

    def test_an_unknown_profile_is_refused(self):  # CFG-025
        self.assertIn("wobble", bad("capabilities:\n  - hygiene\nprofiles:\n  - wobble"))

    def test_profiles_default_to_empty(self):  # CFG-025
        self.assertEqual(parse_config("capabilities:\n  - hygiene").profiles, [])


if __name__ == "__main__":
    unittest.main()
