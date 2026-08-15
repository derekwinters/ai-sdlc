"""SYS-001 to SYS-023 — the closing-keyword required check."""

import subprocess
import sys
import unittest

from _support import ROOT

SCRIPT = ROOT / "skills" / "hygiene" / "closing-keyword" / "check_closing_keyword.py"

sys.path.insert(0, str(SCRIPT.parent))
from check_closing_keyword import EXEMPT_LABEL, check  # noqa: E402


class TestAcceptedForms(unittest.TestCase):
    def test_closes(self):  # SYS-001
        self.assertTrue(check("Closes #12").satisfied)

    def test_fixes(self):  # SYS-001
        self.assertTrue(check("Fixes #12").satisfied)

    def test_resolves(self):  # SYS-001
        self.assertTrue(check("Resolves #12").satisfied)

    def test_case_insensitive(self):  # SYS-002
        self.assertTrue(check("closes #12").satisfied)
        self.assertTrue(check("CLOSES #12").satisfied)

    def test_every_github_form(self):  # SYS-003
        for word in ("close", "closes", "closed", "fix", "fixes", "fixed",
                     "resolve", "resolves", "resolved"):
            self.assertTrue(check(f"{word} #12").satisfied, word)

    def test_a_cross_repository_reference(self):  # SYS-004
        self.assertTrue(check("Closes derekwinters/ai-sdlc#12").satisfied)

    def test_it_may_appear_mid_body(self):  # SYS-001
        self.assertTrue(check("Some prose.\n\nCloses #12\n\nMore prose.").satisfied)

    def test_a_colon_between_is_allowed(self):  # SYS-001
        self.assertTrue(check("Closes: #12").satisfied)


class TestRejectedForms(unittest.TestCase):
    def test_a_bare_mention_does_not_close(self):  # SYS-005
        self.assertFalse(check("Related to #12").satisfied)

    def test_refs_does_not_close(self):  # SYS-005
        self.assertFalse(check("Refs #12").satisfied)

    def test_see_does_not_close(self):  # SYS-005
        self.assertFalse(check("See #12").satisfied)

    def test_a_keyword_with_no_number(self):  # SYS-005
        self.assertFalse(check("This closes the gap").satisfied)

    def test_inside_a_code_fence_does_not_count(self):  # SYS-006
        self.assertFalse(check("```\nCloses #12\n```").satisfied)

    def test_a_tilde_fence_too(self):  # SYS-006
        self.assertFalse(check("~~~\nCloses #12\n~~~").satisfied)

    def test_outside_a_fence_still_counts(self):  # SYS-006
        self.assertTrue(check("```\nexample\n```\nCloses #12").satisfied)

    def test_an_empty_body(self):  # SYS-007
        self.assertFalse(check("").satisfied)

    def test_a_missing_body(self):  # SYS-007
        self.assertFalse(check(None).satisfied)


class TestTheReport(unittest.TestCase):
    def test_it_names_the_keyword_found(self):  # SYS-008
        self.assertIn("Closes", check("Closes #12").detail)

    def test_it_names_the_issue(self):  # SYS-008
        self.assertIn("#12", check("Closes #12").detail)

    def test_a_failure_explains_what_is_missing(self):  # SYS-008
        self.assertIn("Closes #", check("Refs #12").detail)

    def test_a_failure_names_the_escape_hatch(self):  # SYS-011
        self.assertIn(EXEMPT_LABEL, check("Refs #12").detail)


class TestTheEscapeHatch(unittest.TestCase):
    def test_the_label_satisfies_the_check(self):  # SYS-010
        self.assertTrue(check("Refs #12", labels=[EXEMPT_LABEL]).satisfied)

    def test_the_exemption_is_reported(self):  # SYS-011
        result = check("Refs #12", labels=[EXEMPT_LABEL])
        self.assertIn(EXEMPT_LABEL, result.detail)

    def test_the_exemption_is_distinguishable_from_a_pass(self):  # SYS-011
        self.assertTrue(check("Refs #12", labels=[EXEMPT_LABEL]).exempt)
        self.assertFalse(check("Closes #12").exempt)

    def test_another_label_does_not_exempt(self):  # SYS-010
        self.assertFalse(check("Refs #12", labels=["skip-docs"]).satisfied)

    def test_the_label_name_is_fixed(self):  # SYS-013
        self.assertEqual(EXEMPT_LABEL, "no-closing-keyword")


class TestRunningAsAScript(unittest.TestCase):
    def run_it(self, body, labels=""):
        return subprocess.run(
            [sys.executable, str(SCRIPT)],
            input=body,
            capture_output=True,
            text=True,
            env={"PR_LABELS": labels, "PATH": "/usr/bin:/bin"},
        )

    def test_a_satisfied_body_exits_zero(self):  # SYS-021
        self.assertEqual(self.run_it("Closes #12").returncode, 0)

    def test_an_unsatisfied_body_exits_one(self):  # SYS-021
        self.assertEqual(self.run_it("Refs #12").returncode, 1)

    def test_it_reads_the_body_from_stdin(self):  # SYS-020
        self.assertIn("#12", self.run_it("Closes #12").stdout)

    def test_the_label_comes_from_the_environment(self):  # SYS-012
        result = self.run_it("Refs #12", labels="no-closing-keyword")
        self.assertEqual(result.returncode, 0)

    def test_it_always_reports_something(self):  # SYS-012
        self.assertTrue(self.run_it("Closes #12").stdout.strip())

    def test_it_uses_only_the_standard_library(self):  # SYS-022
        import ast

        tree = ast.parse(SCRIPT.read_text())
        allowed = {"re", "sys", "os", "__future__"}
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    self.assertIn(alias.name.split(".")[0], allowed)
            elif isinstance(node, ast.ImportFrom) and node.module:
                self.assertIn(node.module.split(".")[0], allowed)

    def test_it_reads_no_network(self):  # SYS-023
        import ast

        tree = ast.parse(SCRIPT.read_text())
        roots = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                roots.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                roots.add(node.module.split(".")[0])
        self.assertEqual(roots & {"urllib", "http", "socket", "requests"}, set())


if __name__ == "__main__":
    unittest.main()
