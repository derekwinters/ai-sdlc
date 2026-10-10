"""ADOPT-120 to ADOPT-132 — manual tasks, checked before they are reported.

Adoption used to report every manual task as prose, unconditionally, and
whoever ran it opened an issue for each: "allow GitHub Actions to create pull
requests" on a repository where it was already on, and the same issue again on
every upgrade. Each task now carries an identifier, a marker, and a status read
from GitHub where GitHub can answer.

Every test here is offline by construction: the client is a `FakeGitHub`, or
there is none.
"""

import contextlib
import importlib.util
import io
import json
import os
import unittest
from unittest import mock

from _adopt import SKILL, repository, PIN
import _adopt  # noqa: F401
from adopt import (
    DONE, NEEDED, TRACKED, UNKNOWN, apply, client_from_environment, plan,
    pull_request_checks, task_line, task_report, task_summary,
)
from lib.fake_github import FakeFailure, FakeGitHub

CONFIG_PATH = ".ai-sdlc/repo-config.yml"
HYGIENE = "capabilities:\n  - hygiene\n"
LABELS_ONLY = "capabilities:\n  - labels\n"
MKDOCS = HYGIENE + "profiles:\n  - mkdocs\n"
SKILLS = HYGIENE + "skills:\n  - ci-watch\n"
PIPELINE = (
    "capabilities:\n  - hygiene\n  - consistency\n  - labels\n  - release\n"
    "  - pipeline\nowners:\n  - someone\nskills:\n  - ci-watch\ndashboard_issue: 7\n"
)

READS = {"issue", "issues", "comments", "reactions", "milestones", "blocked_by",
         "labels", "issue_id", "default_branch", "workflow_permissions",
         "branch_protection", "branch_rules"}


def tasks(config=HYGIENE, github=None):
    root = repository({CONFIG_PATH: config})
    return {t.id: t for t in plan(root, pin=PIN, github=github).manual_tasks}


def protected(*contexts, branch="main", checks_form=False):
    """A classic protection rule requiring `contexts` on `branch`."""
    required = ({"checks": [{"context": c} for c in contexts]} if checks_form
                else {"contexts": list(contexts)})
    return {branch: {"required_status_checks": required}}


def ruleset(*contexts, branch="main"):
    return {branch: [{
        "type": "required_status_checks",
        "parameters": {"required_status_checks": [{"context": c} for c in contexts]},
    }]}


def tracking(task_id, number=42, pull_request=False, state="open"):
    issue = {"number": number, "state": state, "title": "x",
             "body": f"words\n\n<!-- ai-sdlc-task: {task_id} -->\n"}
    if pull_request:
        issue["pull_request"] = {"url": "x"}
    return issue


class TestEveryTaskHasAnIdentifier(unittest.TestCase):
    def test_the_five_identifiers(self):  # ADOPT-120
        self.assertEqual(
            set(tasks(PIPELINE, FakeGitHub())),
            {"require-checks", "no-skip-if", "renamed-checks", "actions-can-open-prs",
             "dashboard-issue"},
        )

    def test_the_prose_is_kept(self):  # ADOPT-120
        found = tasks(SKILLS)
        self.assertIn("Make the checks required", found["require-checks"].text)
        self.assertIn("create and approve pull requests", found["actions-can-open-prs"].text)

    def test_a_task_is_still_its_text(self):  # ADOPT-120
        """Existing readers join the tasks as strings; they still can."""
        found = tasks(HYGIENE)
        self.assertEqual(str(found["no-skip-if"]), found["no-skip-if"].text)

    def test_apply_uses_the_same_identifiers(self):  # ADOPT-120
        root = repository({CONFIG_PATH: SKILLS})
        applied = {t.id for t in apply(root, pin=PIN).manual_tasks}
        self.assertEqual(applied, set(tasks(SKILLS)))


class TestEveryTaskHasAMarker(unittest.TestCase):
    def test_the_marker_names_the_identifier(self):  # ADOPT-121
        self.assertEqual(tasks()["require-checks"].marker,
                         "<!-- ai-sdlc-task: require-checks -->")

    def test_the_suggested_body_carries_it(self):  # ADOPT-121
        task = tasks()["require-checks"]
        self.assertIn(task.marker, task.issue_body)


class TestClassification(unittest.TestCase):
    def test_without_a_client_everything_is_unknown(self):  # ADOPT-122
        self.assertEqual({t.status for t in tasks(PIPELINE).values()}, {UNKNOWN})

    def test_without_a_client_the_reason_says_so(self):  # ADOPT-122
        self.assertIn("no GitHub", tasks()["require-checks"].reason)

    def test_with_a_client_every_status_is_one_of_four(self):  # ADOPT-122
        found = tasks(PIPELINE, FakeGitHub())
        self.assertTrue({t.status for t in found.values()} <= {DONE, TRACKED, NEEDED, UNKNOWN})

    def test_plan_is_otherwise_unchanged(self):  # ADOPT-122
        root = repository({CONFIG_PATH: HYGIENE})
        with_client = plan(root, pin=PIN, github=FakeGitHub())
        without = plan(root, pin=PIN)
        self.assertEqual((with_client.creates, with_client.updates),
                         (without.creates, without.updates))


