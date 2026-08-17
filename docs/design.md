# ai-sdlc — Design

`ai-sdlc` is the single source of truth for AI-assisted software development across Derek's
repositories. It defines the issue lifecycle, the skills and agents that operate it, the CI
workflows that enforce it, and the house rules that govern it — once, so that every consuming
repository behaves identically without holding a copy of the logic.

This document describes the system. Design decisions and the evidence behind them are recorded
separately in `docs/decisions/`.

---

## 1. Goals

1. **One implementation.** Pipeline logic exists exactly once. A consuming repository holds
   configuration and thin callers, never a second copy of the behaviour.
2. **Specified before built.** Every behaviour has a written requirement with an ID. The spec is
   authoritative; the code conforms to it.
3. **Exceptionally stable.** Every requirement is covered by a test. No test reaches the network.
   The suite runs offline in seconds.
4. **Consistency enforced, not remembered.** Spec, tests, skills, and published docs are checked
   against each other in CI. They cannot silently diverge.
5. **Deliberate upgrades.** Consumers pin to a released version. Adopting a new one is a
   reviewable pull request, never a silent change.
6. **Additive and reversible.** Adoption adds files to a consumer; it never modifies product code,
   and removing it restores the prior state.

## 2. Non-goals

- Cross-repository project management or reporting.
- Any change to a consumer's product or application code.
- Forcing every repository onto the same degree of automation. The system supports both a
  scheduled autonomous pipeline and an on-demand one; a repository chooses.
- Autonomous self-updating of consumers. Updates are proposed, never applied unattended.

---

## 3. Structure

### 3.1 Capabilities

ai-sdlc is a set of **capabilities**, not a single block. A repository adopts the ones it wants.
Each capability is independently installable, independently specified, and independently useful.

They are ordered by how much they assume about how a repository works. Lower ones assume almost
nothing; higher ones encode a particular way of working.

| Capability | Assumes | Depends on |
|---|---|---|
| **substrate** — distribution, `adopt`, `repo-config.yml` | a GitHub repository | — |
| **hygiene** — Conventional Commits, closing-keyword check, "Deviations and Decisions" | pull requests are how change lands | substrate |
| **consistency** — spec↔test traceability, spec↔skill parity, docs build gate | the repository has specs and tests | substrate |
| **labels** — taxonomy as code, sync workflow | nothing; the taxonomy itself is configuration | substrate |
| **release** — release-please flow, version as source of truth | release-please | substrate, hygiene |
| **pipeline** — gatekeeper, triage, development queue, dashboard, blockers, milestones, CI watch, `dev` agent | a specific way of working: issues are triaged, approved by a human, then built | all of the above |

**Invariant — a capability may depend only on capabilities below it, never above.** This is what
makes partial adoption real rather than aspirational, and it is checked: `verify` fails when an
installed capability's dependencies are absent, and the consistency gate fails when a lower
capability's code imports a higher one's.

The **pipeline** capability is the most opinionated thing here, which is why it is deliberately
the top layer rather than the centre. It encodes one way of working — AI triages, a human
approves, AI builds — that suits a single owner working with agents. A repository wanting only
Conventional Commits enforcement and spec traceability takes `hygiene` and `consistency` and never
installs it.

### 3.1a Profiles

Opt-in, shared by a family of repositories, layered on whichever capabilities are installed. A
profile adds behaviour; it never alters a capability's behaviour.

| Profile | Contents | Consumers |
|---|---|---|
| `unity` | scaffold-core, core-unity-split, run-tests, Game CI, APK build and release workflows | Unity games |
| `mkdocs` | docs build/publish workflows, strict-mode gate, versioned publishing | documentation sites |
| `python`, `node`, `kotlin` | test/lint/typecheck workflow modules | by runtime |

### 3.1b Per-repository configuration

Small values only, in `.claude/repo-config.yml`, validated against a published JSON schema:
enabled capabilities and profiles, test and verify commands, spec validator, owner logins, bot
identity, label vocabulary, milestone ordering strategy, dashboard issue number, domain terms.

