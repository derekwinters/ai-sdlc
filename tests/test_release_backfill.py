"""REL-040 to REL-047 — recovering tags from release commits.

ai-sdlc reached 0.4.0 with four release commits on `main` and no tags at all:
release-please's action was refused for being tag-pinned (#64), so it never ran
to do the tagging. Without a tag to compute from, its first successful run
proposed the whole history as one release.

Everything here is pure: it takes the output of `git log` and the contents of
`CHANGELOG.md` as text. The workflow does the git.
"""

import unittest

from _release import SKILL  # noqa: F401 - puts the skill on the path
from backfill_tags import changelog_section, plan

LOG = "\n".join(
    [
        "d2ca143\tchore(main): release 0.4.0",
        "0f3e636\tfeat(rules): add the shared house-rules fragment (#62)",
        "6deffff\tchore(main): release 0.3.0",
        "bc0f15a\tfeat(rel): add the release flow (#58)",
        "11bb221\tchore(main): release 0.2.0",
        "d410565\tchore(main): release 0.1.0",
    ]
)

CHANGELOG = """# Changelog

## 0.4.0 (2026-08-15)

Adoption.

### Features

* the adopt command

## 0.3.0 (2026-08-15)

The working loop.
"""


class TestDerivingThePlan(unittest.TestCase):
    def test_a_release_commit_becomes_a_tag(self):  # REL-040
        self.assertIn(("v0.1.0", "d410565"), [(e.tag, e.sha) for e in plan(LOG, [])])

    def test_an_ordinary_commit_is_not_a_release(self):  # REL-040
        self.assertNotIn("0f3e636", [e.sha for e in plan(LOG, [])])

    def test_every_release_commit_is_found(self):  # REL-040
        self.assertEqual(len(plan(LOG, [])), 4)

    def test_an_empty_history_plans_nothing(self):  # REL-040
        self.assertEqual(plan("", []), [])

    def test_the_tag_carries_a_v_prefix(self):  # REL-042
        self.assertTrue(all(e.tag.startswith("v") for e in plan(LOG, [])))

    def test_the_plan_runs_oldest_first(self):  # REL-044
        self.assertEqual(
            [e.tag for e in plan(LOG, [])], ["v0.1.0", "v0.2.0", "v0.3.0", "v0.4.0"]
        )

    def test_the_plan_orders_by_version_not_by_string(self):  # REL-044
        log = "a\tchore(main): release 0.10.0\nb\tchore(main): release 0.9.0"
        self.assertEqual([e.tag for e in plan(log, [])], ["v0.9.0", "v0.10.0"])


class TestSkipping(unittest.TestCase):
    def test_an_already_tagged_version_is_skipped(self):  # REL-041
        self.assertNotIn("v0.1.0", [e.tag for e in plan(LOG, ["v0.1.0"])])

    def test_skipping_leaves_the_rest(self):  # REL-041
        self.assertEqual(len(plan(LOG, ["v0.1.0", "v0.2.0"])), 2)

    def test_a_fully_tagged_history_plans_nothing(self):  # REL-041
        tags = ["v0.1.0", "v0.2.0", "v0.3.0", "v0.4.0"]
        self.assertEqual(plan(LOG, tags), [])


class TestRefusingToGuess(unittest.TestCase):
    def test_a_release_commit_without_a_version_is_skipped(self):  # REL-043
        entries = plan("abc\tchore(main): release the hounds", [])
        self.assertEqual([e.tag for e in entries if e.tag], [])

    def test_a_release_commit_without_a_version_is_reported(self):  # REL-043
        entries = plan("abc\tchore(main): release the hounds", [])
        self.assertEqual(len(entries), 1)
        self.assertTrue(entries[0].problem)

    def test_a_prerelease_is_reported_and_skipped(self):  # REL-046
        entries = plan("abc\tchore(main): release 1.0.0-rc.1", [])
        self.assertTrue(entries[0].problem)
        self.assertFalse(entries[0].tag)

    def test_build_metadata_is_reported_and_skipped(self):  # REL-046
        entries = plan("abc\tchore(main): release 1.0.0+build.5", [])
        self.assertTrue(entries[0].problem)

    def test_a_reported_entry_keeps_its_sha_so_the_log_is_useful(self):  # REL-047
        self.assertEqual(plan("abc\tchore(main): release nope", [])[0].sha, "abc")


class TestReleaseBodies(unittest.TestCase):
    def test_a_version_gets_its_own_section(self):  # REL-045
        self.assertIn("Adoption.", changelog_section(CHANGELOG, "0.4.0"))

    def test_a_section_stops_at_the_next_version(self):  # REL-045
        self.assertNotIn("The working loop", changelog_section(CHANGELOG, "0.4.0"))

    def test_a_section_keeps_its_own_subheadings(self):  # REL-045
        self.assertIn("### Features", changelog_section(CHANGELOG, "0.4.0"))

    def test_the_last_section_runs_to_the_end(self):  # REL-045
        self.assertIn("The working loop", changelog_section(CHANGELOG, "0.3.0"))

    def test_a_missing_version_is_empty_not_another_version(self):  # REL-045
        self.assertEqual(changelog_section(CHANGELOG, "0.9.9"), "")

    def test_the_heading_itself_is_not_repeated_in_the_body(self):  # REL-045
        self.assertNotIn("## 0.4.0", changelog_section(CHANGELOG, "0.4.0"))


class TestTheRealRepository(unittest.TestCase):
    def test_the_workflow_defaults_to_a_dry_run(self):  # REL-048
        # Asserted against the workflow file: the default lives there, and a
        # default that only the script knows about is not the one that runs.
        from pathlib import Path

        from _support import ROOT

        text = Path(ROOT, ".github/workflows/backfill-tags.yml").read_text()
        apply = text.split("apply:", 1)[1].split("publish_releases:", 1)[0]
        self.assertIn("default: false", apply)


if __name__ == "__main__":
    unittest.main()
