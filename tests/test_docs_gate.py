"""PROF-020 to PROF-025 — the documentation reconciliation gate."""

import subprocess
import sys
import unittest

from _support import ROOT

SCRIPT = ROOT / "skills" / "mkdocs" / "docs-gate" / "check_docs_changed.py"

sys.path.insert(0, str(SCRIPT.parent))
from check_docs_changed import DEFAULT_DOC_PATTERNS, EXEMPT_LABEL, check  # noqa: E402


def files(*names):
    return list(names)


class TestTheGate(unittest.TestCase):
    def test_code_without_documentation_fails(self):  # PROF-020
        self.assertFalse(check(files("lib/thing.py")).satisfied)

    def test_code_with_documentation_passes(self):  # PROF-020
        self.assertTrue(check(files("lib/thing.py", "docs/thing.md")).satisfied)

    def test_documentation_only_passes(self):  # PROF-022
        self.assertTrue(check(files("docs/thing.md")).satisfied)

    def test_a_root_markdown_file_counts_as_documentation(self):  # PROF-022
        self.assertTrue(check(files("lib/thing.py", "README.md")).satisfied)

    def test_no_files_at_all_passes(self):  # PROF-023
        self.assertTrue(check(files()).satisfied)

    def test_neither_code_nor_docs_passes(self):  # PROF-023
        self.assertTrue(check(files(".gitignore")).satisfied)


class TestTheEscapeHatch(unittest.TestCase):
    def test_the_label_makes_it_pass(self):  # PROF-021
        self.assertTrue(check(files("lib/thing.py"), labels=[EXEMPT_LABEL]).satisfied)

    def test_the_exemption_is_distinguishable(self):  # PROF-021
        self.assertTrue(check(files("lib/thing.py"), labels=[EXEMPT_LABEL]).exempt)

    def test_a_normal_pass_is_not_an_exemption(self):  # PROF-021
        self.assertFalse(check(files("docs/x.md")).exempt)

    def test_another_label_does_not_exempt(self):  # PROF-021
        self.assertFalse(check(files("lib/thing.py"), labels=["urgent"]).satisfied)

    def test_the_label_name_is_the_conventional_one(self):  # PROF-021
        self.assertEqual(EXEMPT_LABEL, "skip-docs")


class TestConfigurability(unittest.TestCase):
    def test_the_defaults_cover_docs_and_markdown(self):  # PROF-024
        self.assertIn("docs/", str(DEFAULT_DOC_PATTERNS))
        self.assertIn("*.md", str(DEFAULT_DOC_PATTERNS))

    def test_a_custom_pattern_is_honoured(self):  # PROF-024
        result = check(files("lib/thing.py", "handbook/x.rst"),
                       doc_patterns=["handbook/"])
        self.assertTrue(result.satisfied)

    def test_a_custom_pattern_replaces_the_default(self):  # PROF-024
        result = check(files("lib/thing.py", "docs/x.md"), doc_patterns=["handbook/"])
        self.assertFalse(result.satisfied)


class TestTheReport(unittest.TestCase):
    def test_it_names_the_code_files(self):  # PROF-025
        self.assertIn("lib/thing.py", check(files("lib/thing.py")).detail)

    def test_it_names_the_documentation_files(self):  # PROF-025
        detail = check(files("lib/thing.py", "docs/x.md")).detail
        self.assertIn("docs/x.md", detail)

    def test_a_failure_names_the_escape_hatch(self):  # PROF-021
        self.assertIn(EXEMPT_LABEL, check(files("lib/thing.py")).detail)

    def test_a_long_file_list_is_bounded(self):  # PROF-025
        many = [f"lib/file{n}.py" for n in range(200)]
        self.assertLess(len(check(many).detail), 2_000)


class TestRunningAsAScript(unittest.TestCase):
    def run_it(self, names, labels=""):
        return subprocess.run(
            [sys.executable, str(SCRIPT)],
            input="\n".join(names),
            capture_output=True,
            text=True,
            env={"PR_LABELS": labels, "PATH": "/usr/bin:/bin"},
        )

    def test_it_exits_one_when_unsatisfied(self):  # PROF-020
        self.assertEqual(self.run_it(["lib/thing.py"]).returncode, 1)

    def test_it_exits_zero_when_satisfied(self):  # PROF-022
        self.assertEqual(self.run_it(["docs/x.md"]).returncode, 0)

    def test_the_label_makes_it_exit_zero(self):  # PROF-021
        self.assertEqual(self.run_it(["lib/thing.py"], labels="skip-docs").returncode, 0)

    def test_it_always_reports(self):  # PROF-025
        self.assertTrue(self.run_it(["docs/x.md"]).stdout.strip())


if __name__ == "__main__":
    unittest.main()