**Invariant — a difference between repositories is expressed as configuration, never as a
modified copy of a skill.** A skill edited in place in a consumer is overwritten on the next
update and its change is lost. Anything that must vary is a config key, or it is a change to the
capability.

**Configuration describes a repository; it does not switch behaviour on and off.** A key exists
because repositories genuinely differ — how many owners, what a milestone means, what the test
command is — not to make one implementation serve two incompatible designs. A proposed key that
would fork behaviour rather than describe a fact is a sign that a separate capability is wanted.

### 3.2 Repository layout

```
ai-sdlc/
  skills/
    substrate/<skill>/SKILL.md, *.py, tests/
    hygiene/<skill>/…
    consistency/<skill>/…
    labels/<skill>/…
    release/<skill>/…
    pipeline/<skill>/…          # the opinionated capability
    unity/<skill>/…             # profiles share the same {scope} mechanism
    mkdocs/<skill>/…
  agents/
    dev.md
  lib/
    github.py            # the only module that performs network I/O
    config.py            # repo-config loading and validation
  .github/workflows/     # reusable-*.yml — workflow_call definitions
                         # (GitHub requires them here, not at the root)
  schema/
    repo-config.schema.json
  docs/                  # mkdocs source: the spec, published to GitHub Pages
    spec/<area>.md
    decisions/
  mkdocs.yml
```

The `skills/{scope}/` layout is a native `gh skill` discovery convention, so both capability and
profile membership are expressed by directory position and require no registry file. A consumer
installs a capability by installing its scope.

### 3.3 A consuming repository

```
<consumer>/
  .claude/
    skills/…             # installed by gh skill, pinned, not hand-edited
    agents/dev.md        # installed
    repo-config.yml      # hand-written
  .github/
    labels.core.yml      # installed, pinned — the pipeline state vocabulary
    labels.repo.yml      # hand-written — this repository's domain labels
    scripts/sync_labels.py
    workflows/           # thin callers: uses: …/reusable-<x>.yml@<sha> # <version>
  CLAUDE.md              # @import of the shared fragment + repo-specific rules
```

A caller workflow is roughly fifteen lines: the trigger, and a `uses:` with inputs. Triggers that
cannot be centralised — `schedule`, `pull_request`, `issue_comment` — are declared in the consumer;
all logic lives in the reusable workflow.

---

## 4. Specification

The spec is the contract. It lives in `docs/spec/`, is published to GitHub Pages, and is the
document a reader consults to learn what the system does.

- Every behaviour carries a requirement ID of the form `AREA-NNN`.
- Areas, grouped by the capability that owns them:
  - *substrate*: `CFG` (configuration), `API` (GitHub access), `DIST` (distribution and
    versioning), `ADOPT` (adoption and upgrade)
  - *hygiene*: `SYS` (commit and pull-request rules)
  - *consistency*: `VAL` (validators and gates)
  - *labels*: `LBL`
  - *release*: `REL`
  - *pipeline*: `GK` (gatekeeper), `TRI` (triage), `DEV` (development queue), `DASH` (dashboard),
    `BLK` (blockers), `MS` (milestones), `CIW` (CI watch)
  - *profiles*: `SC` (scaffolding, unity)
- A requirement never references an area belonging to a capability above its own.
- Each requirement is `auto` — covered by a named test — or explicitly `manual` with a stated
  reason. There is no third state.
- Where a component could be built in a way that is technically correct but wrong, the spec states
  an **`**Invariant — …**`** constraining how it may work, so the bad implementation is excluded
  before it is written rather than argued about afterwards.
- A change to what a spec page *says*, as opposed to new coverage, carries a plain-English
  **"How the spec is changing"** note: what it used to say, what it now says, why.

---

## 5. Testing architecture

Development is strict TDD: the spec section, then the failing test, then the implementation.

