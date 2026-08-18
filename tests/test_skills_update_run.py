"""DIST-001 to DIST-004 and DIST-030 to DIST-035 — running the update.

Two halves. The command that installs a skill, and the workflow that decides
whether anything came of it — a run that changed nothing opens no pull request,
and a run that changed something opens exactly one, on a branch it reuses.
"""

import re
import unittest

from _skills_update import (  # noqa: F401 - sets up sys.path
    OLDER,
    PIN,
    Installer,
    consumer,
    frontmatter,
    installed_skill,
    source_at,
)
from _support import ROOT
from skills_update import (
    INSTALL_ROOT,
    MODIFIED,
    SOURCE,
    apply,
    install_command,
    plan,
    report,
)

WORKFLOW = ROOT / ".github" / "workflows" / "reusable-skills-update.yml"


class TestTheInstallCommand(unittest.TestCase):
    def test_it_is_gh_skill_install_at_the_pinned_ref(self):  # DIST-003
        self.assertEqual(
            install_command("ci-watch", PIN),
            ["gh", "skill", "install", SOURCE, f"ci-watch@{PIN}",
             "--agent", "claude-code", "--scope", "project"],
        )

    def test_it_names_ai_sdlc_as_the_source(self):  # DIST-003
        self.assertIn("derekwinters/ai-sdlc", install_command("ci-watch", PIN))

    def test_it_installs_at_project_scope_for_claude_code(self):  # DIST-003
        command = install_command("ci-watch", PIN)
        self.assertEqual(command[command.index("--agent") + 1], "claude-code")
        self.assertEqual(command[command.index("--scope") + 1], "project")

    def test_it_never_forces(self):  # DIST-003
        """`--force` overwrites a locally-modified skill. That is the defect."""
        self.assertNotIn("--force", install_command("ci-watch", PIN))

    def test_the_install_root_is_the_project_skills_directory(self):  # DIST-003
        self.assertEqual(INSTALL_ROOT.as_posix(), ".claude/skills")


class TestApplying(unittest.TestCase):
    def _apply(self, names, root, source, installer=None):
        installer = installer or Installer()
        proposed = plan(names, PIN, root=root, source=source)
        return apply(proposed, PIN, installer=installer), installer

    def test_an_absent_skill_is_installed(self):  # DIST-010
        result, installer = self._apply(
            ["ci-watch"], consumer(), source_at([PIN], ["ci-watch"]))
        self.assertEqual(installer.calls, [("ci-watch", PIN)])
        self.assertEqual(result.installed, ["ci-watch"])

    def test_a_stale_skill_is_reinstalled_at_the_pin(self):  # DIST-002
        root = consumer({"ci-watch": installed_skill("ci-watch", OLDER)})
        result, installer = self._apply(
            ["ci-watch"], root, source_at([OLDER, PIN], ["ci-watch"]))
        self.assertEqual(installer.calls, [("ci-watch", PIN)])
        self.assertEqual(result.updated, ["ci-watch"])

    def test_a_current_skill_runs_nothing(self):  # DIST-011
        root = consumer({"ci-watch": installed_skill("ci-watch", PIN)})
        result, installer = self._apply(["ci-watch"], root, source_at([PIN], ["ci-watch"]))
        self.assertEqual(installer.calls, [])
        self.assertFalse(result.changes)

    def test_a_modified_skill_runs_nothing(self):  # DIST-014
        files = installed_skill("ci-watch", OLDER)
        files["main.py"] = "print('ours')\n"
        root = consumer({"ci-watch": files})
        result, installer = self._apply(
            ["ci-watch"], root, source_at([OLDER, PIN], ["ci-watch"]))
        self.assertEqual(installer.calls, [])
        self.assertEqual([s.state for s in result.skipped], [MODIFIED])

    def test_the_installer_is_injected(self):  # DIST-004
        """No test reaches the network, and none needs `gh` on the machine."""
        _, installer = self._apply(["ci-watch"], consumer(), source_at([PIN], ["ci-watch"]))
        self.assertTrue(installer.calls)

    def test_a_failing_install_does_not_stop_the_others(self):  # DIST-035
        root = consumer()
        source = source_at([PIN], ["ci-watch", "pipeline-dev"])
        result, installer = self._apply(
            ["ci-watch", "pipeline-dev"], root, source, installer=Installer(fails=["ci-watch"]))
        self.assertEqual(result.installed, ["pipeline-dev"])
        self.assertEqual([f.name for f in result.failed], ["ci-watch"])

    def test_a_skipped_skill_does_not_stop_the_others(self):  # DIST-035
        root = consumer({"pipeline-dev": {"SKILL.md": frontmatter("pipeline-dev")}})
        source = source_at([PIN], ["ci-watch", "pipeline-dev"])
        result, _ = self._apply(["pipeline-dev", "ci-watch"], root, source)
        self.assertEqual(result.installed, ["ci-watch"])
        self.assertEqual(len(result.skipped), 1)


