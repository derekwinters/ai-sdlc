"""VAL-030 to VAL-033 — a capability may not import from one above it."""

import tempfile
import unittest
from pathlib import Path

from _support import ROOT  # noqa: F401
from lib.validators.boundaries import capability_of, validate_boundaries


class Tree(unittest.TestCase):
    def build(self, files):
        root = Path(tempfile.mkdtemp())
        for name, text in files.items():
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)
        return root


class TestWhichCapabilityAModuleBelongsTo(unittest.TestCase):
    def test_a_skill_belongs_to_its_scope(self):  # VAL-032
        self.assertEqual(capability_of(Path("skills/pipeline/gatekeeper/run.py")), "pipeline")

    def test_a_hygiene_skill(self):  # VAL-032
        self.assertEqual(capability_of(Path("skills/hygiene/keyword/check.py")), "hygiene")

    def test_a_shared_library_is_substrate(self):  # VAL-032
        self.assertEqual(capability_of(Path("lib/github.py")), "substrate")

    def test_an_unscoped_file_is_substrate(self):  # VAL-032
        self.assertEqual(capability_of(Path("scripts/thing.py")), "substrate")

    def test_a_profile_directory_is_not_a_capability(self):  # VAL-032
        self.assertIsNone(capability_of(Path("skills/unity/scaffold/run.py")))


class TestTheDirection(Tree):
    def test_downward_imports_are_allowed(self):  # VAL-030
        root = self.build(
            {
                "skills/pipeline/gk/run.py": "from lib.github import GitHub\n",
                "lib/github.py": "",
            }
        )
        self.assertEqual(validate_boundaries(root), [])

    def test_sideways_within_a_capability_is_allowed(self):  # VAL-030
        root = self.build(
            {
                "skills/pipeline/gk/run.py": "from skills.pipeline.gk import gates\n",
                "skills/pipeline/gk/gates.py": "",
            }
        )
        self.assertEqual(validate_boundaries(root), [])

    def test_an_upward_import_is_reported(self):  # VAL-031
        root = self.build(
            {
                "skills/hygiene/keyword/check.py": "from skills.pipeline.gk import gates\n",
                "skills/pipeline/gk/gates.py": "",
            }
        )
        self.assertEqual(len(validate_boundaries(root)), 1)

    def test_the_report_names_both_modules(self):  # VAL-031
        root = self.build(
            {
                "skills/hygiene/keyword/check.py": "from skills.pipeline.gk import gates\n",
                "skills/pipeline/gk/gates.py": "",
            }
        )
        message = validate_boundaries(root)[0]
        self.assertIn("check.py", message)
        self.assertIn("pipeline", message)

    def test_the_report_names_both_capabilities(self):  # VAL-031
        root = self.build(
            {"skills/labels/sync/run.py": "from skills.release.flow import cut\n",
             "skills/release/flow.py": ""}
        )
        message = validate_boundaries(root)[0]
        self.assertIn("labels", message)
        self.assertIn("release", message)

    def test_substrate_importing_pipeline_is_reported(self):  # VAL-031
        root = self.build(
            {"lib/thing.py": "from skills.pipeline.gk import gates\n",
             "skills/pipeline/gk/gates.py": ""}
        )
        self.assertEqual(len(validate_boundaries(root)), 1)


class TestTheOrderComesFromOnePlace(unittest.TestCase):
    def test_it_uses_the_capability_order_declared_in_config(self):  # VAL-033
        from lib.config import CAPABILITIES
        from lib.validators.boundaries import ORDER

        self.assertEqual(ORDER, list(CAPABILITIES))

    def test_the_validator_does_not_declare_its_own_order(self):  # VAL-033
        import ast

        from _support import ROOT

        source = (ROOT / "lib" / "validators" / "boundaries.py").read_text()
        tree = ast.parse(source)
        imported = {
            node.module
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module
        }
        self.assertIn("lib.config", imported)


class TestTheRealRepository(unittest.TestCase):
    def test_this_repository_respects_its_own_boundaries(self):  # VAL-030
        from _support import ROOT

        self.assertEqual(validate_boundaries(ROOT), [])


if __name__ == "__main__":
    unittest.main()
