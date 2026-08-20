"""ADOPT-080 to ADOPT-087 — moving a repository out of `.claude/`.

The risky half of the move. Everything else here writes files this tool wrote;
this relocates a file the *repository* authored, and gets exactly one chance to
do it without losing anything.
"""

import unittest

from _adopt import repository, OLDER_PIN, PIN
import _adopt  # noqa: F401
from adopt import (
    AdoptRefused,
    with_provenance,
    CONFIG_FILE,
    HOUSE_RULES,
    IMPORT_LINE,
    LEGACY_IMPORT_LINE,
    PIN_FILE,
    apply,
    migrate,
    migration,
    plan,
    verify,
)

CONFIG = "capabilities:\n  - hygiene\n"

#: What a repository adopted before 0.4.18 looks like on disk.
ADOPTED = {
    ".claude/repo-config.yml": CONFIG,
    ".claude/ai-sdlc.pin": "v0.4.17 " + "b" * 40 + "\n",
    # Managed, at the previous pin — the state a real upgrade actually finds.
    ".claude/ai-sdlc/house-rules.md": with_provenance(
        "# House rules\n\nAs they read at the previous version.\n", OLDER_PIN),
    "CLAUDE.md": f"# Ours\n\nSomething important.\n\n{LEGACY_IMPORT_LINE}\n",
}


def adopted(extra=None):
    return repository(dict(ADOPTED, **(extra or {})))


class TestItMoves(unittest.TestCase):
    def test_apply_moves_the_configuration(self):  # ADOPT-080
        root = adopted()
        apply(root, pin=PIN)
        self.assertTrue((root / CONFIG_FILE).is_file())

    def test_apply_moves_the_pin(self):  # ADOPT-080
        root = adopted()
        apply(root, pin=PIN)
        self.assertTrue((root / PIN_FILE).is_file())

    def test_apply_moves_the_house_rules(self):  # ADOPT-080
        root = adopted()
        apply(root, pin=PIN)
        self.assertTrue((root / HOUSE_RULES).is_file())

    def test_it_reports_what_it_moved(self):  # ADOPT-080
        self.assertEqual(len(apply(adopted(), pin=PIN).migrated), 4)


class TestTheConfigurationIsNotRewritten(unittest.TestCase):
    """ADOPT-081 — byte-for-byte, or not at all.

    `repo-config.yml` is authored by the repository, not written by this tool.
    A consumer's copy carries hand-written comments explaining every choice, and
    a "helpful" reformat would throw them away for good.
    """

    AUTHORED = (
        "# Why this repository is the way it is.\r\n"
        "#\r\n"
        "#   an indented note\t\twith tabs\r\n"
        "capabilities:\r\n"
        "  - hygiene\r\n"
        # An explicit "none", so this fixture tests migration alone. Without it
        # `ADOPT-110` would seed the key and the equality below would be
        # asserting two things at once.
        "skills: []\r\n"
        "\r\n"
        "# a trailing comment, and no trailing newline"
    )

    def test_the_bytes_are_identical(self):  # ADOPT-081
        root = adopted({".claude/repo-config.yml": self.AUTHORED})
        migrate(root)
        self.assertEqual((root / CONFIG_FILE).read_bytes(), self.AUTHORED.encode())

    def test_it_gains_no_provenance_header(self):  # ADOPT-081
        root = adopted()
        migrate(root)
        self.assertNotIn("ai-sdlc:", (root / CONFIG_FILE).read_text())

    def test_a_later_apply_still_leaves_it_alone(self):  # ADOPT-081
        root = adopted({".claude/repo-config.yml": self.AUTHORED})
        apply(root, pin=PIN)
        self.assertEqual((root / CONFIG_FILE).read_bytes(), self.AUTHORED.encode())


class TestNothingIsLeftBehind(unittest.TestCase):
    """ADOPT-082 — a stale copy beside a live one is a trap, not a backup."""

    def test_the_old_configuration_is_gone(self):  # ADOPT-082
        root = adopted()
        migrate(root)
        self.assertFalse((root / ".claude/repo-config.yml").exists())

    def test_the_old_pin_is_gone(self):  # ADOPT-082
        root = adopted()
        migrate(root)
        self.assertFalse((root / ".claude/ai-sdlc.pin").exists())

    def test_the_old_directory_is_gone(self):  # ADOPT-082
        root = adopted()
        migrate(root)
        self.assertFalse((root / ".claude/ai-sdlc").exists())

    def test_a_directory_holding_something_else_survives(self):  # ADOPT-082
        """Anything a consumer put in there is theirs, not ours to delete."""
        root = adopted({".claude/ai-sdlc/notes.md": "mine\n"})
        migrate(root)
        self.assertTrue((root / ".claude/ai-sdlc/notes.md").is_file())


class TestTheImportFollows(unittest.TestCase):
    """ADOPT-083 — an import naming a moved file is an import of nothing."""

    def test_the_import_is_repointed(self):  # ADOPT-083
        root = adopted()
        migrate(root)
        self.assertIn(IMPORT_LINE, (root / "CLAUDE.md").read_text())

    def test_the_old_import_is_gone(self):  # ADOPT-083
        root = adopted()
        migrate(root)
        self.assertNotIn(LEGACY_IMPORT_LINE, (root / "CLAUDE.md").read_text())

    def test_the_rest_of_the_file_is_untouched(self):  # ADOPT-083
        root = adopted()
        migrate(root)
        self.assertIn("Something important.", (root / "CLAUDE.md").read_text())

    def test_it_is_not_added_where_there_was_none(self):  # ADOPT-083
        root = adopted({"CLAUDE.md": "# Ours\n"})
        migrate(root)
        self.assertNotIn(IMPORT_LINE, (root / "CLAUDE.md").read_text())


