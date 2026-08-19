"""ADOPT-100 to ADOPT-106 — callers that use an action, and check out nothing.

A reusable workflow has to fetch the code it runs, which meant every consumer's
run cloned ai-sdlc into its own workspace. An action is fetched by the runner
before any step executes, outside the workspace entirely, so the consumer's
working tree holds only the consumer.
"""

import re
import unittest

from _adopt import repository, PIN
import _adopt  # noqa: F401
from _support import ROOT
from adopt import SOURCE, apply

HYGIENE = "capabilities:\n  - hygiene\n"
MKDOCS = "capabilities:\n  - hygiene\nprofiles:\n  - mkdocs\n"


def caller(name, config=HYGIENE):
    root = repository({".ai-sdlc/repo-config.yml": config})
    apply(root, pin=PIN)
    return (root / ".github" / "workflows" / f"{name}.yml").read_text()


class TestTheCallerUsesAnAction(unittest.TestCase):
    def test_closing_keyword_uses_the_action(self):  # ADOPT-100
        self.assertIn(f"uses: {SOURCE}/.github/actions/closing-keyword@", caller("closing-keyword"))

    def test_docs_gate_uses_the_action(self):  # ADOPT-100
        self.assertIn(f"uses: {SOURCE}/.github/actions/docs-gate@", caller("docs-gate", MKDOCS))

    def test_the_action_is_pinned_to_the_commit(self):  # ADOPT-100
        self.assertIn(f"actions/closing-keyword@{PIN[1]} # {PIN[0]}", caller("closing-keyword"))

    def test_it_calls_no_reusable_workflow(self):  # ADOPT-100
        self.assertNotIn("reusable-", caller("closing-keyword"))


class TestNothingIsCheckedOutButTheConsumer(unittest.TestCase):
    """ADOPT-101 — the reason for the whole change.

    `actions/checkout` empties the directory it writes into. #150 had to rename
    the checkout path because a consumer had started keeping `repo-config.yml`
    at `.ai-sdlc/`, and its own configuration would have been replaced by
    ai-sdlc's and then read. A run that fetches nothing cannot do that.
    """

    def test_the_caller_checks_ai_sdlc_out_nowhere(self):  # ADOPT-101
        for name, config in (("closing-keyword", HYGIENE), ("docs-gate", MKDOCS)):
            with self.subTest(caller=name):
                text = caller(name, config)
                self.assertNotIn("repository: derekwinters/ai-sdlc", text)
                self.assertNotIn(".ai-sdlc-checkout", text)

    def test_the_caller_names_no_skill_root(self):  # ADOPT-101
        self.assertNotIn("SKILL_ROOT", caller("closing-keyword"))

    def test_the_caller_passes_no_ref_input(self):  # ADOPT-102
        """One reference, not two.

        `ADOPT-060` exists because a caller carried the workflow's `@sha` and a
        `ref:` input that had to agree. An action has a single reference, so
        they cannot disagree.
        """
        self.assertNotRegex(caller("closing-keyword"), r"^\s*ref:", )


class TestTheActionsExist(unittest.TestCase):
    ACTIONS = ROOT / ".github" / "actions"

    def test_every_referenced_action_is_present(self):  # ADOPT-103
        for name in ("closing-keyword", "docs-gate"):
            with self.subTest(action=name):
                self.assertTrue((self.ACTIONS / name / "action.yml").is_file())

    def test_each_declares_itself_composite(self):  # ADOPT-103
        for name in ("closing-keyword", "docs-gate"):
            with self.subTest(action=name):
                text = (self.ACTIONS / name / "action.yml").read_text()
                self.assertIn("using: composite", text)

    def test_each_script_it_runs_resolves(self):  # ADOPT-104
        """The action reaches its script by a path relative to itself.

        A path-based action checks out the *whole* repository, so `../../..`
        from `.github/actions/<name>/` is the repository root. That is load
        bearing and invisible, so moving a script has to fail here rather than
        in a consumer's run.
        """
        for path in sorted(self.ACTIONS.glob("*/action.yml")):
            for reference in re.findall(r"\$\{?GITHUB_ACTION_PATH\}?(/[^\s\"']+\.py)", path.read_text()):
                with self.subTest(action=path.parent.name, script=reference):
                    self.assertTrue((path.parent / reference.lstrip("/")).resolve().is_file())

    def test_an_action_reaches_no_script_by_absolute_path(self):  # ADOPT-104
        for path in sorted(self.ACTIONS.glob("*/action.yml")):
            with self.subTest(action=path.parent.name):
                self.assertNotRegex(path.read_text(), r"run:.*\s/(home|github|runner)/")


class TestTheConvertedWorkflowsAreGone(unittest.TestCase):
    """ADOPT-105 — one delivery mechanism per script, not two.

    A reusable workflow left beside its action is a second copy that nothing
    installs and nothing keeps in step — which is the shape `DIST` refuses for
    skills, for the same reason.
    """

    WORKFLOWS = ROOT / ".github" / "workflows"

    def test_the_reusable_workflows_they_replace_are_removed(self):  # ADOPT-105
        for name in ("reusable-closing-keyword.yml", "reusable-docs-gate.yml"):
            with self.subTest(workflow=name):
                self.assertFalse((self.WORKFLOWS / name).exists())

    def test_no_workflow_still_calls_them(self):  # ADOPT-105
        for path in sorted(self.WORKFLOWS.glob("*.yml")):
            with self.subTest(workflow=path.name):
                text = path.read_text()
                self.assertNotIn("reusable-closing-keyword.yml", text)
                self.assertNotIn("reusable-docs-gate.yml", text)


class TestTheRenamedCheckIsReported(unittest.TestCase):
    """ADOPT-106 — converting a caller renames its status check.

    A reusable workflow reports as `<workflow> / <job>`; a job running an action
    reports as `<job>`. A branch protection rule naming the old one then waits
    on a check that will never report again, which is the trap `MANUAL_TASKS`
    already warns about — arriving through an upgrade nobody thought was risky.
    Only a human can change a protection rule, so it is reported as a task.
    """

    def _tasks(self, config):
        root = repository({".ai-sdlc/repo-config.yml": config})
        return " ".join(apply(root, pin=PIN).manual_tasks)

    def test_a_repository_with_an_action_caller_is_told(self):  # ADOPT-106
        self.assertIn("no longer reports", self._tasks(HYGIENE))

    def test_the_task_names_both_forms(self):  # ADOPT-106
        tasks = self._tasks(HYGIENE)
        self.assertIn("closing-keyword / closing-keyword", tasks)

    def test_a_repository_with_none_is_not(self):  # ADOPT-106
        self.assertNotIn("no longer reports", self._tasks("capabilities:\n  - labels\n"))


if __name__ == "__main__":
    unittest.main()
