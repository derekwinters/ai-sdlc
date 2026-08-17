#!/usr/bin/env python3
"""`sweep:` — the bounds on what the backstop may spend.

These are configuration rather than constants because they are the only thing
standing between a reconciliation fault and an account's usage limits, and the
right value depends on how big a board is and how often the schedule runs. The
defaults are set as a circuit breaker, not a throttle: high enough that
ordinary operation never reaches them, so reaching one is evidence of a fault.

Specification: docs/spec/configuration.md (`CFG`), docs/spec/gatekeeper.md
(`GK-139`, `GK-141`).
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lib.config import ConfigError, load  # noqa: E402

BASE = """
capabilities:
  - hygiene
  - labels
  - consistency
  - release
  - pipeline
owners:
  - someone
dashboard_issue: 1
"""


def config(extra="", tmp=None):
    path = Path(tmp) / "repo-config.yml"
    path.write_text(BASE + extra)
    return load(path=path)


class TestDefaults(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.tmp = tempfile.mkdtemp()

    def test_a_repository_that_says_nothing_still_has_bounds(self):  # CFG-055
        """Absent configuration must not mean an unbounded sweep."""
        sweep = config(tmp=self.tmp).sweep
        self.assertGreater(sweep.ceiling, 0)
        self.assertGreater(sweep.stale_after, 0)

    def test_the_default_ceiling_clears_an_ordinary_board(self):  # CFG-055
        """A circuit breaker, not a throttle. A ceiling that bit during normal
        operation would train its owner to raise it until it never bit at all.
        """
        self.assertGreaterEqual(config(tmp=self.tmp).sweep.ceiling, 10)

    def test_there_is_no_give_up_duration(self):  # CFG-055
        """How many times an issue may be poked is carried by the markers, not
        by a clock. A duration was tried and removed: every clock available
        here is reset by ordinary activity, so it bounded nothing."""
        self.assertFalse(hasattr(config(tmp=self.tmp).sweep, "give_up_after"))


class TestOverrides(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.tmp = tempfile.mkdtemp()

    def test_a_repository_may_lower_the_ceiling(self):  # CFG-056
        self.assertEqual(
            config("sweep:\n  ceiling: 3\n", tmp=self.tmp).sweep.ceiling, 3)

    def test_a_ceiling_of_zero_is_allowed_as_an_off_switch(self):  # CFG-056
        """Turning the backstop off is a setting, not a code change."""
        self.assertEqual(
            config("sweep:\n  ceiling: 0\n", tmp=self.tmp).sweep.ceiling, 0)

    def test_a_negative_ceiling_is_refused(self):  # CFG-056
        with self.assertRaises(ConfigError):
            config("sweep:\n  ceiling: -1\n", tmp=self.tmp)

    def test_an_unknown_sweep_key_is_refused(self):  # CFG-056
        """A misspelled bound that silently defaults is a bound nobody has."""
        with self.assertRaises(ConfigError):
            config("sweep:\n  celing: 3\n", tmp=self.tmp)

    def test_a_negative_staleness_is_refused(self):  # CFG-056
        with self.assertRaises(ConfigError):
            config("sweep:\n  stale_after: -1\n", tmp=self.tmp)

    def test_a_removed_key_is_refused_rather_than_ignored(self):  # CFG-056
        """`give_up_after` was real for one version. A repository still setting
        it should be told, not silently given an unbounded-looking sweep whose
        bound now lives somewhere else."""
        with self.assertRaises(ConfigError):
            config("sweep:\n  give_up_after: 3600\n", tmp=self.tmp)


if __name__ == "__main__":
    unittest.main()
