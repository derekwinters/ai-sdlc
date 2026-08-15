"""REL-030 to REL-034 — confirming the release actually happened."""

import unittest

import _release  # noqa: F401
from release_flow import Verification, verify_release


class World:
    """A repository that reveals the tag and release after N attempts."""

    def __init__(self, tag_after=0, release_after=0, version="0.3.0"):
        self.tag_after = tag_after
        self.release_after = release_after
        self.version = version
        self.attempts = 0

    def tag(self, name):
        self.attempts += 1
        return self.attempts > self.tag_after

    def release(self, name):
        return self.attempts > self.release_after

    def recorded_version(self):
        return self.version


def verify(world, version="0.3.0", attempts=3):
    return verify_release(world, version, attempts=attempts, sleep=lambda _s: None)


class TestASuccessfulRelease(unittest.TestCase):
    def test_it_is_complete(self):  # REL-030
        self.assertTrue(verify(World()).complete)

    def test_the_tag_is_confirmed(self):  # REL-030
        self.assertTrue(verify(World()).tag_found)

    def test_the_release_is_confirmed(self):  # REL-031
        self.assertTrue(verify(World()).release_found)

    def test_the_version_matches(self):  # REL-032
        self.assertTrue(verify(World()).version_matches)


class TestIncompleteReleases(unittest.TestCase):
    def test_a_missing_tag_is_incomplete(self):  # REL-033
        self.assertFalse(verify(World(tag_after=99)).complete)

    def test_a_missing_release_is_incomplete(self):  # REL-033
        self.assertFalse(verify(World(release_after=99)).complete)

    def test_a_mismatched_version_is_incomplete(self):  # REL-032
        self.assertFalse(verify(World(version="0.2.0")).complete)

    def test_the_report_says_which_part_is_missing(self):  # REL-033
        result = verify(World(tag_after=99))
        self.assertIn("tag", result.reason.lower())

    def test_a_missing_release_names_the_release(self):  # REL-033
        result = verify(World(release_after=99))
        self.assertIn("release", result.reason.lower())

    def test_incomplete_is_distinct_from_failed(self):  # REL-033
        """The merge succeeded; the release did not complete. Different problems."""
        result = verify(World(tag_after=99))
        self.assertIsInstance(result, Verification)
        self.assertFalse(result.complete)


class TestRetrying(unittest.TestCase):
    def test_a_tag_appearing_late_is_found(self):  # REL-034
        self.assertTrue(verify(World(tag_after=1)).complete)

    def test_it_gives_up_after_the_configured_attempts(self):  # REL-034
        world = World(tag_after=99)
        verify(world, attempts=3)
        self.assertEqual(world.attempts, 3)

    def test_one_attempt_is_allowed(self):  # REL-034
        world = World()
        self.assertTrue(verify(world, attempts=1).complete)


if __name__ == "__main__":
    unittest.main()
