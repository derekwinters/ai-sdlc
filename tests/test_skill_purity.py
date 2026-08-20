"""DIST-040 to DIST-043 — what an installed skill may contain.

`connor-multiplying-frogs` installed six skills and four of them could not do
the thing they existed to do. The reason was not packaging, which is what #153
originally chased: it was that they were written as **libraries with an injected
dependency** and shipped as **skills**.

Every one of the four took `api` as a parameter. In ai-sdlc's own tests that
caller is the test, handing over `FakeGitHub`. In a consumer there is no caller
at all — a skill is a directory an agent reads, and nothing in that arrangement
constructs a `GitHub`. A `def take(api, issue, labels)` in an installed skill is
a function with no possible caller.

So the split is not "skill versus library". It is:

* a **script** runs in a workflow with no agent present, so it must talk to
  GitHub in code — and it is delivered to the runner, never installed;
* a **skill** is loaded by an agent, and every GitHub read and write it needs
  is done by that agent through `github-api` (`API-070`).
"""

import ast
import sys
import unittest

from _support import ROOT

sys.path.insert(0, str(ROOT / "skills" / "substrate" / "adopt"))
from adopt import INVOKED_LOCALLY  # noqa: E402


def installable():
    """Every skill name a repository may legitimately put in `skills:`."""
    return {name for names in INVOKED_LOCALLY.values() for name in names}


def skill_directory(name):
    matches = [p.parent for p in ROOT.glob(f"skills/*/{name}/SKILL.md")]
    assert len(matches) == 1, f"{name}: expected one skill directory, found {matches}"
    return matches[0]


def modules(name):
    return sorted(skill_directory(name).glob("*.py"))


class TestTheInstallableSetIsKnown(unittest.TestCase):
    def test_every_installable_skill_exists(self):  # DIST-040
        for name in sorted(installable()):
            with self.subTest(skill=name):
                self.assertTrue((skill_directory(name) / "SKILL.md").is_file())

    def test_a_script_skill_is_not_installable(self):  # DIST-041
        """These run from ai-sdlc's own tree inside an action. A copy in a
        consumer is a second version nothing reads."""
        for name in ("pipeline-gatekeeper", "pipeline-dashboard", "label-sync",
                     "closing-keyword", "docs-gate", "skills-update", "adopt"):
            with self.subTest(skill=name):
                self.assertNotIn(name, installable())


class TestAnInstalledSkillCarriesNoClientCode(unittest.TestCase):
    """DIST-042 — the test that would have caught the whole defect.

    Both halves are stated, because either alone is satisfiable in a way that
    keeps the bug: a module could avoid importing `lib` and still take an `api`,
    or take no `api` and still open a socket.
    """

    def test_no_module_imports_lib(self):  # DIST-042
        for name in sorted(installable()):
            for path in modules(name):
                with self.subTest(skill=name, module=path.name):
                    tree = ast.parse(path.read_text())
                    imported = set()
                    for node in ast.walk(tree):
                        if isinstance(node, ast.Import):
                            imported |= {a.name.split(".")[0] for a in node.names}
                        elif isinstance(node, ast.ImportFrom) and node.module:
                            imported.add(node.module.split(".")[0])
                    self.assertNotIn("lib", imported)

    def test_no_function_expects_a_client(self):  # DIST-042
        """`api` is the parameter name every one of the four used. A skill that
        wants one is a skill waiting for a caller that does not exist."""
        for name in sorted(installable()):
            for path in modules(name):
                tree = ast.parse(path.read_text())
                for node in ast.walk(tree):
                    if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        continue
                    taken = [a.arg for a in node.args.args + node.args.kwonlyargs]
                    with self.subTest(skill=name, module=path.name, function=node.name):
                        self.assertNotIn("api", taken)

    def test_no_module_imports_a_network_library(self):  # DIST-042
        """`API`'s first invariant, from the other end. Vendoring the client
        into four skills was #153's original proposal, and it would have put
        `import urllib` in four more modules."""
        for name in sorted(installable()):
            for path in modules(name):
                with self.subTest(skill=name, module=path.name):
                    text = path.read_text()
                    for library in ("urllib", "http.client", "requests", "socket"):
                        self.assertNotIn(f"import {library}", text)


class TestTheConvertedFourCarryNoModulesAtAll(unittest.TestCase):
    """DIST-043 — these four were entirely client code, so nothing is left.

    Stated separately from `DIST-042` because "no module imports `lib`" is
    satisfiable by a skill that keeps a module doing something else. These four
    were the state machine, the ordering and the routing, and all of that is
    now described rather than executed.
    """

    CONVERTED = ("issue-blockers", "milestone-ops", "pipeline-dev", "triage-issue")

    def test_each_is_instructions_only(self):  # DIST-043
        for name in self.CONVERTED:
            with self.subTest(skill=name):
                self.assertEqual(modules(name), [])

    def test_each_points_at_the_github_api_skill(self):  # DIST-043
        """The work did not stop needing GitHub; it stopped doing GitHub
        itself. A skill that describes a write without saying what performs it
        has moved the gap rather than closed it."""
        for name in self.CONVERTED:
            with self.subTest(skill=name):
                self.assertIn("github-api", (skill_directory(name) / "SKILL.md").read_text())

    def test_none_still_shows_a_python_call(self):  # DIST-043
        """Each `SKILL.md` documented an invocation — `Blockers(api)`,
        `Milestones(api)`, `take(api, …)` — that never had a caller in a
        consumer. A left-behind example is worse than none: it reads as
        supported."""
        for name in self.CONVERTED:
            with self.subTest(skill=name):
                self.assertNotIn("(api", (skill_directory(name) / "SKILL.md").read_text())


if __name__ == "__main__":
    unittest.main()