class TestTracked(unittest.TestCase):
    def test_an_open_issue_with_the_marker_tracks_it(self):  # ADOPT-123
        task = tasks(HYGIENE, FakeGitHub(issues=[tracking("require-checks", 42)]))["require-checks"]
        self.assertEqual((task.status, task.issue), (TRACKED, 42))

    def test_an_open_pull_request_tracks_it_too(self):  # ADOPT-123
        github = FakeGitHub(issues=[tracking("require-checks", 9, pull_request=True)])
        self.assertEqual(tasks(HYGIENE, github)["require-checks"].status, TRACKED)

    def test_a_closed_issue_does_not(self):  # ADOPT-123
        github = FakeGitHub(issues=[tracking("require-checks", 9, state="closed")])
        self.assertEqual(tasks(HYGIENE, github)["require-checks"].status, NEEDED)

    def test_done_wins(self):  # ADOPT-123
        github = FakeGitHub(
            issues=[tracking("actions-can-open-prs", 5)],
            workflow_permissions={"can_approve_pull_request_reviews": True},
        )
        self.assertEqual(tasks(SKILLS, github)["actions-can-open-prs"].status, DONE)

    def test_another_tasks_marker_does_not(self):  # ADOPT-123
        github = FakeGitHub(issues=[tracking("no-skip-if", 5)])
        self.assertEqual(tasks(HYGIENE, github)["require-checks"].status, NEEDED)


class TestActionsCanOpenPullRequests(unittest.TestCase):
    def test_enabled_is_done(self):  # ADOPT-124
        github = FakeGitHub(workflow_permissions={"can_approve_pull_request_reviews": True})
        self.assertEqual(tasks(SKILLS, github)["actions-can-open-prs"].status, DONE)

    def test_disabled_is_needed(self):  # ADOPT-124
        github = FakeGitHub(workflow_permissions={"can_approve_pull_request_reviews": False})
        self.assertEqual(tasks(SKILLS, github)["actions-can-open-prs"].status, NEEDED)


class TestRequireChecks(unittest.TestCase):
    def test_the_names_follow_the_callers(self):  # ADOPT-125
        root = repository({CONFIG_PATH: MKDOCS})
        from adopt import _load_config

        self.assertEqual(set(pull_request_checks(_load_config(root), PIN)),
                         {"closing-keyword", "docs-gate", "docs-build / build"})

    def test_required_by_protection_is_done(self):  # ADOPT-125
        github = FakeGitHub(protection=protected("closing-keyword"))
        self.assertEqual(tasks(HYGIENE, github)["require-checks"].status, DONE)

    def test_the_checks_form_counts(self):  # ADOPT-125
        github = FakeGitHub(protection=protected("closing-keyword", checks_form=True))
        self.assertEqual(tasks(HYGIENE, github)["require-checks"].status, DONE)

    def test_required_by_a_ruleset_is_done(self):  # ADOPT-125
        github = FakeGitHub(rules=ruleset("closing-keyword"))
        self.assertEqual(tasks(HYGIENE, github)["require-checks"].status, DONE)

    def test_the_default_branch_is_the_one_read(self):  # ADOPT-125
        github = FakeGitHub(default_branch="trunk",
                            protection=protected("closing-keyword", branch="main"))
        self.assertEqual(tasks(HYGIENE, github)["require-checks"].status, NEEDED)

    def test_one_missing_is_needed_and_named(self):  # ADOPT-125
        github = FakeGitHub(protection=protected("closing-keyword", "docs-gate"))
        task = tasks(MKDOCS, github)["require-checks"]
        self.assertEqual(task.status, NEEDED)
        self.assertIn("docs-build / build", task.reason)

    def test_nothing_to_require_is_done(self):  # ADOPT-125
        self.assertEqual(tasks(LABELS_ONLY, FakeGitHub())["require-checks"].status, DONE)


class TestRenamedChecks(unittest.TestCase):
    def test_an_old_name_still_required_is_needed(self):  # ADOPT-126
        github = FakeGitHub(protection=protected("closing-keyword / closing-keyword"))
        task = tasks(HYGIENE, github)["renamed-checks"]
        self.assertEqual(task.status, NEEDED)
        self.assertIn("closing-keyword / closing-keyword", task.reason)

    def test_no_old_name_is_done(self):  # ADOPT-126
        github = FakeGitHub(protection=protected("closing-keyword"))
        self.assertEqual(tasks(HYGIENE, github)["renamed-checks"].status, DONE)


