"""VAL-050 to VAL-055 — third-party actions are pinned to a commit SHA.

This validator exists because of a real failure: `release-please.yml` referenced
`googleapis/release-please-action@v4`, the repository requires third-party
actions to be pinned to a full-length SHA, and every run of the release
workflow failed at the point of *starting* the step — a failure mode that no
test in the suite could see, because nothing here reads workflow files.
"""

import tempfile
import unittest
from pathlib import Path

from _support import ROOT
from lib.validators.actions import validate_actions

PINNED = "5c625bfb5d1ff62eadeeb3772007f7f66fdcf071"


class Tree(unittest.TestCase):
    def build(self, **workflows):
        root = Path(tempfile.mkdtemp())
        (root / ".github" / "workflows").mkdir(parents=True)
        for name, text in workflows.items():
            (root / ".github" / "workflows" / f"{name}.yml").write_text(text)
        return root


class TestPinning(Tree):
    def test_a_third_party_action_pinned_to_a_sha_passes(self):  # VAL-051
        root = self.build(a=f"      - uses: googleapis/x@{PINNED} # v4\n")
        self.assertEqual(validate_actions(root), [])

    def test_a_third_party_action_on_a_tag_is_reported(self):  # VAL-051
        root = self.build(a="      - uses: googleapis/x@v4\n")
        problems = validate_actions(root)
        self.assertTrue(any("googleapis/x" in p for p in problems))

    def test_a_third_party_action_on_a_branch_is_reported(self):  # VAL-051
        root = self.build(a="      - uses: googleapis/x@main\n")
        self.assertTrue(validate_actions(root))

    def test_a_short_sha_is_not_a_pin(self):  # VAL-051
        root = self.build(a="      - uses: googleapis/x@5c625bf # v4\n")
        self.assertTrue(validate_actions(root))

    def test_the_problem_names_the_file_and_line(self):  # VAL-055
        root = self.build(a="\n\n      - uses: googleapis/x@v4\n")
        problem = validate_actions(root)[0]
        self.assertIn("a.yml", problem)
        self.assertIn(":3", problem)


class TestExemptions(Tree):
    def test_a_local_reference_is_exempt(self):  # VAL-052
        root = self.build(a="      - uses: ./.github/workflows/reusable-x.yml\n")
        self.assertEqual(validate_actions(root), [])

    def test_a_github_owned_action_is_not_exempt(self):  # VAL-053
        # The repository's policy makes no exception for `actions/*`, so
        # neither does this. Assuming otherwise is what produced the second
        # round of failures on the very PR that added this validator.
        root = self.build(a="      - uses: actions/checkout@v4\n")
        self.assertTrue(validate_actions(root))

    def test_a_pinned_github_owned_action_passes(self):  # VAL-053
        root = self.build(a=f"      - uses: actions/checkout@{PINNED} # v4\n")
        self.assertEqual(validate_actions(root), [])

    def test_a_reusable_workflow_reference_is_not_exempt(self):  # VAL-056
        # It runs with the caller's token, so a moving ref is the same exposure
        # as a moving action. `adopt` now writes a SHA, so there is no longer a
        # contradiction between this gate and the skill (#72).
        root = self.build(
            a="    uses: derekwinters/ai-sdlc/.github/workflows/reusable-x.yml@v0.1.0\n"
        )
        self.assertTrue(validate_actions(root))

    def test_a_reusable_workflow_pinned_to_a_sha_passes(self):  # VAL-056
        root = self.build(
            a=f"    uses: derekwinters/ai-sdlc/.github/workflows/x.yml@{PINNED} # v0.1.0\n"
        )
        self.assertEqual(validate_actions(root), [])

    def test_a_docker_reference_is_exempt(self):  # VAL-052
        root = self.build(a="      - uses: docker://alpine:3.19\n")
        self.assertEqual(validate_actions(root), [])


class TestReadability(Tree):
    def test_a_pin_without_a_version_comment_is_reported(self):  # VAL-054
        root = self.build(a=f"      - uses: googleapis/x@{PINNED}\n")
        problems = validate_actions(root)
        self.assertTrue(any("comment" in p for p in problems))

    def test_a_version_comment_may_be_any_shape(self):  # VAL-054
        root = self.build(a=f"      - uses: googleapis/x@{PINNED}  # pin to v4.1.2\n")
        self.assertEqual(validate_actions(root), [])


class TestScope(Tree):
    def test_every_workflow_file_is_read(self):  # VAL-050
        root = self.build(
            a=f"      - uses: actions/checkout@{PINNED} # v4\n",
            b="      - uses: googleapis/x@v4\n",
        )
        problems = validate_actions(root)
        self.assertEqual(len(problems), 1)
        self.assertIn("b.yml", problems[0])

    def test_a_repository_with_no_workflows_is_clean(self):  # VAL-050
        self.assertEqual(validate_actions(Path(tempfile.mkdtemp())), [])

    def test_yaml_and_yml_are_both_read(self):  # VAL-050
        root = self.build(a=f"      - uses: actions/checkout@{PINNED} # v4\n")
        (root / ".github" / "workflows" / "c.yaml").write_text(
            "      - uses: googleapis/x@v4\n"
        )
        self.assertTrue(validate_actions(root))


class TestTheRealRepository(unittest.TestCase):
    def test_this_repository_pins_every_third_party_action(self):  # VAL-051
        self.assertEqual(validate_actions(ROOT), [])


if __name__ == "__main__":
    unittest.main()
