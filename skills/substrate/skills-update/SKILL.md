---
name: skills-update
description: Install and update the ai-sdlc skills a repository's `skills:` list names, at the version it pins, and never overwrite one that has been edited locally. Use when skills are missing from a consumer, after moving the ai-sdlc pin, or when checking whether installed skills have drifted.
allowed-tools: Bash, Read
---

# skills-update

`docs/design.md` §7 settled how skills reach a consuming repository — `gh skill install`, pinned,
with provenance recorded in each installed skill's frontmatter — and then nothing ran it. This is
the thing that runs it.

```bash
python3 .claude/skills/skills-update/main.py plan  <ref>   # read-only
python3 .claude/skills/skills-update/main.py apply <ref>   # installs
```

`<ref>` is the ai-sdlc ref the repository pins, the same one its callers name. There is no second
version to keep in step.

## The list belongs to the repository

What gets installed is `skills:` in `.ai-sdlc/repo-config.yml`:

```yaml
skills:
  - triage-issue
  - pipeline-dev
  - ci-watch
```

Not a workflow input — a caller is an `adopt`-managed file, and hand-editing one turns it into a
`CONFLICT` that never gets upgraded again. And not a central registry, which is the more important
half: **a scheduled skill sync has been built twice in this fleet and disabled twice**, both times
because a registry decided what a repository should have and the sync reverted work the repository
had done.

## A locally-modified skill is never overwritten

| State | What happens |
| --- | --- |
| absent | installed at the pin |
| installed at the pin, unmodified | left alone |
| installed at an earlier ref, unmodified | reinstalled at the pin |
| **edited locally** | **reported, left alone** |
| installed with no provenance | reported, left alone |
| a name ai-sdlc does not ship | reported, left alone |

This is the one thing that had to be got right, and it does not come free from the tool.
`gh skill update` without `--force` skips a modified skill — but moving a *pinned* skill to a new
version is a **reinstall**, and `gh skill install` overwrites local modifications with the original
content. So the check happens here, before the command runs. Nothing is ever installed with
`--force`.

Modification is decided by comparing the installed files with ai-sdlc's own copy **at the ref the
installation records** — not at the pin. Comparing against the pin would call every merely
outdated skill modified, and nothing would ever be updated again.

The frontmatter keys `gh skill` injects (`github-repo`, `github-ref`, `github-path`,
`github-tree-sha`) are excluded from the comparison, and so is `__pycache__` — running a skill
writes bytecode inside its own directory, and running them is the point.

## A pull request, never a direct commit

`skills-update.yml` runs this on a schedule and opens a pull request when the tree changed. It
opens none when nothing changed, and says so in the job summary.

Installed skills are instructions an agent reads. A job that committed them straight to the default
branch on a timer would put unreviewed ones in front of it, which is a consent problem rather than
a tidiness one.

One stable branch — `ai-sdlc/skills-update` — so a second run proposes onto the open pull request
rather than beside it.

Specification: `docs/spec/distribution.md` (`DIST`), 23 requirements.
