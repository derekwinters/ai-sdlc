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

## 2. Write `.claude/repo-config.yml`

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

## The shared rules

Adoption installs [`house-rules.md`](house-rules.md) into `.claude/ai-sdlc/` and appends one import
line to your `CLAUDE.md`. Your own file is never rewritten — it is usually the most carefully
considered file a repository has, and everything specific to your repository stays in it.

A repository with no `CLAUDE.md` gets one reported rather than created. What that file should say
is your decision.

## ai-sdlc's own adoption

ai-sdlc is its first consumer. `.claude/repo-config.yml` in this repository enables `hygiene` and
`consistency`, and the closing-keyword check runs on its own pull requests — so a change that
breaks the check breaks this repository before it reaches anyone else's.

`pipeline` is deliberately not enabled here yet: it needs the label taxonomy and a dashboard issue,
neither of which exists. Enabling it now would be a configuration error, which is the dependency
rule working rather than a limitation.
