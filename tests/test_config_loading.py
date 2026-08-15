"""CFG-001 to CFG-006 — finding and reading the file."""

import tempfile
import unittest
from pathlib import Path

import _support  # noqa: F401
from lib.config import ConfigError, load

MINIMAL = """
capabilities:
  - hygiene
"""


class Written(unittest.TestCase):
    def write(self, text, name=".claude/repo-config.yml"):
        root = Path(tempfile.mkdtemp())
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        return root, path


class TestWhereItLooks(Written):
    def test_it_reads_the_conventional_path(self):  # CFG-001
        root, _ = self.write(MINIMAL)
        self.assertEqual(load(root=root).capabilities, ["substrate", "hygiene"])

    def test_the_path_is_injectable(self):  # CFG-002
        root, _ = self.write(MINIMAL, name="candidate.yml")
        self.assertIsNotNone(load(path=root / "candidate.yml"))

    def test_a_missing_file_names_the_expected_path(self):  # CFG-003
        root = Path(tempfile.mkdtemp())
        with self.assertRaises(ConfigError) as caught:
            load(root=root)
        self.assertIn("repo-config.yml", str(caught.exception))

    def test_a_missing_file_is_not_an_empty_config(self):  # CFG-003
        with self.assertRaises(ConfigError):
            load(root=Path(tempfile.mkdtemp()))


class TestUnparseable(Written):
    def test_bad_yaml_names_the_file(self):  # CFG-004
        root, path = self.write("a:\n\tb: 1")
        with self.assertRaises(ConfigError) as caught:
            load(root=root)
        self.assertIn(str(path.name), str(caught.exception))

    def test_bad_yaml_reports_the_parse_problem(self):  # CFG-004
        root, _ = self.write("a:\n\tb: 1")
        with self.assertRaises(ConfigError) as caught:
            load(root=root)
        self.assertIn("tab", str(caught.exception).lower())


class TestPurity(Written):
    def test_loading_does_not_modify_the_file(self):  # CFG-005
        root, path = self.write(MINIMAL)
        before = path.read_text()
        load(root=root)
        self.assertEqual(path.read_text(), before)

    def test_the_module_imports_no_network_library(self):  # CFG-005
        import ast

        from _support import ROOT

        tree = ast.parse((ROOT / "lib" / "config.py").read_text())
        roots = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                roots.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                roots.add(node.module.split(".")[0])
        self.assertEqual(roots & {"urllib", "http", "socket", "requests"}, set())

    def test_no_third_party_yaml_library_is_used(self):  # CFG-006
        import ast

        from _support import ROOT

        tree = ast.parse((ROOT / "lib" / "config.py").read_text())
        names = {
            a.name.split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for a in node.names
        }
        self.assertNotIn("yaml", names)


if __name__ == "__main__":
    unittest.main()