class TestItIsIdempotent(unittest.TestCase):
    """ADOPT-084 — driven by what is there, so a second run finds nothing."""

    def test_a_second_migrate_moves_nothing(self):
        root = adopted()
        migrate(root)
        self.assertEqual(migrate(root), [])

    def test_a_second_apply_writes_nothing(self):  # ADOPT-084
        root = adopted()
        apply(root, pin=PIN)
        self.assertEqual(apply(root, pin=PIN).written, [])

    def test_the_configuration_survives_both(self):  # ADOPT-084
        answered = CONFIG + "skills: []\n"
        root = adopted({".claude/repo-config.yml": answered})
        apply(root, pin=PIN)
        apply(root, pin=PIN)
        self.assertEqual((root / CONFIG_FILE).read_text(), answered)

    def test_a_repository_never_in_the_old_place_has_nothing_to_move(self):  # ADOPT-084
        root = repository({CONFIG_FILE: CONFIG})
        self.assertEqual(migration(root), [])


class TestBothPlacesIsRefused(unittest.TestCase):
    """ADOPT-085 — two copies is not a state to guess at.

    One of them is what CI reads and the other is what somebody will edit next,
    and nothing here can tell which is which.
    """

    def both(self):
        return adopted({CONFIG_FILE: "capabilities:\n  - labels\n"})

    def test_migrate_refuses(self):  # ADOPT-085
        with self.assertRaises(AdoptRefused):
            migrate(self.both())

    def test_the_refusal_names_both_paths(self):  # ADOPT-085
        try:
            migrate(self.both())
        except AdoptRefused as error:
            self.assertIn(".claude/repo-config.yml", str(error))
            self.assertIn(CONFIG_FILE, str(error))

    def test_a_refusal_moves_nothing(self):  # ADOPT-085
        root = self.both()
        try:
            migrate(root)
        except AdoptRefused:
            pass
        self.assertTrue((root / ".claude/ai-sdlc.pin").is_file())

    def test_apply_refuses_too(self):  # ADOPT-085
        with self.assertRaises(AdoptRefused):
            apply(self.both(), pin=PIN)


class TestPlanAndVerifySeeIt(unittest.TestCase):
    """ADOPT-086 — the read-only halves report the move rather than trip on it."""

    def test_plan_reports_the_pending_moves(self):  # ADOPT-086
        self.assertEqual(len(plan(adopted(), pin=PIN).migrations), 3)

    def test_plan_writes_nothing(self):  # ADOPT-086
        root = adopted()
        plan(root, pin=PIN)
        self.assertTrue((root / ".claude/repo-config.yml").is_file())
        self.assertFalse((root / CONFIG_FILE).exists())

    def test_a_pending_migration_is_not_current(self):  # ADOPT-086
        root = adopted()
        apply(root, pin=PIN)
        # Everything at this pin, so the only thing left to report would be a
        # migration — and there is none.
        self.assertTrue(plan(root, pin=PIN).current)

    def test_a_file_about_to_move_is_not_reported_as_a_create(self):  # ADOPT-086
        """Where it *is*, not where it is going. Reporting an upgrade of an
        existing house-rules file as a create reads as "this repository had
        none", and the plan is the one place a reviewer would catch that."""
        proposed = plan(adopted(), pin=PIN)
        self.assertNotIn(HOUSE_RULES, proposed.creates)
        self.assertIn(HOUSE_RULES, proposed.updates)

    def test_the_moving_pin_is_an_update_not_a_create(self):  # ADOPT-086
        proposed = plan(adopted(), pin=PIN)
        self.assertNotIn(PIN_FILE, proposed.creates)
        self.assertIn(PIN_FILE, proposed.updates)

    def test_verify_fails_on_an_unmigrated_repository(self):  # ADOPT-086
        self.assertFalse(verify(adopted(), pin=PIN).ok)

    def test_the_problem_names_the_new_path(self):  # ADOPT-086
        problems = " ".join(verify(adopted(), pin=PIN).problems)
        self.assertIn(CONFIG_FILE, problems)


class TestSkillsDoNotMove(unittest.TestCase):
    """ADOPT-087 — `.claude/skills/` genuinely is Claude Code's required path.

    The seam is drawn on ownership. A skill is loaded by Claude Code from a path
    Claude Code chooses; a `capabilities:` list parsed by a GitHub Actions job is
    not Claude Code's business at all. Only the second moves.
    """

    def test_an_installed_skill_is_left_where_it_is(self):  # ADOPT-087
        root = adopted({".claude/skills/ci-watch/SKILL.md": "---\nname: ci-watch\n---\n"})
        apply(root, pin=PIN)
        self.assertTrue((root / ".claude/skills/ci-watch/SKILL.md").is_file())

    def test_the_install_root_is_unchanged(self):  # ADOPT-087
        import sys

        from _support import ROOT

        sys.path.insert(0, str(ROOT / "skills" / "substrate" / "skills-update"))
        from skills_update import INSTALL_ROOT

        self.assertEqual(str(INSTALL_ROOT), ".claude/skills")

    def test_the_update_workflow_still_commits_that_path(self):  # ADOPT-087
        from _support import ROOT

        text = (ROOT / ".github/workflows/reusable-skills-update.yml").read_text()
        self.assertIn("git add -A .claude/skills", text)


if __name__ == "__main__":
    unittest.main()
