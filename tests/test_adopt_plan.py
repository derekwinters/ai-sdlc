"""ADOPT-010 to ADOPT-015 — the read-only half."""

import unittest

from _adopt import PYTHON_MARKER, repository, NEWER_PIN, OLDER_PIN, PIN
import _adopt  # noqa: F401
from adopt import CONFLICT, plan

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


def planned(files=None, **kwargs):
    files = dict(files or {})
    files.setdefault(".ai-sdlc/repo-config.yml", CONFIG)
    return plan(repository(files), pin=PIN, **kwargs)


class TestItReportsEverything(unittest.TestCase):
    def test_absent_files_are_reported_as_creations(self):  # ADOPT-010
        self.assertTrue(planned().creates)

    def test_each_creation_names_its_path(self):  # ADOPT-010
        self.assertTrue(all("/" in path or "." in path for path in planned().creates))

    def test_manual_tasks_are_reported(self):  # ADOPT-012
        self.assertTrue(planned().manual_tasks)

    def test_a_manual_task_says_what_to_do(self):  # ADOPT-012
        self.assertTrue(all(task.strip() for task in planned().manual_tasks))


class TestItWritesNothing(unittest.TestCase):
    def test_no_file_is_created(self):  # ADOPT-011
        root = repository({".ai-sdlc/repo-config.yml": CONFIG})
        before = sorted(str(p) for p in root.rglob("*"))
        plan(root, pin=PIN)
        self.assertEqual(sorted(str(p) for p in root.rglob("*")), before)

    def test_no_file_is_modified(self):  # ADOPT-011
        root = repository({".ai-sdlc/repo-config.yml": CONFIG})
        before = (root / ".ai-sdlc/repo-config.yml").read_text()
        plan(root, pin=PIN)
        self.assertEqual((root / ".ai-sdlc/repo-config.yml").read_text(), before)


class TestConflictsAreSeparate(unittest.TestCase):
    def test_a_conflict_is_not_listed_as_an_update(self):  # ADOPT-013
        files = {".github/workflows/closing-keyword.yml": "somebody wrote this"}
        result = planned(files)
        self.assertNotIn(".github/workflows/closing-keyword.yml", result.updates)

    def test_it_is_listed_as_a_conflict(self):  # ADOPT-013
        files = {".github/workflows/closing-keyword.yml": "somebody wrote this"}
        self.assertIn(".github/workflows/closing-keyword.yml", planned(files).conflicts)


class TestCollisionsAreSeparateAgain(unittest.TestCase):
    def test_a_trigger_collision_is_reported(self):  # ADOPT-014
        result = planned({".github/workflows/theirs.yml": COLLIDING,
                 ".ai-sdlc/repo-config.yml": PIPELINE_CONFIG})
        self.assertEqual([c.workflow for c in result.collisions], ["theirs.yml"])

    def test_it_is_not_merely_a_conflict(self):  # ADOPT-014
        result = planned({".github/workflows/theirs.yml": COLLIDING,
                 ".ai-sdlc/repo-config.yml": PIPELINE_CONFIG})
        self.assertNotIn("theirs.yml", result.conflicts)

    def test_none_when_there_are_none(self):  # ADOPT-014
        self.assertEqual(planned().collisions, [])

    def test_a_hygiene_only_adoption_ignores_issue_workflows(self):  # ADOPT-035
        """It installs no issue handler, so somebody else's is not its concern."""
        self.assertEqual(planned({".github/workflows/theirs.yml": COLLIDING}).collisions, [])


class TestNothingToDo(unittest.TestCase):
    def test_an_up_to_date_repository_reports_no_changes(self):  # ADOPT-015
        from adopt import apply

        root = repository({".ai-sdlc/repo-config.yml": CONFIG})
        apply(root, pin=PIN)
        result = plan(root, pin=PIN)
        self.assertEqual((result.creates, result.updates), ([], []))

    def test_and_says_it_is_current(self):  # ADOPT-015
        from adopt import apply

        root = repository({".ai-sdlc/repo-config.yml": CONFIG})
        apply(root, pin=PIN)
        self.assertTrue(plan(root, pin=PIN).current)


if __name__ == "__main__":
    unittest.main()