class TestDashboardIssue(unittest.TestCase):
    def dashboard(self, number, state="open"):
        return {"number": number, "state": state, "title": "Pipeline",
                "body": "# Pipeline\n\n**Focus:** none.\n"}

    def test_a_configured_issue_is_trusted_offline(self):  # ADOPT-127
        self.assertNotIn("dashboard-issue", tasks(PIPELINE))

    def test_an_open_configured_issue_is_not_reported(self):  # ADOPT-127
        github = FakeGitHub(issues=[self.dashboard(7)])
        self.assertNotIn("dashboard-issue", tasks(PIPELINE, github))

    def test_a_missing_configured_issue_is_needed(self):  # ADOPT-127
        task = tasks(PIPELINE, FakeGitHub())["dashboard-issue"]
        self.assertEqual(task.status, NEEDED)
        self.assertIn("#7", task.reason)

    def test_a_closed_configured_issue_is_needed(self):  # ADOPT-127
        github = FakeGitHub(issues=[self.dashboard(7, state="closed")])
        self.assertEqual(tasks(PIPELINE, github)["dashboard-issue"].status, NEEDED)

    def test_an_existing_dashboard_tracks_it(self):  # ADOPT-127
        github = FakeGitHub(issues=[self.dashboard(193)])
        task = tasks(PIPELINE, github)["dashboard-issue"]
        self.assertEqual((task.status, task.issue), (TRACKED, 193))
        self.assertIn("dashboard_issue: 193", task.reason)

    def test_an_unreadable_issue_is_trusted(self):  # ADOPT-127
        github = FakeGitHub(fail={"issue": FakeFailure(status=403)})
        self.assertNotIn("dashboard-issue", tasks(PIPELINE, github))


class TestAdvice(unittest.TestCase):
    def test_advice_is_unknown(self):  # ADOPT-128
        self.assertEqual(tasks(HYGIENE, FakeGitHub())["no-skip-if"].status, UNKNOWN)

    def test_unless_an_issue_tracks_it(self):  # ADOPT-128
        github = FakeGitHub(issues=[tracking("no-skip-if", 3)])
        self.assertEqual(tasks(HYGIENE, github)["no-skip-if"].status, TRACKED)


class TestAFailedCheckIsUnknown(unittest.TestCase):
    def test_a_refusal_is_unknown(self):  # ADOPT-129
        github = FakeGitHub(fail={"workflow_permissions": FakeFailure(status=403)})
        task = tasks(SKILLS, github)["actions-can-open-prs"]
        self.assertEqual(task.status, UNKNOWN)
        self.assertIn("403", task.reason)

    def test_no_default_branch_is_unknown(self):  # ADOPT-129
        github = FakeGitHub(fail={"default_branch": FakeFailure(status=None)})
        found = tasks(HYGIENE, github)
        self.assertEqual((found["require-checks"].status, found["renamed-checks"].status),
                         (UNKNOWN, UNKNOWN))

    def test_nothing_readable_about_the_branch_is_unknown(self):  # ADOPT-129
        github = FakeGitHub(fail={"branch_rules": FakeFailure(status=403)})
        self.assertEqual(tasks(HYGIENE, github)["require-checks"].status, UNKNOWN)

    def test_an_unprotected_branch_beside_a_readable_ruleset_is_needed(self):  # ADOPT-129
        self.assertEqual(tasks(HYGIENE, FakeGitHub())["require-checks"].status, NEEDED)

    def test_a_refused_protection_read_falls_back_to_rulesets(self):  # ADOPT-129
        github = FakeGitHub(rules=ruleset("closing-keyword"),
                            fail={"branch_protection": FakeFailure(status=403)})
        self.assertEqual(tasks(HYGIENE, github)["require-checks"].status, DONE)

    def test_an_unreadable_issue_list_still_checks_settings(self):  # ADOPT-129
        github = FakeGitHub(fail={"issues": FakeFailure(status=500)},
                            workflow_permissions={"can_approve_pull_request_reviews": True})
        self.assertEqual(tasks(SKILLS, github)["actions-can-open-prs"].status, DONE)

    def test_an_unexpected_error_never_fails_apply(self):  # ADOPT-129
        class Broken(FakeGitHub):
            def default_branch(self):
                raise KeyError("default_branch")

        root = repository({CONFIG_PATH: HYGIENE})
        result = apply(root, pin=PIN, github=Broken())
        self.assertTrue(result.written)
        self.assertEqual({t.id: t.status for t in result.manual_tasks}["require-checks"],
                         UNKNOWN)


