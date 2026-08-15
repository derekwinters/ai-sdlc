"""ADOPT-040 to ADOPT-046 — writing, and refusing to."""

import unittest

from _adopt import repository, NEWER_PIN, OLDER_PIN, PIN
import _adopt  # noqa: F401
from adopt import AdoptRefused, apply, plan

CONFIG = "capabilities:\n  - hygiene\n"
PIPELINE_CONFIG = (
    "capabilities:\n  - hygiene\n  - consistency\n  - labels\n  - release\n"
    "  - pipeline\nowners:\n  - derekwinters\ndashboard_issue: 193\n"
)


COLLIDING = """
name: theirs
on:
  issue_comment:
    types: [created]
jobs:
  run:
    runs-on: ubuntu-latest
"""


def applied(files=None, **kwargs):
    files = dict(files or {})
    files.setdefault(".claude/repo-config.yml", CONFIG)
    root = repository(files)
    return apply(root, pin=PIN, **kwargs), root


class TestWriting(unittest.TestCase):
    def test_it_creates_the_caller_workflow(self):  # ADOPT-040
        _, root = applied()
        self.assertTrue((root / ".github/workflows/closing-keyword.yml").is_file())

    def test_written_files_carry_provenance(self):  # ADOPT-024
        _, root = applied()
        text = (root / ".github/workflows/closing-keyword.yml").read_text()
        self.assertIn("ai-sdlc:", text)

    def test_it_records_the_version(self):  # ADOPT-045
        _, root = applied()
        recorded = (root / ".claude/ai-sdlc.pin").read_text()
        self.assertIn(PIN[0], recorded)
        self.assertIn(PIN[1], recorded)

    def test_it_reports_what_it_wrote(self):  # ADOPT-040
        result, _ = applied()
        self.assertTrue(result.written)


class TestIdempotence(unittest.TestCase):
    def test_a_second_run_writes_nothing(self):  # ADOPT-041
        _, root = applied()
        second = apply(root, pin=PIN)
        self.assertEqual(second.written, [])

    def test_the_files_are_unchanged(self):  # ADOPT-041
        _, root = applied()
        before = (root / ".github/workflows/closing-keyword.yml").read_text()
        apply(root, pin=PIN)
        self.assertEqual((root / ".github/workflows/closing-keyword.yml").read_text(), before)


class TestUpgrading(unittest.TestCase):
    def test_a_higher_pin_updates_managed_files(self):  # ADOPT-046
        _, root = applied()
        result = apply(root, pin=NEWER_PIN)
        self.assertTrue(result.written)

    def test_the_new_pin_is_recorded(self):  # ADOPT-046
        _, root = applied()
        apply(root, pin=NEWER_PIN)
        self.assertIn("v0.5.0", (root / ".claude/ai-sdlc.pin").read_text())

    def test_a_conflict_is_left_alone_on_upgrade(self):  # ADOPT-046
        _, root = applied()
        target = root / ".github/workflows/closing-keyword.yml"
        target.write_text("hand edited")
        apply(root, pin=NEWER_PIN)
        self.assertEqual(target.read_text(), "hand edited")


class TestItNeverOverwrites(unittest.TestCase):
    def test_an_unmanaged_file_is_untouched(self):  # ADOPT-023
        _, root = applied({".github/workflows/closing-keyword.yml": "theirs"})
        self.assertEqual((root / ".github/workflows/closing-keyword.yml").read_text(), "theirs")

    def test_claude_md_is_never_rewritten(self):  # ADOPT-043
        _, root = applied({"CLAUDE.md": "# Their rules\n\nSomething.\n"})
        self.assertIn("Their rules", (root / "CLAUDE.md").read_text())

    def test_an_import_line_is_added_to_claude_md(self):  # ADOPT-043
        _, root = applied({"CLAUDE.md": "# Their rules\n"})
        self.assertIn("@", (root / "CLAUDE.md").read_text())

    def test_the_import_is_not_added_twice(self):  # ADOPT-043
        _, root = applied({"CLAUDE.md": "# Their rules\n"})
        apply(root, pin=PIN)
        self.assertEqual((root / "CLAUDE.md").read_text().count("ai-sdlc/house-rules"), 1)


