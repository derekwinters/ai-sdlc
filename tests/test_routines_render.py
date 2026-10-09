"""RTN-010 to RTN-014 — turning a template into the text a routine will hold.

An unknown placeholder is the failure that matters here: passed through, it
becomes a live routine telling a fresh session about a repository literally
called `{repository}`, and nothing complains until it runs.
"""

import unittest

import _routines  # noqa: F401
from routines import RoutineError, render, repository_slug


VALUES = {"repo": "derekwinters/example", "owner": "derekwinters", "repo_name": "example"}


class TestPlaceholders(unittest.TestCase):
    def test_each_placeholder_renders(self):  # RTN-010
        self.assertEqual(
            render("{repo} {owner} {repo_name}", "derekwinters/example", "t"),
            "derekwinters/example derekwinters example",
        )

    def test_a_template_with_none_is_unchanged(self):  # RTN-010
        self.assertEqual(render("plain text", "a/b", "t"), "plain text")


class TestAnUnknownPlaceholderIsAnError(unittest.TestCase):
    def test_it_is_refused(self):  # RTN-011
        with self.assertRaises(RoutineError) as caught:
            render("Work in {repository}.", "a/b", "triage")
        message = " ".join(caught.exception.problems)
        self.assertIn("{repository}", message)
        self.assertIn("triage", message)

    def test_every_unknown_placeholder_is_named(self):  # RTN-011
        with self.assertRaises(RoutineError) as caught:
            render("{one} and {two}", "a/b", "t")
        self.assertEqual(len(caught.exception.problems), 2)

    def test_a_case_variant_is_unknown(self):  # RTN-011
        with self.assertRaises(RoutineError):
            render("{Repo}", "a/b", "t")


class TestLiteralBraces(unittest.TestCase):
    def test_doubled_braces_are_literal(self):  # RTN-012
        self.assertEqual(render("{{repo}} is {repo}", "a/b", "t"), "{repo} is a/b")

    def test_a_lone_brace_with_space_is_left_alone(self):  # RTN-012
        self.assertEqual(render("a { b } c", "a/b", "t"), "a { b } c")


class TestWhichRepository(unittest.TestCase):
    def test_an_explicit_name_wins(self):  # RTN-013
        self.assertEqual(
            repository_slug("o/r", environ={"GITHUB_REPOSITORY": "x/y"}, remote=lambda: None),
            "o/r",
        )

    def test_the_environment_comes_next(self):  # RTN-013
        self.assertEqual(
            repository_slug(None, environ={"GITHUB_REPOSITORY": "x/y"}, remote=lambda: "z"),
            "x/y",
        )

    def test_the_remote_is_the_fallback(self):  # RTN-013
        for url in ("git@github.com:derekwinters/example.git",
                    "https://github.com/derekwinters/example",
                    "http://proxy@127.0.0.1:1234/git/derekwinters/example"):
            with self.subTest(url=url):
                self.assertEqual(
                    repository_slug(None, environ={}, remote=lambda u=url: u),
                    "derekwinters/example",
                )

    def test_something_that_is_not_owner_slash_name_is_refused(self):  # RTN-013
        for bad in ("example", "a/b/c", "a b/c", ""):
            with self.subTest(bad=bad):
                with self.assertRaises(RoutineError):
                    repository_slug(bad, environ={}, remote=lambda: None)

    def test_no_source_at_all_is_refused(self):  # RTN-013
        with self.assertRaises(RoutineError):
            repository_slug(None, environ={}, remote=lambda: None)


class TestTheRemoteIsNeverQuoted(unittest.TestCase):
    def test_an_unparseable_remote_is_not_echoed(self):  # RTN-014
        url = "https://x-access-token:ghs_SECRETVALUE@example.invalid/"
        with self.assertRaises(RoutineError) as caught:
            repository_slug(None, environ={}, remote=lambda: url)
        message = str(caught.exception)
        self.assertNotIn("SECRETVALUE", message)
        self.assertNotIn("example.invalid", message)


if __name__ == "__main__":
    unittest.main()
