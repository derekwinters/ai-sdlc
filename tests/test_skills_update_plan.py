"""DIST-010 to DIST-023 — deciding what may be written, before anything is.

The defect that disabled the two previous attempts at this is one line of this
file: a skill somebody edited locally was overwritten, and the sync reverted
work. `gh skill install` overwrites a modified skill with the original content
— that is documented behaviour, not a bug — and moving a pinned skill to a new
version *is* a reinstall. So the check happens here, before the command runs.
"""

import unittest

from _skills_update import (  # noqa: F401 - sets up sys.path
    OLDER,
    PIN,
    Source,
    consumer,
    frontmatter,
    installed_skill,
    source_at,
    source_skill,
)
from skills_update import (
    ABSENT,
    CURRENT,
    MODIFIED,
    STALE,
    UNKNOWN,
    UNMANAGED,
    UNVERIFIABLE,
    plan,
    provenance,
    without_provenance,
)


def classified(names, root, source, ref=PIN):
    return {s.name: s.state for s in plan(names, ref, root=root, source=source).skills}


class TestAbsent(unittest.TestCase):
    def test_a_skill_nothing_installed_is_absent(self):  # DIST-010
        root = consumer()
        source = source_at([PIN], ["ci-watch"])
        self.assertEqual(classified(["ci-watch"], root, source), {"ci-watch": ABSENT})

    def test_an_absent_skill_is_scheduled_for_install(self):  # DIST-010
        proposed = plan(["ci-watch"], PIN, root=consumer(), source=source_at([PIN], ["ci-watch"]))
        self.assertEqual(proposed.install, ["ci-watch"])

    def test_only_the_named_skills_are_considered(self):  # DIST-001
        root = consumer({"other": installed_skill("other", OLDER)})
        proposed = plan(["ci-watch"], PIN, root=root, source=source_at([PIN], ["ci-watch"]))
        self.assertEqual([s.name for s in proposed.skills], ["ci-watch"])

    def test_an_unnamed_installed_skill_is_never_removed(self):  # DIST-001
        root = consumer({"local-thing": installed_skill("local-thing", OLDER)})
        plan(["ci-watch"], PIN, root=root, source=source_at([PIN], ["ci-watch"]))
        self.assertTrue((root / ".claude/skills/local-thing/SKILL.md").is_file())


class TestCurrent(unittest.TestCase):
    def test_installed_at_the_pin_and_unmodified_is_current(self):  # DIST-011
        root = consumer({"ci-watch": installed_skill("ci-watch", PIN)})
        source = source_at([PIN], ["ci-watch"])
        self.assertEqual(classified(["ci-watch"], root, source), {"ci-watch": CURRENT})

    def test_a_current_skill_is_neither_installed_nor_updated(self):  # DIST-011
        root = consumer({"ci-watch": installed_skill("ci-watch", PIN)})
        proposed = plan(["ci-watch"], PIN, root=root, source=source_at([PIN], ["ci-watch"]))
        self.assertEqual((proposed.install, proposed.update), ([], []))

    def test_nothing_to_do_is_visible_on_the_plan(self):  # DIST-011
        root = consumer({"ci-watch": installed_skill("ci-watch", PIN)})
        proposed = plan(["ci-watch"], PIN, root=root, source=source_at([PIN], ["ci-watch"]))
        self.assertFalse(proposed.changes)


class TestStale(unittest.TestCase):
    def test_an_earlier_ref_unmodified_is_stale(self):  # DIST-012
        root = consumer({"ci-watch": installed_skill("ci-watch", OLDER)})
        source = source_at([OLDER, PIN], ["ci-watch"])
        self.assertEqual(classified(["ci-watch"], root, source), {"ci-watch": STALE})

    def test_a_stale_skill_is_scheduled_for_update(self):  # DIST-012
        root = consumer({"ci-watch": installed_skill("ci-watch", OLDER)})
        proposed = plan(
            ["ci-watch"], PIN, root=root, source=source_at([OLDER, PIN], ["ci-watch"])
        )
        self.assertEqual(proposed.update, ["ci-watch"])

    def test_stale_is_decided_against_the_recorded_ref(self):  # DIST-015
        """The defect that would make this whole job a no-op.

        ai-sdlc's copy at the *pin* differs from the installed copy — that is
        what "out of date" means. Comparing against the pin would call every
        stale skill modified, and nothing would ever be updated again.
        """
        root = consumer({"ci-watch": installed_skill("ci-watch", OLDER)})
        source = Source({
            OLDER: {"ci-watch": source_skill("ci-watch")},
            PIN: {"ci-watch": source_skill("ci-watch", description="Rewritten upstream.")},
        })
        self.assertEqual(classified(["ci-watch"], root, source), {"ci-watch": STALE})

    def test_the_recorded_ref_is_the_one_read(self):  # DIST-015
        root = consumer({"ci-watch": installed_skill("ci-watch", OLDER)})
        source = source_at([OLDER, PIN], ["ci-watch"])
        plan(["ci-watch"], PIN, root=root, source=source)
        self.assertIn(("ci-watch", OLDER), source.asked)