class TestCollisionsRefuse(unittest.TestCase):
    def test_an_unacknowledged_collision_refuses(self):  # ADOPT-032
        with self.assertRaises(AdoptRefused):
            applied({".github/workflows/theirs.yml": COLLIDING,
                 ".claude/repo-config.yml": PIPELINE_CONFIG})

    def test_the_refusal_names_the_workflow(self):  # ADOPT-032
        try:
            applied({".github/workflows/theirs.yml": COLLIDING,
                 ".claude/repo-config.yml": PIPELINE_CONFIG})
        except AdoptRefused as error:
            self.assertIn("theirs.yml", str(error))

    def test_a_refusal_writes_nothing(self):  # ADOPT-032
        files = {".claude/repo-config.yml": PIPELINE_CONFIG,
                 ".github/workflows/theirs.yml": COLLIDING}
        root = repository(files)
        try:
            apply(root, pin=PIN)
        except AdoptRefused:
            pass
        self.assertFalse((root / ".github/workflows/closing-keyword.yml").exists())

    def test_an_acknowledged_collision_proceeds(self):  # ADOPT-033
        result, root = applied({".github/workflows/theirs.yml": COLLIDING,
                                ".claude/repo-config.yml": PIPELINE_CONFIG},
                               acknowledged=["theirs.yml"])
        self.assertTrue(result.written)


class TestLabelsAndDashboard(unittest.TestCase):
    def test_no_label_is_renamed(self):  # ADOPT-042
        """Renaming rewrites the label on every issue that carried it."""
        from _support import ROOT
        import ast

        source = (ROOT / "skills" / "substrate" / "adopt" / "adopt.py").read_text()
        tree = ast.parse(source)
        names = [n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]
        self.assertFalse([n for n in names if "rename" in n.lower()])

    def test_an_existing_dashboard_issue_is_reused(self):  # ADOPT-044
        config = CONFIG + "dashboard_issue: 193\n"
        result, _ = applied({".claude/repo-config.yml": config})
        self.assertNotIn("dashboard", str(result.manual_tasks).lower())


if __name__ == "__main__":
    unittest.main()


class TestACapabilityInstallsWhatItNeeds(unittest.TestCase):
    """A capability's workflow and the files that workflow reads land together.

    Twice now a capability has installed half of itself: the `CLAUDE.md` import
    without `house-rules.md` (#71), and `labels-sync.yml` without
    `labels.core.yml` (#75). Both fail only when something runs, which is long
    after the pull request that introduced them was reviewed.
    """

    def test_enabling_labels_installs_the_core_manifest(self):  # ADOPT-047
        root = repository({".claude/repo-config.yml": "capabilities:\n  - labels\n"})
        apply(root, pin=PIN)
        self.assertTrue((root / ".github/labels.core.yml").is_file())

    def test_the_core_manifest_is_managed_not_hand_written(self):  # ADOPT-047
        root = repository({".claude/repo-config.yml": "capabilities:\n  - labels\n"})
        apply(root, pin=PIN)
        text = (root / ".github/labels.core.yml").read_text()
        self.assertIn("ai-sdlc:", text)

    def test_it_is_the_manifest_the_sync_actually_reads(self):  # ADOPT-047
        # Not a second copy that can drift — the same file the skill ships.
        from _support import ROOT

        source = (ROOT / "skills" / "labels" / "label-sync" / "labels.core.yml").read_text()
        root = repository({".claude/repo-config.yml": "capabilities:\n  - labels\n"})
        apply(root, pin=PIN)
        installed = (root / ".github/labels.core.yml").read_text()
        self.assertIn("ready-for-work", installed)
        self.assertTrue(installed.endswith(source))

    def test_labels_off_installs_no_manifest(self):  # ADOPT-047
        root = repository({".claude/repo-config.yml": "capabilities:\n  - hygiene\n"})
        apply(root, pin=PIN)
        self.assertFalse((root / ".github/labels.core.yml").exists())
