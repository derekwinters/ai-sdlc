# Specification — House rules (`RULES`)

The rules an agent works under, maintained once and imported by every consuming repository.

This is the third distribution channel, and the one with the least teeth by design. A rule with
teeth belongs in a CI gate, where it is enforced; a rule here is one that shapes judgement, which
no gate can do. Keeping the two apart matters: a document full of rules nothing checks trains
readers to skim it, and then the rules that *do* matter get skimmed too.

`RULES` belongs to the **hygiene** capability.

Every requirement below is `auto` (covered by a named test) unless marked otherwise.

---

## Invariants

> **Invariant — a repository's own `CLAUDE.md` is never rewritten.** It is usually the most
> carefully considered file a repository has. Adoption appends one import line and nothing else.

> **Invariant — the fragment states rules; it does not duplicate gates.** Where CI enforces
> something, the fragment says so and points at it rather than restating the rule as if it were
> advisory.

> **Invariant — the fragment names no stack.** A stack named here is one every other consumer has
> to mentally ignore.

---

## 1. The fragment

- **RULES-001** The fragment is a single Markdown file, installed and pinned.
- **RULES-002** It carries provenance, so `verify` can tell whether it is current.
- **RULES-003** It is imported by a line in the repository's own `CLAUDE.md`.
- **RULES-004** The import is appended once; a second adoption does not add it again.
- **RULES-005** A repository with no `CLAUDE.md` is reported rather than having one created. What
  the file should say is the owner's decision.

## 2. What it contains

- **RULES-010** Conventional Commits, including that the squash-merge title is the commit
  release-please parses.
- **RULES-011** One issue, one branch, one pull request.
- **RULES-012** The `## Deviations and Decisions` section, and what belongs in it.
- **RULES-013** The plain-English lead.
- **RULES-014** Documentation reconciled in the same pull request.
- **RULES-015** Specification before code, and a failing test before an implementation.
- **RULES-016** Ask rather than invent a design decision.
- **RULES-017** Tasks needing a human are filed one per issue, never collected into one.
- **RULES-018** Where the installed files are: the fragment names `.ai-sdlc/adoption.md`,
  `.ai-sdlc/repo-config.yml` and the `ai-sdlc` skill, so discovery does not depend on the skill
  firing. Skill discovery is probabilistic — a skill loads when the model judges its description
  matches the task — and that is useless for the failure this prevents: an agent editing a stale
  pipeline document does not know ai-sdlc governs that file, so it never goes looking. You cannot
  search for what you do not know exists. The import is always-on, so one sentence in it closes
  the gap at the cost of a line.

## 3. What it does not contain

- **RULES-020** No stack-specific instruction.
- **RULES-021** No rule that a CI gate already enforces, stated as though it were advisory. Where
  a gate exists the fragment names it.
- **RULES-022** No repository-specific detail — those stay in the repository's own file.

---

## Traceability

| Section | IDs | Tests |
|---|---|---|
| The fragment | RULES-001–005 | `test_house_rules.py` |
| What it contains | RULES-010–018 | `test_house_rules.py` |
| What it does not contain | RULES-020–022 | `test_house_rules.py` |

**17 requirements, all `auto`.**
