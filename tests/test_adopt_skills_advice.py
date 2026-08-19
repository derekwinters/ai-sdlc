"""ADOPT-110 to ADOPT-114 — telling a repository which skills it probably wants.

`DIST-001` says a repository installs the names in `skills:`. Nothing ever put
that key in front of the person adopting, so a repository upgrading to v0.4.17
got `skills-update.yml` only if it had already guessed the key existed and
guessed its contents right. A missing optional key is not an error, so the
mechanism stayed dormant and said nothing (#149).

`adopt` therefore writes a starting list, once, into a file it otherwise only
reads — and never touches the key again. Derek's call: the list of skills this
process needs is legitimately part of the repository's configuration, so the
tool that installs the process may put it there.

Written once is not the same as re-asserted on a schedule. The two previous
fleet syncs both read a registry that decided what a repository *should* have,
and both reverted work a repository had done. Writing a default the repository
then owns is the opposite of that, and the distinction is what `DIST`'s
invariant now states.
"""

import unittest

from _adopt import repository, PIN
import _adopt  # noqa: F401
from adopt import CONFIG_FILE, apply, plan

PIPELINE = (
    "capabilities:\n  - hygiene\n  - consistency\n  - labels\n  - release\n"
    "  - pipeline\nowners:\n  - someone\ndashboard_issue: 7\n"
)
HYGIENE = "capabilities:\n  - hygiene\n"


def seeded(config):
    """The configuration file as it stands after an `apply`.

    `newline=""` because the default translates line endings on read, which
    would make a CRLF file compare equal to the LF rewrite this is here to
    catch.
    """
    root = repository({CONFIG_FILE: config})
    apply(root, pin=PIN)
    with (root / CONFIG_FILE).open(newline="") as handle:
        return handle.read()


def listed(config):
    """The names under the `skills:` key, once it exists."""
    text = seeded(config)
    if "skills:" not in text:
        return []
    return [
        line.strip().lstrip("- ")
        for line in text[text.index("skills:"):].splitlines()[1:]
        if line.strip().startswith("- ")
    ]


class TestTheKeyIsWrittenOnce(unittest.TestCase):
    def test_a_pipeline_repository_gets_a_starting_list(self):  # ADOPT-110
        self.assertIn("skills:", seeded(PIPELINE))

    def test_it_names_the_skills_that_repository_invokes(self):  # ADOPT-110
        for name in ("triage-issue", "pipeline-dev", "ci-watch"):
            self.assertIn(name, listed(PIPELINE))

    def test_the_write_is_reported(self):  # ADOPT-110
        """Adoption writing to the one file a repository authors is worth
        saying out loud rather than discovering in a diff."""
        root = repository({CONFIG_FILE: PIPELINE})
        self.assertIn(CONFIG_FILE, apply(root, pin=PIN).written)

    def test_the_list_says_it_is_now_the_repositorys(self):  # ADOPT-110
        self.assertIn("yours", seeded(PIPELINE).lower())


class TestNothingElseInTheFileMoves(unittest.TestCase):
    """ADOPT-111 — the key is appended; everything already there is untouched.

    A consumer's `repo-config.yml` carries hand-written comments explaining
    every choice. Adoption may add a key to it; it may not reformat, reorder or
    lose a single byte of what was there.
    """

    AUTHORED = (
        "# Why this repository is the way it is.\r\n"
        "capabilities:\r\n"
        "  - hygiene\r\n"
        "  - consistency\r\n"
        "  - labels\r\n"
        "  - release\r\n"
        "  - pipeline\r\n"
        "owners:\r\n"
        "  - someone\r\n"
        "dashboard_issue: 7\r\n"
        "\r\n"
        "# a trailing comment, and no trailing newline"
    )

    def test_everything_authored_survives_byte_for_byte(self):  # ADOPT-111
        after = seeded(self.AUTHORED)
        self.assertTrue(after.startswith(self.AUTHORED))

    def test_the_key_is_appended_at_the_end(self):  # ADOPT-111
        after = seeded(PIPELINE)
        self.assertLess(after.index("capabilities:"), after.index("skills:"))

    def test_plan_reports_it_and_writes_nothing(self):  # ADOPT-111
        root = repository({CONFIG_FILE: PIPELINE})
        self.assertIn(CONFIG_FILE, plan(root, pin=PIN).creates + plan(root, pin=PIN).updates)
        self.assertEqual((root / CONFIG_FILE).read_text(), PIPELINE)