class TestTheReport(unittest.TestCase):
    def _report(self, names, root, source):
        proposed = plan(names, PIN, root=root, source=source)
        return report(apply(proposed, PIN, installer=Installer()), PIN)

    def test_every_named_skill_appears(self):  # DIST-030
        root = consumer({"pipeline-dev": installed_skill("pipeline-dev", PIN)})
        text = self._report(
            ["ci-watch", "pipeline-dev"], root, source_at([PIN], ["ci-watch", "pipeline-dev"]))
        self.assertIn("ci-watch", text)
        self.assertIn("pipeline-dev", text)

    def test_a_run_that_changed_nothing_says_so(self):  # DIST-031
        root = consumer({"ci-watch": installed_skill("ci-watch", PIN)})
        self.assertIn("nothing changed", self._report(
            ["ci-watch"], root, source_at([PIN], ["ci-watch"])).lower())

    def test_a_skipped_skill_is_named_with_its_reason(self):  # DIST-034
        root = consumer({"ci-watch": {"SKILL.md": frontmatter("ci-watch")}})
        text = self._report(["ci-watch"], root, source_at([PIN], ["ci-watch"]))
        self.assertIn("ci-watch", text)
        self.assertIn("no provenance", text)

    def test_a_modified_skill_is_named_as_left_alone(self):  # DIST-034
        files = installed_skill("ci-watch", PIN)
        files["main.py"] = "print('ours')\n"
        root = consumer({"ci-watch": files})
        text = self._report(["ci-watch"], root, source_at([PIN], ["ci-watch"]))
        self.assertIn("edited locally", text)

    def test_the_ref_is_named(self):  # DIST-030
        self.assertIn(PIN, self._report(["ci-watch"], consumer(), source_at([PIN], ["ci-watch"])))

    def test_a_failed_install_is_named(self):  # DIST-035
        proposed = plan(["ci-watch"], PIN, root=consumer(), source=source_at([PIN], ["ci-watch"]))
        text = report(apply(proposed, PIN, installer=Installer(fails=["ci-watch"])), PIN)
        self.assertIn("ci-watch", text)
        self.assertIn("failed", text.lower())


class TestTheWorkflow(unittest.TestCase):
    """The half the Python cannot decide: whether a pull request is opened."""

    @classmethod
    def setUpClass(cls):
        cls.text = WORKFLOW.read_text() if WORKFLOW.is_file() else ""

    def test_the_workflow_exists(self):  # DIST-032
        self.assertTrue(WORKFLOW.is_file(), f"{WORKFLOW.name} is not shipped")

    def test_it_opens_a_pull_request(self):  # DIST-032
        self.assertRegex(self.text, r"(?m)^\s*gh pr create\b")

    def test_it_never_pushes_to_the_branch_it_was_called_on(self):  # DIST-032
        """A direct commit would put unreviewed instructions in front of an agent."""
        self.assertNotRegex(self.text, r"git push[^\n]*HEAD:")
        self.assertNotRegex(self.text, r"git push\s+origin\s+main")

    def test_the_pull_request_is_conditional_on_a_change(self):  # DIST-031
        # The step running `gh pr create` must be guarded, or a run that
        # changed nothing opens an empty pull request every night. The nearest
        # `if:` above the command is that step's condition.
        before = self.text[: re.search(r"(?m)^\s*gh pr create\b", self.text).start()]
        guards = re.findall(r"(?m)^\s*if:\s*(.+)$", before)
        self.assertTrue(guards, "the step opening the pull request has no condition")
        self.assertIn("steps.update.outputs.changed", guards[-1])

    def test_the_branch_is_stable(self):  # DIST-033
        branch = re.search(r"BRANCH:\s*(\S+)", self.text)
        self.assertTrue(branch, "the workflow names no branch")
        self.assertNotIn("github.run", branch.group(1))
        self.assertNotIn("github.sha", branch.group(1))

    def test_the_report_becomes_the_pull_request_body(self):  # DIST-034
        command = re.search(r"(?m)^\s*gh pr create\b", self.text)
        create = self.text[command.start():]
        self.assertRegex(create[:500], r"--body-file\s+\"?\$\{RUNNER_TEMP\}/skills-update\.md")

    def test_it_says_so_when_nothing_changed(self):  # DIST-031
        self.assertIn("GITHUB_STEP_SUMMARY", self.text)

    def test_it_runs_the_skill_from_the_ai_sdlc_checkout(self):  # DIST-004
        self.assertIn("skills/substrate/skills-update/main.py", self.text)
        # API-060: the checkout path is a variable, so ai-sdlc calling its own
        # workflow — where there is no `.ai-sdlc` directory — still works.
        self.assertIn("SKILL_ROOT", self.text)


if __name__ == "__main__":
    unittest.main()
