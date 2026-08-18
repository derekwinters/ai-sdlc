"""Every reusable workflow can actually import the skill it runs.

The gatekeeper workflow ran `python3 .ai-sdlc/…/main.py` with no PYTHONPATH,
so the skill died on `from lib.github import …` before doing anything:

    ModuleNotFoundError: No module named 'lib'

It was the pipeline's central workflow and it had never been executed
anywhere, so nothing had noticed. `labels-sync` and `dashboard` set PYTHONPATH;
the two gatekeepers did not, and a difference between sibling workflows is
exactly what a test should hold still.

Sixth defect of the "ships incomplete" shape (#71, #75, #78, #81, #84, #87).
"""

import re
import unittest

from _support import ROOT

WORKFLOWS = ROOT / ".github" / "workflows"

#: A step that runs a Python file out of the skills tree. Matched on the script
#: path rather than on `python3 …`, because the invocation may be split across a
#: line continuation — which is exactly what the fix for this turned it into.
RUNS_A_SKILL = re.compile(r"skills/\S+\.py")


def _reusable():
    for path in sorted(WORKFLOWS.glob("reusable-*.yml")):
        yield path, path.read_text()


class TestASkillCanImportItsLibrary(unittest.TestCase):
    def test_there_are_workflows_running_skills(self):  # API-060
        running = [p.name for p, t in _reusable() if RUNS_A_SKILL.search(t)]
        self.assertGreaterEqual(len(running), 3, "the sweep found nothing to check")

    def test_a_workflow_running_a_skill_that_imports_lib_sets_pythonpath(self):  # API-060
        # Conditional on the import, not on running a script at all: the
        # closing-keyword and docs-gate skills are deliberately self-contained
        # stdlib scripts, and requiring PYTHONPATH of them would be cargo cult.
        for path, text in _reusable():
            scripts = [ROOT / m for m in RUNS_A_SKILL.findall(text)]
            needs_lib = any(
                s.is_file() and re.search(r"^from lib[. ]|^import lib", s.read_text(), re.M)
                for s in scripts
            )
            if not needs_lib:
                continue
            with self.subTest(workflow=path.name):
                self.assertIn(
                    "PYTHONPATH", text,
                    f"{path.name} runs a skill that imports `lib`, with no "
                    f"PYTHONPATH — it dies on ModuleNotFoundError before doing "
                    f"anything",
                )

    def test_at_least_one_workflow_runs_a_lib_importing_skill(self):  # API-060
        # Guards the test above from passing vacuously if the import moves.
        found = [
            path.name for path, text in _reusable()
            for m in RUNS_A_SKILL.findall(text)
            if (ROOT / m).is_file()
            and re.search(r"^from lib[. ]|^import lib", (ROOT / m).read_text(), re.M)
        ]
        self.assertTrue(found, "no workflow runs a skill importing lib")

    def test_no_workflow_hard_codes_the_checkout_path(self):  # API-060
        # `.ai-sdlc` is where a *consumer* checks ai-sdlc out. ai-sdlc calling
        # its own reusable workflow has no such directory, so a hard-coded path
        # works in exactly one of the two places it has to work.
        for path, text in _reusable():
            if not RUNS_A_SKILL.search(text):
                continue
            with self.subTest(workflow=path.name):
                self.assertNotRegex(
                    text, r"\.ai-sdlc/skills/\S+\.py",
                    f"{path.name} hard-codes .ai-sdlc/ instead of using SKILL_ROOT",
                )

    def test_no_workflow_checks_out_over_the_configuration_directory(self):  # API-061
        """A consumer's `.ai-sdlc/` holds files the consumer has committed.

        `actions/checkout` empties the directory it checks out into. Fetching
        ai-sdlc into the path where the consumer keeps `repo-config.yml` would
        replace that file with **ai-sdlc's own** — same name, same place, wrong
        repository — and every skill in the run would then read the wrong
        configuration and say nothing about it.

        The checkout path is an implementation detail of these workflows and
        nothing outside them names it. The configuration directory is a path
        consumers commit to and documents point at. So the checkout moves.
        """
        from lib.config import CONFIG_DIR

        for path, text in _reusable():
            with self.subTest(workflow=path.name):
                self.assertNotRegex(
                    text, rf"(?m)^\s*path:\s*{re.escape(str(CONFIG_DIR))}\s*$",
                    f"{path.name} checks ai-sdlc out over the consumer's "
                    f"{CONFIG_DIR}/ configuration",
                )

    def test_the_checkout_path_is_the_one_skill_root_names(self):  # API-061
        """Two places name it — the `path:` and the `SKILL_ROOT` — and a run
        where they disagree fetches to one directory and reads from another."""
        for path, text in _reusable():
            paths = set(re.findall(r"^\s*path:\s*(\S+)\s*$", text, re.M))
            roots = set(re.findall(r"SKILL_ROOT:.*?'(\.[\w.-]+)'", text))
            if not paths and not roots:
                continue
            with self.subTest(workflow=path.name):
                self.assertEqual(paths, roots, path.name)

    def test_no_consumer_checkout_uses_the_ai_sdlc_ref(self):  # ADOPT-067
        """`inputs.ref` names a commit in **ai-sdlc**, not in the caller.

        Every caller passes `ref: <ai-sdlc sha>`. Handing that to a checkout of
        the consumer's own repository asks GitHub for a commit that repository
        has never seen:

            fatal: remote error: upload-pack: not our ref 86edeee...

        So a step may only use `inputs.ref` when it is also checking out
        ai-sdlc — which means naming `repository:`. Introduced in #103 and
        caught by the first consumer to run it (frogs#362), because ai-sdlc
        does not install its own callers and so never exercises this path.
        """
        steps = re.compile(r"-\s+(?:if:[^\n]*\n\s+)?uses:\s*actions/checkout@[^\n]*\n"
                           r"((?:\s+(?!-\s)\S[^\n]*\n)*)")
        for path, text in _reusable():
            for block in steps.findall(text):
                if "inputs.ref" not in block:
                    continue
                with self.subTest(workflow=path.name):
                    self.assertIn(
                        "repository:", block,
                        f"{path.name} passes the ai-sdlc ref to a checkout of the "
                        f"caller's own repository; that commit does not exist there",
                    )