class TestModified(unittest.TestCase):
    def _edited(self, changes):
        files = installed_skill("ci-watch", PIN)
        files.update(changes)
        return consumer({"ci-watch": files})

    def test_an_edited_skill_md_is_modified(self):  # DIST-014
        root = self._edited({"SKILL.md": frontmatter("ci-watch", "Ours now.", provenance=PIN)})
        source = source_at([PIN], ["ci-watch"])
        self.assertEqual(classified(["ci-watch"], root, source), {"ci-watch": MODIFIED})

    def test_an_edited_script_is_modified(self):  # DIST-022
        root = self._edited({"main.py": "print('ours')\n"})
        source = source_at([PIN], ["ci-watch"])
        self.assertEqual(classified(["ci-watch"], root, source), {"ci-watch": MODIFIED})

    def test_an_added_file_is_modified(self):  # DIST-022
        root = self._edited({"extra.py": "print('ours')\n"})
        source = source_at([PIN], ["ci-watch"])
        self.assertEqual(classified(["ci-watch"], root, source), {"ci-watch": MODIFIED})

    def test_a_deleted_file_is_modified(self):  # DIST-022
        files = installed_skill("ci-watch", PIN)
        del files["main.py"]
        root = consumer({"ci-watch": files})
        source = source_at([PIN], ["ci-watch"])
        self.assertEqual(classified(["ci-watch"], root, source), {"ci-watch": MODIFIED})

    def test_a_modified_skill_is_never_scheduled(self):  # DIST-014
        root = self._edited({"main.py": "print('ours')\n"})
        proposed = plan(["ci-watch"], PIN, root=root, source=source_at([PIN], ["ci-watch"]))
        self.assertEqual((proposed.install, proposed.update), ([], []))

    def test_a_modified_stale_skill_is_never_scheduled(self):  # DIST-014
        """The exact shape of the two disabled predecessors.

        Out of date *and* edited. An updater that only asked "is it out of
        date?" reinstalls it and the edit is gone.
        """
        files = installed_skill("ci-watch", OLDER)
        files["main.py"] = "print('ours')\n"
        root = consumer({"ci-watch": files})
        proposed = plan(
            ["ci-watch"], PIN, root=root, source=source_at([OLDER, PIN], ["ci-watch"])
        )
        self.assertEqual((proposed.install, proposed.update), ([], []))
        self.assertEqual([s.state for s in proposed.skipped], [MODIFIED])

    def test_bytecode_caches_are_not_modifications(self):  # DIST-023
        """Running a skill writes `__pycache__` inside its own directory."""
        files = installed_skill("ci-watch", PIN)
        files["__pycache__/main.cpython-311.pyc"] = "not really bytecode\n"
        root = consumer({"ci-watch": files})
        source = source_at([PIN], ["ci-watch"])
        self.assertEqual(classified(["ci-watch"], root, source), {"ci-watch": CURRENT})


class TestUnmanaged(unittest.TestCase):
    def test_a_skill_with_no_provenance_is_unmanaged(self):  # DIST-013
        root = consumer({"ci-watch": {"SKILL.md": frontmatter("ci-watch")}})
        source = source_at([PIN], ["ci-watch"])
        self.assertEqual(classified(["ci-watch"], root, source), {"ci-watch": UNMANAGED})

    def test_a_directory_with_no_skill_md_is_unmanaged(self):  # DIST-013
        root = consumer({"ci-watch": {"notes.md": "mine\n"}})
        source = source_at([PIN], ["ci-watch"])
        self.assertEqual(classified(["ci-watch"], root, source), {"ci-watch": UNMANAGED})

    def test_an_unmanaged_skill_is_never_scheduled(self):  # DIST-013
        root = consumer({"ci-watch": {"SKILL.md": frontmatter("ci-watch")}})
        proposed = plan(["ci-watch"], PIN, root=root, source=source_at([PIN], ["ci-watch"]))
        self.assertEqual((proposed.install, proposed.update), ([], []))