class TestARepositoryThatHasDecidedIsLeftAlone(unittest.TestCase):
    """ADOPT-112 — written once, never re-asserted.

    This is the whole difference between a default and a registry. Both
    previous fleet syncs re-asserted a central answer over a local one, on a
    timer, and both reverted work a repository had done.
    """

    def test_an_existing_list_is_never_rewritten(self):  # ADOPT-112
        kept = PIPELINE + "skills:\n  - ci-watch\n"
        self.assertEqual(seeded(kept), kept)

    def test_a_deliberately_empty_list_is_a_decision(self):  # ADOPT-112
        """`skills: []` says "none, and I meant it"."""
        kept = PIPELINE + "skills: []\n"
        self.assertEqual(seeded(kept), kept)

    def test_a_second_apply_writes_nothing(self):  # ADOPT-112
        root = repository({CONFIG_FILE: PIPELINE})
        apply(root, pin=PIN)
        once = (root / CONFIG_FILE).read_text()
        self.assertEqual(apply(root, pin=PIN).written, [])
        self.assertEqual((root / CONFIG_FILE).read_text(), once)

    def test_a_repository_that_deleted_a_name_keeps_it_deleted(self):  # ADOPT-112
        """The failure mode that disabled two syncs, in miniature."""
        pruned = PIPELINE + "skills:\n  - ci-watch\n"
        root = repository({CONFIG_FILE: pruned})
        apply(root, pin=PIN)
        apply(root, pin=PIN)
        self.assertNotIn("triage-issue", (root / CONFIG_FILE).read_text())


class TestWhatIsWritten(unittest.TestCase):
    """ADOPT-113 — only skills something in the consumer actually invokes."""

    EXECUTED_CENTRALLY = ("pipeline-gatekeeper", "pipeline-dashboard", "label-sync",
                          "closing-keyword", "docs-gate", "skills-update")

    def test_a_centrally_executed_skill_is_never_recommended(self):  # ADOPT-113
        """These run from ai-sdlc's own tree inside an action or workflow, so a
        copy in a consumer is a second version that nothing reads and `DIST-012`
        then has to keep at the pin forever."""
        names = listed(PIPELINE)
        for name in self.EXECUTED_CENTRALLY:
            with self.subTest(skill=name):
                self.assertNotIn(name, names)

    def test_adopt_is_never_recommended(self):  # ADOPT-113
        """It imports `lib.config`, which is not part of the skill, so an
        installed copy cannot run — upgrades run from an ai-sdlc checkout."""
        self.assertNotIn("adopt", listed(PIPELINE))

    def test_a_repository_with_no_pipeline_is_advised_less(self):  # ADOPT-114
        """The recommendation follows the capabilities, so a repository taking
        only hygiene is not told to install the pipeline's skills."""
        self.assertNotIn("triage-issue", listed(HYGIENE))

    def test_every_recommended_name_exists_in_this_repository(self):  # ADOPT-114
        """A recommendation naming a skill ai-sdlc does not ship would fail as
        `DIST-016` unknown, in the consumer, at install time."""
        from _support import ROOT

        present = {p.parent.name for p in ROOT.glob("skills/*/*/SKILL.md")}
        names = listed(PIPELINE)
        self.assertTrue(names)
        for name in names:
            with self.subTest(skill=name):
                self.assertIn(name, present)


class TestTheCallerLandsInTheSameRun(unittest.TestCase):
    """ADOPT-115 — seeding and installing are one operation."""

    CALLER = ".github/workflows/skills-update.yml"

    def test_one_apply_writes_both_the_key_and_the_caller(self):  # ADOPT-115
        """`ADOPT-048` makes the caller follow the list. If the list is decided
        after the file set is built, the first run seeds a key that installs
        nothing and the caller waits for a second run nobody knew to make."""
        root = repository({CONFIG_FILE: PIPELINE})
        written = apply(root, pin=PIN).written
        self.assertIn(CONFIG_FILE, written)
        self.assertIn(self.CALLER, written)

    def test_plan_says_so_before_the_run(self):  # ADOPT-115
        root = repository({CONFIG_FILE: PIPELINE})
        proposed = plan(root, pin=PIN)
        self.assertIn(self.CALLER, proposed.creates)


if __name__ == "__main__":
    unittest.main()
