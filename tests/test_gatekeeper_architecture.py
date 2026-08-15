"""GK-130 to GK-137 — the structural rules, checked rather than trusted."""

import ast
import unittest
from pathlib import Path

from _support import ROOT

SKILL = ROOT / "skills" / "pipeline" / "pipeline-gatekeeper"
NETWORK = {"urllib", "http", "socket", "requests", "ssl", "httpx"}

#: Modules that must stay pure: given a snapshot they return a plan.
PURE = ("parse_commands.py", "scope.py", "arguments.py", "gates.py",
        "ordering.py", "apply_actions.py", "acknowledge.py", "authority.py")


def imports(path):
    tree = ast.parse(Path(path).read_text())
    found = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.add(node.module)
    return found


def roots(path):
    return {name.split(".")[0] for name in imports(path)}


class TestTheNetworkSeam(unittest.TestCase):
    def test_no_gatekeeper_module_imports_a_network_library(self):  # GK-130
        for path in sorted(SKILL.glob("*.py")):
            self.assertEqual(roots(path) & NETWORK, set(), path.name)

    def test_network_access_goes_through_lib_github(self):  # GK-130
        """The fire's transport is imported from the seam, not built here."""
        self.assertIn("lib.github", imports(SKILL / "downstream.py"))


class TestPureModules(unittest.TestCase):
    def test_they_import_no_client(self):  # GK-131
        for name in PURE:
            self.assertNotIn("lib.github", imports(SKILL / name), name)

    def test_they_import_no_subprocess_or_filesystem(self):  # GK-131
        for name in PURE:
            self.assertEqual(roots(SKILL / name) & {"subprocess", "os", "shutil"},
                             set(), name)

    def test_they_take_no_api_argument(self):  # GK-131
        """A pure stage that accepts a client will eventually use it."""
        for name in PURE:
            tree = ast.parse((SKILL / name).read_text())
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef) and not node.name.startswith("_"):
                    argument_names = [a.arg for a in node.args.args]
                    self.assertNotIn("api", argument_names, f"{name}:{node.name}")


class TestPagination(unittest.TestCase):
    def test_collection_reads_go_through_paginate(self):  # GK-132
        from lib.github import PAGE_SIZE, GitHub

        self.assertTrue(hasattr(GitHub, "paginate"))
        self.assertGreater(PAGE_SIZE, 1)

    def test_an_empty_page_is_not_an_error(self):  # GK-133
        from _support import RecordingTransport, Response
        from lib.github import GitHub

        api = GitHub("t", "o/r", transport=RecordingTransport(Response(200, "[]")))
        self.assertEqual(api.paginate("/issues"), [])


class TestDegradation(unittest.TestCase):
    def test_a_failing_blocker_read_does_not_end_the_run(self):  # GK-134
        from lib.fake_github import FakeFailure, FakeGitHub
        from run_comment_event import Settings, handle_comment
        from lib.config import STATES

        api = FakeGitHub(
            issues=[{"number": 7, "labels": [{"name": "pending-approval"}],
                     "milestone": {"title": "v0.1"}}],
            comments={7: [{"id": 55, "body": "/approve",
                           "user": {"login": "derekwinters"}}]},
            milestones=[{"number": 1, "title": "v0.1", "state": "open"}],
            fail={"blocked_by": FakeFailure("dependencies are down")},
            actor="sdlc-bot[bot]",
        )
        event = {"issue": {"number": 7},
                 "comment": {"id": 55, "body": "/approve",
                             "user": {"login": "derekwinters"}}}
        result = handle_comment(
            api,
            event,
            Settings(owners=["derekwinters"], bot_login="sdlc-bot[bot]",
                     labels=dict(STATES), dashboard_issue=193),
        )
        self.assertEqual([a.command for a in result.applied], ["approve"])


class TestConfiguration(unittest.TestCase):
    def test_settings_come_from_repo_config(self):  # GK-135
        from lib.config import parse_config
        from run_comment_event import Settings

        config = parse_config(
            "capabilities:\n  - hygiene\n  - consistency\n  - labels\n"
            "  - release\n  - pipeline\nowners:\n  - derekwinters\n"
            "dashboard_issue: 193\nmilestone_ordering: lexical\n"
        )
        settings = Settings.from_config(config)
        self.assertEqual(settings.owners, ["derekwinters"])
        self.assertEqual(settings.dashboard_issue, 193)
        self.assertEqual(settings.milestone_ordering, "lexical")

    def test_the_label_vocabulary_comes_from_configuration(self):  # GK-135
        from lib.config import parse_config
        from run_comment_event import Settings

        config = parse_config(
            "capabilities:\n  - hygiene\n  - consistency\n  - labels\n"
            "  - release\n  - pipeline\nowners:\n  - d\ndashboard_issue: 1\n"
            "labels:\n  approved: queued\n"
        )
        self.assertEqual(Settings.from_config(config).labels["approved"], "queued")


class TestCapabilityBoundary(unittest.TestCase):
    def test_the_gatekeeper_imports_nothing_above_pipeline(self):  # GK-137
        from lib.validators.boundaries import validate_boundaries

        self.assertEqual(validate_boundaries(ROOT), [])

    def test_no_lower_capability_imports_the_gatekeeper(self):  # GK-137
        for path in sorted((ROOT / "skills").rglob("*.py")):
            capability = path.relative_to(ROOT).parts[1]
            if capability == "pipeline":
                continue
            for module in imports(path):
                self.assertNotIn("pipeline", module, path.name)


class TestNoTestTouchesTheNetwork(unittest.TestCase):
    def test_no_gatekeeper_test_imports_a_network_library(self):  # GK-136
        for path in sorted((ROOT / "tests").glob("*.py")):
            self.assertEqual(roots(path) & NETWORK, set(), path.name)


if __name__ == "__main__":
    unittest.main()