class TestUnknownNames(unittest.TestCase):
    def test_a_name_ai_sdlc_does_not_ship_is_unknown(self):  # DIST-016
        root = consumer()
        source = source_at([PIN], ["ci-watch"])
        self.assertEqual(classified(["not-a-skill"], root, source), {"not-a-skill": UNKNOWN})

    def test_an_unknown_name_is_never_installed(self):  # DIST-016
        proposed = plan(["not-a-skill"], PIN, root=consumer(), source=source_at([PIN], []))
        self.assertEqual(proposed.install, [])

    def test_an_unknown_name_does_not_stop_the_others(self):  # DIST-035
        root = consumer()
        source = source_at([PIN], ["ci-watch"])
        proposed = plan(["not-a-skill", "ci-watch"], PIN, root=root, source=source)
        self.assertEqual(proposed.install, ["ci-watch"])

    def test_a_skill_removed_upstream_since_install_is_unknown(self):  # DIST-016
        root = consumer({"ci-watch": installed_skill("ci-watch", OLDER)})
        source = Source({OLDER: {"ci-watch": source_skill("ci-watch")}, PIN: {}})
        self.assertEqual(classified(["ci-watch"], root, source), {"ci-watch": UNKNOWN})


class TestUnverifiable(unittest.TestCase):
    def test_a_ref_the_checkout_cannot_read_is_unverifiable(self):  # DIST-017
        root = consumer({"ci-watch": installed_skill("ci-watch", "v0.0.1")})
        source = Source({PIN: {"ci-watch": source_skill("ci-watch")}}, unreadable=["v0.0.1"])
        self.assertEqual(classified(["ci-watch"], root, source), {"ci-watch": UNVERIFIABLE})

    def test_an_unverifiable_skill_is_left_alone(self):  # DIST-017
        root = consumer({"ci-watch": installed_skill("ci-watch", "v0.0.1")})
        source = Source({PIN: {"ci-watch": source_skill("ci-watch")}}, unreadable=["v0.0.1"])
        proposed = plan(["ci-watch"], PIN, root=root, source=source)
        self.assertEqual((proposed.install, proposed.update), ([], []))
        self.assertEqual([s.state for s in proposed.skipped], [UNVERIFIABLE])


class TestProvenance(unittest.TestCase):
    def test_the_four_keys_are_read(self):  # DIST-020
        found = provenance(frontmatter("ci-watch", provenance=PIN))
        self.assertEqual(found["github-ref"], PIN)
        self.assertEqual(found["github-repo"], "https://github.com/derekwinters/ai-sdlc")
        self.assertEqual(found["github-path"], "skills/pipeline/ci-watch")
        self.assertEqual(found["github-tree-sha"], "0" * 40)

    def test_a_file_without_them_records_nothing(self):  # DIST-020
        self.assertEqual(provenance(frontmatter("ci-watch")), {})

    def test_a_file_without_frontmatter_records_nothing(self):  # DIST-020
        self.assertEqual(provenance("# ci-watch\n\nNo frontmatter here.\n"), {})

    def test_stripping_them_leaves_ai_sdlcs_own_copy(self):  # DIST-021
        self.assertEqual(
            without_provenance(frontmatter("ci-watch", provenance=PIN)),
            frontmatter("ci-watch"),
        )

    def test_stripping_keeps_every_other_key(self):  # DIST-021
        stripped = without_provenance(frontmatter("ci-watch", "Keep me.", provenance=PIN))
        self.assertIn("description: Keep me.", stripped)
        self.assertIn("name: ci-watch", stripped)

    def test_stripping_a_file_without_them_changes_nothing(self):  # DIST-021
        self.assertEqual(without_provenance(frontmatter("ci-watch")), frontmatter("ci-watch"))


class TestThePlanIsInspectable(unittest.TestCase):
    def test_every_named_skill_appears_with_its_state(self):  # DIST-030
        root = consumer({
            "ci-watch": installed_skill("ci-watch", PIN),
            "pipeline-dev": installed_skill("pipeline-dev", OLDER),
        })
        source = source_at([OLDER, PIN], ["ci-watch", "pipeline-dev", "triage-issue"])
        states = classified(["ci-watch", "pipeline-dev", "triage-issue"], root, source)
        self.assertEqual(
            states,
            {"ci-watch": CURRENT, "pipeline-dev": STALE, "triage-issue": ABSENT},
        )

    def test_a_skipped_skill_carries_a_reason(self):  # DIST-034
        root = consumer({"ci-watch": {"SKILL.md": frontmatter("ci-watch")}})
        proposed = plan(["ci-watch"], PIN, root=root, source=source_at([PIN], ["ci-watch"]))
        self.assertTrue(proposed.skipped[0].detail)

    def test_changes_is_true_when_anything_would_be_written(self):  # DIST-030
        proposed = plan(["ci-watch"], PIN, root=consumer(), source=source_at([PIN], ["ci-watch"]))
        self.assertTrue(proposed.changes)

    def test_a_plan_writes_nothing(self):  # DIST-030
        root = consumer()
        plan(["ci-watch"], PIN, root=root, source=source_at([PIN], ["ci-watch"]))
        self.assertFalse((root / ".claude" / "skills").exists())


if __name__ == "__main__":
    unittest.main()
