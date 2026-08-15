"""CIW-020 to CIW-024 — what a failure report contains."""

import unittest

from _ciwatch import check
import _ciwatch  # noqa: F401
from ci_watch import MAX_EXCERPT, Check, attach_logs


class Logs:
    def __init__(self, logs=None, error=None):
        self.logs = logs or {}
        self.error = error
        self.asked = []

    def __call__(self, name):
        self.asked.append(name)
        if self.error:
            raise self.error
        return self.logs.get(name, "")


def failed(name="build"):
    return Check(name, "completed", "failure")


def passed(name="lint"):
    return Check(name, "completed", "success")


class TestExcerpts(unittest.TestCase):
    def test_a_failed_check_gets_its_log(self):  # CIW-020
        checks = attach_logs([failed()], Logs({"build": "boom"}))
        self.assertIn("boom", checks[0].detail)

    def test_a_passing_check_is_not_fetched(self):  # CIW-020
        logs = Logs({"lint": "fine"})
        attach_logs([passed()], logs)
        self.assertEqual(logs.asked, [])

    def test_the_excerpt_is_bounded(self):  # CIW-021
        checks = attach_logs([failed()], Logs({"build": "x" * 100_000}))
        self.assertLessEqual(len(checks[0].detail), MAX_EXCERPT)

    def test_the_excerpt_comes_from_the_end(self):  # CIW-022
        log = "early noise\n" * 5_000 + "THE ACTUAL ERROR"
        checks = attach_logs([failed()], Logs({"build": log}))
        self.assertIn("THE ACTUAL ERROR", checks[0].detail)

    def test_a_short_log_is_kept_whole(self):  # CIW-022
        checks = attach_logs([failed()], Logs({"build": "short failure"}))
        self.assertEqual(checks[0].detail.strip(), "short failure")


class TestUnreadableLogs(unittest.TestCase):
    def test_an_unreadable_log_still_reports_the_check(self):  # CIW-023
        checks = attach_logs([failed()], Logs(error=RuntimeError("403")))
        self.assertEqual(checks[0].name, "build")

    def test_it_says_why(self):  # CIW-023
        checks = attach_logs([failed()], Logs(error=RuntimeError("403")))
        self.assertIn("403", checks[0].detail)

    def test_it_does_not_raise(self):  # CIW-023
        attach_logs([failed()], Logs(error=RuntimeError("403")))

    def test_one_unreadable_log_does_not_lose_the_others(self):  # CIW-023
        class Selective(Logs):
            def __call__(self, name):
                if name == "build":
                    raise RuntimeError("403")
                return "readable"

        checks = attach_logs([failed("build"), failed("test")], Selective())
        self.assertIn("readable", checks[1].detail)


class TestCheckNames(unittest.TestCase):
    """CIW-024 — a prettified name cannot be used to configure a required check."""

    def test_a_name_with_a_slash_is_preserved(self):
        checks = attach_logs([failed("closing-keyword / closing-keyword")], Logs())
        self.assertEqual(checks[0].name, "closing-keyword / closing-keyword")

    def test_case_is_preserved(self):
        checks = attach_logs([failed("Build And Test")], Logs())
        self.assertEqual(checks[0].name, "Build And Test")

    def test_the_name_is_used_verbatim_to_fetch_the_log(self):
        logs = Logs()
        attach_logs([failed("closing-keyword / closing-keyword")], logs)
        self.assertEqual(logs.asked, ["closing-keyword / closing-keyword"])


if __name__ == "__main__":
    unittest.main()
