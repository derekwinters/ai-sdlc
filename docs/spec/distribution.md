# Specification — Distribution (`DIST`)

How ai-sdlc's skills reach a consuming repository, and what keeps them there once they have
arrived.

`docs/design.md` §7 already settled the *mechanism*: `gh skill install`, pinned, with provenance
recorded in each installed skill's frontmatter. This page specifies the thing that **runs** it — a
scheduled job in the consumer that installs what its configuration names, updates what it
installed, and opens a pull request when the tree changed.

`DIST` belongs to the **substrate** capability and depends only on `CFG`.

Every requirement below is `auto` (covered by a named test) unless marked otherwise.

---

## Invariants

> **Invariant — the repository owns the list.** What a repository installs is `skills:` in its own
> `.ai-sdlc/repo-config.yml`. Nothing central decides on its behalf. A scheduled skill sync has been
> built twice in this fleet and disabled twice, and both read a registry that decided what a
> repository *should* have — so both reverted work the repository had done. A list the repository
> owns inverts that.
>
> **Seeding is not deciding.** `adopt` writes a starting list into the key **once**, when the key
> is absent entirely (`ADOPT-110`), because a repository that has never heard of it cannot exercise
> ownership of it. From that moment the list is the repository's: adoption never reads it back to
> compare, never adds a name to it, and never restores one that was removed — including from a
> repository that answered "none" by writing `skills: []`.
>
> Written once and re-asserted on a schedule are different mechanisms, and only the second is what
> failed twice here. Both previous syncs read a central registry every run and reverted work a
> repository had done between runs. A default that is written when there is nothing to overwrite,
> and then owned locally, has no run in which it can revert anything.

> **Invariant — a locally-modified skill is never overwritten.** Reinstalling an already-installed
> skill overwrites local modifications with the original content; that is what `gh skill install`
> does, and moving a pinned skill to a new version *is* a reinstall. `gh skill update` without
> `--force` skips a modified skill, but the update path is not the one this uses. The check is
> therefore ours to make before the command runs, not the tool's to make for us.

> **Invariant — a pull request, never a direct commit.** Installed skills are instructions an agent
> reads. A scheduled job that committed them straight to the default branch would pull unreviewed
> third-party instructions into the agent's context on a timer. Review is the point, not tidiness.

---

## 1. What is installed

- **DIST-001** The skills a repository installs are the names in `skills:` (`CFG-060`). Nothing
  else is installed, and nothing installed is removed for being absent from the list — an
  uninstall strips files, and a list edited by mistake should not.
- **DIST-002** A skill is installed at the ref the repository pins, which is the same ref its
  callers already name (`ADOPT-060`). There is no second version to keep in step.
- **DIST-003** Installing is `gh skill install <source> <name>@<ref> --agent claude-code
  --scope project`, and the installed files land under `.claude/skills/<name>/`.
- **DIST-004** The installer is injected, so no test performs network I/O and the one-module
  network seam holds.

## 2. Classification

Every named skill is classified before anything runs. The classes mirror `ADOPT-020`–`ADOPT-025`,
because the question is the same one: may we write here?

- **DIST-010** **Absent** — nothing installed under that name; it is installed.
- **DIST-011** **Current** — installed, unmodified, and its recorded ref is the pinned ref; left
  alone.
- **DIST-012** **Stale** — installed, unmodified, and its recorded ref is some earlier ref;
  reinstalled at the pin.
- **DIST-013** **Unmanaged** — installed with no recorded provenance; reported and left alone. A
  directory somebody wrote by hand is not ours to replace, whatever it contains.
- **DIST-014** **Modified** — installed, with provenance, and its files differ from ai-sdlc's own
  copy of them; reported and left alone.
- **DIST-015** Modification is decided against ai-sdlc's copy **at the ref the installation
  records**, never at the pinned ref. Comparing against the pin would classify every merely
  outdated skill as modified, which would make the whole job a no-op the first time ai-sdlc moved.
- **DIST-016** A name that ai-sdlc's tree does not carry at that ref is reported as unknown, not
  silently skipped. `CFG-063` defers the check to here precisely because here is where the source
  is present.
- **DIST-017** A recorded ref whose content cannot be read is reported, and the skill is left
  alone. A claim that cannot be checked is not a licence to overwrite.

## 3. Provenance

- **DIST-020** Provenance is the frontmatter `gh skill` writes into the installed `SKILL.md`:
  `github-repo`, `github-ref`, `github-path` and `github-tree-sha`.
- **DIST-021** Those four keys are excluded from the content comparison. They are written by the
  installer and are absent from the source, so including them would make every installed skill
  look modified — and the whole mechanism would refuse to do anything, for ever.
- **DIST-022** Every other file in the skill directory is compared, not only `SKILL.md`. A skill is
  its scripts as much as its instructions, and an edit to one of them is an edit.
- **DIST-023** Bytecode caches are excluded from the comparison. Running a skill writes
  `__pycache__` inside its own directory, so comparing it would make every skill that has ever run
  look modified — and running them is the point.

## 4. The run

- **DIST-030** A run reports, for every named skill, which class it fell into and what was done.
- **DIST-031** A run that installs and updates nothing opens no pull request, and says that it
  changed nothing.
- **DIST-032** A run that changed the tree opens a pull request. It never commits to the default
  branch.
- **DIST-033** A run uses one stable branch, so a second run proposes changes on the open pull
  request rather than opening another beside it.
- **DIST-034** Skipped skills are named in the run's report and in the pull request body, with the
  reason for each. A skip nobody is told about is indistinguishable from an install.
- **DIST-035** A skipped skill does not fail the run. The other skills are still installed, and the
  report says what was left out — the same bargain `adopt` makes with a conflict.

---

## Traceability

| Section | IDs | Tests |
|---|---|---|
| What is installed | DIST-001–004 | `test_skills_update_run.py` |
| Classification | DIST-010–017 | `test_skills_update_plan.py` |
| Provenance | DIST-020–023 | `test_skills_update_plan.py` |
| The run | DIST-030–035 | `test_skills_update_run.py` |

**23 requirements, all `auto`.**
