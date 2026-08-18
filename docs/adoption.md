# Adoption

A repository joins ai-sdlc by taking the capabilities it wants. Nothing is all-or-nothing: a
repository that only wants Conventional Commits enforcement and the closing-keyword check takes
`hygiene` and never installs an issue lifecycle.

Until the `adopt` command exists (#17), adoption is done by hand, and this page is the procedure.

## 1. Choose capabilities

| Capability | Assumes | Depends on |
| --- | --- | --- |
| substrate | a GitHub repository | — |
| hygiene | pull requests are how change lands | substrate |
| consistency | the repository has specs and tests | substrate |
| labels | nothing; the taxonomy is configuration | substrate |
| release | release-please | substrate, hygiene |
| pipeline | issues are triaged, approved by a human, then built | all of the above |

A capability may depend only on capabilities below it. Enabling one without its dependencies is a
configuration error refused at load — not a runtime surprise.

## 2. Write `.ai-sdlc/repo-config.yml`

```yaml
capabilities:
  - hygiene
  - consistency

commands:
  test: python3 -m unittest discover -s tests
```

Everything optional has a default; see [Configuration](spec/configuration.md) for the full schema.
A repository enabling `pipeline` also needs `owners` and `dashboard_issue`.

## 3. Add caller workflows

The logic lives in ai-sdlc. A consumer holds a thin caller, because some triggers cannot be
centralised — `pull_request`, `issue_comment` and `schedule` must be declared in the repository
they fire for.

```yaml
name: closing-keyword

on:
  pull_request:
    types: [opened, edited, reopened, synchronize, labeled, unlabeled]

permissions:
  contents: read

jobs:
  closing-keyword:
    uses: derekwinters/ai-sdlc/.github/workflows/reusable-closing-keyword.yml@5c625bfb5d1ff62eadeeb3772007f7f66fdcf071 # v0.4.1
    with:
      ref: 5c625bfb5d1ff62eadeeb3772007f7f66fdcf071
```

Pin to a **commit**, not a tag and not `main`. A reusable workflow runs with the caller's token, on
`issue_comment` and `issues`, so a mutable ref there is the same exposure as a mutable action —
publishing it ourselves says who could move the tag, not that it cannot move.

The version comment is what keeps this readable: nobody reads forty characters of hexadecimal and
knows whether they are three releases behind. `adopt` writes both, and rewrites both on upgrade, so
an upgrade is still a pull request that moves one line and nobody resolves a SHA by hand.

## 4. Make the checks required

A check that is not required is advisory. In **Settings → Branches** (or Rulesets), protect the
default branch and require the checks you added.

**Do not add an `if:` that skips a required check.** A skipped required check stays pending forever
and blocks the merge it was meant to permit. Escape hatches — the `no-closing-keyword` label, the
`skip-docs` label — make a check *pass*, never absent.

## 5. Name the skills you install

The workflows are only half of ai-sdlc; the rest is skills an agent reads. Which ones a repository
installs is its own decision, written in its own configuration:

```yaml
skills:
  - triage-issue
  - pipeline-dev
  - ci-watch
```

`adopt` then writes a `skills-update.yml` caller, which installs what is missing and reinstalls
what has fallen behind the pin — and **opens a pull request**, because installed skills are
instructions an agent reads and a timer that put unreviewed ones in front of it would be a consent
problem.

A skill you have edited locally is reported and left alone, never overwritten. If you need a skill
to behave differently, change it in ai-sdlc and move the pin; a local edit is preserved, but it
stops that skill being updated, and `skills-update` will say so on every run.

That pull request needs one setting only you can switch on: **Settings → Actions → General →
Workflow permissions → Allow GitHub Actions to create and approve pull requests**. Without it the
job pushes its branch and then cannot open the pull request.

See [Distribution](spec/distribution.md) for the whole mechanism.

## Where it all lives

Everything ai-sdlc owns in your repository sits in one directory:

| Path | Holds | Written by |
| --- | --- | --- |
| `.ai-sdlc/repo-config.yml` | Everything your repository decides for itself | You |
| `.ai-sdlc/ai-sdlc.pin` | The version installed, and the commit it resolves to | `adopt` |
| `.ai-sdlc/house-rules.md` | The shared rules, imported by your `CLAUDE.md` | `adopt` |
| `.ai-sdlc/adoption.md` | What is installed here, generated from your configuration | `adopt` |
| `.claude/skills/ai-sdlc/SKILL.md` | A pointer at the three above, for an agent | `adopt` |

`.claude/skills/` is the one exception, and it is Claude Code's required path rather than a choice.
Everything else is ai-sdlc's, so it is under ai-sdlc's own name: a workflow parsing `capabilities`
and `owners` is not an AI coding assistant's business.

`adoption.md` restates nothing. It says what is installed and at what version, and links the
specification at the exact commit your repository runs — because a copy of an explanation drifts
from the explanation, and then somebody believes the copy.

## Upgrading from before 0.4.18

Those files used to live under `.claude/`. `adopt apply` moves them as part of the upgrade, in one
commit with the rest of it: your `repo-config.yml` moves byte-for-byte with its comments intact,
the old copies are removed, and the import line in your `CLAUDE.md` is repointed.

You do not migrate by hand, and you should not half-migrate. A repository with a file in both
places is refused rather than guessed at — one of the two is what CI reads and the other is what
somebody will edit next, and nothing can tell which.

## The shared rules

Adoption installs [`house-rules.md`](house-rules.md) into `.ai-sdlc/` and appends one import
line to your `CLAUDE.md`. Your own file is never rewritten — it is usually the most carefully
considered file a repository has, and everything specific to your repository stays in it.

A repository with no `CLAUDE.md` gets one reported rather than created. What that file should say
is your decision.

## ai-sdlc's own adoption

ai-sdlc is its first consumer. `.ai-sdlc/repo-config.yml` in this repository enables `hygiene` and
`consistency`, and the closing-keyword check runs on its own pull requests — so a change that
breaks the check breaks this repository before it reaches anyone else's.

`pipeline` is deliberately not enabled here yet: it needs the label taxonomy and a dashboard issue,
neither of which exists. Enabling it now would be a configuration error, which is the dependency
rule working rather than a limitation.
