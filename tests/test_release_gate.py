"""REL-005 to REL-012 — what must be true before merging, and the title."""

import unittest

from _release import pull_request
import _release  # noqa: F401
from release_flow import Halt, ReleaseError, squash_title, ready_to_merge


def check(name, conclusion="success", status="completed"):
    return {"name": name, "status": status, "conclusion": conclusion}


def halt(checks):
    result = ready_to_merge(pull_request(), checks)
    if isinstance(result, Halt):
        return result
    raise AssertionError("expected a Halt")


class TestTheGate(unittest.TestCase):
    def test_all_passing_is_ready(self):  # REL-005
        self.assertIsNone(ready_to_merge(pull_request(), [check("build")]))

    def test_a_failing_check_halts(self):  # REL-005
        self.assertIn("build", halt([check("build", conclusion="failure")]).reason)

    def test_a_running_check_halts(self):  # REL-006
        self.assertIn("build", halt([check("build", status="in_progress",
                                           conclusion=None)]).reason)

    def test_a_queued_check_halts(self):  # REL-006
        self.assertIn("build", halt([check("build", status="queued",
                                           conclusion=None)]).reason)

    def test_no_checks_at_all_halts(self):  # REL-007
        self.assertIn("no checks", halt([]).reason.lower())

    def test_a_skipped_check_does_not_halt(self):  # REL-005
        self.assertIsNone(ready_to_merge(pull_request(),
                                         [check("a"), check("b", conclusion="skipped")]))


class TestItNeverTogglesState(unittest.TestCase):
    """REL-008 — closing and reopening loses the review and the approval."""

    def test_the_halt_carries_no_action(self):
        self.assertFalse(getattr(halt([]), "action", None))

    def test_the_module_cannot_toggle_anything(self):
        """Asserted structurally, not by grepping prose.

        An earlier version searched the source for "reopen" and failed on the
        docstring forbidding it — testing prose again. The real property is
        stronger: this module is pure. It decides and explains; every write is
        the caller's, so there is no code path here that could close a pull
        request even by mistake.
        """
        import ast

        from _support import ROOT

        source = (ROOT / "skills" / "release" / "release-flow" / "release_flow.py").read_text()
        tree = ast.parse(source)

        imported = {
            node.module
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module
        }
        self.assertNotIn("lib.github", imported)

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                self.assertNotIn("api", [a.arg for a in node.args.args], node.name)

    def test_the_halt_explains_what_would_resolve_it(self):  # REL-009
        self.assertTrue(halt([check("build", conclusion="failure")]).remedy)

    def test_the_remedy_does_not_suggest_reopening(self):  # REL-008
        self.assertNotIn("reopen", halt([]).remedy.lower())


class TestTheSquashTitle(unittest.TestCase):
    def test_it_is_composed_from_the_version(self):  # REL-010
        self.assertEqual(squash_title("0.3.0"), "chore(main): release 0.3.0")

    def test_it_is_not_the_pull_request_title(self):  # REL-011
        """A pull request retitled by hand must not become the release commit."""
        self.assertNotIn("Please merge me", squash_title("0.3.0"))

    def test_it_is_a_valid_conventional_commit(self):  # REL-012
        import sys
        from _support import ROOT

        sys.path.insert(0, str(ROOT / ".github" / "scripts"))
        from check_pr_title import check as check_title

        self.assertIsNone(check_title(squash_title("0.3.0")))

    def test_a_missing_version_is_refused(self):  # REL-012
        with self.assertRaises(ReleaseError):
            squash_title(None)

    def test_a_nonsense_version_is_refused(self):  # REL-012
        with self.assertRaises(ReleaseError):
            squash_title("not-a-version")


if __name__ == "__main__":
    unittest.main()