**A single network seam.** `lib/github.py` is the only module permitted to perform I/O. Every other
module receives a client and is tested against a fake. This is what makes exhaustive offline
testing possible, and it is enforced: pure-logic modules are checked not to import the client, and
the suite is checked not to open a socket.

**Typed boundaries.** Commands, verdicts, plans, and outcomes are dataclasses, not dictionaries.
The types are the documented interface between stages and make partial states unrepresentable.

**Test classes.**

| Class | Purpose |
|---|---|
| Unit | one function against its requirement |
| Fixture-replay | real captured GitHub payload shapes through the parsing layer |
| Idempotency | the same input applied twice produces one effect |
| Degradation | a failing sub-request degrades the result rather than losing it |
| Architectural | import boundaries and no-network invariants hold |

**Invariant — no test performs network I/O.** A test that needs GitHub uses the fake. The suite
runs with no credentials and no connection.

---

## 6. Enforced consistency

`ai-sdlc`'s own CI runs six gates. Together they are the guarantee that the spec, the code, the
skills, and the published documentation describe the same system.

1. **Tests** — every skill suite passes, offline.
2. **Spec ↔ tests** — every `auto` requirement has a referencing test; every test names a real
   requirement.
3. **Spec ↔ skills** — every `skills/**/SKILL.md` has a spec page and every spec page a skill;
   `gh skill` validation passes (name matches directory, `name` and `description` present,
   `allowed-tools` a string, install metadata absent).
4. **Configuration** — every example `repo-config.yml` validates against the schema, and every
   config key the code reads is present in the schema.
5. **Docs** — `mkdocs build --strict`.
6. **Commits** — Conventional Commits, including the squash-merge title.

---

## 7. Distribution

Three channels, each maintaining its logic in one place.

| What | Mechanism | In the consumer |
|---|---|---|
| Skills and agents | `gh skill install derekwinters/ai-sdlc <skill>@<tag> --agent claude-code --scope project` | installed files, pinned |
| Workflows | reusable `workflow_call`, in `.github/workflows/reusable-*.yml` | a thin caller per workflow |
| House rules | shared CLAUDE.md fragment | one `@import` line plus repo-specific rules |

`gh skill` records provenance in each installed skill's frontmatter — source repository, ref, and
content tree SHA. A consumer's drift from its pinned version is therefore detectable by comparing
recorded SHAs, with no additional bookkeeping.

**Versioning.** `ai-sdlc` is versioned by release-please from Conventional Commits.
`gh skill publish` cuts the release consumers pin to. A change to the label vocabulary, a
requirement's meaning, or a workflow's inputs is breaking and is marked as such.

**Upgrade path.** A consumer opens a pull request that moves its pins. CI in that repository runs
the new version against the repository's own configuration before it merges. No consumer is
upgraded unattended.

---

## 8. Adoption

A repository joins ai-sdlc by running `adopt`, a stdlib-Python command distributed as a skill.
Adoption is per-repository and run in place, when that repository is ready. There is no
fleet-wide operation: `adopt` reads and writes only the repository it runs in, and never reaches
into another.

```bash
gh skill install derekwinters/ai-sdlc adopt --agent claude-code --scope project
python3 .claude/skills/adopt/adopt.py plan
python3 .claude/skills/adopt/adopt.py apply
```

The distribution channel installs its own installer; `gh` is the only prerequisite.

### 8.1 Subcommands

| Command | Purpose | Writes |
|---|---|---|
| `plan` | detect the stack, select profiles, report every proposed change and the manual-task list | no |
| `apply` | make those changes, idempotently, on a branch | yes |
| `verify` | assert the repository matches its pinned version | no |

`apply` is also the upgrade path: re-running it after a version bump reconciles configuration,
installed skills, and caller workflows to the new pin. Install and upgrade are one mechanism, so
the upgrade path cannot rot independently of the install path.

`verify` runs as a check in the consumer's CI, so an adopted repository cannot silently decay.

