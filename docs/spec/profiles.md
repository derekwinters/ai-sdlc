# Specification — Profiles (`PROF`)

Opt-in behaviour shared by a family of repositories, layered on whichever capabilities are
installed.

A profile adds; it never alters a capability's behaviour. That distinction is what keeps profiles
from becoming a second configuration system: if a profile needed to change how a capability
behaves, the right answer is a capability, not a flag.

`PROF` belongs to the **substrate** capability, which owns profile selection; each profile's own
content belongs to itself.

Every requirement below is `auto` (covered by a named test) unless marked otherwise.

---

## Invariants

> **Invariant — a profile adds behaviour; it never alters a capability's.** A profile that changes
> what a capability does is a capability wearing a disguise.

> **Invariant — a profile is inert when not selected.** Installing ai-sdlc must not make a
> repository run a docs gate it never asked for.

---

## 1. Selection

- **PROF-001** A profile is enabled only by being listed in configuration.
- **PROF-002** Detection proposes profiles; it never enables one.
- **PROF-003** An unknown profile name is a configuration error.
- **PROF-004** A profile whose files are absent is inert rather than an error.

## 2. The mkdocs profile

- **PROF-010** It provides a strict documentation build as a pull request check.
- **PROF-011** A build warning fails the check. Strict mode exists because a broken link is a
  broken page, and a warning nobody sees is a broken page shipped.
- **PROF-012** It publishes on merge to the default branch, and never from a pull request.
- **PROF-013** Publication is skipped when the build fails.

## 3. The documentation gate

- **PROF-020** A pull request that changes code and no documentation fails the gate.
- **PROF-021** The `skip-docs` label makes the gate **pass**, never skip. A skipped required check
  stays pending and blocks the merge it was meant to permit.
- **PROF-022** A pull request changing only documentation passes.
- **PROF-023** A pull request changing neither passes; there is nothing to reconcile.
- **PROF-024** What counts as documentation is configurable, defaulting to `docs/` and `*.md`.
- **PROF-025** The gate reports which files it judged code and which documentation, so a
  surprising verdict is explainable.

---

## Traceability

| Section | IDs | Tests |
|---|---|---|
| Selection | PROF-001–004 | `test_profiles.py` |
| The mkdocs profile | PROF-010–013 | `test_profiles.py` |
| The documentation gate | PROF-020–025 | `test_docs_gate.py` |

**15 requirements, all `auto`.**
