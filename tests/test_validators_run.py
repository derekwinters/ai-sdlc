"""VAL-040 to VAL-044 — each validator runs alone and reports plainly."""

import subprocess
import sys
import unittest
from pathlib import Path

from _support import ROOT

SCRIPTS = ("specs", "boundaries", "docs")


def run(name, cwd=ROOT):
    return subprocess.run(
        [sys.executable, "-m", f"lib.validators.{name}"],
        cwd=cwd,
        capture_output=True,
        text=True,
    )


class TestEachRunsAlone(unittest.TestCase):
    def test_each_is_runnable_with_no_arguments(self):  # VAL-040
        for name in SCRIPTS:
            self.assertIn(run(name).returncode, (0, 1), name)

    def test_each_exits_zero_on_this_repository(self):  # VAL-041
        for name in SCRIPTS:
            result = run(name)
            self.assertEqual(result.returncode, 0, f"{name}: {result.stderr}")

    def test_each_prints_a_summary_when_clean(self):  # VAL-042
        for name in SCRIPTS:
            self.assertTrue(run(name).stdout.strip(), name)

    def test_the_summary_names_the_validator(self):  # VAL-042
        for name in SCRIPTS:
            self.assertIn(name.rstrip("s"), run(name).stdout, name)


class TestFailureIsNonZero(unittest.TestCase):
    def test_a_broken_tree_exits_one(self):  # VAL-041
        import tempfile

        root = Path(tempfile.mkdtemp())
        (root / "docs" / "spec").mkdir(parents=True)
        (root / "docs" / "spec" / "ex.md").write_text(
            "# Specification — Example (`EX`)\n\nBelongs to the **substrate** capability.\n"
            "\n- **EX-001** Uncovered.\n"
        )
        (root / "lib").mkdir()
        for name in ("__init__.py", "config.py"):
            (root / "lib" / name).write_text((ROOT / "lib" / name).read_text())
        (root / "lib" / "validators").mkdir()
        for name in ("__init__.py", "specs.py"):
            (root / "lib" / "validators" / name).write_text(
                (ROOT / "lib" / "validators" / name).read_text()
            )
        result = run("specs", cwd=root)
        self.assertEqual(result.returncode, 1)
        self.assertIn("EX-001", result.stderr)


class TestStdlibOnly(unittest.TestCase):
    def test_no_validator_imports_a_third_party_library(self):  # VAL-043
        import ast

        allowed = {"lib", "ast", "re", "sys", "pathlib", "os", "json", "difflib", "collections"}
        for path in (ROOT / "lib" / "validators").glob("*.py"):
            tree = ast.parse(path.read_text())
            for node in ast.walk(tree):
                roots = set()
                if isinstance(node, ast.Import):
                    roots = {a.name.split(".")[0] for a in node.names}
                elif isinstance(node, ast.ImportFrom) and node.module:
                    roots = {node.module.split(".")[0]}
                for name in roots - {"__future__"}:
                    self.assertIn(name, allowed, f"{path.name} imports {name}")


class TestStableOutput(unittest.TestCase):
    def test_problems_are_reported_in_a_stable_order(self):  # VAL-044
        """Two runs over the same tree produce identical output."""
        first, second = run("specs").stdout, run("specs").stdout
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
