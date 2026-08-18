"""ADOPT-040 to ADOPT-048 — writing, and refusing to."""

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
    files.setdefault(".ai-sdlc/repo-config.yml", CONFIG)
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
        recorded = (root / ".ai-sdlc/ai-sdlc.pin").read_text()
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
        self.assertIn("v0.5.0", (root / ".ai-sdlc/ai-sdlc.pin").read_text())

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
                 ".ai-sdlc/repo-config.yml": PIPELINE_CONFIG})

    def test_the_refusal_names_the_workflow(self):  # ADOPT-032
        try:
            applied({".github/workflows/theirs.yml": COLLIDING,
                 ".ai-sdlc/repo-config.yml": PIPELINE_CONFIG})
        except AdoptRefused as error:
            self.assertIn("theirs.yml", str(error))

    def test_a_refusal_writes_nothing(self):  # ADOPT-032
        files = {".ai-sdlc/repo-config.yml": PIPELINE_CONFIG,
                 ".github/workflows/theirs.yml": COLLIDING}
        root = repository(files)
        try:
            apply(root, pin=PIN)
        except AdoptRefused:
            pass
        self.assertFalse((root / ".github/workflows/closing-keyword.yml").exists())

    def test_an_acknowledged_collision_proceeds(self):  # ADOPT-033
        result, root = applied({".github/workflows/theirs.yml": COLLIDING,
                                ".ai-sdlc/repo-config.yml": PIPELINE_CONFIG},
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
        result, _ = applied({".ai-sdlc/repo-config.yml": config})
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
        root = repository({".ai-sdlc/repo-config.yml": "capabilities:\n  - labels\n"})
        apply(root, pin=PIN)
        self.assertTrue((root / ".github/labels.core.yml").is_file())

    def test_the_core_manifest_is_managed_not_hand_written(self):  # ADOPT-047
        root = repository({".ai-sdlc/repo-config.yml": "capabilities:\n  - labels\n"})
        apply(root, pin=PIN)
        text = (root / ".github/labels.core.yml").read_text()
        self.assertIn("ai-sdlc:", text)

    def test_it_is_the_manifest_the_sync_actually_reads(self):  # ADOPT-047
        # Not a second copy that can drift — the same file the skill ships.
        from _support import ROOT

        source = (ROOT / "skills" / "labels" / "label-sync" / "labels.core.yml").read_text()
        root = repository({".ai-sdlc/repo-config.yml": "capabilities:\n  - labels\n"})
        apply(root, pin=PIN)
        installed = (root / ".github/labels.core.yml").read_text()
        self.assertIn("ready-for-work", installed)
        self.assertTrue(installed.endswith(source))

    def test_labels_off_installs_no_manifest(self):  # ADOPT-047
        root = repository({".ai-sdlc/repo-config.yml": "capabilities:\n  - hygiene\n"})
        apply(root, pin=PIN)
        self.assertFalse((root / ".github/labels.core.yml").exists())


class TestTheSkillsCaller(unittest.TestCase):
    """ADOPT-048 — the list in configuration is what installs the caller.

    `docs/design.md` §7 specified how skills reach a consumer and nothing ran
    it: `connor-multiplying-frogs` ran the pipeline for weeks with none of the
    pipeline skills present, and its own documentation said they were installed
    (#144).
    """

    CALLER = ".github/workflows/skills-update.yml"

    def _apply(self, skills):
        _, root = applied({".ai-sdlc/repo-config.yml": CONFIG + skills})
        return root

    def test_a_repository_naming_skills_gets_the_caller(self):  # ADOPT-048
        root = self._apply("skills:\n  - ci-watch\n")
        self.assertTrue((root / self.CALLER).is_file())

    def test_a_repository_naming_none_gets_no_caller(self):  # ADOPT-048
        self.assertFalse((self._apply("") / self.CALLER).exists())

    def test_the_caller_runs_on_a_schedule(self):  # ADOPT-048
        text = (self._apply("skills:\n  - ci-watch\n") / self.CALLER).read_text()
        self.assertIn("schedule:", text)
        self.assertIn("workflow_dispatch:", text)

    def test_the_caller_passes_the_pinned_ref(self):  # ADOPT-060
        text = (self._apply("skills:\n  - ci-watch\n") / self.CALLER).read_text()
        self.assertIn(f"ref: {PIN[1]}", text)
        self.assertIn(f"reusable-skills-update.yml@{PIN[1]} # {PIN[0]}", text)

    def test_the_caller_names_no_skills_itself(self):  # ADOPT-048
        """The list stays in configuration.

        A caller is an `adopt`-managed file, so editing the list in it would
        make the file a CONFLICT and stop it being upgraded ever again.
        """
        text = (self._apply("skills:\n  - ci-watch\n") / self.CALLER).read_text()
        self.assertNotIn("ci-watch", text)


class TestTheManualTaskForPullRequests(unittest.TestCase):
    """ADOPT-012 — a permission only a human can grant is a manual task.

    A workflow opening a pull request with GITHUB_TOKEN needs the repository
    setting switched on, and without it the run fails at `gh pr create` — after
    the push, so the branch exists and no pull request does.
    """

    def _tasks(self, skills):
        result, _ = applied({".ai-sdlc/repo-config.yml": CONFIG + skills})
        return " ".join(result.manual_tasks).lower()

    def test_naming_skills_adds_the_task(self):  # ADOPT-012
        self.assertIn("pull request", self._tasks("skills:\n  - ci-watch\n"))

    def test_naming_none_does_not(self):  # ADOPT-012
        self.assertNotIn("create and approve pull requests", self._tasks(""))

