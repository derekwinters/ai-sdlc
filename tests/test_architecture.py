"""The structural invariants, checked rather than trusted.

A seam only stays one module wide if something fails when it widens.
"""

import ast
import unittest
from pathlib import Path

from _support import ROOT

NETWORK = {"urllib", "http", "socket", "requests", "httpx", "ssl", "ftplib", "telnetlib"}

# The one module allowed to reach the network, and the tests' own transport double.
ALLOWED = {ROOT / "lib" / "github.py"}


def python_files():
    for path in sorted(ROOT.rglob("*.py")):
        if any(part in {".git", "site", ".venv"} for part in path.parts):
            continue
        yield path


def imported_roots(path):
    tree = ast.parse(path.read_text(), filename=str(path))
    roots = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            roots.add(node.module.split(".")[0])
    return roots


class TestTheNetworkSeam(unittest.TestCase):
    def test_only_lib_github_imports_a_network_library(self):
        offenders = [
            str(path.relative_to(ROOT))
            for path in python_files()
            if path not in ALLOWED and imported_roots(path) & NETWORK
        ]
        self.assertEqual(offenders, [], f"network imports outside the seam: {offenders}")

    def test_the_seam_itself_does_reach_the_network(self):
        self.assertTrue(imported_roots(ROOT / "lib" / "github.py") & NETWORK)


class TestNoTestOpensASocket(unittest.TestCase):
    def test_no_test_module_imports_a_network_library(self):
        offenders = [
            str(path.relative_to(ROOT))
            for path in (ROOT / "tests").rglob("*.py")
            if imported_roots(path) & NETWORK
        ]
        self.assertEqual(offenders, [])

    def test_creating_a_client_performs_no_io(self):
        """Construction must not connect; only an explicit request may."""
        from lib.github import GitHub

        def explode(*args, **kwargs):  # pragma: no cover - must never run
            raise AssertionError("constructing a client performed I/O")

        GitHub("t", "o/r", transport=explode)


if __name__ == "__main__":
    unittest.main()