**Invariant — `apply` writes to a branch, never to the default branch.** Every adoption and every
upgrade is a reviewable pull request.

### 8.2 Existing content

Each path adoption owns is classified before anything is written.

| Classification | Condition | `apply` |
|---|---|---|
| Absent | nothing present | creates |
| Managed, current | provenance matches the pin | leaves alone |
| Managed, stale | provenance from an earlier pin | updates |
| Conflict | present without provenance, or content differs | **reports only** |

Provenance is the frontmatter `gh skill` writes on install — source repository, ref, and content
tree SHA — and an equivalent generated-by header on workflows.

**Invariant — `apply` never replaces content it did not create.** A conflict is resolved by the
owner, as *adopt* (replace, prior content preserved in the branch), *keep* (leave it, recorded as
an exception in `repo-config.yml` with a reason), or *defer*.

An exception is recorded and reported by `verify`. A repository that keeps its own version of a
component is visibly non-standard rather than appearing adopted.

Never touched: existing labels are never renamed; `CLAUDE.md` is never rewritten, only extended
with the `@import` line; skills outside ai-sdlc's namespace are ignored entirely; an existing
dashboard issue is reused rather than duplicated; a capability the repository already satisfies is
recorded as satisfied rather than installed twice.

### 8.3 Trigger collisions

A file-level comparison cannot detect the most harmful conflict: two workflows responding to the
same event. An adopted `gatekeeper-comment` running alongside a repository's existing
`issue_comment` workflow produces two handlers parsing the same command and writing the same
labels.

**Invariant — `apply` refuses to proceed while an unacknowledged existing workflow listens on an
event the adoption claims.** `plan` inspects triggers, not only paths, and reports every collision
on `issue_comment`, `issues`, and `pull_request`.

For a repository already running a pipeline, adoption is therefore a cutover — old workflows
disabled and new callers added in the same pull request — not an addition.

### 8.4 Manual tasks

`plan` reports the work no agent can perform: enabling required status checks, branch protection,
secrets for an optional custom GitHub App, and any profile-specific credentials. Output is a
checklist and an `ADOPTION.md` in the repository. An opt-in flag files them as one-task-per-issue
in the `Direct Involvement Needed` milestone; it is off by default.

### 8.5 Labels

The label taxonomy carries the pipeline's state machine — and, alongside it, the attempt markers
that record how many times a lost poke has been retried. Both live in git and are applied from
there rather than configured through the GitHub interface.

| File | Owner | Contents |
|---|---|---|
| `labels.core.yml` | ai-sdlc, pinned | the pipeline state vocabulary and shared control labels |
| `labels.repo.yml` | the repository | domain labels — `area:*` and anything local |

`sync_labels.py` applies the union. Separate files rather than sections of one file mean an
upgrade never produces a merge conflict, and `verify` asserts `labels.core.yml` is identical to
its pin — a repository cannot redefine a state label and still appear adopted.

**Invariant — a label is deleted only when explicitly listed for deletion.** Labels absent from
the manifest are left alone. Deleting a label strips it from every issue carrying it and cannot be
undone, so it is never an implicit consequence of editing a file.

`apply` seeds the core manifest and runs the sync once, so the vocabulary exists before anything
else runs. Thereafter the `labels-sync` workflow applies it on push to `main` touching the
manifest, and on demand.

## 9. Documentation site

`docs/` builds with mkdocs-material and publishes to GitHub Pages on merge to `main`. It contains:

- **Spec** — the requirements, by area. The authoritative description of behaviour.
- **Skills** — one page per skill: purpose, commands, configuration, requirement IDs.
- **Adoption** — how a repository consumes ai-sdlc, and how it upgrades.
- **Profiles** — what each profile adds and who uses it.
- **Decisions** — the record of why the system is shaped as it is.

The site is a CI gate, not a byproduct: a change that leaves it unbuildable or inconsistent with
the spec does not merge.