class TestItOnlyReads(unittest.TestCase):
    def test_no_write_reaches_github(self):  # ADOPT-130
        github = FakeGitHub(issues=[tracking("require-checks", 4)])
        root = repository({CONFIG_PATH: PIPELINE})
        apply(root, pin=PIN, github=github)
        self.assertTrue(github.calls)
        self.assertEqual({name for name, _ in github.calls} - READS, set())


def _load_main():
    spec = importlib.util.spec_from_file_location("adopt_main", SKILL / "main.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run_main(command, config, github):
    """Run `main.py <command>` in a throwaway repository, offline."""
    main = _load_main()
    root = repository({CONFIG_PATH: config})
    out = io.StringIO()
    before = os.getcwd()
    try:
        os.chdir(root)
        with mock.patch.object(main, "as_pin", return_value=PIN), \
                mock.patch.object(main, "client_from_environment", return_value=github), \
                contextlib.redirect_stdout(out):
            code = main.main(["main.py", command, "v0.4.0"])
    finally:
        os.chdir(before)
    return code, out.getvalue(), root


class TestTheTasksCommand(unittest.TestCase):
    def test_it_prints_json(self):  # ADOPT-131
        github = FakeGitHub(issues=[tracking("require-checks", 42)])
        code, out, _ = _run_main("tasks", SKILLS, github)
        records = {r["id"]: r for r in json.loads(out)}
        self.assertEqual(code, 0)
        self.assertEqual((records["require-checks"]["status"],
                          records["require-checks"]["issue"]), (TRACKED, 42))

    def test_each_record_carries_what_an_issue_needs(self):  # ADOPT-131
        record = task_report(tasks(SKILLS, FakeGitHub()).values())[0]
        for key in ("id", "status", "issue", "reason", "marker", "title", "body", "text"):
            with self.subTest(key=key):
                self.assertIn(key, record)
        self.assertIn(record["marker"], record["body"])

    def test_it_writes_nothing(self):  # ADOPT-131
        _, _, root = _run_main("tasks", SKILLS, FakeGitHub())
        self.assertEqual(sorted(p.name for p in root.rglob("*") if p.is_file()),
                         ["repo-config.yml"])

    def test_plan_prints_each_status(self):  # ADOPT-131
        github = FakeGitHub(workflow_permissions={"can_approve_pull_request_reviews": True},
                            issues=[tracking("require-checks", 42)])
        _, out, _ = _run_main("plan", SKILLS, github)
        self.assertIn("[done] actions-can-open-prs", out)
        self.assertIn("[tracked #42] require-checks", out)
        self.assertIn("skipped 3 of 4", out)

    def test_a_needed_line_carries_the_text(self):  # ADOPT-131
        task = tasks(SKILLS, FakeGitHub())["actions-can-open-prs"]
        self.assertIn(task.text, task_line(task))
        self.assertTrue(task_line(task).startswith("[needed] actions-can-open-prs"))

    def test_the_summary_points_at_needed_only(self):  # ADOPT-131
        summary = task_summary(tasks(SKILLS, FakeGitHub()).values())
        self.assertIn("needed", summary)


class TestTheClient(unittest.TestCase):
    def test_no_token_is_no_client(self):  # ADOPT-132
        self.assertIsNone(client_from_environment(
            "/", environ={"GITHUB_REPOSITORY": "o/r"}, remote=lambda root: None))

    def test_a_token_and_a_repository(self):  # ADOPT-132
        client = client_from_environment(
            "/", environ={"GITHUB_TOKEN": "t", "GITHUB_REPOSITORY": "o/r"},
            remote=lambda root: None)
        self.assertEqual(client.repository, "o/r")

    def test_gh_token_and_the_origin_remote(self):  # ADOPT-132
        client = client_from_environment(
            "/", environ={"GH_TOKEN": "t"},
            remote=lambda root: "https://x-access-token:s3cret@github.com/o/r.git")
        self.assertEqual(client.repository, "o/r")

    def test_an_ssh_remote(self):  # ADOPT-132
        client = client_from_environment(
            "/", environ={"GH_TOKEN": "t"}, remote=lambda root: "git@github.com:o/r.git")
        self.assertEqual(client.repository, "o/r")

    def test_no_repository_is_no_client(self):  # ADOPT-132
        self.assertIsNone(client_from_environment(
            "/", environ={"GH_TOKEN": "t"}, remote=lambda root: None))

    def test_the_remote_is_never_printed(self):  # ADOPT-132
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            client = client_from_environment(
                "/", environ={"GH_TOKEN": "t"},
                remote=lambda root: "https://user:s3cret@example.com/not-a-slug")
        self.assertIsNone(client)
        self.assertNotIn("s3cret", out.getvalue())


if __name__ == "__main__":
    unittest.main()
