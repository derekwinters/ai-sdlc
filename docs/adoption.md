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
    uses: derekwinters/ai-sdlc/.github/workflows/reusable-closing-keyword.yml@v0.1.0
    with:
      ref: v0.1.0
```

Pin to a released tag rather than `main`. An upgrade is then a pull request that moves the pin,
reviewed like any other change.

## 4. Make the checks required

A check that is not required is advisory. In **Settings → Branches** (or Rulesets), protect the
default branch and require the checks you added.

**Do not add an `if:` that skips a required check.** A skipped required check stays pending forever
and blocks the merge it was meant to permit. Escape hatches — the `no-closing-keyword` label, the
`skip-docs` label — make a check *pass*, never absent.

## ai-sdlc's own adoption

ai-sdlc is its first consumer. `.claude/repo-config.yml` in this repository enables `hygiene` and
`consistency`, and the closing-keyword check runs on its own pull requests — so a change that
breaks the check breaks this repository before it reaches anyone else's.

`pipeline` is deliberately not enabled here yet: it needs the label taxonomy and a dashboard issue,
neither of which exists. Enabling it now would be a configuration error, which is the dependency
rule working rather than a limitation.
