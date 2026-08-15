"""GK-061, GK-063 — comparing milestone titles under each strategy.

Milestones meaning versions is a property of how a repository names them, not
a universal fact. `Direct Involvement Needed` is a real milestone in this very
repository and orders under none of the version schemes.
"""

import unittest

import _gatekeeper  # noqa: F401
from ordering import UNORDERED, ordering_for


class TestSemver(unittest.TestCase):
    def setUp(self):
        self.rank = ordering_for("semver")

    def test_a_version_title_orders(self):  # GK-061
        self.assertNotEqual(self.rank("v0.4"), UNORDERED)

    def test_a_patch_orders_within_its_minor(self):  # GK-061
        self.assertLess(self.rank("v0.4.1"), self.rank("v0.5"))

    def test_a_minor_bump_orders_above_a_patch(self):  # GK-061
        self.assertLess(self.rank("v0.4.9"), self.rank("v0.5.0"))

    def test_a_major_bump_orders_above_a_minor(self):  # GK-061
        self.assertLess(self.rank("v0.16"), self.rank("v1.0"))

    def test_numeric_not_lexical(self):  # GK-061
        """v0.16 is after v0.4, which string comparison gets wrong."""
        self.assertLess(self.rank("v0.4"), self.rank("v0.16"))

    def test_a_title_with_a_suffix_still_orders(self):  # GK-061
        self.assertLess(self.rank("v0.1 — Gatekeeper pilot"), self.rank("v0.2 — State"))

    def test_a_leading_v_is_optional(self):  # GK-061
        self.assertEqual(self.rank("0.4"), self.rank("v0.4"))

    def test_a_non_version_title_is_unordered(self):  # GK-061
        self.assertEqual(self.rank("Direct Involvement Needed"), UNORDERED)

    def test_an_empty_title_is_unordered(self):  # GK-061
        self.assertEqual(self.rank(""), UNORDERED)

    def test_none_is_unordered(self):  # GK-061
        self.assertEqual(self.rank(None), UNORDERED)


class TestDate(unittest.TestCase):
    def setUp(self):
        self.rank = ordering_for("date")

    def test_an_iso_date_orders(self):  # GK-061
        self.assertLess(self.rank("2026-01-15"), self.rank("2026-02-01"))

    def test_a_date_with_a_suffix_orders(self):  # GK-061
        self.assertLess(self.rank("2026-01 January"), self.rank("2026-02 February"))

    def test_a_year_month_orders(self):  # GK-061
        self.assertLess(self.rank("2025-12"), self.rank("2026-01"))

    def test_a_non_date_is_unordered(self):  # GK-061
        self.assertEqual(self.rank("Someday"), UNORDERED)


class TestLexical(unittest.TestCase):
    def setUp(self):
        self.rank = ordering_for("lexical")

    def test_titles_order_alphabetically(self):  # GK-061
        self.assertLess(self.rank("alpha"), self.rank("beta"))

    def test_case_does_not_matter(self):  # GK-061
        self.assertLess(self.rank("Alpha"), self.rank("beta"))

    def test_everything_orders(self):  # GK-061
        self.assertNotEqual(self.rank("anything at all"), UNORDERED)

    def test_an_empty_title_is_still_unordered(self):  # GK-061
        self.assertEqual(self.rank(""), UNORDERED)


class TestNone(unittest.TestCase):
    def test_nothing_orders(self):  # GK-063
        rank = ordering_for("none")
        for title in ("v0.4", "2026-01-01", "anything"):
            self.assertEqual(rank(title), UNORDERED, title)


class TestTheStrategyComesFromConfiguration(unittest.TestCase):
    def test_an_unknown_strategy_raises_rather_than_defaulting(self):  # GK-061
        with self.assertRaises(ValueError):
            ordering_for("vibes")

    def test_every_configured_strategy_is_implemented(self):  # GK-061
        from lib.config import ORDERING_STRATEGIES

        for strategy in ORDERING_STRATEGIES:
            self.assertTrue(callable(ordering_for(strategy)), strategy)


if __name__ == "__main__":
    unittest.main()
